import site
# add path to installed packages to PATH:
site.addsitedir('/mnt/web105/e0/90/517590/htdocs/.local/lib/python3.11/site-packages')
import json, os
from flask import Flask
from flask_smorest import Api
from flask_talisman import Talisman
from apispec.ext.marshmallow import MarshmallowPlugin
import firebase_admin
from firebase_admin import credentials

import logging
from datetime import datetime, date, timedelta

from .provider import db, ma, ap_scheduler, login_manager, google_oauth, mail, migrate
from .models import *
from .util import *
from .api import *

def create_app(config_file=None):
    # --- Launch app --- 
    app = Flask(__name__)
    app.logger.info(f"App running in {os.getenv('FLASK_ENV')} mode")

    # --- Firebase Admin Setup ---
    # Only initialize when service account key is present and readable (e.g. disabled in tests/CI)
    app.config["FIREBASE_ENABLED"] = False
    if not firebase_admin._apps:
        cred_path = os.path.join(app.root_path, 'config', 'serviceAccountKey.json')
        try:
            if os.path.isfile(cred_path):
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)
                app.config["FIREBASE_ENABLED"] = True
                app.logger.info("Firebase Admin initialized successfully")
            else:
                app.logger.info("Firebase disabled: serviceAccountKey.json not found")
        except Exception as e:
            app.logger.info("Firebase disabled: could not load service account key: %s", e)

    # load config
    if not config_file:
        config_file = os.getenv("APP_CONFIG", "config/config.json")
    app.config.from_file(config_file, load=json.load)
    config = app.config
    app.secret_key = config["APP"]["secret_key"]
    config["API_VERSION"] = f"v{config['VERSION']['version']}" if config["VERSION"]["version"] else "version-undefined"

    # configure logger
    level_name = config['APP'].get('log_level', 'WARNING') 
    app.logger.setLevel(getattr(logging, level_name.upper(), logging.WARNING))
    app.logger.info(f"App logging level set to: {level_name}")

    # also log to a file, create a fresh logfile on every restart
    try:
        logs_dir = config['APP'].get('log_dir', None)
        os.makedirs(logs_dir, exist_ok=True)
        log_filename = f"adventureboard_start-{datetime.now().strftime('%Y%m%d-%H%M')}.log"
        log_path = os.path.join(logs_dir, log_filename)

        file_handler = logging.FileHandler(log_path, encoding='utf-8')
        file_handler.setLevel(app.logger.level)

        # Attach to app logger
        if not any(isinstance(h, logging.FileHandler) for h in app.logger.handlers):
            app.logger.addHandler(file_handler)

        app.logger.info(f"File logging enabled at: {log_path}")
    except Exception as e:
        # Do not fail app start on logging errors
        app.logger.warning(f"Failed to initialize file logging: {e}")

    # configure WSGI middleware
    if config["APP"]["behind_proxy"]:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
        app.config['PREFERRED_URL_SCHEME'] = config["APP"]["behind_proxy"]
        app.logger.info(f"App running behind proxy: {config['APP']['behind_proxy']}")


    # --- Database setup ---
    # Dynamically construct the SQLALCHEMY_DATABASE_URI from app.config['DB']
    db_conf = config['DB']

    # Handle SQLite separately since it has a different format
    if db_conf["flavor"].startswith("sqlite"):
        uri = f"{db_conf['flavor']}:///{db_conf['database']}.db"
    else:
        uri = (
            f"{db_conf['flavor']}://{db_conf['user']}:{db_conf['password']}"
            f"@{db_conf['host']}/{db_conf['database']}"
        )

    config["SQLALCHEMY_DATABASE_URI"] = uri

    db.init_app(app)
    with app.app_context():
        db.create_all()
        ensure_event_type_schema_compat()
        ensure_default_event_types()

    # --- Migrations setup ---
    migrate.init_app(app, db)


    # --- (De)Serialization setup ---
    ma.init_app(app)
    marshmallow_plugin = MarshmallowPlugin(schema_name_resolver=custom_name_resolver)
    api = Api(app, spec_kwargs={"marshmallow_plugin": marshmallow_plugin})
    for blp in api_blueprints:
        api.register_blueprint(blp)


    # --- APScheduler setup --- 
    ap_scheduler.init_app(app)
    ap_scheduler.start()


    # --- Google OAuth setup ---
    google_oauth.init_app(app)


    # --- User session management setup --- 
    # https://flask-login.readthedocs.io/en/latest
    login_manager.init_app(app)
    # Flask-Login helper to retrieve a user from our db
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, user_id)
    login_manager.anonymous_user = Anonymous


    # --- Security headers ---
    talisman = Talisman(app)
    talisman.content_security_policy = config['APP']['content_security_policy']


    # --- Email setup ---
    # Map JSON "EMAIL" section to Flask-Mail config
    if config.get("EMAIL", {}).get("active", False):
        email_cfg = config["EMAIL"]

        app.config["MAIL_SERVER"] = email_cfg.get("smtp_address", "smtp.gmail.com")
        app.config["MAIL_PORT"] = email_cfg.get("smtp_port", 587)
        app.config["MAIL_USERNAME"] = email_cfg.get("address")
        app.config["MAIL_PASSWORD"] = email_cfg.get("password")
        app.config["MAIL_USE_TLS"] = email_cfg.get("tls", True)
        app.config["MAIL_USE_SSL"] = email_cfg.get("ssl", False)
        mail.init_app(app)


    # --- Cronjobs ---   
    a_d, a_h = config['TIMING']['assignment_day'].split("@")

    @ap_scheduler.task('cron', id='make_assignments', day_of_week=a_d, hour=a_h)
    def cron_make_assignments():
        with app.app_context():
            app.logger.info("--- Triggering scheduled 'make assignment' job ---")
            assign_players_to_adventures()

    @ap_scheduler.task('cron', id='three_day_signup_confirmation', hour=config['TIMING'].get('signup_confirmation_hour', 9))
    def cron_three_day_signup_confirmation():
        with app.app_context():
            today = date.today()
            target_date = today + timedelta(days=3)

            assignments = db.session.execute(
                db.select(Assignment)
                .join(Adventure, Assignment.adventure_id == Adventure.id)
                .join(EventType, Adventure.event_type_id == EventType.id)
                .options(
                    db.contains_eager(Assignment.adventure),
                )
                .where(
                    Adventure.date == target_date,
                    Adventure.is_waitinglist == 0,
                    EventType.signup_mode == "immediate_automatic",
                )
            ).scalars().all()

            if not assignments:
                return

            grouped: dict[int, list[str]] = {}
            users: dict[int, User] = {}
            for assignment in assignments:
                user = assignment.user
                adventure = assignment.adventure
                if not user or not adventure:
                    continue
                users[user.id] = user
                grouped.setdefault(user.id, []).append(adventure.title)

            for user_id, titles in grouped.items():
                user = users.get(user_id)
                if not user:
                    continue
                send_fcm_notification(
                    user,
                    "Upcoming event",
                    f"You are signed up for: {', '.join(sorted(set(titles)))}",
                    category="signup_confirmation_3d",
                )

    @ap_scheduler.task('cron', id='event_session_reminders', hour=config['TIMING'].get('signup_confirmation_hour', 9))
    def cron_event_session_reminders():
        with app.app_context():
            today = date.today()
            # Find all active events and check each session's reminder lead
            events = db.session.execute(
                db.select(Event)
                .options(
                    db.joinedload(Event.days)
                    .joinedload(EventDay.sessions)
                    .joinedload(EventSession.participants)
                    .joinedload(EventSessionParticipant.user)
                )
                .where(Event.is_active == True)
            ).unique().scalars().all()

            notifications_sent = 0
            notified: set[tuple[int, int]] = set()  # (user_id, session_id)
            for event in events:
                for event_day in (event.days or []):
                    target_date = event_day.date
                    for session in (event_day.sessions or []):
                        days_before = event.notification_days_before
                        if today + timedelta(days=days_before) != target_date:
                            continue
                        for participant in session.participants:
                            if participant.status != EventSessionParticipant.STATUS_PLACED:
                                continue
                            if not participant.user_id or not participant.user:
                                continue
                            key = (participant.user_id, session.id)
                            if key in notified:
                                continue
                            notified.add(key)
                            send_fcm_notification(
                                participant.user,
                                "Upcoming session",
                                f"You are signed up for '{session.title}' on {target_date.strftime('%A %d %B')}",
                                category="assignments",
                            )
                            notifications_sent += 1
            app.logger.info(f"Event session reminders: sent {notifications_sent} notifications")

    return app