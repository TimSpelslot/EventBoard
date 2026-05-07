from datetime import date, timedelta

from app.models import Adventure, Assignment, User
from app.provider import db
from tests.conftest import login


def _future_adventure_date() -> date:
    return date.today() + timedelta(days=7)


def _future_week_bounds() -> tuple[str, str]:
    target_date = _future_adventure_date()
    week_start = target_date - timedelta(days=target_date.weekday())
    week_end = week_start + timedelta(days=6)
    return week_start.isoformat(), week_end.isoformat()


def _create_adventure_with_assignment(app, released=False):
    future_date = _future_adventure_date()

    with app.app_context():
        approved = User.create(google_id="approved-user", name="Approved", privilege_level=1)
        other = User.create(google_id="other-user", name="Other", privilege_level=1)

        adventure = Adventure.create(
            title="Permission Session",
            short_description="Permission test",
            user_id=approved.id,
            max_players=5,
            date=future_date,
            tags=None,
            is_waitinglist=0,
            release_assignments=released,
            commit=False,
        )
        assignment = Assignment()
        assignment.user_id = other.id
        assignment.adventure_id = adventure.id
        db.session.add(assignment)
        db.session.commit()

        return adventure.id, approved.id


def test_assignment_users_forbidden_for_privilege_zero(client, app, normal_user_id):
    adventure_id, _ = _create_adventure_with_assignment(app)
    login(client, normal_user_id)

    response = client.get(
        f"/api/player-assignments?adventure_id={adventure_id}",
        base_url="https://localhost",
    )

    assert response.status_code == 401


def test_assignment_users_visible_for_privilege_one(client, app):
    adventure_id, approved_id = _create_adventure_with_assignment(app)
    login(client, approved_id)

    response = client.get(
        f"/api/player-assignments?adventure_id={adventure_id}",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) == 1
    assert data[0]["display_name"] == "Other"


def test_adventure_list_hides_assignments_for_privilege_zero(client, app, normal_user_id):
    week_start, week_end = _future_week_bounds()
    _create_adventure_with_assignment(app)
    login(client, normal_user_id)

    response = client.get(
        f"/api/adventures?week_start={week_start}&week_end={week_end}",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1
    assert "assignments" not in data[0]


def test_adventure_list_shows_only_own_assignment_for_privilege_zero(client, app):
    future_date = _future_adventure_date()
    week_start, week_end = _future_week_bounds()

    with app.app_context():
        noob = User.create(google_id="noob-user", name="Noob", privilege_level=0)
        approved = User.create(google_id="approved-owner", name="Approved Owner", privilege_level=1)
        other = User.create(google_id="other-assigned", name="Other Assigned", privilege_level=1)

        adventure = Adventure.create(
            title="Own Placement Session",
            short_description="Own assignment visibility",
            user_id=approved.id,
            max_players=5,
            date=future_date,
            tags=None,
            is_waitinglist=0,
            release_assignments=True,
            commit=False,
        )
        assignment_noob = Assignment()
        assignment_noob.user_id = noob.id
        assignment_noob.adventure_id = adventure.id
        db.session.add(assignment_noob)

        assignment_other = Assignment()
        assignment_other.user_id = other.id
        assignment_other.adventure_id = adventure.id
        db.session.add(assignment_other)
        db.session.commit()
        noob_id = noob.id

    login(client, noob_id)

    response = client.get(
        f"/api/adventures?week_start={week_start}&week_end={week_end}",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1
    assert "assignments" in data[0]
    assert len(data[0]["assignments"]) == 1
    assert data[0]["assignments"][0]["user"]["id"] == noob_id


def test_adventure_list_shows_assignments_for_privilege_one(client, app):
    week_start, week_end = _future_week_bounds()
    _, approved_id = _create_adventure_with_assignment(app, released=True)
    login(client, approved_id)

    response = client.get(
        f"/api/adventures?week_start={week_start}&week_end={week_end}",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1
    assert "assignments" in data[0]


def test_adventure_list_hides_assignments_for_privilege_one_before_release(client, app):
    week_start, week_end = _future_week_bounds()
    _, approved_id = _create_adventure_with_assignment(app, released=False)
    login(client, approved_id)

    response = client.get(
        f"/api/adventures?week_start={week_start}&week_end={week_end}",
        base_url="https://localhost",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert len(data) >= 1
    assert "assignments" not in data[0]


def test_adventure_create_forbidden_for_privilege_zero(client, normal_user_id):
    login(client, normal_user_id)

    response = client.post(
        "/api/adventures",
        json={
            "title": "Blocked Session",
            "short_description": "Should fail",
            "max_players": 5,
            "date": _future_adventure_date().isoformat(),
        },
        base_url="https://localhost",
    )

    assert response.status_code == 401


def test_adventure_create_allowed_for_privilege_one(client, app):
    with app.app_context():
        approved = User.create(google_id="creator-user", name="Creator", privilege_level=1)
        approved_id = approved.id

    login(client, approved_id)

    response = client.post(
        "/api/adventures",
        json={
            "title": "Allowed Session",
            "short_description": "Should succeed",
            "max_players": 5,
            "date": _future_adventure_date().isoformat(),
        },
        base_url="https://localhost",
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == "Allowed Session"


def test_non_admin_cannot_promote_user_to_admin(client, app, normal_user_id):
    with app.app_context():
        target = User.create(google_id="target-user", name="Target", privilege_level=1)
        target_id = target.id

    login(client, normal_user_id)

    response = client.patch(
        f"/api/users/{target_id}",
        json={"privilege_level": 2},
        base_url="https://localhost",
    )

    assert response.status_code == 401


def test_admin_can_promote_user_to_admin(client, app, admin_user_id):
    with app.app_context():
        target = User.create(google_id="target-admin-user", name="Target Admin", privilege_level=1)
        target_id = target.id

    login(client, admin_user_id)

    response = client.patch(
        f"/api/users/{target_id}",
        json={"privilege_level": 2},
        base_url="https://localhost",
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["privilege_level"] == 2
