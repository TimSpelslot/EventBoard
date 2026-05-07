from app.models import Event, EventMembership, User
from app.provider import db
from app.util import can_manage_event, can_manage_event_sessions, can_send_event_notifications, is_event_admin


def test_event_authorization_helpers_respect_scoped_roles(app):
    with app.app_context():
        super_admin = User.create(google_id="super-admin", name="Super Admin", privilege_level=2)
        event_admin = User.create(google_id="event-admin", name="Event Admin", privilege_level=0)
        helper = User.create(google_id="event-helper", name="Event Helper", privilege_level=0)
        outsider = User.create(google_id="outsider", name="Outsider", privilege_level=0)

        event = Event(
            title="Scoped Permissions",
            allow_event_admin_notifications=True,
            created_by_user_id=super_admin.id,
        )
        db.session.add(event)
        db.session.flush()

        db.session.add_all([
            EventMembership(
                event_id=event.id,
                user_id=event_admin.id,
                role=EventMembership.ROLE_EVENT_ADMIN,
                can_send_notifications=True,
            ),
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
                can_send_notifications=False,
            ),
        ])
        db.session.commit()

        assert is_event_admin(super_admin, event) is True
        assert can_manage_event(super_admin, event) is True
        assert can_manage_event_sessions(super_admin, event) is True
        assert can_send_event_notifications(super_admin, event) is True

        assert is_event_admin(event_admin, event) is True
        assert can_manage_event(event_admin, event) is True
        assert can_manage_event_sessions(event_admin, event) is True
        assert can_send_event_notifications(event_admin, event) is True

        assert is_event_admin(helper, event) is False
        assert can_manage_event(helper, event) is False
        assert can_manage_event_sessions(helper, event) is True
        assert can_send_event_notifications(helper, event) is False

        assert is_event_admin(outsider, event) is False
        assert can_manage_event(outsider, event) is False
        assert can_manage_event_sessions(outsider, event) is False
        assert can_send_event_notifications(outsider, event) is False


def test_event_notification_permission_requires_event_toggle(app):
    with app.app_context():
        super_admin = User.create(google_id="toggle-admin", name="Toggle Admin", privilege_level=2)
        event_admin = User.create(google_id="toggle-event-admin", name="Toggle Event Admin", privilege_level=0)

        event = Event(
            title="Notification Toggle",
            allow_event_admin_notifications=False,
            created_by_user_id=super_admin.id,
        )
        db.session.add(event)
        db.session.flush()
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=event_admin.id,
                role=EventMembership.ROLE_EVENT_ADMIN,
                can_send_notifications=True,
            )
        )
        db.session.commit()

        assert can_send_event_notifications(event_admin, event) is False