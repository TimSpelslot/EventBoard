from sqlalchemy import inspect, text

from app import create_app
from app.provider import db


USER_DROP_COLUMNS = [
    "personal_room",
    "world_builder_name",
    "dnd_beyond_name",
    "dnd_beyond_campaign",
    "karma",
    "story_player",
    "notify_new_adventure",
    "notify_deadline",
    "notify_create_adventure_reminder",
]

ADVENTURE_DROP_COLUMNS = [
    "requested_room",
    "num_sessions",
    "predecessor_id",
    "rank_combat",
    "rank_exploration",
    "rank_roleplaying",
    "exclude_from_karma",
    "is_story_adventure",
]


def _ensure_event_types_table_sqlite(conn) -> None:
    conn.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS event_types (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(255) NOT NULL UNIQUE,
                description TEXT,
                image_url VARCHAR(1024),
                weekday INTEGER NOT NULL,
                week_of_month INTEGER NOT NULL,
                exclude_july_august BOOLEAN NOT NULL DEFAULT 0,
                is_single_event BOOLEAN NOT NULL DEFAULT 0,
                signup_mode VARCHAR(32) NOT NULL DEFAULT 'delayed_manual',
                default_release_reminder_days INTEGER NOT NULL DEFAULT 2,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                sort_order INTEGER NOT NULL DEFAULT 0,
                created_by_user_id INTEGER,
                created_at DATETIME,
                FOREIGN KEY(created_by_user_id) REFERENCES users(id)
            )
            """
        )
    )


def _ensure_event_types_table_non_sqlite(conn, dialect: str) -> None:
    if dialect == "postgresql":
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS event_types (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    image_url VARCHAR(1024),
                    weekday INTEGER NOT NULL,
                    week_of_month INTEGER NOT NULL,
                    exclude_july_august BOOLEAN NOT NULL DEFAULT FALSE,
                    is_single_event BOOLEAN NOT NULL DEFAULT FALSE,
                    signup_mode VARCHAR(32) NOT NULL DEFAULT 'delayed_manual',
                    default_release_reminder_days INTEGER NOT NULL DEFAULT 2,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_by_user_id INTEGER REFERENCES users(id),
                    created_at TIMESTAMP
                )
                """
            )
        )
    else:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS event_types (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    title VARCHAR(255) NOT NULL UNIQUE,
                    description TEXT,
                    image_url VARCHAR(1024),
                    weekday INTEGER NOT NULL,
                    week_of_month INTEGER NOT NULL,
                    exclude_july_august BOOLEAN NOT NULL DEFAULT 0,
                    is_single_event BOOLEAN NOT NULL DEFAULT 0,
                    signup_mode VARCHAR(32) NOT NULL DEFAULT 'delayed_manual',
                    default_release_reminder_days INTEGER NOT NULL DEFAULT 2,
                    is_active BOOLEAN NOT NULL DEFAULT 1,
                    sort_order INTEGER NOT NULL DEFAULT 0,
                    created_by_user_id INTEGER NULL,
                    created_at DATETIME,
                    FOREIGN KEY(created_by_user_id) REFERENCES users(id)
                )
                """
            )
        )


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _drop_columns_non_sqlite(table_name: str, columns: list[str]) -> None:
    inspector = inspect(db.engine)
    existing = {c["name"] for c in inspector.get_columns(table_name)}
    to_drop = [c for c in columns if c in existing]

    if not to_drop:
        return

    dialect = db.engine.dialect.name
    conn = db.session.connection()

    if table_name == "adventures" and "predecessor_id" in to_drop:
        for fk in inspector.get_foreign_keys("adventures"):
            constrained = fk.get("constrained_columns") or []
            fk_name = fk.get("name")
            if "predecessor_id" in constrained and fk_name:
                conn.execute(text(f"ALTER TABLE adventures DROP FOREIGN KEY {fk_name}"))

    for col in to_drop:
        if dialect == "postgresql":
            conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {col} CASCADE"))
        else:
            conn.execute(text(f"ALTER TABLE {table_name} DROP COLUMN {col}"))


def _migrate_sqlite() -> None:
    conn = db.session.connection()

    conn.execute(text("PRAGMA foreign_keys=OFF"))

    _ensure_event_types_table_sqlite(conn)

    inspector = inspect(db.engine)
    if _table_exists(inspector, "event_types"):
        event_type_cols = {c["name"] for c in inspector.get_columns("event_types")}
        if "is_single_event" not in event_type_cols:
            conn.execute(
                text(
                    "ALTER TABLE event_types ADD COLUMN is_single_event BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            inspector = inspect(db.engine)

    if _table_exists(inspector, "users"):
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if any(c in user_cols for c in USER_DROP_COLUMNS):
            conn.execute(text("ALTER TABLE users RENAME TO users__old"))
            conn.execute(
                text(
                    """
                    CREATE TABLE users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        google_id VARCHAR(100) NOT NULL UNIQUE,
                        name VARCHAR(255) NOT NULL,
                        display_name VARCHAR(255),
                        privilege_level INTEGER NOT NULL DEFAULT 0,
                        email VARCHAR(255),
                        profile_pic VARCHAR(512),
                        notify_assignments BOOLEAN DEFAULT 1,
                        notify_event_updates BOOLEAN DEFAULT 1,
                        notify_signup_confirmation_3d BOOLEAN DEFAULT 1,
                        notify_live_signup_updates BOOLEAN DEFAULT 1
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO users (
                        id, google_id, name, display_name, privilege_level,
                        email, profile_pic,
                        notify_assignments, notify_event_updates,
                        notify_signup_confirmation_3d, notify_live_signup_updates
                    )
                    SELECT
                        id,
                        google_id,
                        name,
                        COALESCE(display_name, name),
                        privilege_level,
                        email,
                        profile_pic,
                        COALESCE(notify_assignments, 1),
                        COALESCE(notify_event_updates, 1),
                        COALESCE(notify_signup_confirmation_3d, 1),
                        COALESCE(notify_live_signup_updates, 1)
                    FROM users__old
                    """
                )
            )
            conn.execute(text("DROP TABLE users__old"))

    inspector = inspect(db.engine)
    if _table_exists(inspector, "adventures"):
        adv_cols = {c["name"] for c in inspector.get_columns("adventures")}
        if any(c in adv_cols for c in ADVENTURE_DROP_COLUMNS):
            conn.execute(text("ALTER TABLE adventures RENAME TO adventures__old"))
            conn.execute(
                text(
                    """
                    CREATE TABLE adventures (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title VARCHAR(255) NOT NULL,
                        short_description TEXT NOT NULL,
                        user_id INTEGER,
                        event_type_id INTEGER,
                        max_players INTEGER NOT NULL DEFAULT 5,
                        date DATE NOT NULL,
                        tags VARCHAR(255),
                        release_assignments BOOLEAN NOT NULL DEFAULT 0,
                        release_reminder_days INTEGER NOT NULL DEFAULT 2,
                        is_waitinglist INTEGER NOT NULL DEFAULT 0,
                        FOREIGN KEY(user_id) REFERENCES users(id),
                        FOREIGN KEY(event_type_id) REFERENCES event_types(id)
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    INSERT INTO adventures (
                        id, title, short_description, user_id, event_type_id, max_players,
                        date, tags, release_assignments, release_reminder_days, is_waitinglist
                    )
                    SELECT
                        id,
                        title,
                        short_description,
                        user_id,
                        NULL,
                        max_players,
                        date,
                        tags,
                        COALESCE(release_assignments, 0),
                        COALESCE(release_reminder_days, 2),
                        COALESCE(is_waitinglist, 0)
                    FROM adventures__old
                    """
                )
            )
            conn.execute(text("DROP TABLE adventures__old"))

    inspector = inspect(db.engine)
    if _table_exists(inspector, "adventure_requested_players"):
        conn.execute(text("DROP TABLE adventure_requested_players"))

    conn.execute(text("PRAGMA foreign_keys=ON"))


def migrate_single_event_schema() -> None:
    inspector = inspect(db.engine)
    dialect = db.engine.dialect.name

    if dialect == "sqlite":
        _migrate_sqlite()
        db.session.commit()
        return

    if _table_exists(inspector, "users"):
        _drop_columns_non_sqlite("users", USER_DROP_COLUMNS)

    conn = db.session.connection()
    _ensure_event_types_table_non_sqlite(conn, dialect)

    inspector = inspect(db.engine)
    if _table_exists(inspector, "event_types"):
        et_cols = {c["name"] for c in inspector.get_columns("event_types")}
        if "is_single_event" not in et_cols:
            default_clause = "FALSE" if dialect == "postgresql" else "0"
            conn.execute(
                text(
                    f"ALTER TABLE event_types ADD COLUMN is_single_event BOOLEAN NOT NULL DEFAULT {default_clause}"
                )
            )
        if "default_release_reminder_days" not in et_cols:
            conn.execute(
                text(
                    "ALTER TABLE event_types ADD COLUMN default_release_reminder_days INTEGER NOT NULL DEFAULT 2"
                )
            )
        if "signup_mode" not in et_cols:
            conn.execute(
                text(
                    "ALTER TABLE event_types ADD COLUMN signup_mode VARCHAR(32) NOT NULL DEFAULT 'delayed_manual'"
                )
            )

    if _table_exists(inspector, "users"):
        user_cols = {c["name"] for c in inspector.get_columns("users")}
        if "notify_event_updates" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN notify_event_updates BOOLEAN NOT NULL DEFAULT 1"))
        if "notify_signup_confirmation_3d" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN notify_signup_confirmation_3d BOOLEAN NOT NULL DEFAULT 1"))
        if "notify_live_signup_updates" not in user_cols:
            conn.execute(text("ALTER TABLE users ADD COLUMN notify_live_signup_updates BOOLEAN NOT NULL DEFAULT 1"))

    if _table_exists(inspector, "adventures"):
        _drop_columns_non_sqlite("adventures", ADVENTURE_DROP_COLUMNS)

    inspector = inspect(db.engine)
    adv_cols = {c["name"] for c in inspector.get_columns("adventures")} if _table_exists(inspector, "adventures") else set()
    if "event_type_id" not in adv_cols and _table_exists(inspector, "adventures"):
        conn.execute(text("ALTER TABLE adventures ADD COLUMN event_type_id INTEGER NULL"))
    if "release_assignments" not in adv_cols and _table_exists(inspector, "adventures"):
        conn.execute(text("ALTER TABLE adventures ADD COLUMN release_assignments BOOLEAN NOT NULL DEFAULT 0"))
    if "release_reminder_days" not in adv_cols and _table_exists(inspector, "adventures"):
        conn.execute(text("ALTER TABLE adventures ADD COLUMN release_reminder_days INTEGER NOT NULL DEFAULT 2"))

    inspector = inspect(db.engine)
    if _table_exists(inspector, "adventure_requested_players"):
        conn.execute(text("DROP TABLE adventure_requested_players"))

    db.session.commit()


if __name__ == "__main__":
    app = create_app()
    with app.app_context():
        migrate_single_event_schema()
        print("Single-event schema migration completed.")
