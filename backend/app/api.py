from flask_smorest import Blueprint, abort
from marshmallow import validates_schema, ValidationError, validate, fields
from flask_login import (
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask.views import MethodView
from flask import ( 
    request, 
    current_app, 
    url_for, 
    redirect,
    jsonify, 
    g 
    )
from sqlalchemy import text, delete, func
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError, SQLAlchemyError, MultipleResultsFound
import json
import requests
from typing import Any, cast

from .models import (
    db,
    User,
    Adventure,
    Assignment,
    FCMToken,
    EventType,
    Event,
    EventDay,
    EventTable,
    EventMembership,
    EventSession,
    EventSessionParticipant,
    GuestPlayer,
)
from .util import *
from .provider import ma, ap_scheduler
from firebase_admin import messaging


blp_utils = Blueprint("utils", "utils", url_prefix="/api/",
               description="Utils API: Everything that does not fit in the other categories.")
blp_adventures = Blueprint("adventures", "adventures", url_prefix="/api/adventures",
               description="Adventures API: Everything related to adventures. The big boxes with adventure names and descriptions.")
blp_assignments = Blueprint("player-assignment", "player-assignment", url_prefix="/api/player-assignments",
               description="Assignment API: Everything related to the assignments of players to adventures. The boxes with player names.")
blp_signups = Blueprint("signups", "signups", url_prefix="/api/signups",
               description="Signups API: Everything related to the signups of users. Priority medals 1, 2, 3")
blp_users = Blueprint("users", "users", url_prefix="/api/users",
               description="Users API: Everything related to the users.")
blp_event_types = Blueprint("event-types", "event-types", url_prefix="/api/event-types",
               description="Event Types API: Public event-type cards and admin management.")
blp_events = Blueprint("events", "events", url_prefix="/api/events",
               description="Events API: Concrete multi-day events, memberships, and schedule setup.")
blp_event_days = Blueprint("event-days", "event-days", url_prefix="/api/event-days",
               description="Event-day API: Tables and sessions within a concrete event day.")
blp_event_tables = Blueprint("event-tables", "event-tables", url_prefix="/api/event-tables",
               description="Event-table API: Table-level mutations within concrete event days.")
blp_event_sessions = Blueprint("event-sessions", "event-sessions", url_prefix="/api/event-sessions",
               description="Event-session API: Session-level mutations within concrete events.")
# 1. Define the Blueprint for Notifications
blp_notifications = Blueprint("notifications", "notifications", url_prefix="/api/notifications",
               description="FCM Operations: Saving tokens and triggering test pushes.")
api_blueprints = [
    blp_utils,
    blp_users,
    blp_event_types,
    blp_events,
    blp_event_days,
    blp_event_tables,
    blp_event_sessions,
    blp_adventures,
    blp_assignments,
    blp_signups,
    blp_notifications,
]

# ----------------------- Schemas ---------------------------------

class AliveSchema(ma.Schema):
    status = fields.String()
    db = fields.String()
    version = fields.String()

class RedirectSchema(ma.Schema):
    redirect_url = fields.Url(required=True)

class MessageSchema(ma.Schema):
    message = fields.String(required=True)

class AdminActionSchema(ma.Schema):
    action = fields.String(required=True)
    date = fields.Date(allow_none=True, required=False)

class DateSchema(ma.Schema):
    date = fields.Date(allow_none=True)

class JobSchema(ma.Schema):
    id = fields.Str(required=True)
    name = fields.Str(required=True)
    next_run_time = fields.DateTime(allow_none=True, required=False)
    trigger = fields.Str(required=True)

class SiteMapLinkSchema(ma.Schema):
    url = fields.Url(required=True)
    endpoint = fields.Str(required=True)

class UserSchema(ma.SQLAlchemyAutoSchema):
    """Schema for User that excludes the `name` column and exposes
    `display_name` (as the canonical display identity).

    Only a small set of non-sensitive fields are included by default. If you
    need to show or hide additional fields (email, google_id, etc.) consider
    adding parameters or a `hide_fields` pattern as in your original model file.
    """

    class Meta:
        model = User
        include_fk = True
        load_instance = False
        sqla_session = db.session
        # Exclude the database `name` field
        exclude = ("name","google_id","email")

class SignupUserSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Signup
        include_fk = True
        load_instance = False
        sqla_session = db.session
        exclude = ("id", "user_id", "adventure_date")

    user = fields.Nested(UserSchema, dump_only=True)

class AdventureSmallSchema(ma.SQLAlchemyAutoSchema):
    """Auto-schema for Adventure used for both output (dump) and input (load). Without any references
    """

    class Meta:
        model = Adventure
        include_fk = True
        load_instance = False
        sqla_session = db.session

class SignupAdventureSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Signup
        include_fk = True
        load_instance = True
        sqla_session = db.session
        exclude = ("id", "user_id", "adventure_date")

    adventure = fields.Nested(AdventureSmallSchema, dump_only=True)

class UserWithSignupsSchema(ma.SQLAlchemyAutoSchema):
    """Schema for User that excludes the `name` column and exposes
    `display_name` (as the canonical display identity).

    Only a small set of non-sensitive fields are included by default. If you
    need to show or hide additional fields (email, google_id, etc.) consider
    adding parameters when using this schema.
    """
    signups = fields.Nested(SignupAdventureSchema, many=True, dump_only=True)

    class Meta:
        model = User
        include_fk = True
        load_instance = True
        sqla_session = db.session

        exclude = ("id","name","google_id","email","privilege_level")


class UserPatchSchema(ma.Schema):
    display_name = fields.String(required=False)
    notify_assignments = fields.Boolean(required=False)
    notify_event_updates = fields.Boolean(required=False)
    notify_signup_confirmation_3d = fields.Boolean(required=False)
    notify_live_signup_updates = fields.Boolean(required=False)
    privilege_level = fields.Integer(required=False, validate=validate.OneOf([0, 1, 2]))

class AdventureQuerySchema(ma.Schema):
    adventure_id = fields.Integer(allow_none=True)
    week_start = fields.Date(allow_none=True)
    week_end = fields.Date(allow_none=True)
    event_type_id = fields.Integer(allow_none=True)
    include_archive = fields.Boolean(allow_none=True)

    @validates_schema
    def validate_dates(self, data, **kwargs):
        sd = data.get("week_start")
        ed = data.get("week_end")
        if sd and ed and sd > ed:
            raise ValidationError("week_start must be <= week_end.")
        
class AssignmentSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Assignment
        include_fk = True
        exclude = ("adventure_id","preference_place","user_id")

    user = fields.Nested(UserSchema, dump_only=True)

class AssignmentMoveSchema(ma.Schema):
    player_id = fields.Integer(required=True)
    from_adventure_id = fields.Integer(required=True)
    to_adventure_id = fields.Integer(required=True)

class AssignmentUpdateSchema(ma.Schema):
    user_id = fields.Integer(required=True)
    adventure_id = fields.Integer(required=True)
    appeared = fields.Boolean(required=True)

class AssignmentDeleteSchema(ma.Schema):
    adventure_id = fields.Integer(required=True)
    user_id = fields.Integer(required=False)  # Optional: for admins to specify which user's assignment to delete


class AdventureSchema(ma.SQLAlchemyAutoSchema):
    """Auto-schema for Adventure used for both output (dump) and input (load).

    - `players` is a nested list of UserSchema for dumping only.
    - `requested_players` is a load-only list of ints that the POST endpoint
       will use to create Assignment rows.
    """

    # assignments -> nested users (dump only)
    assignments = fields.List(fields.Nested(AssignmentSchema), dump_only=True)

    # signups -> nested users (dump only)
    signups = fields.List(fields.Nested(SignupUserSchema), dump_only=True)

    # allow creator to be set during creation
    creator = fields.Nested(UserSchema, dump_only=True)

    class Meta:
        model = Adventure
        include_fk = True
        load_instance = True
        sqla_session = db.session

    @validates_schema
    def validate_dates(self, data, **kwargs):
        sd = data.get("start_date")
        ed = data.get("end_date")
        max_players = data.get("max_players")
        if sd and ed and sd > ed:
            raise ValidationError("start_date must be <= end_date.")
        if not (max_players > 0 and max_players <= 30):
            raise ValidationError("max_players between 1 and 30, inclusive.")
        


class ConflictResponseSchema(ma.Schema):
    message = fields.Str(required=True)
    mis_assignments = fields.List(fields.Integer(), required=True)
    adventure = fields.Nested(AdventureSchema)


class EventTypeSchema(ma.SQLAlchemyAutoSchema):
    signup_mode = fields.String(
        required=False,
        validate=validate.OneOf(["immediate_automatic", "delayed_manual"]),
    )

    class Meta:
        model = EventType
        include_fk = True
        load_instance = False
        sqla_session = db.session
        dump_only = ("id", "created_at", "created_by_user_id")


class EventTypeResponseSchema(EventTypeSchema):
    next_date = fields.String(dump_only=True)


class EventMembershipSchema(ma.SQLAlchemyAutoSchema):
    user = fields.Nested(UserSchema, dump_only=True)

    class Meta:
        model = EventMembership
        include_fk = True
        load_instance = False
        sqla_session = db.session


class EventTableSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = EventTable
        include_fk = True
        load_instance = False
        sqla_session = db.session


class EventSessionSchema(ma.SQLAlchemyAutoSchema):
    host = fields.Nested(UserSchema, dump_only=True)
    creator = fields.Nested(UserSchema, dump_only=True)

    class Meta:
        model = EventSession
        include_fk = True
        load_instance = False
        sqla_session = db.session


class EventDaySchema(ma.SQLAlchemyAutoSchema):
    tables = fields.List(fields.Nested(lambda: EventTableSchema()), dump_only=True)
    sessions = fields.List(fields.Nested(lambda: EventSessionSchema()), dump_only=True)

    class Meta:
        model = EventDay
        include_fk = True
        load_instance = False
        sqla_session = db.session


class EventSchema(ma.SQLAlchemyAutoSchema):
    creator = fields.Nested(UserSchema, dump_only=True)
    memberships = fields.List(fields.Nested(lambda: EventMembershipSchema()), dump_only=True)
    days = fields.List(fields.Nested(lambda: EventDaySchema()), dump_only=True)

    class Meta:
        model = Event
        include_fk = True
        load_instance = False
        sqla_session = db.session


class EventCreateSchema(ma.Schema):
    title = fields.String(required=True)
    description = fields.String(required=False, allow_none=True)
    notification_days_before = fields.Integer(required=False, load_default=2)
    allow_event_admin_notifications = fields.Boolean(required=False, load_default=False)
    is_active = fields.Boolean(required=False, load_default=True)


class EventUpdateSchema(ma.Schema):
    title = fields.String(required=False)
    description = fields.String(required=False, allow_none=True)
    notification_days_before = fields.Integer(required=False)
    allow_event_admin_notifications = fields.Boolean(required=False)
    is_active = fields.Boolean(required=False)


class EventMembershipCreateSchema(ma.Schema):
    user_id = fields.Integer(required=True)
    role = fields.String(required=True, validate=validate.OneOf(list(EventMembership.VALID_ROLES)))
    can_send_notifications = fields.Boolean(required=False, load_default=False)


class EventDayCreateSchema(ma.Schema):
    date = fields.Date(required=True)
    label = fields.String(required=False, allow_none=True)
    sort_order = fields.Integer(required=False, load_default=0)


class EventDayUpdateSchema(ma.Schema):
    date = fields.Date(required=False)
    label = fields.String(required=False, allow_none=True)
    sort_order = fields.Integer(required=False)


class EventTableCreateSchema(ma.Schema):
    name = fields.String(required=True)
    sort_order = fields.Integer(required=False, load_default=0)


class EventTableUpdateSchema(ma.Schema):
    name = fields.String(required=False)
    sort_order = fields.Integer(required=False)


class EventSessionCreateSchema(ma.Schema):
    title = fields.String(required=True)
    short_description = fields.String(required=True)
    event_table_id = fields.Integer(required=True)
    host_user_id = fields.Integer(required=False, allow_none=True)
    max_players = fields.Integer(required=False, load_default=5)
    start_time = fields.Time(required=True)
    duration_minutes = fields.Integer(required=False, load_default=60)
    placement_mode = fields.String(required=False, load_default=EventSession.PLACEMENT_DELAYED, validate=validate.OneOf(list(EventSession.VALID_PLACEMENT_MODES)))
    release_assignments = fields.Boolean(required=False, load_default=False)
    release_reminder_days = fields.Integer(required=False, load_default=2)


class EventSessionUpdateSchema(ma.Schema):
    title = fields.String(required=False)
    short_description = fields.String(required=False)
    event_table_id = fields.Integer(required=False)
    host_user_id = fields.Integer(required=False, allow_none=True)
    max_players = fields.Integer(required=False)
    start_time = fields.Time(required=False)
    duration_minutes = fields.Integer(required=False)
    placement_mode = fields.String(required=False, validate=validate.OneOf(list(EventSession.VALID_PLACEMENT_MODES)))
    release_assignments = fields.Boolean(required=False)
    release_reminder_days = fields.Integer(required=False)


class EventSessionParticipantSchema(ma.SQLAlchemyAutoSchema):
    user = fields.Nested(UserSchema, dump_only=True)

    class GuestPlayerMiniSchema(ma.Schema):
        id = fields.Integer(required=True)
        display_name = fields.String(required=True)

    guest_player = fields.Nested(GuestPlayerMiniSchema, dump_only=True)

    class Meta:
        model = EventSessionParticipant
        include_fk = True
        load_instance = False
        sqla_session = db.session


class EventSessionManualParticipantCreateSchema(ma.Schema):
    display_name = fields.String(required=True)
    status = fields.String(required=False, load_default=EventSessionParticipant.STATUS_PLACED, validate=validate.OneOf(list(EventSessionParticipant.VALID_STATUSES)))
    priority = fields.Integer(required=False, allow_none=True, validate=validate.Range(min=1, max=3))
    comment = fields.String(required=False, allow_none=True)


class EventSessionUserParticipantCreateSchema(ma.Schema):
    user_id = fields.Integer(required=True)
    status = fields.String(required=False, load_default=EventSessionParticipant.STATUS_PLACED, validate=validate.OneOf(list(EventSessionParticipant.VALID_STATUSES)))
    priority = fields.Integer(required=False, allow_none=True, validate=validate.Range(min=1, max=3))
    comment = fields.String(required=False, allow_none=True)


class EventSessionParticipantUpdateSchema(ma.Schema):
    status = fields.String(required=False, validate=validate.OneOf(list(EventSessionParticipant.VALID_STATUSES)))
    priority = fields.Integer(required=False, allow_none=True, validate=validate.Range(min=1, max=3))
    comment = fields.String(required=False, allow_none=True)


class EventSessionNotifySchema(ma.Schema):
    title = fields.String(required=True)
    body = fields.String(required=True)
    include_waitlist = fields.Boolean(required=False, load_default=True)
    include_blocked = fields.Boolean(required=False, load_default=False)


class UserSearchQuerySchema(ma.Schema):
    q = fields.String(required=False, load_default='')


class PublicEventSessionSchema(ma.Schema):
    id = fields.Integer(required=True)
    title = fields.String(required=True)
    short_description = fields.String(required=True)
    event_table_id = fields.Integer(required=True)
    table_name = fields.String(required=True)
    host_user_id = fields.Integer(allow_none=True)
    max_players = fields.Integer(required=True)
    start_time = fields.Time(required=True)
    duration_minutes = fields.Integer(required=True)
    placement_mode = fields.String(required=True)
    placed_count = fields.Integer(required=True)
    waitlist_count = fields.Integer(required=True)
    my_status = fields.String(allow_none=True)
    my_participant_id = fields.Integer(allow_none=True)


class PublicEventDaySchema(ma.Schema):
    id = fields.Integer(required=True)
    date = fields.Date(required=True)
    label = fields.String(allow_none=True)
    sessions = fields.List(fields.Nested(PublicEventSessionSchema), required=True)


class PublicEventSchema(ma.Schema):
    id = fields.Integer(required=True)
    title = fields.String(required=True)
    description = fields.String(allow_none=True)
    days = fields.List(fields.Nested(PublicEventDaySchema), required=True)


def _event_query():
    return db.select(Event).options(
        joinedload(Event.creator),
        joinedload(Event.memberships).joinedload(EventMembership.user),
        joinedload(Event.days).joinedload(EventDay.tables),
        joinedload(Event.days).joinedload(EventDay.sessions).joinedload(EventSession.host),
        joinedload(Event.days).joinedload(EventDay.sessions).joinedload(EventSession.creator),
    )


def _has_table_schedule_conflict(
    event_day_id: int,
    event_table_id: int,
    start_time_value,
    duration_minutes: int,
    exclude_session_id: int | None = None,
) -> bool:
    candidate = EventSession(
        title="candidate",
        short_description="candidate",
        event_day_id=event_day_id,
        event_table_id=event_table_id,
        start_time=start_time_value,
        duration_minutes=duration_minutes,
    )
    query = db.select(EventSession).where(
        EventSession.event_day_id == event_day_id,
        EventSession.event_table_id == event_table_id,
    )
    if exclude_session_id is not None:
        query = query.where(EventSession.id != exclude_session_id)
    existing_sessions = db.session.execute(query).scalars().all()
    return any(candidate.overlaps_with(existing_session) for existing_session in existing_sessions)


def _placed_participant_count(event_session_id: int) -> int:
    return len(db.session.execute(
        db.select(EventSessionParticipant).where(
            EventSessionParticipant.event_session_id == event_session_id,
            EventSessionParticipant.status == EventSessionParticipant.STATUS_PLACED,
        )
    ).scalars().all())


def _placed_participant_count_excluding(event_session_id: int, exclude_participant_id: int | None = None) -> int:
    query = db.select(EventSessionParticipant).where(
        EventSessionParticipant.event_session_id == event_session_id,
        EventSessionParticipant.status == EventSessionParticipant.STATUS_PLACED,
    )
    if exclude_participant_id is not None:
        query = query.where(EventSessionParticipant.id != exclude_participant_id)
    return len(db.session.execute(query).scalars().all())


def _has_user_session_overlap(user_id: int, target_session: EventSession) -> bool:
    target_event_day = db.session.get(EventDay, target_session.event_day_id)
    session_rows = db.session.execute(
        db.select(EventSession)
        .join(EventSessionParticipant, EventSessionParticipant.event_session_id == EventSession.id)
        .options(joinedload(EventSession.event_day))
        .where(
            EventSessionParticipant.user_id == user_id,
            EventSessionParticipant.status == EventSessionParticipant.STATUS_PLACED,
            EventSession.id != target_session.id,
        )
    ).scalars().all()

    for existing in session_rows:
        if existing.event_day_id == target_session.event_day_id:
            if existing.overlaps_with(target_session):
                return True
            continue

        if existing.event_day and target_event_day and existing.event_day.date == target_event_day.date:
            if existing.start_time < target_session.end_time and target_session.start_time < existing.end_time:
                return True

    return False


def _next_waitlist_participant(event_session_id: int):
    return db.session.execute(
        db.select(EventSessionParticipant)
        .where(
            EventSessionParticipant.event_session_id == event_session_id,
            EventSessionParticipant.status == EventSessionParticipant.STATUS_WAITLIST,
        )
        .order_by(EventSessionParticipant.created_at.asc(), EventSessionParticipant.id.asc())
    ).scalars().first()


def _promote_next_waitlist_participant(event_session: EventSession):
    if _placed_participant_count(event_session.id) >= event_session.max_players:
        return None

    while True:
        candidate = _next_waitlist_participant(event_session.id)
        if not candidate:
            return None

        if candidate.user_id and _has_user_session_overlap(candidate.user_id, event_session):
            candidate.status = EventSessionParticipant.STATUS_BLOCKED_CONFLICT
            db.session.flush()
            continue

        candidate.status = EventSessionParticipant.STATUS_PLACED
        db.session.flush()
        return candidate


def _notify_user_participant_status_change(participant: EventSessionParticipant, event_session: EventSession, event_day: EventDay, trigger: str):
    if not participant.user_id:
        return

    user = db.session.get(User, participant.user_id)
    if not user:
        return

    date_str = event_day.date.isoformat() if event_day and event_day.date else "the event day"
    status = participant.status

    if trigger == "removed":
        send_fcm_notification(
            user,
            "Session update",
            f"You were removed from {event_session.title} on {date_str}.",
            category="assignments",
        )
        return

    if status == EventSessionParticipant.STATUS_PLACED:
        body = f"You are placed in {event_session.title} on {date_str}."
    elif status == EventSessionParticipant.STATUS_WAITLIST:
        body = f"You are on the waiting list for {event_session.title} on {date_str}."
    elif status == EventSessionParticipant.STATUS_BLOCKED_CONFLICT:
        body = f"You are currently blocked for {event_session.title} on {date_str} due to a schedule overlap."
    elif status == EventSessionParticipant.STATUS_CANCELLED:
        body = f"Your participation in {event_session.title} on {date_str} was cancelled."
    else:
        return

    send_fcm_notification(
        user,
        "Session update",
        body,
        category="assignments",
    )

# ----------------------- Routes ----------------------------------

# --- EVENT TYPES ---
@blp_event_types.route("")
class EventTypesResource(MethodView):
    @blp_event_types.response(200, EventTypeResponseSchema(many=True))
    def get(self):
        event_types = db.session.execute(
            db.select(EventType)
            .where(EventType.is_active.is_(True))
            .order_by(EventType.sort_order.asc(), EventType.title.asc())
        ).scalars().all()

        out = []
        for et in event_types:
            next_date = get_next_date_for_event_type(et)
            out.append({
                "id": et.id,
                "title": et.title,
                "description": et.description,
                "image_url": et.image_url,
                "weekday": et.weekday,
                "week_of_month": et.week_of_month,
                "exclude_july_august": et.exclude_july_august,
                "is_single_event": et.is_single_event,
                "signup_mode": et.signup_mode,
                "default_release_reminder_days": et.default_release_reminder_days,
                "is_active": et.is_active,
                "sort_order": et.sort_order,
                "next_date": next_date.isoformat(),
            })
        return out

    @login_required
    @blp_event_types.arguments(EventTypeSchema())
    @blp_event_types.response(201, EventTypeResponseSchema)
    def post(self, args):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        event_type = EventType()
        for key, value in args.items():
            setattr(event_type, key, value)
        event_type.created_by_user_id = current_user.id
        db.session.add(event_type)
        db.session.commit()

        next_date = get_next_date_for_event_type(event_type)
        return {
            "id": event_type.id,
            "title": event_type.title,
            "description": event_type.description,
            "image_url": event_type.image_url,
            "weekday": event_type.weekday,
            "week_of_month": event_type.week_of_month,
            "exclude_july_august": event_type.exclude_july_august,
            "is_single_event": event_type.is_single_event,
            "signup_mode": event_type.signup_mode,
            "default_release_reminder_days": event_type.default_release_reminder_days,
            "is_active": event_type.is_active,
            "sort_order": event_type.sort_order,
            "next_date": next_date.isoformat(),
        }


@blp_event_types.route("/<int:event_type_id>")
class EventTypeResource(MethodView):
    @login_required
    @blp_event_types.arguments(EventTypeSchema(partial=True))
    @blp_event_types.response(200, EventTypeResponseSchema)
    def patch(self, args, event_type_id):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        event_type = db.get_or_404(EventType, event_type_id)

        for key, value in args.items():
            setattr(event_type, key, value)

        if "signup_mode" in args:
            release_now = args.get("signup_mode") == "immediate_automatic"
            db.session.execute(
                db.update(Adventure)
                .where(
                    Adventure.event_type_id == event_type.id,
                    Adventure.date >= date.today(),
                )
                .values(release_assignments=release_now)
            )

        if "default_release_reminder_days" in args:
            db.session.execute(
                db.update(Adventure)
                .where(
                    Adventure.event_type_id == event_type.id,
                    Adventure.date >= date.today(),
                    Adventure.is_waitinglist == 0,
                    Adventure.release_assignments.is_(False),
                )
                .values(release_reminder_days=event_type.default_release_reminder_days)
            )

        db.session.commit()

        next_date = get_next_date_for_event_type(event_type)
        return {
            "id": event_type.id,
            "title": event_type.title,
            "description": event_type.description,
            "image_url": event_type.image_url,
            "weekday": event_type.weekday,
            "week_of_month": event_type.week_of_month,
            "exclude_july_august": event_type.exclude_july_august,
            "is_single_event": event_type.is_single_event,
            "signup_mode": event_type.signup_mode,
            "default_release_reminder_days": event_type.default_release_reminder_days,
            "is_active": event_type.is_active,
            "sort_order": event_type.sort_order,
            "next_date": next_date.isoformat(),
        }

    @login_required
    @blp_event_types.response(200, MessageSchema)
    def delete(self, event_type_id):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        notify_mode = (request.args.get("notify_mode") or "none").strip().lower()
        if notify_mode not in {"none", "removed", "cancelled"}:
            abort(400, message="Invalid notify_mode. Use none, removed, or cancelled.")

        event_type = db.get_or_404(EventType, event_type_id)

        future_adventures = db.session.execute(
            db.select(Adventure).where(
                Adventure.event_type_id == event_type_id,
                Adventure.date >= date.today(),
            )
        ).scalars().all()
        adventure_ids = [a.id for a in future_adventures]

        notify_users: list[User] = []
        if notify_mode != "none" and adventure_ids:
            signup_users = db.session.execute(
                db.select(User)
                .join(Signup, Signup.user_id == User.id)
                .where(Signup.adventure_id.in_(adventure_ids))
            ).scalars().all()
            assignment_users = db.session.execute(
                db.select(User)
                .join(Assignment, Assignment.user_id == User.id)
                .where(Assignment.adventure_id.in_(adventure_ids))
            ).scalars().all()
            seen = set()
            for u in [*signup_users, *assignment_users]:
                if u.id in seen:
                    continue
                seen.add(u.id)
                notify_users.append(u)

        if adventure_ids:
            db.session.execute(db.delete(Signup).where(Signup.adventure_id.in_(adventure_ids)))
            db.session.execute(db.delete(Assignment).where(Assignment.adventure_id.in_(adventure_ids)))
            db.session.execute(db.delete(Adventure).where(Adventure.id.in_(adventure_ids)))

        event_type.is_active = False
        db.session.commit()

        if notify_users:
            if notify_mode == "cancelled":
                body = f"{event_type.title} has been cancelled."
            else:
                body = f"{event_type.title} was removed and may be set up again."
            for u in notify_users:
                send_fcm_notification(u, "Event update", body, category="event_updates")

        return {"message": f"Event type {event_type.title} deleted successfully."}


# --- EVENTS ---
@blp_events.route("")
class EventsResource(MethodView):
    @login_required
    @blp_events.response(200, EventSchema(many=True))
    def get(self):
        query = _event_query().order_by(Event.created_at.desc())
        if not is_admin(current_user):
            query = query.join(Event.memberships).where(EventMembership.user_id == current_user.id)
        return db.session.execute(query).unique().scalars().all()

    @login_required
    @blp_events.arguments(EventCreateSchema())
    @blp_events.response(201, EventSchema)
    def post(self, args):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        event = Event(**args)
        event.created_by_user_id = current_user.id
        db.session.add(event)
        db.session.commit()
        return db.session.execute(
            _event_query().where(Event.id == event.id)
        ).unique().scalars().one()


@blp_events.route("/public")
class PublicEventsResource(MethodView):
    @login_required
    @blp_events.response(200, PublicEventSchema(many=True))
    def get(self):
        """Public browse endpoint for players with per-session signup state."""
        events = db.session.execute(
            db.select(Event)
            .options(
                joinedload(Event.days)
                .joinedload(EventDay.sessions)
                .joinedload(EventSession.event_table),
                joinedload(Event.days)
                .joinedload(EventDay.sessions)
                .joinedload(EventSession.participants),
            )
            .where(Event.is_active == True)
            .order_by(Event.created_at.desc())
        ).unique().scalars().all()

        today = date.today()
        payload = []
        for event in events:
            days_payload = []
            for day in sorted((event.days or []), key=lambda d: (d.date, d.sort_order, d.id)):
                if day.date < today:
                    continue
                sessions_payload = []
                for session in sorted((day.sessions or []), key=lambda s: (s.start_time, s.id)):
                    placed_count = 0
                    waitlist_count = 0
                    my_status = None
                    my_participant_id = None
                    for participant in (session.participants or []):
                        if participant.status == EventSessionParticipant.STATUS_PLACED:
                            placed_count += 1
                        elif participant.status == EventSessionParticipant.STATUS_WAITLIST:
                            waitlist_count += 1

                        if participant.user_id == current_user.id:
                            my_status = participant.status
                            my_participant_id = participant.id

                    sessions_payload.append({
                        "id": session.id,
                        "title": session.title,
                        "short_description": session.short_description,
                        "event_table_id": session.event_table_id,
                        "table_name": session.event_table.name if session.event_table else "Table",
                        "host_user_id": session.host_user_id,
                        "max_players": session.max_players,
                        "start_time": session.start_time,
                        "duration_minutes": session.duration_minutes,
                        "placement_mode": session.placement_mode,
                        "placed_count": placed_count,
                        "waitlist_count": waitlist_count,
                        "my_status": my_status,
                        "my_participant_id": my_participant_id,
                    })

                if sessions_payload:
                    days_payload.append({
                        "id": day.id,
                        "date": day.date,
                        "label": day.label,
                        "sessions": sessions_payload,
                    })

            if days_payload:
                payload.append({
                    "id": event.id,
                    "title": event.title,
                    "description": event.description,
                    "days": days_payload,
                })

        return payload


@blp_events.route("/<int:event_id>")
class EventResource(MethodView):
    @login_required
    @blp_events.response(200, EventSchema)
    def get(self, event_id):
        return db.session.execute(
            _event_query().where(Event.id == event_id)
        ).unique().scalars().one_or_none() or abort(404, message="Event not found")

    @login_required
    @blp_events.arguments(EventUpdateSchema())
    @blp_events.response(200, EventSchema)
    def patch(self, args, event_id):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        event = db.get_or_404(Event, event_id)
        for key, value in args.items():
            setattr(event, key, value)
        db.session.commit()
        return db.session.execute(
            _event_query().where(Event.id == event.id)
        ).unique().scalars().one()

    @login_required
    @blp_events.response(204)
    def delete(self, event_id):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        event = db.get_or_404(Event, event_id)
        db.session.delete(event)
        db.session.commit()


@blp_events.route("/<int:event_id>/memberships")
class EventMembershipsResource(MethodView):
    @login_required
    @blp_events.arguments(EventMembershipCreateSchema())
    @blp_events.response(201, EventMembershipSchema)
    def post(self, args, event_id):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        db.get_or_404(Event, event_id)
        user = db.session.get(User, args["user_id"])
        if not user:
            abort(404, message="User not found")

        membership = EventMembership(event_id=event_id, **args)
        db.session.add(membership)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="Membership already exists for this user and event")

        return db.session.execute(
            db.select(EventMembership)
            .options(joinedload(EventMembership.user))
            .where(EventMembership.id == membership.id)
        ).scalars().one()


