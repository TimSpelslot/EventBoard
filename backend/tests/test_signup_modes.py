from datetime import date

from app.models import Adventure, Assignment, EventType, User
from app.provider import db
from tests.conftest import login


def create_immediate_event_type() -> EventType:
    event_type = EventType()
    event_type.title = 'Immediate Event'
    event_type.description = 'Immediate signup mode'
    event_type.weekday = 2
    event_type.week_of_month = 3
    event_type.exclude_july_august = False
    event_type.signup_mode = 'immediate_automatic'
    event_type.is_active = True
    event_type.sort_order = 5
    db.session.add(event_type)
    db.session.flush()
    return event_type


def create_adventure(title: str, creator_id: int, event_type_id: int, max_players: int = 1) -> Adventure:
    adventure = Adventure()
    adventure.title = title
    adventure.short_description = title
    adventure.user_id = creator_id
    adventure.event_type_id = event_type_id
    adventure.max_players = max_players
    adventure.date = date(2026, 3, 20)
    adventure.is_waitinglist = 0
    adventure.release_assignments = True
    db.session.add(adventure)
    db.session.flush()
    return adventure


def test_immediate_mode_uses_single_shared_waiting_list_and_clears_it_on_assignment(client, app):
    with app.app_context():
        creator = User.create(google_id='creator', name='Creator', privilege_level=1)
        filler = User.create(google_id='filler', name='Filler')
        waitlisted = User.create(google_id='waitlisted', name='Waitlisted')

        event_type = create_immediate_event_type()
        full_adventure = create_adventure('Full Adventure', creator.id, event_type.id, max_players=1)
        open_adventure = create_adventure('Open Adventure', creator.id, event_type.id, max_players=2)
        db.session.commit()

        filler_id = filler.id
        waitlisted_id = waitlisted.id
        full_adventure_id = full_adventure.id
        open_adventure_id = open_adventure.id
        event_type_id = event_type.id

    login(client, filler_id)
    response = client.post(
        '/api/signups',
        json={'adventure_id': full_adventure_id, 'priority': 1},
        base_url='https://localhost',
    )
    assert response.status_code == 200

    login(client, waitlisted_id)
    response = client.post(
        '/api/signups',
        json={'adventure_id': full_adventure_id, 'priority': 1},
        base_url='https://localhost',
    )
    assert response.status_code == 200

    with app.app_context():
        waiting_lists = db.session.execute(
            db.select(Adventure).where(
                Adventure.event_type_id == event_type_id,
                Adventure.date == date(2026, 3, 20),
                Adventure.is_waitinglist == 1,
            )
        ).scalars().all()

        assert len(waiting_lists) == 1
        waiting_list = waiting_lists[0]

        waiting_assignment = db.session.execute(
            db.select(Assignment).where(
                Assignment.user_id == waitlisted_id,
                Assignment.adventure_id == waiting_list.id,
            )
        ).scalars().first()
        assert waiting_assignment is not None

    response = client.post(
        '/api/signups',
        json={'adventure_id': open_adventure_id, 'priority': 2},
        base_url='https://localhost',
    )
    assert response.status_code == 200

    with app.app_context():
        assigned_open = db.session.execute(
            db.select(Assignment).where(
                Assignment.user_id == waitlisted_id,
                Assignment.adventure_id == open_adventure_id,
            )
        ).scalars().first()
        assert assigned_open is not None

        waiting_list = db.session.execute(
            db.select(Adventure).where(
                Adventure.event_type_id == event_type_id,
                Adventure.date == date(2026, 3, 20),
                Adventure.is_waitinglist == 1,
            )
        ).scalars().one()

        stale_waiting_assignment = db.session.execute(
            db.select(Assignment).where(
                Assignment.user_id == waitlisted_id,
                Assignment.adventure_id == waiting_list.id,
            )
        ).scalars().first()
        assert stale_waiting_assignment is None


def test_immediate_mode_does_not_waitlist_player_already_assigned_elsewhere(client, app):
    with app.app_context():
        creator = User.create(google_id='creator-2', name='Creator 2', privilege_level=1)
        player = User.create(google_id='assigned-player', name='Assigned Player')
        filler = User.create(google_id='other-filler', name='Other Filler')

        event_type = create_immediate_event_type()
        first_adventure = create_adventure('Assigned Adventure', creator.id, event_type.id, max_players=2)
        full_adventure = create_adventure('Already Full Adventure', creator.id, event_type.id, max_players=1)
        db.session.commit()

        player_id = player.id
        filler_id = filler.id
        first_adventure_id = first_adventure.id
        full_adventure_id = full_adventure.id
        event_type_id = event_type.id

    login(client, filler_id)
    response = client.post(
        '/api/signups',
        json={'adventure_id': full_adventure_id, 'priority': 1},
        base_url='https://localhost',
    )
    assert response.status_code == 200

    login(client, player_id)
    response = client.post(
        '/api/signups',
        json={'adventure_id': first_adventure_id, 'priority': 1},
        base_url='https://localhost',
    )
    assert response.status_code == 200

    response = client.post(
        '/api/signups',
        json={'adventure_id': full_adventure_id, 'priority': 2},
        base_url='https://localhost',
    )
    assert response.status_code == 200

    with app.app_context():
        assigned = db.session.execute(
            db.select(Assignment)
            .join(Adventure, Assignment.adventure_id == Adventure.id)
            .where(
                Assignment.user_id == player_id,
                Adventure.event_type_id == event_type_id,
                Adventure.date == date(2026, 3, 20),
                Adventure.is_waitinglist == 0,
            )
        ).scalars().all()
        assert len(assigned) == 1
        assert assigned[0].adventure_id == first_adventure_id

        waiting_list = db.session.execute(
            db.select(Adventure).where(
                Adventure.event_type_id == event_type_id,
                Adventure.date == date(2026, 3, 20),
                Adventure.is_waitinglist == 1,
            )
        ).scalars().one()

        waiting_assignment = db.session.execute(
            db.select(Assignment).where(
                Assignment.user_id == player_id,
                Assignment.adventure_id == waiting_list.id,
            )
        ).scalars().first()
        assert waiting_assignment is None