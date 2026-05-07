from datetime import date, timedelta

from app.models import Adventure, User
from app.provider import db
from tests.conftest import login


def _future_adventure_date() -> date:
    return date.today() + timedelta(days=7)


def _future_week_bounds() -> tuple[str, str]:
    target_date = _future_adventure_date()
    week_start = target_date - timedelta(days=target_date.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def test_alive_endpoint_reports_status(client):
    response = client.get("/api/alive", base_url="https://localhost")

    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert data["db"] == "reachable"
    assert data["version"] == "test"


def test_users_list_excludes_karma(client, app):
    with app.app_context():
        admin = User.create(google_id="u0", name="Admin", privilege_level=2)
        User.create(google_id="u1", name="User One")
        User.create(google_id="u2", name="User Two")
        admin_id = admin.id

    login(client, admin_id)

    response = client.get("/api/users", base_url="https://localhost")

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 3
    assert "karma" not in data[0]


def test_user_detail_and_patch(client, app):
    with app.app_context():
        user = User.create(google_id="u3", name="User Three")
        user_id = user.id
        db.session.commit()

    login(client, user_id)

    detail_response = client.get(f"/api/users/{user_id}", base_url="https://localhost")
    assert detail_response.status_code == 200
    detail_data = detail_response.get_json()
    assert detail_data["id"] == user_id

    patch_response = client.patch(
        f"/api/users/{user_id}",
        json={"display_name": "Updated Name"},
        base_url="https://localhost",
    )
    assert patch_response.status_code == 200
    patch_data = patch_response.get_json()
    assert patch_data["display_name"] == "Updated Name"


def test_adventure_create_rejects_requested_room_field(client, app):
    with app.app_context():
        user = User.create(google_id="approved-user", name="Approved", privilege_level=1)
        user_id = user.id

    login(client, user_id)

    response = client.post(
        "/api/adventures",
        json={
            "title": "Roomless Session",
            "short_description": "No rooms anymore",
            "max_players": 5,
            "date": _future_adventure_date().isoformat(),
            "requested_room": "A",
        },
        base_url="https://localhost",
    )

    assert response.status_code == 422


def test_adventure_response_excludes_requested_room(client, app):
    future_date = _future_adventure_date()
    week_start, week_end = _future_week_bounds()

    with app.app_context():
        creator = User.create(google_id="creator-user", name="Creator", privilege_level=1)
        db.session.add(
            Adventure(
                title="Visible Session",
                short_description="Should not expose room",
                user_id=creator.id,
                max_players=5,
                date=future_date,
                tags=None,
                is_waitinglist=0,
            )
        )
        db.session.commit()

    response = client.get(
        f"/api/adventures?week_start={week_start}&week_end={week_end}",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert "requested_room" not in data[0]