@blp_events.route("/<int:event_id>/memberships/<int:membership_id>")
class EventMembershipResource(MethodView):
    @login_required
    @blp_events.response(204)
    def delete(self, event_id, membership_id):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        membership = db.session.execute(
            db.select(EventMembership)
            .where(EventMembership.id == membership_id, EventMembership.event_id == event_id)
        ).scalars().one_or_none()
        if not membership:
            abort(404, message="Membership not found")

        db.session.delete(membership)
        db.session.commit()


@blp_events.route("/<int:event_id>/days")
class EventDaysResource(MethodView):
    @login_required
    @blp_events.arguments(EventDayCreateSchema())
    @blp_events.response(201, EventDaySchema)
    def post(self, args, event_id):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        db.get_or_404(Event, event_id)
        event_day = EventDay(event_id=event_id, **args)
        db.session.add(event_day)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="An event day already exists for this date")
        return event_day


@blp_event_days.route("/<int:event_day_id>")
class EventDayResource(MethodView):
    @login_required
    @blp_event_days.arguments(EventDayUpdateSchema())
    @blp_event_days.response(200, EventDaySchema)
    def patch(self, args, event_day_id):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        event_day = db.get_or_404(EventDay, event_day_id)
        for key, value in args.items():
            setattr(event_day, key, value)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="An event day already exists for this date")
        return event_day

    @login_required
    @blp_event_days.response(200, MessageSchema)
    def delete(self, event_day_id):
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        event_day = db.get_or_404(EventDay, event_day_id)
        db.session.delete(event_day)
        db.session.commit()
        return {"message": "Event day deleted"}


