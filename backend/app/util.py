from datetime import datetime, timedelta, date
from flask import current_app
from collections import defaultdict
from sqlalchemy.orm import joinedload
from sqlalchemy import func, inspect, text
import calendar

from .models import *
from firebase_admin import messaging


def ensure_event_type_schema_compat():
    """Best-effort compatibility patch for legacy DBs missing key event-type columns."""
    try:
        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        conn = db.session.connection()

        if "adventures" in table_names:
            adventure_cols = {c["name"] for c in inspector.get_columns("adventures")}
            if "event_type_id" not in adventure_cols:
                current_app.logger.warning(
                    "Schema compat: missing adventures.event_type_id, applying ALTER TABLE."
                )
                conn.execute(text("ALTER TABLE adventures ADD COLUMN event_type_id INTEGER NULL"))
            if "release_assignments" not in adventure_cols:
                current_app.logger.warning(
                    "Schema compat: missing adventures.release_assignments, applying ALTER TABLE."
                )
                conn.execute(
                    text(
                        "ALTER TABLE adventures ADD COLUMN release_assignments BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if "release_reminder_days" not in adventure_cols:
                current_app.logger.warning(
                    "Schema compat: missing adventures.release_reminder_days, applying ALTER TABLE."
                )
                conn.execute(
                    text(
                        "ALTER TABLE adventures ADD COLUMN release_reminder_days INTEGER NOT NULL DEFAULT 2"
                    )
                )

        if "event_types" in table_names:
            event_type_cols = {c["name"] for c in inspector.get_columns("event_types")}
            if "is_single_event" not in event_type_cols:
                current_app.logger.warning(
                    "Schema compat: missing event_types.is_single_event, applying ALTER TABLE."
                )
                conn.execute(
                    text(
                        "ALTER TABLE event_types ADD COLUMN is_single_event BOOLEAN NOT NULL DEFAULT 0"
                    )
                )
            if "default_release_reminder_days" not in event_type_cols:
                current_app.logger.warning(
                    "Schema compat: missing event_types.default_release_reminder_days, applying ALTER TABLE."
                )
                conn.execute(
                    text(
                        "ALTER TABLE event_types ADD COLUMN default_release_reminder_days INTEGER NOT NULL DEFAULT 2"
                    )
                )

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        current_app.logger.warning(
            "Schema compat patch failed for event-type columns: %s", exc
        )

def is_admin(user):
    return user.is_authenticated and user.privilege_level >= 2

def get_next_wednesday(today=None):
    today = today or date.today()
    days_ahead = (2 - today.weekday() + 7) % 7  # 2 is Wednesday
    return today if days_ahead == 0 else today + timedelta(days=days_ahead)


def get_nth_weekday_of_month(year: int, month: int, weekday: int, week_of_month: int):
    """Return date for nth weekday in a month, or None if it does not exist."""
    first_day = date(year, month, 1)
    offset = (weekday - first_day.weekday() + 7) % 7
    day_num = 1 + offset + (week_of_month - 1) * 7
    last_day = calendar.monthrange(year, month)[1]
    if day_num > last_day:
        return None
    return date(year, month, day_num)


def get_next_date_for_event_type(event_type, today=None):
    """Compute the next date for an event type with a monthly nth-weekday rule."""
    today = today or date.today()

    year = today.year
    month = today.month

    for _ in range(36):
        if not (event_type.exclude_july_august and month in (7, 8)):
            candidate = get_nth_weekday_of_month(
                year,
                month,
                int(event_type.weekday),
                int(event_type.week_of_month),
            )
            if candidate and candidate >= today:
                return candidate

        month += 1
        if month > 12:
            month = 1
            year += 1

    return today


def ensure_default_event_types():
    """Create default event types once if none are configured yet."""
    if db.session.scalar(db.select(func.count(EventType.id))) > 0:
        return

    jeugd = EventType()
    jeugd.title = "Dungeons & Dragons Jeugd 12-18"
    jeugd.description = "Elke eerste zondag van de maand, behalve juli en augustus."
    jeugd.weekday = 6
    jeugd.week_of_month = 1
    jeugd.exclude_july_august = True
    jeugd.sort_order = 1

    junior = EventType()
    junior.title = "Dungeons & Dragons Junior 8-12"
    junior.description = "Elke tweede woensdag van de maand, behalve juli en augustus."
    junior.weekday = 2
    junior.week_of_month = 2
    junior.exclude_july_august = True
    junior.sort_order = 2

    defaults = [jeugd, junior]

    db.session.add_all(defaults)
    db.session.commit()

def get_this_week(today=None):
    """
    Returns the start (Monday) and end (Sunday) of the this week.
    """
    today = today or date.today()
    # Find Monday of the current week
    start_of_current_week = today - timedelta(days=today.weekday())
    end_of_current_week = start_of_current_week + timedelta(days=6)

    return start_of_current_week, end_of_current_week

def get_upcoming_week(today=None):
    """
    Returns the start (Monday) and end (Sunday) of the upcoming week.
    - If today is Monday–Wednesday → return this week's Mon–Sun.
    - If today is Thursday–Sunday → return next week's Mon–Sun.
    """
    today = today or date.today()
    start_of_current_week, end_of_current_week = get_this_week(today)

    if today.weekday() <= 2:  # Mon(0), Tue(1), Wed(2)
        return start_of_current_week, end_of_current_week
    else:  # Thu–Sun
        start_of_next_week = start_of_current_week + timedelta(weeks=1)
        end_of_next_week = end_of_current_week + timedelta(weeks=1)
        return start_of_next_week, end_of_next_week
    
def get_this_month(today=None):
    """
    Returns the start (first day) and end (last day) of the current month.
    """
    today = today or date.today()
    # First day of this month
    start_of_month = today.replace(day=1)

    # Last day of this month
    last_day = calendar.monthrange(today.year, today.month)[1]
    end_of_month = today.replace(day=last_day)

    return start_of_month, end_of_month
    
WAITING_LIST_NAME = "Waiting List"


def make_waiting_list_for_event(event_type_id: int | None, target_date: date) -> Adventure:
    """Ensure a waiting-list Adventure exists for a specific event type and date."""
    existing_waiting_list = db.session.execute(
        db.select(Adventure).where(
            Adventure.is_waitinglist == 1,
            Adventure.date == target_date,
            Adventure.event_type_id == event_type_id,
        )
    ).scalars().first()

    if existing_waiting_list:
        return existing_waiting_list

    waiting_list = Adventure.create(
        title=WAITING_LIST_NAME,
        max_players=128,
        short_description='',
        date=target_date,
        is_waitinglist=1,
        event_type_id=event_type_id,
    )
    db.session.add(waiting_list)
    db.session.flush()
    return waiting_list


def make_waiting_list(today=None) -> Adventure:
    """Backward-compatible helper for the next Wednesday default waiting list."""
    today = today or date.today()
    next_wed = get_next_wednesday(today)
    return make_waiting_list_for_event(None, next_wed)
    

def try_to_signup_user_for_adventure(taken_places, players_signedup_not_assigned, adventure, user, assignment_map, preference_place=None):
    """
    Attempts to sign up a user for an adventure.

    Modifies:
      - taken_places (dict): increments the count for this adventure.
      - players_signedup_not_assigned (list): removes the user if successfully assigned.
      - assignment_map (dict): traces assignment in a human readable map. Provide None to disable this logging.
    """
    # Check if there is still room
    if taken_places.get(adventure.id, 0) < adventure.max_players:
        # Create an assignment (assuming this persists automatically)
        assignment = Assignment(user=user, adventure=adventure, preference_place=preference_place)  # type: ignore
        db.session.add(assignment)
        if assignment_map is not None: # For human readability
            assignment_map.setdefault(adventure.title, []).append(user.display_name)
        db.session.flush()

        # Increment the number of taken places
        taken_places[adventure.id] = taken_places.get(adventure.id, 0) + 1
        
        # Remove the player from the not-assigned list (if present)
        if user in players_signedup_not_assigned:
            players_signedup_not_assigned.remove(user)
        
        return True  # Success
    return False  # No slot available


def assign_players_to_adventures(today=None):
    """
    Creates assignments for players that signed up this week. Working in 3 rounds:
    1. Signup players by signup priority.
    2. Signup all remaining players to any available adventure.
    3. Signup the rest of the players to the waiting list.
    """
    today = today or date.today()
    start_of_week, end_of_week = get_upcoming_week(today)
    current_app.logger.info(f" >--- Assigning players from waiting list for week {start_of_week} to {end_of_week} ---< ")
    # create a placeholder that will track how many places are already taken per adventure
    taken_places = defaultdict(int)
    assignment_map = defaultdict(list) # trace assignments in moa for human readability.


    # Query old assignments per adventure in the date window to check for taken places
    already_taken = (
        db.session.execute(
            db.select(
                Assignment.adventure_id,
                func.count(Assignment.user_id)
            )
            .join(Assignment.adventure)
            .filter(
                Adventure.date >= start_of_week,
                Adventure.date <= end_of_week,
            )
            .group_by(Assignment.adventure_id)
        ).all()
    )
    for adventure_id, count in already_taken:
        taken_places[adventure_id] = count

    # Subquery: get all assigned user ids this week
    assigned_ids_subq = (
        db.select(User.id)
        .join(User.assignments)
        .join(Assignment.adventure)
        .filter(Adventure.date >= start_of_week, Adventure.date <= end_of_week)
    )

    # Main query: players signed up this week but NOT in assigned_ids_subq
    players_signedup_not_assigned = list(
        db.session.execute(
            db.select(User)
            .join(User.signups)
            .join(Signup.adventure)
            .filter(
                Adventure.date >= start_of_week,
                Adventure.date <= end_of_week,
                ~User.id.in_(assigned_ids_subq)   # exclude already assigned player
            )
            .options(
                db.contains_eager(User.signups).contains_eager(Signup.adventure)
            )
            .order_by(func.random())
        )
        .unique()   # ensures deduplication when eager-loading collections
        .scalars()
        .all()
    )
    current_app.logger.info(f"Players signed up for the week {start_of_week} to {end_of_week}:   #{len(players_signedup_not_assigned)}: {[dict({user: user.signups}) for user in players_signedup_not_assigned]} ")
    MAX_PRIORITY = 3
    
    # -- First round of assigning players --
    # Assign all players by priority.
    round_ = []
    for prio in range(1, MAX_PRIORITY + 1):
        for user in list(players_signedup_not_assigned):
            for signup in [s for s in user.signups if s.priority == prio]:
                adventure = signup.adventure
                if try_to_signup_user_for_adventure(taken_places, players_signedup_not_assigned, adventure, user, assignment_map, preference_place=prio): 
                    round_.append(user.display_name)
                    break
    current_app.logger.info(f"- Players assigned in round 1: #{len(round_)}: {round_} => {dict(taken_places)}")

    adventures_this_week = (
        db.session.execute(
            db.select(Adventure)
            .filter(Adventure.date >= start_of_week, Adventure.date <= end_of_week)
            .order_by(func.random())
            .distinct()
        )
        .scalars()
        .all()
    )

    # -- Second round of assigning players --
    # Assign all players to the first available adventure independent of any signups.
    round_ = []
    for user in list(players_signedup_not_assigned):
        for adventure in adventures_this_week:
            # Check if player still fits into the adventure
            if taken_places[adventure.id] < adventure.max_players:
                # Assigned outside top 3 preferences
                if try_to_signup_user_for_adventure(taken_places, players_signedup_not_assigned, adventure, user, assignment_map, preference_place=4): 
                    round_.append(user.display_name)
                    break
    current_app.logger.info(f"- Players assigned in round 2: #{len(round_)}: {round_} => {dict(taken_places)}")


    # -- Third round of assigning players --
    # Assign all players not assigned yet to the waiting list of their event type/date.
    round_ = []
    for user in list(players_signedup_not_assigned):
        preferred_signup = sorted(user.signups, key=lambda s: s.priority)[0] if user.signups else None
        event_type_id = preferred_signup.adventure.event_type_id if preferred_signup else None
        waiting_date = preferred_signup.adventure.date if preferred_signup else end_of_week
        waiting_list = make_waiting_list_for_event(event_type_id, waiting_date)

        if try_to_signup_user_for_adventure(
            taken_places,
            players_signedup_not_assigned,
            waiting_list,
            user,
            assignment_map,
            preference_place=None,
        ):
            round_.append(user.display_name)
        else:
            current_app.logger.error(
                f"Failed to assign player {user.display_name} to waiting list for event_type={event_type_id}, date={waiting_date}!"
            )
    current_app.logger.info(f"- Players assigned in round 3: #{len(round_)}: {round_} => {dict(taken_places)}")

    current_app.logger.info(f"Assigned players to adventures: {dict(assignment_map)}")
    db.session.commit()


def release_assignments(today=None):
    """Release assignments and notify users of their final status."""
    today = today or date.today()
    start_of_week, end_of_week = get_upcoming_week(today)

    adventures = db.session.execute(
        db.select(Adventure).where(
            Adventure.date >= start_of_week,
            Adventure.date <= end_of_week,
        )
    ).scalars().all()

    if not adventures:
        current_app.logger.info("No adventures found for release window.")
        return

    for adventure in adventures:
        adventure.release_assignments = True

    db.session.commit()

    assignments = db.session.execute(
        db.select(Assignment)
        .join(Assignment.adventure)
        .join(Assignment.user)
        .where(
            Adventure.date >= start_of_week,
            Adventure.date <= end_of_week,
            Adventure.release_assignments.is_(True),
        )
        .options(
            db.contains_eager(Assignment.adventure),
            db.contains_eager(Assignment.user),
        )
    ).scalars().all()

    assigned_messages = defaultdict(list)
    waiting_messages = defaultdict(list)

    for assignment in assignments:
        user = assignment.user
        adventure = assignment.adventure
        if not user or not adventure:
            continue
        if adventure.is_waitinglist == 1:
            waiting_messages[user.id].append(f"{adventure.date.isoformat()}")
        else:
            assigned_messages[user.id].append(adventure.title)

    for user_id, titles in assigned_messages.items():
        user = db.session.get(User, user_id)
        if not user:
            continue
        send_fcm_notification(
            user,
            "Assignments Released",
            f"You are assigned to: {', '.join(sorted(set(titles)))}",
            category="assignments",
        )

    for user_id, dates in waiting_messages.items():
        user = db.session.get(User, user_id)
        if not user:
            continue
        send_fcm_notification(
            user,
            "Waiting List Status",
            "You are currently on a waiting list. We will notify you if a spot opens up.",
            category="assignments",
        )

    creator_messages = defaultdict(list)
    for adventure in adventures:
        if adventure.is_waitinglist == 1 or not adventure.user_id:
            continue
        creator_messages[adventure.user_id].append(adventure.title)

    for creator_id, titles in creator_messages.items():
        creator = db.session.get(User, creator_id)
        if not creator:
            continue
        send_fcm_notification(
            creator,
            "Assignments Released",
            f"Assignments were released for: {', '.join(sorted(set(titles)))}",
            category="assignments",
        )


def reset_release(today=None):
    today = today or date.today()
    start_of_week, end_of_week = get_upcoming_week(today)
    stmt = (
        db.update(Adventure)
        .where(
            Adventure.date >= start_of_week,
            Adventure.date <= end_of_week,
        )
        .values(release_assignments=False)
    )
    db.session.execute(stmt)
    db.session.commit()


def notify_admins_new_adventure(adventure: Adventure, creator: User):
    """Send a create-event notification to admins who opted into admin reminders."""
    admins = db.session.execute(
        db.select(User).where(
            User.privilege_level >= 2,
            User.notify_create_adventure_reminder.is_(True),
        )
    ).scalars().all()

    for admin in admins:
        send_fcm_notification(
            admin,
            "New event created",
            f"{creator.display_name} created: {adventure.title}",
            category="create_adventure_reminder",
        )


def notify_live_signup_change(adventure: Adventure, player: User, outcome: str):
    """Notify admins and creator about immediate post-release placement changes."""
    body = (
        f"{player.display_name} was assigned to {adventure.title}."
        if outcome == "assigned"
        else f"{player.display_name} was placed on the waiting list for {adventure.title}."
    )

    admins = db.session.execute(
        db.select(User).where(
            User.privilege_level >= 2,
            User.notify_create_adventure_reminder.is_(True),
        )
    ).scalars().all()
    for admin in admins:
        send_fcm_notification(
            admin,
            "Live signup update",
            body,
            category="create_adventure_reminder",
        )

    creator = db.session.get(User, adventure.user_id) if adventure.user_id else None
    if creator:
        send_fcm_notification(
            creator,
            "Live signup update",
            body,
            category="assignments",
        )

def reassign_players_from_waiting_list(today=None, auto_commit=True):
    """
    Reassign players from the waiting list to newly opened slots in adventures this week.
    """
    today = today or date.today()
    start_of_week, end_of_week = get_upcoming_week(today)
    current_app.logger.info(f" <--- Reassigning players from waiting list for week {start_of_week} to {end_of_week} ---> ")

    # Get waiting list adventures in the target week.
    waiting_lists = db.session.execute(
        db.select(Adventure).where(
            Adventure.is_waitinglist == 1,
            Adventure.date >= start_of_week,
            Adventure.date <= end_of_week,
        )
    ).scalars().all()

    if not waiting_lists:
        current_app.logger.info("No waiting list adventure found. Skipping reassignment.")
        return

    # Track reassigned users for logging
    reassigned_users = []

    for waiting_list in waiting_lists:
        waiting_list_assignments = db.session.execute(
            db.select(Assignment)
            .join(Assignment.user)
            .where(Assignment.adventure_id == waiting_list.id)
            .options(db.contains_eager(Assignment.user))
            .order_by(Assignment.creation_date.asc())
        ).scalars().all()

        for assignment in waiting_list_assignments:
            user = assignment.user
            assigned = False

            # Find adventures in the same event/date bucket that the user signed up for and have available slots
            available_adventures = db.session.execute(
                db.select(Adventure)
                .outerjoin(Assignment, Assignment.adventure_id == Adventure.id)
                .join(Signup, (Signup.adventure_id == Adventure.id) & (Signup.user_id == user.id))
                .where(
                    Adventure.date == waiting_list.date,
                    Adventure.event_type_id == waiting_list.event_type_id,
                    Adventure.is_waitinglist == 0,
                )
                .group_by(Adventure.id)
                .having(func.count(Assignment.user_id) < Adventure.max_players)
                .order_by(
                    Signup.priority.asc(),
                    func.random(),
                )
            ).scalars().all()

            for adventure in available_adventures:
                prio = db.session.execute(
                    db.select(Signup.priority)
                    .where(Signup.user_id == user.id, Signup.adventure_id == adventure.id)
                ).scalar()
                if prio is None:
                    prio = 4
                new_assignment = Assignment(user=user, adventure=adventure, preference_place=prio)  # type: ignore
                db.session.add(new_assignment)
                db.session.delete(assignment)
                reassigned_users.append((user, adventure.title))
                assigned = True
                break

            if assigned:
                continue

            # If no signed-up adventures are available, assign to any open adventure in same event/date.
            fallback_adventures = db.session.execute(
                db.select(Adventure)
                .outerjoin(Assignment, Assignment.adventure_id == Adventure.id)
                .where(
                    Adventure.date == waiting_list.date,
                    Adventure.event_type_id == waiting_list.event_type_id,
                    Adventure.is_waitinglist == 0,
                )
                .group_by(Adventure.id)
                .having(func.count(Assignment.user_id) < Adventure.max_players)
                .order_by(func.random())
            ).scalars().all()

            for adventure in fallback_adventures:
                new_assignment = Assignment(user=user, adventure=adventure, preference_place=4)  # type: ignore
                db.session.add(new_assignment)
                db.session.delete(assignment)
                reassigned_users.append((user, adventure.title))
                break

    if reassigned_users:
        current_app.logger.info(
            f"Reassigned users from waiting list: {[(u.display_name, title) for u, title in reassigned_users]}"
        )

    if auto_commit and reassigned_users:
        db.session.commit()
        for user, adventure_title in reassigned_users:
            send_fcm_notification(
                user,
                "Reassigned from Waiting List",
                f"You have been moved from the waiting list to {adventure_title}!",
                category="assignments",
            )

    return reassigned_users


def has_no_empty_params(rule):
    defaults = rule.defaults if rule.defaults is not None else ()
    arguments = rule.arguments if rule.arguments is not None else ()
    return len(defaults) >= len(arguments)

def get_google():
    return current_app.extensions["google_oauth"].client, current_app.extensions["google_oauth"].provider_cfg

def send_fcm_notification(user, title, body, category=None, link="OPEN_APP"):
    """Sends a push notification to all devices registered by a specific user."""
    if not current_app.config.get("FIREBASE_ENABLED", False):
        return

    if category:
        setting_name = f"notify_{category}"
        if hasattr(user, setting_name) and not getattr(user, setting_name):
            return  # User has disabled notifications for this category
    # Fetch tokens for this user
    tokens = [t.token for t in FCMToken.query.filter_by(user_id=user.id).all()]
    
    if not tokens:
        current_app.logger.info(f"User {user.display_name} has no registered devices")
        return  # User has no registered devices

    message = messaging.MulticastMessage(
        data = {
            "title": title,
            "body": body,
            "click_action": link  # This can be used on the client to trigger specific behavior
        },
        tokens=tokens,
        webpush=messaging.WebpushConfig(
            headers={
                "Urgency": "high"  # Ensure high priority for web push
            },
        )
    )
    try:
        messaging.send_each_for_multicast(message)
    except Exception as e:
        current_app.logger.error(f"FCM Error: {e}")