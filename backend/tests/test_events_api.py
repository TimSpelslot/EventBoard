from datetime import date, time

import app.api as api_module

from app.models import Event, EventDay, EventMembership, EventSession, EventSessionParticipant, EventTable, User
from app.provider import db
from tests.conftest import login


def test_admin_can_create_event(client, app, admin_user_id):
    login(client, admin_user_id)

    response = client.post(
        "/api/events",
        json={
            "title": "Summer Con",
            "description": "Convention weekend",
            "notification_days_before": 4,
            "allow_event_admin_notifications": True,
        },
        base_url="https://localhost",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == "Summer Con"
    assert data["notification_days_before"] == 4
    assert data["created_by_user_id"] == admin_user_id


def test_non_admin_cannot_create_event(client, normal_user_id):
    login(client, normal_user_id)

    response = client.post(
        "/api/events",
        json={"title": "Blocked Event"},
        base_url="https://localhost",
    )

    assert response.status_code == 401


def test_event_list_is_scoped_to_memberships_for_non_admins(client, app, normal_user_id):
    with app.app_context():
        helper = User.create(google_id="event-list-helper", name="Event List Helper", privilege_level=0)
        first_event = Event(title="Visible Event", created_by_user_id=None)
        hidden_event = Event(title="Hidden Event", created_by_user_id=None)
        db.session.add_all([first_event, hidden_event])
        db.session.flush()
        db.session.add(
            EventMembership(
                event_id=first_event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id

    login(client, helper_id)
    response = client.get('/api/events', base_url='https://localhost')

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['title'] == 'Visible Event'

    login(client, normal_user_id)
    response = client.get('/api/events', base_url='https://localhost')
    assert response.status_code == 200
    assert response.get_json() == []


def test_event_list_returns_all_events_for_super_admin(client, app, admin_user_id):
    with app.app_context():
        db.session.add_all([
            Event(title='Admin Visible One', created_by_user_id=admin_user_id),
            Event(title='Admin Visible Two', created_by_user_id=admin_user_id),
        ])
        db.session.commit()

    login(client, admin_user_id)
    response = client.get('/api/events', base_url='https://localhost')

    assert response.status_code == 200
    titles = {row['title'] for row in response.get_json()}
    assert 'Admin Visible One' in titles
    assert 'Admin Visible Two' in titles


def test_helper_can_search_eligible_users_for_session(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id='search-helper', name='Search Helper', privilege_level=0)
        target = User.create(google_id='search-target', name='Alice Wonder', privilege_level=0)
        other = User.create(google_id='search-other', name='Bob Builder', privilege_level=0)

        event = Event(title='Search Event', created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 13), label='Day 1')
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name='Table Search')
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title='Search Session',
            short_description='Search users',
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(10, 0),
            duration_minutes=45,
            max_players=4,
        )
        db.session.add(event_session)
        db.session.flush()
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.add(
            EventSessionParticipant(
                event_session_id=event_session.id,
                user_id=other.id,
                status=EventSessionParticipant.STATUS_WAITLIST,
                added_by_user_id=admin_user_id,
            )
        )
        db.session.commit()
        helper_id = helper.id
        target_id = target.id
        event_session_id = event_session.id

    login(client, helper_id)
    response = client.get(
        f'/api/event-sessions/{event_session_id}/eligible-users?q=alice',
        base_url='https://localhost',
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]['id'] == target_id
    assert data[0]['display_name'] == 'Alice Wonder'


def test_eligible_user_search_rejects_outsider(client, app, admin_user_id, normal_user_id):
    with app.app_context():
        event = Event(title='Protected Search Event', created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 14), label='Day 1')
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name='Table Guard')
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title='Protected Search Session',
            short_description='Protected users',
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(11, 0),
            duration_minutes=45,
            max_players=4,
        )
        db.session.add(event_session)
        db.session.commit()
        event_session_id = event_session.id

    login(client, normal_user_id)
    response = client.get(
        f'/api/event-sessions/{event_session_id}/eligible-users?q=test',
        base_url='https://localhost',
    )

    assert response.status_code == 401


def test_admin_can_add_membership_and_event_admin_can_add_table(client, app, admin_user_id):
    with app.app_context():
        event_admin = User.create(google_id="scoped-event-admin", name="Scoped Event Admin", privilege_level=0)
        event = Event(title="Role Setup", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 8, 1), label="Saturday")
        db.session.add(event_day)
        db.session.commit()
        event_id = event.id
        event_day_id = event_day.id
        event_admin_id = event_admin.id

    login(client, admin_user_id)
    response = client.post(
        f"/api/events/{event_id}/memberships",
        json={
            "user_id": event_admin_id,
            "role": EventMembership.ROLE_EVENT_ADMIN,
            "can_send_notifications": True,
        },
        base_url="https://localhost",
    )
    assert response.status_code == 201

    login(client, event_admin_id)
    response = client.post(
        f"/api/event-days/{event_day_id}/tables",
        json={"name": "Table Alpha", "sort_order": 1},
        base_url="https://localhost",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["name"] == "Table Alpha"
    assert data["event_day_id"] == event_day_id


def test_admin_can_patch_and_delete_event_day(client, app, admin_user_id):
    with app.app_context():
        event = Event(title="Day Lifecycle", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 8, 2), label="Old Day", sort_order=1)
        db.session.add(event_day)
        db.session.commit()
        event_day_id = event_day.id

    login(client, admin_user_id)
    patch_response = client.patch(
        f"/api/event-days/{event_day_id}",
        json={"label": "New Day", "sort_order": 2},
        base_url="https://localhost",
    )
    assert patch_response.status_code == 200
    assert patch_response.get_json()["label"] == "New Day"

    delete_response = client.delete(
        f"/api/event-days/{event_day_id}",
        base_url="https://localhost",
    )
    assert delete_response.status_code == 200

    with app.app_context():
        assert db.session.get(EventDay, event_day_id) is None


