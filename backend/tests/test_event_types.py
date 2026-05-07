from tests.conftest import login


def test_event_types_list_returns_defaults(client):
    response = client.get('/api/event-types', base_url='https://localhost')

    assert response.status_code == 200
    data = response.get_json()
    titles = {item['title'] for item in data}
    assert 'Dungeons & Dragons Jeugd 12-18' in titles
    assert 'Dungeons & Dragons Junior 8-12' in titles
    assert all('next_date' in item for item in data)
    assert all('is_single_event' in item for item in data)
    assert all('signup_mode' in item for item in data)


def test_event_types_create_requires_admin(client, normal_user_id):
    login(client, normal_user_id)

    response = client.post(
        '/api/event-types',
        json={
            'title': 'Special Event',
            'description': 'Custom monthly event',
            'weekday': 4,
            'week_of_month': 3,
            'exclude_july_august': False,
            'is_single_event': True,
            'is_active': True,
            'sort_order': 50,
        },
        base_url='https://localhost',
    )

    assert response.status_code == 401


def test_event_types_create_admin(client, admin_user_id):
    login(client, admin_user_id)

    response = client.post(
        '/api/event-types',
        json={
            'title': 'Special Event',
            'description': 'Custom monthly event',
            'weekday': 4,
            'week_of_month': 3,
            'exclude_july_august': False,
            'is_single_event': True,
            'is_active': True,
            'sort_order': 50,
        },
        base_url='https://localhost',
    )

    assert response.status_code == 201
    data = response.get_json()
    assert data['title'] == 'Special Event'
    assert data['is_single_event'] is True
    assert data['signup_mode'] == 'delayed_manual'
    assert 'next_date' in data


def test_event_types_update_requires_admin(client, normal_user_id, admin_user_id):
    login(client, admin_user_id)
    created = client.post(
        '/api/event-types',
        json={
            'title': 'Edit Me',
            'description': 'Original',
            'image_url': 'https://example.com/original.jpg',
            'weekday': 4,
            'week_of_month': 3,
            'exclude_july_august': False,
            'is_single_event': False,
            'is_active': True,
            'sort_order': 50,
        },
        base_url='https://localhost',
    )
    event_type_id = created.get_json()['id']

    login(client, normal_user_id)
    response = client.patch(
        f'/api/event-types/{event_type_id}',
        json={'title': 'Hacked'},
        base_url='https://localhost',
    )

    assert response.status_code == 401


def test_event_types_update_admin(client, admin_user_id):
    login(client, admin_user_id)
    created = client.post(
        '/api/event-types',
        json={
            'title': 'Before Update',
            'description': 'Original description',
            'image_url': 'https://example.com/original.jpg',
            'weekday': 6,
            'week_of_month': 1,
            'exclude_july_august': True,
            'is_single_event': False,
            'is_active': True,
            'sort_order': 10,
        },
        base_url='https://localhost',
    )
    event_type_id = created.get_json()['id']

    response = client.patch(
        f'/api/event-types/{event_type_id}',
        json={
            'title': 'After Update',
            'description': 'Updated description',
            'image_url': 'https://example.com/updated.jpg',
            'is_single_event': True,
        },
        base_url='https://localhost',
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data['title'] == 'After Update'
    assert data['description'] == 'Updated description'
    assert data['image_url'] == 'https://example.com/updated.jpg'
    assert data['is_single_event'] is True
    assert 'next_date' in data
