from flask_marshmallow import Marshmallow
from flask_apscheduler import APScheduler
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate

import requests
from oauthlib.oauth2 import WebApplicationClient

ap_scheduler = APScheduler()
ma = Marshmallow()
db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()

class GoogleOAuth:
    def __init__(self, app=None):
        self.client = None
        self.provider_cfg = None
        if app:
            self.init_app(app)

    def init_app(self, app):
        self.client = WebApplicationClient(app.config["GOOGLE"]["client_id"])
        try:
            resp = requests.get(app.config["GOOGLE"]["discovery_url"], timeout=5)
            resp.raise_for_status()
            self.provider_cfg = resp.json()
        except Exception as exc:
            # Do not block API startup if Google is temporarily unreachable.
            self.provider_cfg = None
            app.logger.warning("Google OAuth discovery unavailable during startup: %s", exc)
        app.extensions = getattr(app, "extensions", {})
        app.extensions["google_oauth"] = self
google_oauth = GoogleOAuth()