def test_non_admin_cannot_patch_or_delete_event_day(client, app, normal_user_id, admin_user_id):
    with app.app_context():
        event = Event(title="Protected Day Lifecycle", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 8, 3), label="Locked Day")
        db.session.add(event_day)
        db.session.commit()
        event_day_id = event_day.id

    login(client, normal_user_id)
    patch_response = client.patch(
        f"/api/event-days/{event_day_id}",
        json={"label": "Nope"},
        base_url="https://localhost",
    )
    assert patch_response.status_code == 401

    delete_response = client.delete(
        f"/api/event-days/{event_day_id}",
        base_url="https://localhost",
    )
    assert delete_response.status_code == 401


def test_event_admin_can_patch_and_delete_table(client, app, admin_user_id):
    with app.app_context():
        event_admin = User.create(google_id="table-event-admin", name="Table Event Admin", privilege_level=0)
        event = Event(title="Table Lifecycle", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 8, 4), label="Table Day")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table Old", sort_order=1)
        db.session.add(event_table)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=event_admin.id,
                role=EventMembership.ROLE_EVENT_ADMIN,
            )
        )
        db.session.commit()
        event_admin_id = event_admin.id
        event_table_id = event_table.id

    login(client, event_admin_id)
    patch_response = client.patch(
        f"/api/event-tables/{event_table_id}",
        json={"name": "Table New", "sort_order": 3},
        base_url="https://localhost",
    )
    assert patch_response.status_code == 200
    assert patch_response.get_json()["name"] == "Table New"

    delete_response = client.delete(
        f"/api/event-tables/{event_table_id}",
        base_url="https://localhost",
    )
    assert delete_response.status_code == 200

    with app.app_context():
        assert db.session.get(EventTable, event_table_id) is None


def test_table_delete_cascades_sessions(client, app, admin_user_id):
    with app.app_context():
        event_admin = User.create(google_id="cascade-table-admin", name="Cascade Table Admin", privilege_level=0)
        event = Event(title="Table Cascade", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 8, 5), label="Cascade Day")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Cascade Table")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Cascade Session",
            short_description="Will be removed",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(10, 0),
            duration_minutes=45,
        )
        db.session.add(event_session)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=event_admin.id,
                role=EventMembership.ROLE_EVENT_ADMIN,
            )
        )
        db.session.commit()
        event_admin_id = event_admin.id
        event_table_id = event_table.id
        event_session_id = event_session.id

    login(client, event_admin_id)
    delete_response = client.delete(
        f"/api/event-tables/{event_table_id}",
        base_url="https://localhost",
    )
    assert delete_response.status_code == 200

    with app.app_context():
        assert db.session.get(EventTable, event_table_id) is None
        assert db.session.get(EventSession, event_session_id) is None


def test_helper_cannot_patch_or_delete_table(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="table-helper", name="Table Helper", privilege_level=0)
        event = Event(title="Table Guard", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 8, 6), label="Guard Day")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Guard Table")
        db.session.add(event_table)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        event_table_id = event_table.id

    login(client, helper_id)
    patch_response = client.patch(
        f"/api/event-tables/{event_table_id}",
        json={"name": "Blocked"},
        base_url="https://localhost",
    )
    assert patch_response.status_code == 401

    delete_response = client.delete(
        f"/api/event-tables/{event_table_id}",
        base_url="https://localhost",
    )
    assert delete_response.status_code == 401


def test_helper_can_create_session_in_their_event(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="scoped-helper", name="Scoped Helper", privilege_level=0)
        event = Event(title="Session Setup", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 9, 12), label="Saturday")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table One")
        db.session.add(event_table)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        event_day_id = event_day.id
        event_table_id = event_table.id

    login(client, helper_id)
    response = client.post(
        f"/api/event-days/{event_day_id}/sessions",
        json={
            "title": "Walk-up One Shot",
            "short_description": "Quick event session",
            "event_table_id": event_table_id,
            "start_time": time(14, 0).isoformat(),
            "duration_minutes": 45,
            "max_players": 5,
            "placement_mode": "delayed",
        },
        base_url="https://localhost",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == "Walk-up One Shot"
    assert data["host_user_id"] == helper_id
    assert data["created_by_user_id"] == helper_id


def test_event_admin_cannot_patch_event_metadata(client, app, admin_user_id):
    with app.app_context():
        event_admin = User.create(google_id="metadata-event-admin", name="Metadata Event Admin", privilege_level=0)
        event = Event(title="Locked Metadata", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=event_admin.id,
                role=EventMembership.ROLE_EVENT_ADMIN,
            )
        )
        db.session.commit()
        event_id = event.id
        event_admin_id = event_admin.id

    login(client, event_admin_id)
    response = client.patch(
        f"/api/events/{event_id}",
        json={"title": "Changed Title"},
        base_url="https://localhost",
    )

    assert response.status_code == 401


def test_session_creation_rejects_overlapping_times_on_same_table(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="overlap-helper", name="Overlap Helper", privilege_level=0)
        event = Event(title="Overlap API Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 10, 10), label="Saturday")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Shared Table")
        db.session.add(event_table)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        event_day_id = event_day.id
        event_table_id = event_table.id

    login(client, helper_id)
    first_response = client.post(
        f"/api/event-days/{event_day_id}/sessions",
        json={
            "title": "First Slot",
            "short_description": "Opening session",
            "event_table_id": event_table_id,
            "start_time": time(10, 0).isoformat(),
            "duration_minutes": 60,
        },
        base_url="https://localhost",
    )
    assert first_response.status_code == 201

    overlap_response = client.post(
        f"/api/event-days/{event_day_id}/sessions",
        json={
            "title": "Overlapping Slot",
            "short_description": "Should be rejected",
            "event_table_id": event_table_id,
            "start_time": time(10, 30).isoformat(),
            "duration_minutes": 45,
        },
        base_url="https://localhost",
    )

    assert overlap_response.status_code == 409


