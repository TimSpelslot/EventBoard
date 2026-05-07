from datetime import date, time

import pytest
from sqlalchemy.exc import IntegrityError

from app.models import Event, EventDay, EventMembership, EventSession, EventTable, GuestPlayer, User
from app.provider import db


def test_event_domain_hierarchy_can_be_created(app):
    with app.app_context():
        organizer = User.create(google_id="event-organizer", name="Organizer", privilege_level=2)

        event = Event(
            title="Spring Convention",
            description="Two-day event",
            notification_days_before=5,
            allow_event_admin_notifications=True,
            created_by_user_id=organizer.id,
        )
        db.session.add(event)
        db.session.flush()

        event_day = EventDay(event_id=event.id, date=date(2026, 6, 20), label="Day 1", sort_order=1)
        db.session.add(event_day)
        db.session.flush()

        event_table = EventTable(event_day_id=event_day.id, name="Table 1", sort_order=1)
        db.session.add(event_table)
        db.session.flush()

        membership = EventMembership(
            event_id=event.id,
            user_id=organizer.id,
            role=EventMembership.ROLE_EVENT_ADMIN,
            can_send_notifications=True,
        )
        guest = GuestPlayer(display_name="Walk-in Player", created_by_user_id=organizer.id)
        session = EventSession(
            title="Dungeon Crawl",
            short_description="Fast intro session",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            host_user_id=organizer.id,
            created_by_user_id=organizer.id,
            max_players=6,
            start_time=time(10, 0),
            duration_minutes=45,
            placement_mode=EventSession.PLACEMENT_DELAYED,
        )

        db.session.add_all([membership, guest, session])
        db.session.commit()

        stored_event = db.session.get(Event, event.id)
        assert stored_event is not None
        assert len(stored_event.days) == 1
        assert stored_event.days[0].tables[0].name == "Table 1"
        assert stored_event.memberships[0].is_event_admin is True
        assert stored_event.days[0].sessions[0].event_table.name == "Table 1"
        assert stored_event.days[0].sessions[0].end_time == time(10, 45)
        assert guest.creator.id == organizer.id


def test_event_membership_is_unique_per_user_and_event(app):
    with app.app_context():
        organizer = User.create(google_id="membership-organizer", name="Membership Organizer", privilege_level=2)
        helper = User.create(google_id="membership-helper", name="Membership Helper", privilege_level=1)
        event = Event(title="Scoped Roles", created_by_user_id=organizer.id)
        db.session.add(event)
        db.session.flush()

        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()

        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_ADMIN,
            )
        )

        with pytest.raises(IntegrityError):
            db.session.commit()

        db.session.rollback()


def test_event_session_overlap_is_day_scoped(app):
    with app.app_context():
        organizer = User.create(google_id="overlap-organizer", name="Overlap Organizer", privilege_level=2)
        event = Event(title="Overlap Event", created_by_user_id=organizer.id)
        db.session.add(event)
        db.session.flush()

        first_day = EventDay(event_id=event.id, date=date(2026, 7, 4), label="Saturday")
        second_day = EventDay(event_id=event.id, date=date(2026, 7, 5), label="Sunday")
        db.session.add_all([first_day, second_day])
        db.session.flush()

        first_table = EventTable(event_day_id=first_day.id, name="Table A")
        second_table = EventTable(event_day_id=second_day.id, name="Table A")
        db.session.add_all([first_table, second_table])
        db.session.flush()

        morning = EventSession(
            title="Morning",
            short_description="Morning slot",
            event_day_id=first_day.id,
            event_table_id=first_table.id,
            start_time=time(10, 0),
            duration_minutes=60,
        )
        overlap = EventSession(
            title="Overlap",
            short_description="Overlap slot",
            event_day_id=first_day.id,
            event_table_id=first_table.id,
            start_time=time(10, 30),
            duration_minutes=45,
        )
        next_day = EventSession(
            title="Next Day",
            short_description="Same time, different day",
            event_day_id=second_day.id,
            event_table_id=second_table.id,
            start_time=time(10, 30),
            duration_minutes=45,
        )

        assert morning.overlaps_with(overlap) is True
        assert overlap.overlaps_with(morning) is True
        assert morning.overlaps_with(next_day) is False