@blp_event_days.route("/<int:event_day_id>/tables")
class EventDayTablesResource(MethodView):
    @login_required
    @blp_event_days.arguments(EventTableCreateSchema())
    @blp_event_days.response(201, EventTableSchema)
    def post(self, args, event_day_id):
        event_day = db.get_or_404(EventDay, event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not is_admin(current_user) and not is_event_admin(current_user, event):
            abort(401, message="Unauthorized")

        event_table = EventTable(event_day_id=event_day_id, **args)
        db.session.add(event_table)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="A table with this name already exists for the event day")
        return event_table


@blp_event_tables.route("/<int:event_table_id>")
class EventTableResource(MethodView):
    @login_required
    @blp_event_tables.arguments(EventTableUpdateSchema())
    @blp_event_tables.response(200, EventTableSchema)
    def patch(self, args, event_table_id):
        event_table = db.get_or_404(EventTable, event_table_id)
        event_day = db.get_or_404(EventDay, event_table.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not is_admin(current_user) and not is_event_admin(current_user, event):
            abort(401, message="Unauthorized")

        for key, value in args.items():
            setattr(event_table, key, value)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="A table with this name already exists for the event day")
        return event_table

    @login_required
    @blp_event_tables.response(200, MessageSchema)
    def delete(self, event_table_id):
        event_table = db.get_or_404(EventTable, event_table_id)
        event_day = db.get_or_404(EventDay, event_table.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not is_admin(current_user) and not is_event_admin(current_user, event):
            abort(401, message="Unauthorized")

        db.session.delete(event_table)
        db.session.commit()
        return {"message": "Event table deleted"}


@blp_event_days.route("/<int:event_day_id>/sessions")
class EventDaySessionsResource(MethodView):
    @login_required
    @blp_event_days.arguments(EventSessionCreateSchema())
    @blp_event_days.response(201, EventSessionSchema)
    def post(self, args, event_day_id):
        event_day = db.get_or_404(EventDay, event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        event_table = db.session.get(EventTable, args["event_table_id"])
        if not event_table or event_table.event_day_id != event_day_id:
            abort(400, message="event_table_id must belong to the target event day")

        host_user_id = args.get("host_user_id")
        if host_user_id is not None:
            host_user = db.session.get(User, host_user_id)
            if not host_user:
                abort(404, message="Host user not found")
            if not is_admin(current_user) and not is_event_admin(current_user, event) and host_user_id != current_user.id:
                abort(401, message="Helpers can only create sessions for themselves")
        elif not is_admin(current_user):
            host_user_id = current_user.id

        if _has_table_schedule_conflict(
            event_day_id,
            args["event_table_id"],
            args["start_time"],
            args["duration_minutes"],
        ):
            abort(409, message="This table already has an overlapping session for the selected time")

        session = EventSession(
            title=args["title"],
            short_description=args["short_description"],
            event_day_id=event_day_id,
            event_table_id=args["event_table_id"],
            host_user_id=host_user_id,
            created_by_user_id=current_user.id,
            max_players=args["max_players"],
            start_time=args["start_time"],
            duration_minutes=args["duration_minutes"],
            placement_mode=args["placement_mode"],
            release_assignments=args["release_assignments"],
            release_reminder_days=args["release_reminder_days"],
        )
        db.session.add(session)
        db.session.commit()
        return db.session.execute(
            db.select(EventSession)
            .options(joinedload(EventSession.host), joinedload(EventSession.creator))
            .where(EventSession.id == session.id)
        ).scalars().one()


@blp_event_sessions.route("/<int:event_session_id>")
class EventSessionResource(MethodView):
    @login_required
    @blp_event_sessions.arguments(EventSessionUpdateSchema())
    @blp_event_sessions.response(200, EventSessionSchema)
    def patch(self, args, event_session_id):
        session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        target_table_id = args.get("event_table_id", session.event_table_id)
        if "event_table_id" in args:
            target_table = db.session.get(EventTable, target_table_id)
            if not target_table or target_table.event_day_id != session.event_day_id:
                abort(400, message="event_table_id must belong to the session's event day")

        target_host_user_id = args.get("host_user_id", session.host_user_id)
        if "host_user_id" in args and target_host_user_id is not None:
            target_host_user = db.session.get(User, target_host_user_id)
            if not target_host_user:
                abort(404, message="Host user not found")
            if not is_admin(current_user) and not is_event_admin(current_user, event) and target_host_user_id != current_user.id:
                abort(401, message="Helpers can only assign themselves as host")

        target_start_time = args.get("start_time", session.start_time)
        target_duration = args.get("duration_minutes", session.duration_minutes)
        if _has_table_schedule_conflict(
            session.event_day_id,
            target_table_id,
            target_start_time,
            target_duration,
            exclude_session_id=session.id,
        ):
            abort(409, message="This table already has an overlapping session for the selected time")

        for key, value in args.items():
            setattr(session, key, value)
        db.session.commit()

        return db.session.execute(
            db.select(EventSession)
            .options(joinedload(EventSession.host), joinedload(EventSession.creator))
            .where(EventSession.id == session.id)
        ).scalars().one()

    @login_required
    @blp_event_sessions.response(200, MessageSchema)
    def delete(self, event_session_id):
        session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        db.session.delete(session)
        db.session.commit()
        return {"message": "Event session deleted"}


@blp_event_sessions.route("/<int:event_session_id>/participants/manual")
class EventSessionManualParticipantsResource(MethodView):
    @login_required
    @blp_event_sessions.arguments(EventSessionManualParticipantCreateSchema())
    @blp_event_sessions.response(201, EventSessionParticipantSchema)
    def post(self, args, event_session_id):
        event_session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        requested_status = args["status"]
        # Delayed sessions queue everyone as waitlist; placement is handled via process-placements
        if event_session.placement_mode == EventSession.PLACEMENT_DELAYED:
            requested_status = EventSessionParticipant.STATUS_WAITLIST
        elif requested_status == EventSessionParticipant.STATUS_PLACED and _placed_participant_count(event_session.id) >= event_session.max_players:
            requested_status = EventSessionParticipant.STATUS_WAITLIST

        guest_player = GuestPlayer(
            display_name=args["display_name"],
            created_by_user_id=current_user.id,
            notes=args.get("comment"),
        )
        db.session.add(guest_player)
        db.session.flush()

        participant = EventSessionParticipant(
            event_session_id=event_session.id,
            guest_player_id=guest_player.id,
            status=requested_status,
            priority=args.get("priority"),
            comment=args.get("comment"),
            added_by_user_id=current_user.id,
        )
        db.session.add(participant)
        db.session.commit()

        return db.session.execute(
            db.select(EventSessionParticipant)
            .options(joinedload(EventSessionParticipant.guest_player), joinedload(EventSessionParticipant.user))
            .where(EventSessionParticipant.id == participant.id)
        ).scalars().one()


@blp_event_sessions.route("/<int:event_session_id>/participants/users")
class EventSessionUserParticipantsResource(MethodView):
    @login_required
    @blp_event_sessions.arguments(EventSessionUserParticipantCreateSchema())
    @blp_event_sessions.response(201, EventSessionParticipantSchema)
    def post(self, args, event_session_id):
        event_session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        user = db.session.get(User, args["user_id"])
        if not user:
            abort(404, message="User not found")

        requested_status = args["status"]
        # Delayed sessions queue everyone as waitlist; placement is handled via process-placements
        if event_session.placement_mode == EventSession.PLACEMENT_DELAYED:
            requested_status = EventSessionParticipant.STATUS_WAITLIST
        elif requested_status == EventSessionParticipant.STATUS_PLACED:
            if _has_user_session_overlap(user.id, event_session):
                requested_status = EventSessionParticipant.STATUS_BLOCKED_CONFLICT
            elif _placed_participant_count(event_session.id) >= event_session.max_players:
                requested_status = EventSessionParticipant.STATUS_WAITLIST

        participant = EventSessionParticipant(
            event_session_id=event_session.id,
            user_id=user.id,
            status=requested_status,
            priority=args.get("priority"),
            comment=args.get("comment"),
            added_by_user_id=current_user.id,
        )
        db.session.add(participant)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            abort(409, message="User is already in this session participant list")

        _notify_user_participant_status_change(participant, event_session, event_day, trigger="created")

        return db.session.execute(
            db.select(EventSessionParticipant)
            .options(joinedload(EventSessionParticipant.guest_player), joinedload(EventSessionParticipant.user))
            .where(EventSessionParticipant.id == participant.id)
        ).scalars().one()


@blp_event_sessions.route("/<int:event_session_id>/participants")
class EventSessionParticipantsResource(MethodView):
    @login_required
    @blp_event_sessions.response(200, EventSessionParticipantSchema(many=True))
    def get(self, event_session_id):
        event_session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        return db.session.execute(
            db.select(EventSessionParticipant)
            .options(joinedload(EventSessionParticipant.guest_player), joinedload(EventSessionParticipant.user))
            .where(EventSessionParticipant.event_session_id == event_session_id)
            .order_by(EventSessionParticipant.created_at.asc(), EventSessionParticipant.id.asc())
        ).scalars().all()


@blp_event_sessions.route("/participants/<int:participant_id>")
class EventSessionParticipantResource(MethodView):
    @login_required
    @blp_event_sessions.arguments(EventSessionParticipantUpdateSchema())
    @blp_event_sessions.response(200, EventSessionParticipantSchema)
    def patch(self, args, participant_id):
        participant = db.get_or_404(EventSessionParticipant, participant_id)
        event_session = db.get_or_404(EventSession, participant.event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        original_status = participant.status
        if "status" in args:
            requested_status = args["status"]
            if requested_status == EventSessionParticipant.STATUS_PLACED:
                if participant.user_id and _has_user_session_overlap(participant.user_id, event_session):
                    requested_status = EventSessionParticipant.STATUS_BLOCKED_CONFLICT
                elif _placed_participant_count_excluding(event_session.id, exclude_participant_id=participant.id) >= event_session.max_players:
                    requested_status = EventSessionParticipant.STATUS_WAITLIST
            participant.status = requested_status

        if "comment" in args:
            participant.comment = args["comment"]

        if "priority" in args:
            participant.priority = args["priority"]

        db.session.commit()

        if participant.status != original_status:
            _notify_user_participant_status_change(participant, event_session, event_day, trigger="updated")

        return db.session.execute(
            db.select(EventSessionParticipant)
            .options(joinedload(EventSessionParticipant.guest_player), joinedload(EventSessionParticipant.user))
            .where(EventSessionParticipant.id == participant.id)
        ).scalars().one()

    @login_required
    @blp_event_sessions.response(200, MessageSchema)
    def delete(self, participant_id):
        participant = db.get_or_404(EventSessionParticipant, participant_id)
        event_session = db.get_or_404(EventSession, participant.event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        removed_user_id = participant.user_id
        removed_status = participant.status
        was_placed = participant.status == EventSessionParticipant.STATUS_PLACED
        db.session.delete(participant)

        promoted = None
        auto_promote = (request.args.get("auto_promote") or "true").strip().lower() != "false"
        if was_placed and auto_promote:
            promoted = _promote_next_waitlist_participant(event_session)

        db.session.commit()

        if removed_user_id and removed_status in {
            EventSessionParticipant.STATUS_PLACED,
            EventSessionParticipant.STATUS_WAITLIST,
            EventSessionParticipant.STATUS_BLOCKED_CONFLICT,
            EventSessionParticipant.STATUS_CANCELLED,
        }:
            removed_shadow = EventSessionParticipant(
                user_id=removed_user_id,
                status=EventSessionParticipant.STATUS_CANCELLED,
            )
            _notify_user_participant_status_change(removed_shadow, event_session, event_day, trigger="removed")

        if promoted:
            _notify_user_participant_status_change(promoted, event_session, event_day, trigger="promoted")

        if promoted:
            return {"message": f"Participant removed and waitlist participant {promoted.id} promoted"}
        return {"message": "Participant removed"}


@blp_event_sessions.route("/<int:event_session_id>/participants/promote-next")
class EventSessionPromoteNextResource(MethodView):
    @login_required
    @blp_event_sessions.response(200, EventSessionParticipantSchema)
    def post(self, event_session_id):
        event_session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        promoted = _promote_next_waitlist_participant(event_session)
        if not promoted:
            abort(409, message="No promotable waitlist participant available")

        db.session.commit()
        _notify_user_participant_status_change(promoted, event_session, event_day, trigger="promoted")
        return db.session.execute(
            db.select(EventSessionParticipant)
            .options(joinedload(EventSessionParticipant.guest_player), joinedload(EventSessionParticipant.user))
            .where(EventSessionParticipant.id == promoted.id)
        ).scalars().one()


@blp_event_sessions.route("/<int:event_session_id>/signup")
class EventSessionSelfSignupResource(MethodView):
    @login_required
    @blp_event_sessions.response(200, EventSessionParticipantSchema)
    def post(self, event_session_id):
        """Public self-signup endpoint for logged-in players."""
        event_session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)

        existing = db.session.execute(
            db.select(EventSessionParticipant)
            .where(
                EventSessionParticipant.event_session_id == event_session_id,
                EventSessionParticipant.user_id == current_user.id,
            )
        ).scalars().first()
        if existing:
            abort(409, message="You are already signed up for this session")

        if event_session.placement_mode == EventSession.PLACEMENT_DELAYED:
            status = EventSessionParticipant.STATUS_WAITLIST
        else:
            if _has_user_session_overlap(current_user.id, event_session):
                status = EventSessionParticipant.STATUS_BLOCKED_CONFLICT
            elif _placed_participant_count(event_session.id) >= event_session.max_players:
                status = EventSessionParticipant.STATUS_WAITLIST
            else:
                status = EventSessionParticipant.STATUS_PLACED

        participant = EventSessionParticipant(
            event_session_id=event_session.id,
            user_id=current_user.id,
            status=status,
            added_by_user_id=current_user.id,
        )
        db.session.add(participant)
        db.session.commit()

        _notify_user_participant_status_change(participant, event_session, event_day, trigger="created")
        return db.session.execute(
            db.select(EventSessionParticipant)
            .options(joinedload(EventSessionParticipant.guest_player), joinedload(EventSessionParticipant.user))
            .where(EventSessionParticipant.id == participant.id)
        ).scalars().one()

    @login_required
    @blp_event_sessions.response(200, MessageSchema)
    def delete(self, event_session_id):
        """Cancel current user's signup for a session."""
        event_session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)

        participant = db.session.execute(
            db.select(EventSessionParticipant)
            .where(
                EventSessionParticipant.event_session_id == event_session_id,
                EventSessionParticipant.user_id == current_user.id,
            )
        ).scalars().first()
        if not participant:
            abort(404, message="No signup found for this session")

        removed_user_id = participant.user_id
        removed_status = participant.status
        was_placed = participant.status == EventSessionParticipant.STATUS_PLACED
        db.session.delete(participant)

        promoted = None
        if was_placed:
            promoted = _promote_next_waitlist_participant(event_session)

        db.session.commit()

        if removed_user_id and removed_status in {
            EventSessionParticipant.STATUS_PLACED,
            EventSessionParticipant.STATUS_WAITLIST,
            EventSessionParticipant.STATUS_BLOCKED_CONFLICT,
            EventSessionParticipant.STATUS_CANCELLED,
        }:
            removed_shadow = EventSessionParticipant(
                user_id=removed_user_id,
                status=EventSessionParticipant.STATUS_CANCELLED,
            )
            _notify_user_participant_status_change(removed_shadow, event_session, event_day, trigger="removed")

        if promoted:
            _notify_user_participant_status_change(promoted, event_session, event_day, trigger="promoted")
            return {"message": f"Signup cancelled and waitlist participant {promoted.id} promoted"}

        return {"message": "Signup cancelled"}


@blp_event_sessions.route("/<int:event_session_id>/process-placements")
class EventSessionProcessPlacementsResource(MethodView):
    @login_required
    @blp_event_sessions.response(200, MessageSchema)
    def post(self, event_session_id):
        """Batch-process delayed placements: sort waitlist by priority (1→3, then signup time),
        place into available seats, mark conflicts as blocked, leave the rest on waitlist."""
        event_session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        if event_session.placement_mode != EventSession.PLACEMENT_DELAYED:
            abort(409, message="Session is not in delayed placement mode")

        waitlist = db.session.execute(
            db.select(EventSessionParticipant)
            .options(joinedload(EventSessionParticipant.user))
            .where(
                EventSessionParticipant.event_session_id == event_session_id,
                EventSessionParticipant.status == EventSessionParticipant.STATUS_WAITLIST,
            )
            .order_by(
                EventSessionParticipant.priority.asc().nulls_last(),
                EventSessionParticipant.created_at.asc(),
                EventSessionParticipant.id.asc(),
            )
        ).scalars().all()

        placed_count = _placed_participant_count(event_session.id)
        notifications: list[tuple[EventSessionParticipant, str]] = []

        for participant in waitlist:
            if participant.user_id and _has_user_session_overlap(participant.user_id, event_session):
                participant.status = EventSessionParticipant.STATUS_BLOCKED_CONFLICT
                notifications.append((participant, "updated"))
            elif placed_count < event_session.max_players:
                participant.status = EventSessionParticipant.STATUS_PLACED
                placed_count += 1
                notifications.append((participant, "promoted"))
            # else: leave on waitlist

        db.session.commit()

        for participant, trigger in notifications:
            _notify_user_participant_status_change(participant, event_session, event_day, trigger=trigger)

        placed_now = sum(1 for _, t in notifications if t == "promoted")
        blocked_now = sum(1 for _, t in notifications if t == "updated")
        return {"message": f"Placements processed: {placed_now} placed, {blocked_now} blocked conflict"}


@blp_event_sessions.route("/<int:event_session_id>/notify")
class EventSessionNotifyResource(MethodView):
    @login_required
    @blp_event_sessions.arguments(EventSessionNotifySchema())
    @blp_event_sessions.response(200, MessageSchema)
    def post(self, args, event_session_id):
        event_session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_send_event_notifications(current_user, event):
            abort(401, message="Unauthorized")

        statuses = [EventSessionParticipant.STATUS_PLACED]
        if args["include_waitlist"]:
            statuses.append(EventSessionParticipant.STATUS_WAITLIST)
        if args["include_blocked"]:
            statuses.append(EventSessionParticipant.STATUS_BLOCKED_CONFLICT)

        participants = db.session.execute(
            db.select(EventSessionParticipant)
            .options(joinedload(EventSessionParticipant.user))
            .where(
                EventSessionParticipant.event_session_id == event_session_id,
                EventSessionParticipant.user_id.is_not(None),
                EventSessionParticipant.status.in_(statuses),
            )
        ).scalars().all()

        notified_users = set()
        for participant in participants:
            user = participant.user
            if not user or user.id in notified_users:
                continue
            notified_users.add(user.id)
            send_fcm_notification(
                user,
                args["title"],
                args["body"],
                category="assignments",
            )

        return {"message": f"Notified {len(notified_users)} participants"}


@blp_event_sessions.route("/<int:event_session_id>/eligible-users")
class EventSessionEligibleUsersResource(MethodView):
    @login_required
    @blp_event_sessions.arguments(UserSearchQuerySchema(), location="query")
    @blp_event_sessions.response(200, UserSchema(many=True, exclude=['privilege_level', 'email']))
    def get(self, args, event_session_id):
        event_session = db.get_or_404(EventSession, event_session_id)
        event_day = db.get_or_404(EventDay, event_session.event_day_id)
        event = db.get_or_404(Event, event_day.event_id)
        if not can_manage_event_sessions(current_user, event):
            abort(401, message="Unauthorized")

        query_text = (args.get('q') or '').strip()
        statement = db.select(User).where(User.id != current_user.id)

        if query_text:
            pattern = f"%{query_text}%"
            statement = statement.where(
                User.display_name.ilike(pattern) | User.name.ilike(pattern)
            )

        existing_user_ids = db.session.execute(
            db.select(EventSessionParticipant.user_id).where(
                EventSessionParticipant.event_session_id == event_session_id,
                EventSessionParticipant.user_id.is_not(None),
            )
        ).scalars().all()
        if existing_user_ids:
            statement = statement.where(User.id.not_in(existing_user_ids))

        statement = statement.order_by(User.display_name.asc()).limit(20)
        return db.session.execute(statement).scalars().all()

# --- UTILS ---

@blp_utils.route("/alive")
class AliveResource(MethodView):
    @blp_utils.response(200, AliveSchema)
    def get(self):
        """Check API and DB connectivity."""
        try:
            db.session.execute(text("SELECT 1"))
            return {
                "status": "ok",
                "db": "reachable",
                "version": current_app.config["VERSION"]["version"],
            }
        except SQLAlchemyError as e:
            abort(
                500,
                message=str(e),
                extra={"version": current_app.config["VERSION"]["version"], "status": "error"},
            )
    
#@blp_utils.route("/site-map")
class SiteMapResource(MethodView):
    #@blp_utils.response(200, SiteMapLinkSchema(many=True))
    #@login_required
    def get(self):
        """
        Returns a list of all available endpoints (not only api).

        ---
        TODO: REMOVE
        """
        links = []
        for rule in current_app.url_map.iter_rules():
            # Filter out rules we can't navigate to in a browser
            # and rules that require parameters
            methods = rule.methods or set()
            if "GET" in methods and has_no_empty_params(rule):
                url = url_for(rule.endpoint, **(rule.defaults or {}))
                links.append((url, rule.endpoint))
        # links is now a list of url, endpoint tuples
        return jsonify(links)

@blp_utils.route("/scheduler")
class SchedulerResource(MethodView):
    @blp_utils.response(200, JobSchema(many=True))
    def get(self):
        """
        Returns a list of all scheduled jobs.
        """
        return ap_scheduler.get_jobs()

@blp_utils.route("/login")
class LoginResource(MethodView):
    @blp_utils.response(200, RedirectSchema)
    def get(self):
        """
        Requests a login from Google. Redirects to Google.
        """
        client, google_provider_cfg = get_google()
        # Find out what URL to hit for Google login            
        authorization_endpoint = google_provider_cfg["authorization_endpoint"]

        # Remember the page we want to go back to after logins
        next_url = request.args.get("next", "/")

        # Use library to construct the request for login and provide
        # scopes that let you retrieve user's profile from Google
        request_uri = client.prepare_request_uri(
            authorization_endpoint,
            redirect_uri=request.base_url + "/callback",
            scope=["openid", "email", "profile"],
            state=next_url  # store the original URL
        )
        return redirect(request_uri)
    
@blp_utils.route("/login/callback")
class CallbackResource(MethodView):
    @blp_utils.response(200, RedirectSchema)
    def get(self):
        """
        Endpoint for Google to redirect to after login.
        """
        try:
            # Get authorization code Google sent back to you
            code = request.args.get("code")
            if not code:
                return redirect(url_for("utils.LoginResource"))
            client, google_provider_cfg = get_google()
            state = request.args.get("state", "/")  # this is the original URL the login came from
        except Exception as e:
            return redirect(url_for("utils.LoginResource"))

        # Find out what URL to hit to get tokens that allow you to ask for
        # things on behalf of a user
        token_endpoint = google_provider_cfg["token_endpoint"]

        # Prepare and send request to get tokens! Yay tokens!
        token_url, headers, body = client.prepare_token_request(
            token_endpoint,
            authorization_response=request.url,
            redirect_url=request.base_url,
            code=code,
        )
        token_response = requests.post(
            token_url,
            headers=headers,
            data=body,
            auth=(current_app.config["GOOGLE"]["client_id"], current_app.config["GOOGLE"]["client_secret"]),
        )
        if not token_response.ok:
            return redirect(url_for("utils.LoginResource"))

        # Parse the tokens!
        client.parse_request_body_response(json.dumps(token_response.json()))

        # Now that we have tokens (yay) let's find and hit URL
        # from Google that gives you user's profile information,
        # including their Google Profile Image and Email
        userinfo_endpoint = google_provider_cfg["userinfo_endpoint"]
        uri, headers, body = client.add_token(userinfo_endpoint)
        userinfo_response = requests.get(uri, headers=headers, data=body)
        userinfo = userinfo_response.json() if hasattr(userinfo_response, "json") else {}
        if not userinfo_response.ok:
            return redirect(url_for("utils.LoginResource"))

        # We want to make sure their email is verified.
        # The user authenticated with Google, authorized our
        # app, and now we've verified their email through Google!
        if userinfo.get("email_verified"):
            unique_id = userinfo.get("sub")
            users_email = userinfo.get("email")
            picture = userinfo.get("picture",None)
            users_name = (
                userinfo.get("given_name")
                or userinfo.get("name")
                or (userinfo.get("email") or "").split("@")[0]
                or "Unknown User"
            )
        else:
            abort(400, message="User email not available or not verified by Google.")

        # See if Google’s user_id is already in our table
        stmt = db.select(User).where(User.google_id == unique_id)
        existing = db.session.scalars(stmt).first()

        if existing:
            # They’re already in our DB — use that
            user = existing
            
        else:
            # Not found → create and commit
            new_user = User.create(
                google_id=unique_id,
                name=users_name,
                email=users_email,
                profile_pic=picture)
            db.session.add(new_user)
            db.session.commit()
            user = new_user

        login_user(user)

        # Send user back to homepage or if he has not yet finished setup set him to edit his profile
        if user.is_setup():
            return redirect(state)
        else:
            return redirect(state)


@blp_utils.route('/logout')
class LockoutResource(MethodView):
    @login_required
    @blp_utils.response(200, RedirectSchema)
    def get(self):
        """
        Logout the current user.
        """
        next_url = request.args.get("next", "/")
        logout_user()
        return redirect(next_url)  

    
# --- USERS ---
@blp_users.route("")
class UsersListResource(MethodView):
    @login_required
    @blp_users.response(200, UserSchema(many=True))
    def get(self):
        """
        Return list of all users. 
        
        Returns basic user fields.
        Only non-sensitive fields are included by default. 
        If you are not an admin.
        """
        if not is_admin(current_user):
            abort(401, message="Unauthorized")
        try:
            return db.session.execute(db.select(User)).scalars().all()
        except SQLAlchemyError as e:
            abort(500, message=f"Database error: {str(e)}")

@blp_users.route("/signups/<string:day>")
class UsersListSignupsResource(MethodView):
    @blp_users.response(200)
    def get(self, day):
        """
        Return list of all users. 
        
        Returns users and their signups.
        Only non-sensitive fields are included by default. 
        If you are not an admin.
        """
        exclude = []
        if not is_admin(current_user):
            exclude=["privilege_level", "email", "signups"]
        try:
            today = date.today()
            # If day is provided and valid, use it instead of today
            if (day) and (day != "0"):
                try:
                    today = date.fromisoformat(day)
                except ValueError:
                    abort(400, message="Invalid date format. Use YYYY-MM-DD.")

            start_of_week, end_of_week = get_upcoming_week(today)
            stmt = (
                    db.select(User)
                    .options(
                        joinedload(User.signups),  # type: ignore
                        db.with_loader_criteria(
                            Signup,
                            Signup.adventure_date.between(start_of_week, end_of_week),
                            include_aliases=True
                        )
                    )

                )
            users = db.session.execute(stmt).unique().scalars().all()
        
            return UserWithSignupsSchema(many=True, exclude=exclude).dump(users)
        except SQLAlchemyError as e:
            abort(500, message=f"Database error: {str(e)}")

@blp_users.route("/<int:user_id>")
class UserResource(MethodView):
    @blp_users.response(200, UserSchema()) 
    def get(self, user_id):
        """Return single user by id."""
        try:
            user = db.session.get(User, user_id)
            if not user:
                abort(404, message="User not found")
            return user
        except SQLAlchemyError as e:
            abort(500, message=f"Database error: {str(e)}")

    @login_required
    @blp_users.arguments(UserPatchSchema())
    @blp_users.response(200, UserSchema())
    def patch(self, args, user_id):
        """
        Partially update a user. Only fields present in the JSON body will be changed.
        """
        try:
            user = db.session.get(User, user_id)
            if not user:
                abort(404, message="User not found")

            is_target_self = current_user.id == user_id
            user_is_admin = is_admin(current_user)
            if not is_target_self and not user_is_admin:
                abort(401, message="Unauthorized")

            if "privilege_level" in args and not user_is_admin:
                abort(401, message="Only admins can change privilege level")

            for key, val in args.items():
                setattr(user, key, val)

            db.session.commit()
            return user

        except IntegrityError as e:
            db.session.rollback()
            # typically triggered by unique constraint (e.g. email already exists)
            abort(409, message=f"Conflict: {str(e.orig) if hasattr(e, 'orig') else str(e)}")

        except SQLAlchemyError as e:
            db.session.rollback()
            abort(500, message=f"Database error: {str(e)}")
    
    

@blp_users.route("/me")
class MeResource(MethodView):
    @login_required
    @blp_utils.response(200, UserSchema())
    def get(self):
        """Return current user's details."""
        return current_user

# --- ADVENTURES ---
@blp_adventures.route("")
class AdventureIDlessRequest(MethodView):

    @blp_adventures.arguments(AdventureQuerySchema, location="query")
    #@blp_adventures.response(200, AdventureSchema(many=True))
    def get(self, args):
        """
        Returns a list of Adventure objects within the specified date range. 
        
        The field `players` will be present only when the requester has privilege level >= 1.
        """
        try:
            week_start = args.get("week_start")
            week_end = args.get("week_end")
            event_type_id = args.get("event_type_id")
            include_archive = bool(args.get("include_archive"))
            is_authenticated = current_user.is_authenticated
            is_staff = is_authenticated and current_user.privilege_level >= 1

            if include_archive and not is_staff:
                abort(401, message="Only staff members and admins can view the archive.")
            today = date.today()

            # Eager-load assignments -> user to avoid N+1 queries
            stmt = db.select(Adventure).options(
                joinedload(Adventure.assignments).joinedload(Assignment.user)  # type: ignore
            ).order_by(Adventure.date)


            if week_start and week_end:
                stmt = stmt.where(
                    Adventure.date <= week_end,
                    Adventure.date >= week_start,
                )

            if include_archive:
                stmt = stmt.where(Adventure.date < today)
            else:
                stmt = stmt.where(Adventure.date >= today)

            if event_type_id:
                stmt = stmt.where(Adventure.event_type_id == event_type_id)

            adventures = db.session.execute(stmt).unique().scalars().all()

            # Player visibility:
            # - admins always see full assignments
            # - before release, non-admin users see no assignments
            # - after release, privilege >= 1 sees all; privilege 0 sees own only
            # - anonymous users see no assignments
            user_is_admin = is_admin(current_user)
            display_all_players = is_authenticated and current_user.privilege_level >= 1
            exclude = []
            if not user_is_admin:
                exclude = ["signups"]
            if not is_authenticated:
                exclude = exclude + ["assignments"]

            out = cast(list[dict[str, Any]], AdventureSchema(many=True, exclude=exclude).dump(adventures))

            if is_authenticated and not user_is_admin:
                for adv in out:
                    if "assignments" not in adv:
                        continue
                    if not adv.get("release_assignments", False):
                        adv.pop("assignments", None)
                        continue
                    if display_all_players:
                        continue
                    own_assignments = [
                        assignment
                        for assignment in adv["assignments"]
                        if assignment.get("user", {}).get("id") == current_user.id
                    ]
                    if own_assignments:
                        adv["assignments"] = own_assignments
                    else:
                        adv.pop("assignments", None)

            return out

        except ValidationError as ve:
            abort(400, message=str(ve))

        except SQLAlchemyError as e:
            abort(500, message=f"Database error: {str(e)}")

    @login_required
    @blp_adventures.arguments(
        AdventureSchema(
            exclude=(
                "id",
                "user_id",
            ),
            load_instance=False,
        )
    )
    @blp_adventures.response(201, AdventureSchema()) 
    @blp_adventures.alt_response(409, schema=ConflictResponseSchema())
    def post(self, args):
        """
        Create a new adventure
        """
        if not current_user.is_authenticated or current_user.privilege_level < 1:
            abort(401, message="Only staff members or admins can create sessions.")

        try: 
            event_type = None
            event_type_id = args.get("event_type_id")
            if event_type_id:
                event_type = db.session.get(EventType, event_type_id)

            if "release_reminder_days" not in args:
                if event_type_id:
                    if event_type:
                        args["release_reminder_days"] = event_type.default_release_reminder_days

            if event_type and event_type.signup_mode == "immediate_automatic":
                args["release_assignments"] = True

            new_adv = Adventure.create(
                user_id=current_user.id,
                **args
            )
            db.session.flush()  # new_adv.id available

            # Ensure each event/date bucket has its own waiting list.
            make_waiting_list_for_event(new_adv.event_type_id, new_adv.date)

            db.session.commit()
            # Normal success: return the model instance (decorator will dump it)
            return new_adv

        except ValidationError as ve:
            db.session.rollback()
            abort(400, message=str(ve))

        except SQLAlchemyError as e:
            db.session.rollback()
            abort(500, message=f"Database error: {str(e)}")

        except Exception as e:
            db.session.rollback()
            raise e

@blp_adventures.route("<int:adventure_id>")
class AdventureResource(MethodView):

    @blp_adventures.arguments(AdventureQuerySchema, location="query")
    #@blp_adventures.response(200, AdventureSchema())
    def get(self, args, adventure_id):
        """
        Returns a singular Adventure objects. 
        
        The field `players` will be present only when the requester has privilege level >= 1.
        """
        try:
            # Eager-load assignments -> user to avoid N+1 queries
            stmt = db.select(Adventure).options(
                joinedload(Adventure.assignments).joinedload(Assignment.user)  # type: ignore
            )

            stmt = db.select(Adventure).where(Adventure.id == int(adventure_id))

            adventures = db.session.scalars(stmt).all()

            # Player visibility:
            # - admins always see full assignments
            # - before release, non-admin users see no assignments
            # - after release, privilege >= 1 sees all; privilege 0 sees own only
            # - anonymous users see no assignments
            is_authenticated = current_user.is_authenticated
            user_is_admin = is_admin(current_user)
            display_all_players = is_authenticated and current_user.privilege_level >= 1
            exclude = []
            if not user_is_admin:
                exclude = ["signups"]
            if not is_authenticated:
                exclude = exclude + ["assignments"]

            out = cast(list[dict[str, Any]], AdventureSchema(many=True, exclude=exclude).dump(adventures))

            if is_authenticated and not user_is_admin:
                for adv in out:
                    if "assignments" not in adv:
                        continue
                    if not adv.get("release_assignments", False):
                        adv.pop("assignments", None)
                        continue
                    if display_all_players:
                        continue
                    own_assignments = [
                        assignment
                        for assignment in adv["assignments"]
                        if assignment.get("user", {}).get("id") == current_user.id
                    ]
                    if own_assignments:
                        adv["assignments"] = own_assignments
                    else:
                        adv.pop("assignments", None)

            return out

        except ValidationError as ve:
            abort(400, message=str(ve))

        except SQLAlchemyError as e:
            abort(500, message=f"Database error: {str(e)}")


    @login_required
    @blp_adventures.arguments(
        AdventureSchema(
            partial=True,
            exclude=(
                "id",
                "user_id",
            ),
            load_instance=False,
        )
    )
    def patch(self, args, adventure_id):
        """
        Edit an existing adventure. Only creator or admin can edit.

        Creator is not editable.
        """
        user_id = current_user.id
        adventure = db.session.get(Adventure, adventure_id)
        if not adventure:
            abort(404, message=f"Adventure with id: {adventure_id} not found.")

        # Ownership or admin check
        if not is_admin(current_user) and adventure.user_id != user_id:
            abort(401, message="Unauthorized to edit this adventure.")
            

        # Update provided fields
        for field in args:
            setattr(adventure, field, args[field])

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            abort(500, message=str(e))

        return {"message": "Adventure updated successfully"}
    
    @login_required
    @blp_adventures.response(200, MessageSchema)
    def delete(self, adventure_id):
        """
        Deletes an adventure with the given ID. Only creator or admin can delete.
        """
        user_id = current_user.id
        notify_mode = (request.args.get("notify_mode") or "none").strip().lower()
        if notify_mode not in {"none", "removed", "cancelled"}:
            abort(400, message={"error": "Invalid notify_mode. Use none, removed, or cancelled."})

        if not adventure_id:
            abort(400, message={'error': 'Missing adventure_id'})

        try:
            adventure = db.session.get(Adventure, adventure_id)
            if not adventure:
                abort(404, message={'error': 'Adventure not found'})

            # Check permission: admin or creator
            if not is_admin(current_user) and adventure.user_id != user_id:
                abort(401, message={'error': 'Unauthorized to delete this adventure'})

            notify_users = []
            if adventure.date >= date.today() and notify_mode != "none":
                signup_users = db.session.execute(
                    db.select(User)
                    .join(Signup, Signup.user_id == User.id)
                    .where(Signup.adventure_id == adventure_id)
                ).scalars().all()
                assignment_users = db.session.execute(
                    db.select(User)
                    .join(Assignment, Assignment.user_id == User.id)
                    .where(Assignment.adventure_id == adventure_id)
                ).scalars().all()
                seen_ids = set()
                for u in [*signup_users, *assignment_users]:
                    if u.id in seen_ids:
                        continue
                    seen_ids.add(u.id)
                    notify_users.append(u)

            # Delete signups related to this adventure
            db.session.execute(
                db.delete(Signup).where(Signup.adventure_id == adventure_id)
            )

            # Delete assignments related to this adventure
            db.session.execute(
                db.delete(Assignment).where(Assignment.adventure_id == adventure_id)
            )

            # Delete the adventure itself
            db.session.delete(adventure)
            db.session.commit()

            if notify_users:
                if notify_mode == "cancelled":
                    body = f"{adventure.title} on {adventure.date.isoformat()} has been cancelled."
                else:
                    body = f"{adventure.title} on {adventure.date.isoformat()} was removed and may be set up again."

                for u in notify_users:
                    send_fcm_notification(
                        u,
                        "Session update",
                        body,
                        category="event_updates",
                    )

            return {'message': f'Adventure {adventure_id} and all relations deleted successfully'}

        except SQLAlchemyError as e:
            db.session.rollback()
            return abort(500, message={'error': f'Database error: {str(e)}'})

        except Exception as e:
            return abort(500, message={'error': str(e)})

# --- ASSIGNMENTS ---
@blp_assignments.route('')
class AssignmentResource(MethodView):
    @login_required
    @blp_assignments.response(200,UserSchema(many=True, exclude=['privilege_level', 'email']))
    def get(self):
        """
        Returns a list of players assigned to a single adventure.
        """
        if current_user.privilege_level < 1:
            abort(401, message={'error': 'Unauthorized'})

        try:
            adventure_id = request.args.get('adventure_id', type=int)
            if not adventure_id:
                abort(400, message={'error': 'Adventure ID is required'})
            stmt = db.select(Assignment).join(User).where(
                Assignment.adventure_id == adventure_id
            )
            assignments = db.session.scalars(stmt).all()
            users = [assignment.user for assignment in assignments if assignment.user]

            return users, 200

        except Exception as e:
            return abort(500, message={'error': str(e)})

    @login_required
    @blp_assignments.arguments(AdminActionSchema)
    @blp_assignments.response(200, MessageSchema)
    def put(self, args):
        """
        Executes an admin action.
        """
        # Admin check
        if not is_admin(current_user):
            abort(401, message="Unauthorized")
        
        action = args.get('action')
        today = args.get('date', date.today())

        if action == "assign":
            assign_players_to_adventures(today) 
        elif action == "reassign":
            reassign_players_from_waiting_list(today)
        elif action == "release":
            release_assignments(today)
        elif action == "reset":
            reset_release(today)
        else:
            abort(400, message=f"Invalid action: {action}")

        return {'message': f'{action.capitalize()} action executed successfully for {today}'}, 200
    
    @login_required
    @blp_assignments.arguments(AssignmentUpdateSchema)
    @blp_assignments.response(200, MessageSchema)
    def post(self, args):
        """
        Updates the 'appeared' value for an Assignment for a given user.
        Expects JSON body: { "user_id": int, "adventure_id": int, "appeared": <new_value> }
        """

        if current_user.privilege_level < 1: # Is semi admin (only allowed to watch if players appear)
            return abort(401, message={'error': 'Unauthorized'})
       
        user_id = args['user_id']
        adventure_id = args['adventure_id']
        new_value = args['appeared']

        if not user_id or not adventure_id:
            return abort(400, message={'error': 'Both user_id and adventure_id are required'})

        # Fetch the assignment
        assignment = db.session.scalar(
            db.select(Assignment).where(
                Assignment.user_id == user_id,
                Assignment.adventure_id == adventure_id
            )
        )

        if not assignment:
            return abort(404, message=({'error': 'Assignment not found'}))

        # Update the value
        assignment.appeared = new_value
        try:
            db.session.commit()

            return {'message': 'Assignment updated successfully'}, 200

        except Exception as e:
            db.session.rollback()
            return abort(500, message={'error': str(e)})
        
    
    @blp_assignments.arguments(AssignmentMoveSchema)
    @login_required
    def patch(self, args):
        """
        Moves a players assignment from one adventure to another.
        """
        if not is_admin(current_user):
            abort(401, message="Unauthorized")

        player_id = args['player_id']
        from_adventure_id = args['from_adventure_id']
        to_adventure_id = args['to_adventure_id']

        stmt = db.select(Assignment).where(
            Assignment.user_id == player_id,
            Assignment.adventure_id == from_adventure_id
        )
        assignment = db.session.scalars(stmt).first()

        if not assignment:
            abort(404, message="Assignment not found")

        assignment.adventure_id = to_adventure_id
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            abort(400, message=str(e))

        return {'message': 'Assignment updated successfully'}, 200
    
    @blp_assignments.arguments(AssignmentDeleteSchema)
    @login_required
    def delete(self, args):
        """
        Deletes a players assignment from one adventure.
        """
        current_user_id = current_user.id
        adventure_id = args.get('adventure_id')
        target_user_id = args.get('user_id')  # Optional: for admins to specify which user

        if not adventure_id:
            abort(422, message={'error': 'adventure_id is required'})

        # Build query: non-admins can only delete their own assignment
        # Admins can delete any assignment, optionally specified by user_id
        query = db.select(Assignment).where(Assignment.adventure_id == adventure_id)
        
        if is_admin(current_user):
            # Admin: if user_id is provided, filter by it
            if target_user_id:
                query = query.where(Assignment.user_id == target_user_id)
            try:
                assignment = db.session.execute(query).scalar_one_or_none()
            except MultipleResultsFound:
                # If multiple results and no user_id specified, provide helpful error
                abort(400, message={'error': 'Multiple assignments found for this adventure. Please specify user_id to delete a specific assignment.'})
        else:
            # Non-admin: must be their own assignment
            query = query.where(Assignment.user_id == current_user_id)
            assignment = db.session.execute(query).scalar_one_or_none()
        
        if not assignment:
            abort(404, message={'error': 'Assignment not found'})

        # Check permission: admin or creator
        if not is_admin(current_user) and assignment.user_id != current_user_id:
            abort(401, message={'error': 'Unauthorized to delete this adventure'})

        canceled_adventure_date = assignment.adventure.date if assignment.adventure else date.today()

        # Delete assignments related to this adventure
        db.session.delete(assignment)
        db.session.flush()

        # If someone cancels after assignment, immediately promote from waiting list.
        reassign_players_from_waiting_list(canceled_adventure_date, auto_commit=False)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            abort(400, message=str(e))

        return {'message': 'Assignment updated successfully'}, 200

# --- SIGNUP ---
@blp_signups.route('')
class SignupResource(MethodView):
    @login_required
    @blp_signups.response(200, SignupUserSchema(many=True))
    def get(self):
        """
        Returns all the signups (priority medals 1, 2, 3) of the authenticated user.
        """
        if current_user.is_anonymous: # User is not signed in
            abort(401, message="Unauthorized")

        try:
            stmt = db.select(Signup).where(Signup.user_id == current_user.id)
            signups = db.session.scalars(stmt).all()
            return signups

        except SQLAlchemyError as e:
            abort(500, message=f"Database error: {str(e)}")

        except Exception as e:
            abort(500, message=str(e))

    @login_required
    @blp_signups.arguments(SignupUserSchema())
    @blp_signups.response(200, MessageSchema())
    def post(self, args):
        """
        Makes a signup for a specific adventure.
        Deletes old ones if a signup already exists.
        Acts as a toggle: if the same signup exists, it removes it.
        """
        adventure_id = args["adventure_id"]
        priority = args["priority"]
        user_id = current_user.id

        try:

            # Fetch the adventure for signup rules and optional immediate placement.
            adventure = db.session.get(Adventure, adventure_id)
            if not adventure:
                abort(404, message='Adventure not found')
            adventure_date = adventure.date
            event_type = db.session.get(EventType, adventure.event_type_id) if adventure.event_type_id else None
            signup_mode = (event_type.signup_mode if event_type and event_type.signup_mode else "delayed_manual")
            
            # Check if exact same signup already exists (toggle behavior)
            stmt = db.select(Signup).where(
                Signup.user_id == user_id,
                Signup.adventure_id == adventure_id,
                Signup.priority == priority
            )

            existing_signup = db.session.scalars(stmt).first()

            if existing_signup:
                db.session.delete(existing_signup)
                if signup_mode == "immediate_automatic":
                    # Immediate mode keeps assignment state in sync with signup toggles.
                    existing_assignment = db.session.execute(
                        db.select(Assignment).where(
                            Assignment.user_id == user_id,
                            Assignment.adventure_id == adventure_id,
                        )
                    ).scalars().first()
                    if existing_assignment:
                        db.session.delete(existing_assignment)
                        reassign_players_from_waiting_list(adventure_date, auto_commit=False)

                    waiting_list = make_waiting_list_for_event(adventure.event_type_id, adventure.date)
                    still_signed_up_in_bucket = db.session.execute(
                        db.select(func.count(Signup.id))
                        .join(Adventure, Signup.adventure_id == Adventure.id)
                        .where(
                            Signup.user_id == user_id,
                            Adventure.date == adventure_date,
                            Adventure.event_type_id == adventure.event_type_id,
                            Adventure.is_waitinglist == 0,
                        )
                    ).scalar_one()
                    if not still_signed_up_in_bucket:
                        db.session.execute(
                            db.delete(Assignment).where(
                                Assignment.user_id == user_id,
                                Assignment.adventure_id == waiting_list.id,
                            )
                        )
                message = 'Signup removed'
            else:
                if signup_mode == "delayed_manual":
                    # Remove any existing signup with same priority and date (regardless of adventure)
                    db.session.execute(
                        delete(Signup).where(
                            Signup.user_id == user_id,
                            Signup.priority == priority,
                            Signup.adventure_date == adventure_date
                        )
                    )

                    # Remove any existing signup for same adventure (regardless of priority)
                    db.session.execute(
                        delete(Signup).where(
                            Signup.user_id == user_id,
                            Signup.adventure_id == adventure_id
                        )
                    )

                # Add new signup
                new_signup = Signup(
                    user_id=user_id,  # type: ignore
                    adventure_id=adventure_id,  # type: ignore
                    priority=priority,  # type: ignore
                    adventure_date=adventure_date  # type: ignore
                )
                db.session.add(new_signup)

                if signup_mode == "immediate_automatic" and adventure.is_waitinglist == 0:
                    waiting_list = make_waiting_list_for_event(adventure.event_type_id, adventure.date)
                    already_assigned = db.session.execute(
                        db.select(Assignment)
                        .join(Adventure, Assignment.adventure_id == Adventure.id)
                        .where(
                            Assignment.user_id == user_id,
                            Adventure.date == adventure_date,
                            Adventure.event_type_id == adventure.event_type_id,
                            Adventure.is_waitinglist == 0,
                        )
                    ).scalars().first()

                    if already_assigned:
                        # A player assigned in this event/date bucket may not stay on any waiting list in the bucket.
                        db.session.execute(
                            db.delete(Assignment).where(
                                Assignment.user_id == user_id,
                                Assignment.adventure_id == waiting_list.id,
                            )
                        )
                    else:
                        filled = db.session.execute(
                            db.select(func.count(Assignment.user_id))
                            .where(Assignment.adventure_id == adventure_id)
                        ).scalar_one()

                        if filled < adventure.max_players:
                            assignment = Assignment()
                            assignment.user_id = user_id
                            assignment.adventure_id = adventure_id
                            assignment.preference_place = None
                            db.session.add(assignment)
                            db.session.execute(
                                db.delete(Assignment).where(
                                    Assignment.user_id == user_id,
                                    Assignment.adventure_id == waiting_list.id,
                                )
                            )
                        else:
                            existing_waiting = db.session.execute(
                                db.select(Assignment).where(
                                    Assignment.user_id == user_id,
                                    Assignment.adventure_id == waiting_list.id,
                                )
                            ).scalars().first()
                            if not existing_waiting:
                                waiting_assignment = Assignment()
                                waiting_assignment.user_id = user_id
                                waiting_assignment.adventure_id = waiting_list.id
                                waiting_assignment.preference_place = None
                                db.session.add(waiting_assignment)

                # Delayed/manual mode: after release, place late signups immediately.
                if signup_mode == "delayed_manual" and adventure.release_assignments and adventure.is_waitinglist == 0:
                    already_assigned = db.session.execute(
                        db.select(Assignment)
                        .join(Adventure, Assignment.adventure_id == Adventure.id)
                        .where(
                            Assignment.user_id == user_id,
                            Adventure.date == adventure_date,
                        )
                    ).scalars().first()

                    if not already_assigned:
                        filled = db.session.execute(
                            db.select(func.count(Assignment.user_id))
                            .where(Assignment.adventure_id == adventure_id)
                        ).scalar_one()

                        if filled < adventure.max_players:
                            assignment = Assignment()
                            assignment.user_id = user_id
                            assignment.adventure_id = adventure_id
                            assignment.preference_place = priority
                            db.session.add(assignment)
                            player = db.session.get(User, user_id)
                            if player:
                                notify_live_signup_change(adventure, player, "assigned")
                        else:
                            waiting_list = make_waiting_list_for_event(adventure.event_type_id, adventure.date)
                            existing_waiting = db.session.execute(
                                db.select(Assignment).where(
                                    Assignment.user_id == user_id,
                                    Assignment.adventure_id == waiting_list.id,
                                )
                            ).scalars().first()
                            if not existing_waiting:
                                waiting_assignment = Assignment()
                                waiting_assignment.user_id = user_id
                                waiting_assignment.adventure_id = waiting_list.id
                                waiting_assignment.preference_place = None
                                db.session.add(waiting_assignment)
                                player = db.session.get(User, user_id)
                                if player:
                                    notify_live_signup_change(adventure, player, "waiting")
                message = 'Signup registered'

            db.session.commit()
            return {"message": message}, 200

        except SQLAlchemyError as e:
            db.session.rollback()
            abort(500, message=f"Database error: {str(e)}")

        except Exception as e:
            abort(500, message=str(e))

# --- NOTIFICATIONS ---
@blp_notifications.route("/save-token")
class FCMSaveToken(MethodView):
    @login_required 
    def post(self):
        """Securely link the FCM token to the logged-in user."""
        data = request.get_json()
        fcm_token = data.get("token")

        if not fcm_token:
            abort(400, message="Token is required")

        try:
            # 1. Clean up: One device, one user. 
            # If this token exists elsewhere, reassign it.
            existing = FCMToken.query.filter_by(token=fcm_token).first()
            if existing:
                if existing.user_id != current_user.id:
                    existing.user_id = current_user.id
                    db.session.commit()
            else:
                new_token = FCMToken()
                new_token.user_id = current_user.id
                new_token.token = fcm_token
                db.session.add(new_token)
                db.session.commit()

            # 2. Trigger the success notification using our NEW DATA-ONLY format (if Firebase enabled)
            if current_app.config.get("FIREBASE_ENABLED", False):
                name = getattr(current_user, 'display_name', 'Adventurer')
                message = messaging.Message(
                    data={
                        "title": "Account Linked! 🛡️",
                        "body": f"Hi {name}, your device is now registered.",
                        "click_action": "OPEN_APP"
                    },
                    token=fcm_token,
                )
                messaging.send(message)

            return {"message": "Token linked to your account successfully"}, 200

        except SQLAlchemyError as e:
            db.session.rollback()
            return {"message": "Database error", "error": str(e)}, 500
        except Exception as e:
            # We return 200 even if the welcome msg fails, 
            # because the token WAS successfully saved.
            return {"message": "Token saved, but welcome notification failed", "error": str(e)}, 200

@blp_notifications.route("/broadcast-test")
class FCMBroadcast(MethodView):
    @login_required
    def get(self):
        """Broadcast to all registered devices. Admin only"""
        if not is_admin(current_user):
            abort(403, message="Admin only")
        if not current_app.config.get("FIREBASE_ENABLED", False):
            return {"message": "Firebase is disabled (no service account key)"}, 503

        # 1. Fetch all tokens from the DB
        tokens = [t.token for t in FCMToken.query.all()]
        
        if not tokens:
            return {"message": "No tokens found in DB"}, 404

        # 2. Create a Multicast message (sends to many at once)
        message = messaging.MulticastMessage(
            data={
                "title": "Global Announcement",
                "body": "This is a broadcast test from the Flask server!",
            },
            tokens=tokens,
            webpush=messaging.WebpushConfig(
                headers={"Urgency": "high"}
            ),
        )

        # 3. Send
        response = messaging.send_each_for_multicast(message)
        
        return {
            "success_count": response.success_count,
            "failure_count": response.failure_count,
            "message": "Broadcast attempted"
        }, 200
    
@blp_notifications.route("/debug-push")
class DebugPush(MethodView):
    @login_required
    def get(self):
        """Forces a push notification to the logged-in user."""
        # 1. Find tokens for the real logged-in user
        user_tokens = FCMToken.query.filter_by(user_id=current_user.id).all()
        
        if not current_app.config.get("FIREBASE_ENABLED", False):
            return {"status": "disabled", "message": "Firebase is disabled (no service account key)"}, 503

        if not user_tokens:
            return {
                "status": "error",
                "message": f"No tokens found in DB for user {current_user.name} (ID: {current_user.id})"
            }, 404

        token_list = [t.token for t in user_tokens]
        
        # 2. Try to send
        message = messaging.MulticastMessage(
            notification=messaging.Notification(
                title="System Check 🛡️",
                body=f"Connection confirmed for {current_user.name}!",
            ),
            tokens=token_list,
        )
        
        response = messaging.send_each_for_multicast(message)
        
        return {
            "status": "success",
            "user": current_user.name,
            "tokens_found": len(token_list),
            "success_count": response.success_count,
            "failure_count": response.failure_count
        }, 200
    
@blp_notifications.route("/test-automation/<string:target>")
class TestAutomation(MethodView):
    @login_required
    def post(self, target):
        """
        Manually triggers one of the notification scenarios.
        target can be: 'release', 'event_update', 'signup_confirmation_3d', or 'live_signup'.
        """
        if target == "release":
            # Assignment release notification (to caller)
            send_fcm_notification(
                current_user,
                "Party Assigned!",
                "TEST: You've been assigned to: test adventure",
                category="assignments"
            )
            return {"message": "Sent 'Assignment Release' to your device"}

        elif target == "event_update":
            send_fcm_notification(
                current_user,
                "Session update",
                "TEST: Your upcoming session was updated.",
                category="event_updates",
            )
            return {"message": "Sent 'Event Update' to your device"}

        elif target == "signup_confirmation_3d":
            send_fcm_notification(
                current_user,
                "Upcoming event",
                "TEST: You are signed up for: test adventure",
                category="signup_confirmation_3d",
            )
            return {"message": "Sent '3-day Signup Confirmation' to your device"}

        elif target == "live_signup":
            send_fcm_notification(
                current_user,
                "Live signup update",
                "TEST: A player signed up after release.",
                category="live_signup_updates",
            )
            return {"message": "Sent 'Live Signup Update' to your device"}

        return {"error": "Invalid target"}, 400