def test_helper_can_patch_session_in_their_event(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="patch-helper", name="Patch Helper", privilege_level=0)
        event = Event(title="Patch Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 11, 14), label="Saturday")
        db.session.add(event_day)
        db.session.flush()
        table = EventTable(event_day_id=event_day.id, name="Table A")
        db.session.add(table)
        db.session.flush()
        session = EventSession(
            title="Original Title",
            short_description="Original Description",
            event_day_id=event_day.id,
            event_table_id=table.id,
            host_user_id=admin_user_id,
            created_by_user_id=admin_user_id,
            start_time=time(13, 0),
            duration_minutes=60,
        )
        db.session.add(session)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        session_id = session.id

    login(client, helper_id)
    response = client.patch(
        f"/api/event-sessions/{session_id}",
        json={
            "title": "Updated Title",
            "short_description": "Updated Description",
        },
        base_url="https://localhost",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["title"] == "Updated Title"
    assert data["short_description"] == "Updated Description"


def test_helper_cannot_reassign_host_to_other_user(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="host-helper", name="Host Helper", privilege_level=0)
        other_user = User.create(google_id="other-host", name="Other Host", privilege_level=0)
        event = Event(title="Host Rules", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 11, 15), label="Sunday")
        db.session.add(event_day)
        db.session.flush()
        table = EventTable(event_day_id=event_day.id, name="Table B")
        db.session.add(table)
        db.session.flush()
        session = EventSession(
            title="Host Locked",
            short_description="Host change test",
            event_day_id=event_day.id,
            event_table_id=table.id,
            host_user_id=helper.id,
            created_by_user_id=admin_user_id,
            start_time=time(9, 0),
            duration_minutes=45,
        )
        db.session.add(session)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        other_user_id = other_user.id
        session_id = session.id

    login(client, helper_id)
    response = client.patch(
        f"/api/event-sessions/{session_id}",
        json={"host_user_id": other_user_id},
        base_url="https://localhost",
    )

    assert response.status_code == 401


def test_session_patch_rejects_overlapping_time(client, app, admin_user_id):
    with app.app_context():
        event_admin = User.create(google_id="overlap-event-admin", name="Overlap Event Admin", privilege_level=0)
        event = Event(title="Patch Overlap", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 11, 16), label="Monday")
        db.session.add(event_day)
        db.session.flush()
        table = EventTable(event_day_id=event_day.id, name="Table C")
        db.session.add(table)
        db.session.flush()
        first_session = EventSession(
            title="First",
            short_description="First",
            event_day_id=event_day.id,
            event_table_id=table.id,
            start_time=time(10, 0),
            duration_minutes=60,
        )
        second_session = EventSession(
            title="Second",
            short_description="Second",
            event_day_id=event_day.id,
            event_table_id=table.id,
            start_time=time(12, 0),
            duration_minutes=60,
        )
        db.session.add_all([first_session, second_session])
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=event_admin.id,
                role=EventMembership.ROLE_EVENT_ADMIN,
            )
        )
        db.session.commit()
        event_admin_id = event_admin.id
        second_session_id = second_session.id

    login(client, event_admin_id)
    response = client.patch(
        f"/api/event-sessions/{second_session_id}",
        json={
            "start_time": time(10, 30).isoformat(),
            "duration_minutes": 45,
        },
        base_url="https://localhost",
    )

    assert response.status_code == 409


def test_outsider_cannot_delete_event_session(client, app, admin_user_id, normal_user_id):
    with app.app_context():
        event = Event(title="Delete Guard", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 11, 17), label="Tuesday")
        db.session.add(event_day)
        db.session.flush()
        table = EventTable(event_day_id=event_day.id, name="Table D")
        db.session.add(table)
        db.session.flush()
        session = EventSession(
            title="Protected",
            short_description="Protected session",
            event_day_id=event_day.id,
            event_table_id=table.id,
            start_time=time(16, 0),
            duration_minutes=30,
        )
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    login(client, normal_user_id)
    response = client.delete(
        f"/api/event-sessions/{session_id}",
        base_url="https://localhost",
    )

    assert response.status_code == 401


def test_event_admin_can_delete_event_session(client, app, admin_user_id):
    with app.app_context():
        event_admin = User.create(google_id="delete-event-admin", name="Delete Event Admin", privilege_level=0)
        event = Event(title="Delete Allowed", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 11, 18), label="Wednesday")
        db.session.add(event_day)
        db.session.flush()
        table = EventTable(event_day_id=event_day.id, name="Table E")
        db.session.add(table)
        db.session.flush()
        session = EventSession(
            title="Deletable",
            short_description="Delete me",
            event_day_id=event_day.id,
            event_table_id=table.id,
            start_time=time(18, 0),
            duration_minutes=30,
        )
        db.session.add(session)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=event_admin.id,
                role=EventMembership.ROLE_EVENT_ADMIN,
            )
        )
        db.session.commit()
        event_admin_id = event_admin.id
        session_id = session.id

    login(client, event_admin_id)
    response = client.delete(
        f"/api/event-sessions/{session_id}",
        base_url="https://localhost",
    )

    assert response.status_code == 200


