from datetime import datetime, timedelta
from flask_login import UserMixin, AnonymousUserMixin

from .provider import db

def custom_name_resolver(schema):
    """Return a unique schema name by appending parent class context if needed."""
    name = schema.__class__.__name__
    # Avoid double-suffixing if name already ends with Schema
    if name.endswith("Schema"):
        return name
    return name + "Schema"

class Anonymous(AnonymousUserMixin):
  def __init__(self):
    self.privilege_level = -1
    self.id = -1

class FCMToken(db.Model):
    __tablename__ = 'fcm_tokens'
    id = db.Column(db.Integer, primary_key=True)
    
    # Create a real relationship to the User table
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    token = db.Column(db.String(512), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    # Optional: allow us to see user info from a token object
    user = db.relationship('User', backref=db.backref('fcm_tokens', lazy=True))

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id                  = db.Column(db.Integer, autoincrement=True, primary_key=True)
    google_id           = db.Column(db.String(100), nullable=False, unique=True)
    name                = db.Column(db.String(255), nullable=False)
    display_name        = db.Column(db.String(255), nullable=True)
    privilege_level     = db.Column(db.Integer, nullable=False, default=0)
    email               = db.Column(db.String(255), nullable=True)
    profile_pic         = db.Column(db.String(512), nullable=True)

    adventures_created  = db.relationship('Adventure', back_populates='creator', lazy='dynamic')
    signups             = db.relationship('Signup', back_populates='user')
    assignments         = db.relationship('Assignment', back_populates='user')
    event_types_created = db.relationship('EventType', back_populates='creator')
    events_created      = db.relationship('Event', back_populates='creator')
    event_memberships   = db.relationship('EventMembership', back_populates='user', cascade='all, delete-orphan')
    hosted_sessions     = db.relationship('EventSession', back_populates='host', foreign_keys='EventSession.host_user_id')
    sessions_created    = db.relationship('EventSession', back_populates='creator', foreign_keys='EventSession.created_by_user_id')
    event_session_participations = db.relationship('EventSessionParticipant', back_populates='user', foreign_keys='EventSessionParticipant.user_id')
    event_session_entries_added = db.relationship('EventSessionParticipant', back_populates='added_by_user', foreign_keys='EventSessionParticipant.added_by_user_id')

    # Notification toggles used by push categories.
    notify_assignments = db.Column(db.Boolean, default=True)
    notify_event_updates = db.Column(db.Boolean, default=True)
    notify_signup_confirmation_3d = db.Column(db.Boolean, default=True)
    notify_live_signup_updates = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f"<User(display_name='{self.display_name}', privilege_level={self.privilege_level})>"
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.display_name is None:
            self.display_name = self.name

    def is_finished(self):
        return self.display_name

    @classmethod
    def create(cls, commit=True, **kwargs):
        """
        Factory to create a User and assign campaign if not provided.

        Usage:
            user = User.create(google_id='x', name='Alice', email='a@b.com')
        """
        user = cls(**kwargs)
        db.session.add(user)
        if commit:
            db.session.commit()
        return user
    
    def is_setup(self) -> bool:
        """Check if all required fields are filled in."""
        return bool(self.display_name and self.display_name.strip())



class Adventure(db.Model):
    __tablename__ = 'adventures'

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title               = db.Column(db.String(255), nullable=False)
    short_description   = db.Column(db.Text, nullable=False)
    user_id             = db.Column(db.Integer, db.ForeignKey('users.id')) # This is the creator
    event_type_id       = db.Column(db.Integer, db.ForeignKey('event_types.id'), nullable=True)
    max_players         = db.Column(db.Integer, nullable=False, default=5)
    date                = db.Column(db.Date, nullable=False)
    tags                = db.Column(db.String(255), nullable=True)
    release_assignments = db.Column(db.Boolean, nullable=False, default=False)
    release_reminder_days = db.Column(db.Integer, nullable=False, default=2)
    is_waitinglist      = db.Column(db.Integer, nullable=False, default=0) # 0 = no, 1 = yes, 2 = was waitinglist

    creator         = db.relationship('User', back_populates='adventures_created')
    event_type      = db.relationship('EventType', back_populates='adventures')
    signups         = db.relationship('Signup', back_populates='adventure')
    assignments     = db.relationship('Assignment', back_populates='adventure')

    def __repr__(self):
        return f"<Adventure(id={self.id}, title='{self.title}')>"
    
    @classmethod
    def create(cls, commit=True, **kwargs) -> "Adventure":
        """Factory to create a single Adventure."""
        adventure = cls(**kwargs)
        db.session.add(adventure)
        if commit:
            db.session.commit()

        return adventure

class Assignment(db.Model):
    __tablename__ = 'assignments'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'adventure_id', name='pk_adventure_assignment'),
    )

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    adventure_id = db.Column(db.Integer, db.ForeignKey('adventures.id'), primary_key=True)
    appeared = db.Column(db.Boolean, nullable=False, default=True)
    # preference_place stores the priority of the user's signup that led to this assignment.
    # 1 = first choice, 2 = second choice, 3 = third choice, 4+ = assigned outside top three
    # None = not applicable (e.g., waiting list assignment)
    preference_place = db.Column(db.Integer, nullable=True)
    creation_date = db.Column(db.DateTime, nullable=False, default=datetime.now())

    user = db.relationship('User', back_populates='assignments')
    adventure = db.relationship('Adventure', back_populates='assignments')

    def __repr__(self):
        return f"<Assignment(user_id={self.user_id}, adventure_id={self.adventure_id}, appeared={self.appeared}, preference_place={self.preference_place}, creation_date={self.creation_date})>"


