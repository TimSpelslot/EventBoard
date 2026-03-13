from datetime import datetime
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

    # Notification toggles used by push categories.
    notify_assignments = db.Column(db.Boolean, default=True)
    notify_create_adventure_reminder = db.Column(db.Boolean, default=False)

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
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    sort_order = db.Column(db.Integer, nullable=False, default=0)
    created_by_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)

    creator = db.relationship('User', back_populates='event_types_created')
    adventures = db.relationship('Adventure', back_populates='event_type')

    def __repr__(self):
        return f"<EventType(id={self.id}, title='{self.title}', week_of_month={self.week_of_month}, weekday={self.weekday})>"

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