def test_helper_can_add_manual_guest_participant(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="manual-helper", name="Manual Helper", privilege_level=0)
        event = Event(title="Manual Guest Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 1), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table X")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Guest Session",
            short_description="Manual guest add",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(11, 0),
            duration_minutes=45,
            max_players=3,
            placement_mode=EventSession.PLACEMENT_IMMEDIATE,
        )
        db.session.add(event_session)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        event_session_id = event_session.id

    login(client, helper_id)
    response = client.post(
        f"/api/event-sessions/{event_session_id}/participants/manual",
        json={"display_name": "Walk In Player"},
        base_url="https://localhost",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == EventSessionParticipant.STATUS_PLACED
    assert data["guest_player"]["display_name"] == "Walk In Player"


def test_manual_guest_becomes_waitlist_when_session_is_full(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="full-helper", name="Full Helper", privilege_level=0)
        event = Event(title="Full Session Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 2), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table Y")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Full Session",
            short_description="Already full",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(12, 0),
            duration_minutes=60,
            max_players=1,
        )
        db.session.add(event_session)
        db.session.flush()
        placed_user = User.create(google_id="already-placed", name="Already Placed", privilege_level=0)
        db.session.add(
            EventSessionParticipant(
                event_session_id=event_session.id,
                user_id=placed_user.id,
                status=EventSessionParticipant.STATUS_PLACED,
                added_by_user_id=admin_user_id,
            )
        )
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        event_session_id = event_session.id

    login(client, helper_id)
    response = client.post(
        f"/api/event-sessions/{event_session_id}/participants/manual",
        json={"display_name": "Late Walk-in", "status": "placed"},
        base_url="https://localhost",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == EventSessionParticipant.STATUS_WAITLIST


def test_manual_user_add_blocks_when_overlapping_placed_session_exists(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="conflict-helper", name="Conflict Helper", privilege_level=0)
        player = User.create(google_id="conflict-player", name="Conflict Player", privilege_level=0)
        event = Event(title="Conflict Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 3), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table Z")
        second_table = EventTable(event_day_id=event_day.id, name="Table ZZ")
        db.session.add_all([event_table, second_table])
        db.session.flush()

        first_session = EventSession(
            title="First Placement",
            short_description="First",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(14, 0),
            duration_minutes=60,
            max_players=3,
        )
        second_session = EventSession(
            title="Second Placement",
            short_description="Second",
            event_day_id=event_day.id,
            event_table_id=second_table.id,
            start_time=time(14, 30),
            duration_minutes=45,
            max_players=3,
            placement_mode=EventSession.PLACEMENT_IMMEDIATE,
        )
        db.session.add_all([first_session, second_session])
        db.session.flush()

        db.session.add(
            EventSessionParticipant(
                event_session_id=first_session.id,
                user_id=player.id,
                status=EventSessionParticipant.STATUS_PLACED,
                added_by_user_id=admin_user_id,
            )
        )
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        player_id = player.id
        second_session_id = second_session.id

    login(client, helper_id)
    response = client.post(
        f"/api/event-sessions/{second_session_id}/participants/users",
        json={"user_id": player_id, "status": "placed"},
        base_url="https://localhost",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["status"] == EventSessionParticipant.STATUS_BLOCKED_CONFLICT


def test_outsider_cannot_add_manual_participants(client, app, admin_user_id, normal_user_id):
    with app.app_context():
        event = Event(title="Unauthorized Manual Add", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 4), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table U")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Protected Manual Add",
            short_description="Protected",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(15, 0),
            duration_minutes=45,
            max_players=2,
        )
        db.session.add(event_session)
        db.session.commit()
        event_session_id = event_session.id

    login(client, normal_user_id)
    response = client.post(
        f"/api/event-sessions/{event_session_id}/participants/manual",
        json={"display_name": "Should Not Work"},
        base_url="https://localhost",
    )

    assert response.status_code == 401


def test_delete_placed_participant_auto_promotes_waitlist(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="promote-helper", name="Promote Helper", privilege_level=0)
        first_player = User.create(google_id="first-player", name="First Player", privilege_level=0)
        waitlist_player = User.create(google_id="waitlist-player", name="Waitlist Player", privilege_level=0)

        event = Event(title="Auto Promote Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 5), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table P")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Auto Promote Session",
            short_description="Promotion behavior",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(10, 0),
            duration_minutes=60,
            max_players=1,
        )
        db.session.add(event_session)
        db.session.flush()
        placed = EventSessionParticipant(
            event_session_id=event_session.id,
            user_id=first_player.id,
            status=EventSessionParticipant.STATUS_PLACED,
            added_by_user_id=admin_user_id,
        )
        waitlisted = EventSessionParticipant(
            event_session_id=event_session.id,
            user_id=waitlist_player.id,
            status=EventSessionParticipant.STATUS_WAITLIST,
            added_by_user_id=admin_user_id,
        )
        db.session.add_all([placed, waitlisted])
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        placed_id = placed.id
        waitlisted_id = waitlisted.id

    login(client, helper_id)
    response = client.delete(
        f"/api/event-sessions/participants/{placed_id}",
        base_url="https://localhost",
    )
    assert response.status_code == 200

    with app.app_context():
        promoted = db.session.get(EventSessionParticipant, waitlisted_id)
        assert promoted is not None
        assert promoted.status == EventSessionParticipant.STATUS_PLACED
        removed = db.session.get(EventSessionParticipant, placed_id)
        assert removed is None