class EventType(db.Model):
    __tablename__ = 'event_types'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(1024), nullable=True)
    weekday = db.Column(db.Integer, nullable=False)  # Monday=0 .. Sunday=6
    week_of_month = db.Column(db.Integer, nullable=False)  # 1..5
    exclude_july_august = db.Column(db.Boolean, nullable=False, default=False)
    is_single_event = db.Column(db.Boolean, nullable=False, default=False)
    signup_mode = db.Column(db.String(32), nullable=False, default="delayed_manual")
    default_release_reminder_days = db.Column(db.Integer, nullable=False, default=2)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    creator = db.relationship('User', back_populates='event_types_created')
    adventures = db.relationship('Adventure', back_populates='event_type')

    def __repr__(self):
        return f"<EventType(id={self.id}, title='{self.title}', week_of_month={self.week_of_month}, weekday={self.weekday})>"


class Event(db.Model):
    __tablename__ = 'events'

    PLACEMENT_IMMEDIATE = 'immediate'
    PLACEMENT_DELAYED = 'delayed'
    VALID_PLACEMENT_MODES = (PLACEMENT_IMMEDIATE, PLACEMENT_DELAYED)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(1024), nullable=True)
    placement_mode = db.Column(db.String(32), nullable=False, default=PLACEMENT_DELAYED)
    release_assignments = db.Column(db.Boolean, nullable=False, default=False)
    notification_days_before = db.Column(db.Integer, nullable=False, default=2)
    allow_event_admin_notifications = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    creator = db.relationship('User', back_populates='events_created')
    days = db.relationship('EventDay', back_populates='event', cascade='all, delete-orphan', order_by='EventDay.date')
    memberships = db.relationship('EventMembership', back_populates='event', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<Event(id={self.id}, title='{self.title}')>"


class EventDay(db.Model):
    __tablename__ = 'event_days'
    __table_args__ = (
        db.UniqueConstraint('event_id', 'date', name='unique_event_day_date'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    label = db.Column(db.String(255), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    event = db.relationship('Event', back_populates='days')
    tables = db.relationship('EventTable', back_populates='event_day', cascade='all, delete-orphan', order_by='EventTable.sort_order')
    sessions = db.relationship('EventSession', back_populates='event_day', cascade='all, delete-orphan', order_by='EventSession.start_time')

    def __repr__(self):
        return f"<EventDay(id={self.id}, event_id={self.event_id}, date={self.date})>"


class EventTable(db.Model):
    __tablename__ = 'event_tables'
    __table_args__ = (
        db.UniqueConstraint('event_day_id', 'name', name='unique_event_day_table_name'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_day_id = db.Column(db.Integer, db.ForeignKey('event_days.id'), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(1024), nullable=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    event_day = db.relationship('EventDay', back_populates='tables')
    sessions = db.relationship('EventSession', back_populates='event_table', cascade='all, delete-orphan', order_by='EventSession.start_time')

    def __repr__(self):
        return f"<EventTable(id={self.id}, name='{self.name}', event_day_id={self.event_day_id})>"


class EventMembership(db.Model):
    __tablename__ = 'event_memberships'
    __table_args__ = (
        db.UniqueConstraint('event_id', 'user_id', name='unique_event_user_membership'),
    )

    ROLE_EVENT_ADMIN = 'event_admin'
    ROLE_EVENT_HELPER = 'event_helper'
    VALID_ROLES = (ROLE_EVENT_ADMIN, ROLE_EVENT_HELPER)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_id = db.Column(db.Integer, db.ForeignKey('events.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(32), nullable=False)
    can_send_notifications = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    event = db.relationship('Event', back_populates='memberships')
    user = db.relationship('User', back_populates='event_memberships')

    def __repr__(self):
        return f"<EventMembership(event_id={self.event_id}, user_id={self.user_id}, role='{self.role}')>"

    @property
    def can_manage_sessions(self) -> bool:
        return self.role in self.VALID_ROLES

    @property
    def is_event_admin(self) -> bool:
        return self.role == self.ROLE_EVENT_ADMIN


class GuestPlayer(db.Model):
    __tablename__ = 'guest_players'

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    display_name = db.Column(db.String(255), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    creator = db.relationship('User')
    session_participations = db.relationship('EventSessionParticipant', back_populates='guest_player')

    def __repr__(self):
        return f"<GuestPlayer(id={self.id}, display_name='{self.display_name}')>"


class EventSession(db.Model):
    __tablename__ = 'event_sessions'

    PLACEMENT_IMMEDIATE = 'immediate'
    PLACEMENT_DELAYED = 'delayed'
    VALID_PLACEMENT_MODES = (PLACEMENT_IMMEDIATE, PLACEMENT_DELAYED)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title = db.Column(db.String(255), nullable=False)
    short_description = db.Column(db.Text, nullable=True)
    gamemaster_name = db.Column(db.String(255), nullable=True)
    event_day_id = db.Column(db.Integer, db.ForeignKey('event_days.id'), nullable=False)
    event_table_id = db.Column(db.Integer, db.ForeignKey('event_tables.id'), nullable=False)
    host_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    max_players = db.Column(db.Integer, nullable=False, default=5)
    start_time = db.Column(db.Time, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=60)
    placement_mode = db.Column(db.String(32), nullable=False, default=PLACEMENT_DELAYED)
    release_assignments = db.Column(db.Boolean, nullable=False, default=False)
    release_reminder_days = db.Column(db.Integer, nullable=False, default=2)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    event_day = db.relationship('EventDay', back_populates='sessions')
    event_table = db.relationship('EventTable', back_populates='sessions')
    host = db.relationship('User', back_populates='hosted_sessions', foreign_keys=[host_user_id])
    creator = db.relationship('User', back_populates='sessions_created', foreign_keys=[created_by_user_id])
    participants = db.relationship('EventSessionParticipant', back_populates='event_session', cascade='all, delete-orphan')

    def __repr__(self):
        return f"<EventSession(id={self.id}, title='{self.title}', event_day_id={self.event_day_id})>"

    @property
    def end_time(self):
        return (datetime.combine(datetime.today().date(), self.start_time) + timedelta(minutes=self.duration_minutes)).time()

    @property
    def event_id(self):
        return self.event_day.event_id if self.event_day else None

    def overlaps_with(self, other: 'EventSession') -> bool:
        if self.event_day_id != other.event_day_id:
            return False
        return self.start_time < other.end_time and other.start_time < self.end_time


class EventSessionParticipant(db.Model):
    __tablename__ = 'event_session_participants'
    __table_args__ = (
        db.UniqueConstraint('event_session_id', 'user_id', name='unique_session_user_participant'),
        db.UniqueConstraint('event_session_id', 'guest_player_id', name='unique_session_guest_participant'),
    )

    STATUS_PLACED = 'placed'
    STATUS_WAITLIST = 'waitlist'
    STATUS_BLOCKED_CONFLICT = 'blocked_conflict'
    STATUS_CANCELLED = 'cancelled'
    VALID_STATUSES = (STATUS_PLACED, STATUS_WAITLIST, STATUS_BLOCKED_CONFLICT, STATUS_CANCELLED)

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_session_id = db.Column(db.Integer, db.ForeignKey('event_sessions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    guest_player_id = db.Column(db.Integer, db.ForeignKey('guest_players.id'), nullable=True)
    status = db.Column(db.String(32), nullable=False, default=STATUS_WAITLIST)
    priority = db.Column(db.Integer, nullable=True)  # 1, 2, or 3 — used for delayed-placement ordering
    comment = db.Column(db.Text, nullable=True)
    added_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    event_session = db.relationship('EventSession', back_populates='participants')
    user = db.relationship('User', back_populates='event_session_participations', foreign_keys=[user_id])
    guest_player = db.relationship('GuestPlayer', back_populates='session_participations')
    added_by_user = db.relationship('User', back_populates='event_session_entries_added', foreign_keys=[added_by_user_id])

    def __repr__(self):
        return (
            f"<EventSessionParticipant(id={self.id}, event_session_id={self.event_session_id}, "
            f"status='{self.status}', user_id={self.user_id}, guest_player_id={self.guest_player_id})>"
        )

class Signup(db.Model):
    __tablename__ = 'signups'
    __table_args__ = (
        db.UniqueConstraint('user_id', 'adventure_id', name='unique_user_adventure'),
        db.UniqueConstraint('user_id', 'priority', 'adventure_date', name='unique_user_priority_date'),
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    adventure_id = db.Column(db.Integer, db.ForeignKey('adventures.id'), nullable=False)
    priority = db.Column(db.Integer, nullable=False)
    adventure_date = db.Column(db.Date, nullable=False)

    user = db.relationship('User', back_populates='signups')
    adventure = db.relationship('Adventure', back_populates='signups')

    def __repr__(self):
        return f"<Signup(id={self.id}, user_id={self.user_id}, adventure_id={self.adventure_id}, priority={self.priority})>"