def test_promote_next_skips_conflict_and_promotes_next_eligible(client, app, admin_user_id):
    with app.app_context():
        helper = User.create(google_id="next-helper", name="Next Helper", privilege_level=0)
        conflicted_user = User.create(google_id="conflicted-user", name="Conflicted User", privilege_level=0)
        eligible_user = User.create(google_id="eligible-user", name="Eligible User", privilege_level=0)

        event = Event(title="Promote Next Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 6), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table Q")
        event_table_2 = EventTable(event_day_id=event_day.id, name="Table R")
        db.session.add_all([event_table, event_table_2])
        db.session.flush()

        blocking_session = EventSession(
            title="Blocking",
            short_description="Blocks overlap",
            event_day_id=event_day.id,
            event_table_id=event_table_2.id,
            start_time=time(9, 0),
            duration_minutes=60,
            max_players=4,
        )
        target_session = EventSession(
            title="Target",
            short_description="Waitlist target",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(9, 30),
            duration_minutes=45,
            max_players=1,
        )
        db.session.add_all([blocking_session, target_session])
        db.session.flush()

        db.session.add(
            EventSessionParticipant(
                event_session_id=blocking_session.id,
                user_id=conflicted_user.id,
                status=EventSessionParticipant.STATUS_PLACED,
                added_by_user_id=admin_user_id,
            )
        )
        first_waitlist = EventSessionParticipant(
            event_session_id=target_session.id,
            user_id=conflicted_user.id,
            status=EventSessionParticipant.STATUS_WAITLIST,
            added_by_user_id=admin_user_id,
        )
        second_waitlist = EventSessionParticipant(
            event_session_id=target_session.id,
            user_id=eligible_user.id,
            status=EventSessionParticipant.STATUS_WAITLIST,
            added_by_user_id=admin_user_id,
        )
        db.session.add_all([first_waitlist, second_waitlist])
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        target_session_id = target_session.id
        first_waitlist_id = first_waitlist.id
        second_waitlist_id = second_waitlist.id

    login(client, helper_id)
    response = client.post(
        f"/api/event-sessions/{target_session_id}/participants/promote-next",
        base_url="https://localhost",
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["id"] == second_waitlist_id
    assert data["status"] == EventSessionParticipant.STATUS_PLACED

    with app.app_context():
        blocked = db.session.get(EventSessionParticipant, first_waitlist_id)
        assert blocked is not None
        assert blocked.status == EventSessionParticipant.STATUS_BLOCKED_CONFLICT


def test_outsider_cannot_mutate_participants(client, app, admin_user_id, normal_user_id):
    with app.app_context():
        event = Event(title="Participant Guard Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 7), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table S")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Participant Guard Session",
            short_description="Protected participant mutation",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(16, 0),
            duration_minutes=45,
            max_players=2,
        )
        db.session.add(event_session)
        db.session.flush()
        participant = EventSessionParticipant(
            event_session_id=event_session.id,
            status=EventSessionParticipant.STATUS_WAITLIST,
            added_by_user_id=admin_user_id,
        )
        db.session.add(participant)
        db.session.commit()
        event_session_id = event_session.id
        participant_id = participant.id

    login(client, normal_user_id)

    patch_response = client.patch(
        f"/api/event-sessions/participants/{participant_id}",
        json={"status": "placed"},
        base_url="https://localhost",
    )
    assert patch_response.status_code == 401

    delete_response = client.delete(
        f"/api/event-sessions/participants/{participant_id}",
        base_url="https://localhost",
    )
    assert delete_response.status_code == 401

    promote_response = client.post(
        f"/api/event-sessions/{event_session_id}/participants/promote-next",
        base_url="https://localhost",
    )
    assert promote_response.status_code == 401


def test_manual_user_add_sends_status_notification(client, app, admin_user_id, monkeypatch):
    sent_messages = []

    def fake_send(user, title, body, category=None, link="OPEN_APP"):
        sent_messages.append({"user_id": user.id, "title": title, "body": body, "category": category})

    monkeypatch.setattr(api_module, "send_fcm_notification", fake_send)

    with app.app_context():
        helper = User.create(google_id="notify-helper", name="Notify Helper", privilege_level=0)
        player = User.create(google_id="notify-player", name="Notify Player", privilege_level=0)
        event = Event(title="Notify Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 8), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table N")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Notify Session",
            short_description="Notification test",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(10, 0),
            duration_minutes=45,
            max_players=2,
        )
        db.session.add(event_session)
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        player_id = player.id
        session_id = event_session.id

    login(client, helper_id)
    response = client.post(
        f"/api/event-sessions/{session_id}/participants/users",
        json={"user_id": player_id, "status": "placed"},
        base_url="https://localhost",
    )
    assert response.status_code == 201
    assert len(sent_messages) == 1
    assert sent_messages[0]["user_id"] == player_id
    assert sent_messages[0]["category"] == "assignments"


def test_delete_participant_sends_removed_and_promoted_notifications(client, app, admin_user_id, monkeypatch):
    sent_messages = []

    def fake_send(user, title, body, category=None, link="OPEN_APP"):
        sent_messages.append({"user_id": user.id, "title": title, "body": body, "category": category})

    monkeypatch.setattr(api_module, "send_fcm_notification", fake_send)

    with app.app_context():
        helper = User.create(google_id="notify-delete-helper", name="Notify Delete Helper", privilege_level=0)
        placed_user = User.create(google_id="notify-placed-user", name="Notify Placed", privilege_level=0)
        waitlist_user = User.create(google_id="notify-wait-user", name="Notify Wait", privilege_level=0)

        event = Event(title="Delete Notify Event", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 9), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table D")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Delete Notify Session",
            short_description="Delete notification test",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(12, 0),
            duration_minutes=45,
            max_players=1,
        )
        db.session.add(event_session)
        db.session.flush()

        placed = EventSessionParticipant(
            event_session_id=event_session.id,
            user_id=placed_user.id,
            status=EventSessionParticipant.STATUS_PLACED,
            added_by_user_id=admin_user_id,
        )
        waitlisted = EventSessionParticipant(
            event_session_id=event_session.id,
            user_id=waitlist_user.id,
            status=EventSessionParticipant.STATUS_WAITLIST,
            added_by_user_id=admin_user_id,
        )
        db.session.add_all([placed, waitlisted])
        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
            )
        )
        db.session.commit()
        helper_id = helper.id
        placed_id = placed.id
        placed_user_id = placed_user.id
        waitlist_user_id = waitlist_user.id

    login(client, helper_id)
    response = client.delete(
        f"/api/event-sessions/participants/{placed_id}",
        base_url="https://localhost",
    )
    assert response.status_code == 200

    notified_ids = [m["user_id"] for m in sent_messages]
    assert placed_user_id in notified_ids
    assert waitlist_user_id in notified_ids


def test_super_admin_can_notify_session_participants(client, app, admin_user_id, monkeypatch):
    sent_messages = []

    def fake_send(user, title, body, category=None, link="OPEN_APP"):
        sent_messages.append({"user_id": user.id, "title": title, "body": body, "category": category})

    monkeypatch.setattr(api_module, "send_fcm_notification", fake_send)

    with app.app_context():
        player = User.create(google_id="notify-session-player", name="Notify Session Player", privilege_level=0)
        event = Event(title="Session Notify", created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 10), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table Notify")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Session Notify",
            short_description="Notify endpoint",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(13, 0),
            duration_minutes=45,
            max_players=3,
        )
        db.session.add(event_session)
        db.session.flush()
        db.session.add(
            EventSessionParticipant(
                event_session_id=event_session.id,
                user_id=player.id,
                status=EventSessionParticipant.STATUS_PLACED,
                added_by_user_id=admin_user_id,
            )
        )
        db.session.commit()
        event_session_id = event_session.id
        player_id = player.id

    login(client, admin_user_id)
    response = client.post(
        f"/api/event-sessions/{event_session_id}/notify",
        json={"title": "Heads up", "body": "Session starts soon"},
        base_url="https://localhost",
    )

    assert response.status_code == 200
    assert len(sent_messages) == 1
    assert sent_messages[0]["user_id"] == player_id


def test_event_admin_notify_requires_event_toggle_and_permission_flag(client, app, admin_user_id, monkeypatch):
    sent_messages = []

    def fake_send(user, title, body, category=None, link="OPEN_APP"):
        sent_messages.append({"user_id": user.id, "title": title, "body": body, "category": category})

    monkeypatch.setattr(api_module, "send_fcm_notification", fake_send)

    with app.app_context():
        event_admin = User.create(google_id="notify-event-admin", name="Notify Event Admin", privilege_level=0)
        player = User.create(google_id="notify-event-player", name="Notify Event Player", privilege_level=0)

        event = Event(
            title="Event Admin Notify",
            created_by_user_id=admin_user_id,
            allow_event_admin_notifications=True,
        )
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 11), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table EN")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Event Admin Session",
            short_description="Event admin notification",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(14, 0),
            duration_minutes=45,
            max_players=3,
        )
        db.session.add(event_session)
        db.session.flush()

        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=event_admin.id,
                role=EventMembership.ROLE_EVENT_ADMIN,
                can_send_notifications=True,
            )
        )
        db.session.add(
            EventSessionParticipant(
                event_session_id=event_session.id,
                user_id=player.id,
                status=EventSessionParticipant.STATUS_PLACED,
                added_by_user_id=admin_user_id,
            )
        )
        db.session.commit()
        event_admin_id = event_admin.id
        event_session_id = event_session.id

    login(client, event_admin_id)
    response = client.post(
        f"/api/event-sessions/{event_session_id}/notify",
        json={"title": "Reminder", "body": "See you soon"},
        base_url="https://localhost",
    )
    assert response.status_code == 200
    assert len(sent_messages) == 1


def test_helper_cannot_notify_session_participants(client, app, admin_user_id, monkeypatch):
    sent_messages = []

    def fake_send(user, title, body, category=None, link="OPEN_APP"):
        sent_messages.append({"user_id": user.id, "title": title, "body": body, "category": category})

    monkeypatch.setattr(api_module, "send_fcm_notification", fake_send)

    with app.app_context():
        helper = User.create(google_id="notify-helper-denied", name="Notify Helper Denied", privilege_level=0)
        player = User.create(google_id="notify-denied-player", name="Notify Denied Player", privilege_level=0)
        event = Event(
            title="Helper Notify Denied",
            created_by_user_id=admin_user_id,
            allow_event_admin_notifications=True,
        )
        db.session.add(event)
        db.session.flush()
        event_day = EventDay(event_id=event.id, date=date(2026, 12, 12), label="Day 1")
        db.session.add(event_day)
        db.session.flush()
        event_table = EventTable(event_day_id=event_day.id, name="Table HD")
        db.session.add(event_table)
        db.session.flush()
        event_session = EventSession(
            title="Helper Denied Session",
            short_description="Helper should not notify",
            event_day_id=event_day.id,
            event_table_id=event_table.id,
            start_time=time(15, 0),
            duration_minutes=45,
            max_players=3,
        )
        db.session.add(event_session)
        db.session.flush()

        db.session.add(
            EventMembership(
                event_id=event.id,
                user_id=helper.id,
                role=EventMembership.ROLE_EVENT_HELPER,
                can_send_notifications=True,
            )
        )
        db.session.add(
            EventSessionParticipant(
                event_session_id=event_session.id,
                user_id=player.id,
                status=EventSessionParticipant.STATUS_PLACED,
                added_by_user_id=admin_user_id,
            )
        )
        db.session.commit()
        helper_id = helper.id
        event_session_id = event_session.id

    login(client, helper_id)
    response = client.post(
        f"/api/event-sessions/{event_session_id}/notify",
        json={"title": "Should Fail", "body": "Unauthorized"},
        base_url="https://localhost",
    )

    assert response.status_code == 401
    assert sent_messages == []


# ---------------------------------------------------------------------------
# Delayed-placement tests
# ---------------------------------------------------------------------------

def _make_delayed_session(app, admin_user_id, date_val, start, *, label_suffix=''):
    """Helper: create event/day/table/session with placement_mode=delayed. Returns (session_id, event_id)."""
    from app.models import Event, EventDay, EventTable, EventSession
    from app.provider import db
    event = Event(title=f'Delayed Event {label_suffix}', created_by_user_id=admin_user_id)
    db.session.add(event)
    db.session.flush()
    day = EventDay(event_id=event.id, date=date_val, label='Day 1')
    db.session.add(day)
    db.session.flush()
    table = EventTable(event_day_id=day.id, name=f'Table {label_suffix}')
    db.session.add(table)
    db.session.flush()
    session = EventSession(
        title=f'Delayed Session {label_suffix}',
        short_description='Delayed mode',
        event_day_id=day.id,
        event_table_id=table.id,
        start_time=start,
        duration_minutes=60,
        max_players=2,
        placement_mode=EventSession.PLACEMENT_DELAYED,
    )
    db.session.add(session)
    db.session.flush()
    return session.id, event.id


def test_delayed_session_adds_participants_as_waitlist(client, app, admin_user_id):
    from datetime import time as T
    with app.app_context():
        session_id, _ = _make_delayed_session(app, admin_user_id, date(2027, 1, 10), T(10, 0), label_suffix='A')
        player = User.create(google_id='delayed-add-player', name='Delayed Add Player', privilege_level=0)
        db.session.commit()
        player_id = player.id

    login(client, admin_user_id)
    response = client.post(
        f'/api/event-sessions/{session_id}/participants/users',
        json={'user_id': player_id, 'status': 'placed'},
        base_url='https://localhost',
    )
    assert response.status_code == 201
    data = response.get_json()
    # Delayed mode overrides requested status to waitlist
    assert data['status'] == EventSessionParticipant.STATUS_WAITLIST


def test_process_placements_places_by_priority_order(client, app, admin_user_id, monkeypatch):
    monkeypatch.setattr('app.api.send_fcm_notification', lambda *a, **kw: None)
    from datetime import time as T
    with app.app_context():
        session_id, _ = _make_delayed_session(app, admin_user_id, date(2027, 1, 11), T(10, 0), label_suffix='B')
        p1 = User.create(google_id='dp-p1', name='DP Player 1', privilege_level=0)
        p2 = User.create(google_id='dp-p2', name='DP Player 2', privilege_level=0)
        p3 = User.create(google_id='dp-p3', name='DP Player 3', privilege_level=0)
        db.session.flush()
        # Add in reverse priority order
        from app.models import EventSessionParticipant
        db.session.add_all([
            EventSessionParticipant(event_session_id=session_id, user_id=p3.id, status='waitlist', priority=3, added_by_user_id=admin_user_id),
            EventSessionParticipant(event_session_id=session_id, user_id=p1.id, status='waitlist', priority=1, added_by_user_id=admin_user_id),
            EventSessionParticipant(event_session_id=session_id, user_id=p2.id, status='waitlist', priority=2, added_by_user_id=admin_user_id),
        ])
        db.session.commit()
        p1_id, p2_id, p3_id = p1.id, p2.id, p3.id

    login(client, admin_user_id)
    response = client.post(
        f'/api/event-sessions/{session_id}/process-placements',
        base_url='https://localhost',
    )
    assert response.status_code == 200
    data = response.get_json()
    assert '2 placed' in data['message']

    with app.app_context():
        participants = {
            p.user_id: p.status
            for p in db.session.execute(
                db.select(EventSessionParticipant).where(EventSessionParticipant.event_session_id == session_id)
            ).scalars().all()
        }
    # max_players=2, so p1 (priority 1) and p2 (priority 2) placed; p3 stays waitlist
    assert participants[p1_id] == EventSessionParticipant.STATUS_PLACED
    assert participants[p2_id] == EventSessionParticipant.STATUS_PLACED
    assert participants[p3_id] == EventSessionParticipant.STATUS_WAITLIST


def test_process_placements_marks_conflicts(client, app, admin_user_id, monkeypatch):
    monkeypatch.setattr('app.api.send_fcm_notification', lambda *a, **kw: None)
    from datetime import time as T
    with app.app_context():
        event = Event(title='Conflict Delayed Event', created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        day = EventDay(event_id=event.id, date=date(2027, 1, 12), label='Day 1')
        db.session.add(day)
        db.session.flush()
        t1 = EventTable(event_day_id=day.id, name='Table C1')
        t2 = EventTable(event_day_id=day.id, name='Table C2')
        db.session.add_all([t1, t2])
        db.session.flush()

        # other_session at 10:00-11:00 where player is already placed
        other_session = EventSession(
            title='Other Session', short_description='Already placed here',
            event_day_id=day.id, event_table_id=t1.id,
            start_time=T(10, 0), duration_minutes=60,
            max_players=3, placement_mode='immediate',
        )
        # target_session at 10:30-11:30 (overlaps) - delayed
        target_session = EventSession(
            title='Target Session', short_description='Delayed mode',
            event_day_id=day.id, event_table_id=t2.id,
            start_time=T(10, 30), duration_minutes=60,
            max_players=3, placement_mode='delayed',
        )
        db.session.add_all([other_session, target_session])
        db.session.flush()

        conflict_player = User.create(google_id='conflict-dp', name='Conflict DP', privilege_level=0)
        clear_player = User.create(google_id='clear-dp', name='Clear DP', privilege_level=0)
        db.session.add_all([
            EventSessionParticipant(event_session_id=other_session.id, user_id=conflict_player.id, status='placed', added_by_user_id=admin_user_id),
            EventSessionParticipant(event_session_id=target_session.id, user_id=conflict_player.id, status='waitlist', priority=1, added_by_user_id=admin_user_id),
            EventSessionParticipant(event_session_id=target_session.id, user_id=clear_player.id, status='waitlist', priority=2, added_by_user_id=admin_user_id),
        ])
        db.session.commit()
        target_id = target_session.id
        conflict_id = conflict_player.id
        clear_id = clear_player.id

    login(client, admin_user_id)
    response = client.post(
        f'/api/event-sessions/{target_id}/process-placements',
        base_url='https://localhost',
    )
    assert response.status_code == 200

    with app.app_context():
        statuses = {
            p.user_id: p.status
            for p in db.session.execute(
                db.select(EventSessionParticipant).where(EventSessionParticipant.event_session_id == target_id)
            ).scalars().all()
        }
    assert statuses[conflict_id] == EventSessionParticipant.STATUS_BLOCKED_CONFLICT
    assert statuses[clear_id] == EventSessionParticipant.STATUS_PLACED


def test_process_placements_rejects_immediate_session(client, app, admin_user_id):
    from datetime import time as T
    with app.app_context():
        event = Event(title='Immediate PP Event', created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        day = EventDay(event_id=event.id, date=date(2027, 1, 13), label='Day 1')
        db.session.add(day)
        db.session.flush()
        table = EventTable(event_day_id=day.id, name='Table PP')
        db.session.add(table)
        db.session.flush()
        session = EventSession(
            title='Immediate Session', short_description='Not delayed',
            event_day_id=day.id, event_table_id=table.id,
            start_time=T(11, 0), duration_minutes=45,
            placement_mode=EventSession.PLACEMENT_IMMEDIATE,
        )
        db.session.add(session)
        db.session.commit()
        session_id = session.id

    login(client, admin_user_id)
    response = client.post(
        f'/api/event-sessions/{session_id}/process-placements',
        base_url='https://localhost',
    )
    assert response.status_code == 409


def test_process_placements_rejects_outsider(client, app, admin_user_id, normal_user_id):
    from datetime import time as T
    with app.app_context():
        session_id, _ = _make_delayed_session(app, admin_user_id, date(2027, 1, 14), T(12, 0), label_suffix='G')
        db.session.commit()

    login(client, normal_user_id)
    response = client.post(
        f'/api/event-sessions/{session_id}/process-placements',
        base_url='https://localhost',
    )
    assert response.status_code == 401


def test_public_events_endpoint_includes_my_signup_status(client, app, admin_user_id):
    with app.app_context():
        player = User.create(google_id='public-player', name='Public Player', privilege_level=0)
        event = Event(title='Public Event', created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        day = EventDay(event_id=event.id, date=date(2027, 2, 1), label='Day 1')
        db.session.add(day)
        db.session.flush()
        table = EventTable(event_day_id=day.id, name='Table P')
        db.session.add(table)
        db.session.flush()
        session = EventSession(
            title='Public Session',
            short_description='Public browse',
            event_day_id=day.id,
            event_table_id=table.id,
            start_time=time(10, 0),
            duration_minutes=60,
            max_players=4,
            placement_mode=EventSession.PLACEMENT_IMMEDIATE,
        )
        db.session.add(session)
        db.session.flush()
        db.session.add(
            EventSessionParticipant(
                event_session_id=session.id,
                user_id=player.id,
                status=EventSessionParticipant.STATUS_PLACED,
                added_by_user_id=admin_user_id,
            )
        )
        db.session.commit()
        player_id = player.id
        session_id = session.id

    login(client, player_id)
    response = client.get('/api/events/public', base_url='https://localhost')
    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1
    all_sessions = [s for e in data for d in e['days'] for s in d['sessions']]
    target = [s for s in all_sessions if s['id'] == session_id][0]
    assert target['my_status'] == EventSessionParticipant.STATUS_PLACED


def test_player_can_self_signup_and_cancel(client, app, admin_user_id, monkeypatch):
    monkeypatch.setattr('app.api.send_fcm_notification', lambda *a, **kw: None)
    with app.app_context():
        player = User.create(google_id='self-signup-player', name='Self Signup Player', privilege_level=0)
        event = Event(title='Self Signup Event', created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        day = EventDay(event_id=event.id, date=date(2027, 2, 2), label='Day 1')
        db.session.add(day)
        db.session.flush()
        table = EventTable(event_day_id=day.id, name='Table S')
        db.session.add(table)
        db.session.flush()
        session = EventSession(
            title='Self Signup Session',
            short_description='Self signup',
            event_day_id=day.id,
            event_table_id=table.id,
            start_time=time(11, 0),
            duration_minutes=45,
            max_players=2,
            placement_mode=EventSession.PLACEMENT_IMMEDIATE,
        )
        db.session.add(session)
        db.session.commit()
        player_id = player.id
        session_id = session.id

    login(client, player_id)
    signup_response = client.post(f'/api/event-sessions/{session_id}/signup', base_url='https://localhost')
    assert signup_response.status_code == 200
    assert signup_response.get_json()['status'] == EventSessionParticipant.STATUS_PLACED

    cancel_response = client.delete(f'/api/event-sessions/{session_id}/signup', base_url='https://localhost')
    assert cancel_response.status_code == 200


def test_player_self_signup_delayed_goes_waitlist(client, app, admin_user_id, monkeypatch):
    monkeypatch.setattr('app.api.send_fcm_notification', lambda *a, **kw: None)
    with app.app_context():
        player = User.create(google_id='self-signup-delayed', name='Self Signup Delayed', privilege_level=0)
        event = Event(title='Self Signup Delayed Event', created_by_user_id=admin_user_id)
        db.session.add(event)
        db.session.flush()
        day = EventDay(event_id=event.id, date=date(2027, 2, 3), label='Day 1')
        db.session.add(day)
        db.session.flush()
        table = EventTable(event_day_id=day.id, name='Table SD')
        db.session.add(table)
        db.session.flush()
        session = EventSession(
            title='Self Signup Delayed Session',
            short_description='Delayed',
            event_day_id=day.id,
            event_table_id=table.id,
            start_time=time(12, 0),
            duration_minutes=45,
            max_players=2,
            placement_mode=EventSession.PLACEMENT_DELAYED,
        )
        db.session.add(session)
        db.session.commit()
        player_id = player.id
        session_id = session.id

    login(client, player_id)
    signup_response = client.post(f'/api/event-sessions/{session_id}/signup', base_url='https://localhost')
    assert signup_response.status_code == 200
    assert signup_response.get_json()['status'] == EventSessionParticipant.STATUS_WAITLIST