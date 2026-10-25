"""Product regressions use fictional data and never contact an AI or booking provider."""
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select, update

from app.models import AccountSession, Proposal, utc_now
from app.schemas.planning import ItineraryPlan
from app.services.conversational_ai import ConversationTurn


TOKYO_REQUEST = ('Plan a relaxed six-day Tokyo vacation for two people. Include Japanese food, '
    'photography, anime, Shibuya, Asakusa, Akihabara, and Shinjuku. Keep activities between '
    '9 AM and 9 PM. Stay within Tokyo and our $3,000 total budget. Do not save anything until I approve.')


@pytest.fixture
def owned(client):
    auth = client.post('/api/auth/register', json={'username': 'quality.traveler', 'password': 'Fictional audit account passphrase'}).json()
    headers = {'X-Profile-Token': 'account-session:' + auth['csrf_token']}
    data = {'name': 'Tokyo Adventure 2027', 'destination': 'Tokyo, Japan', 'departure_location': 'Columbus, Ohio, USA',
            'start_date': '2027-05-01', 'end_date': '2027-05-06', 'travelers': 2, 'budget': '3000.00', 'currency': 'USD'}
    response = client.post('/api/trips', headers=headers, json=data)
    assert response.status_code == 201
    return headers, response.json(), data


def stop(title='Sensoji Temple', location='Asakusa, Tokyo', start='09:00', end='10:30', day='2027-05-01', cost='20.00', kind='activity'):
    return {'title': title, 'location': location, 'date': day, 'start_time': start, 'end_time': end,
            'estimated_cost': cost, 'item_type': kind, 'description': 'A suggestion to review.'}


def plan(*items):
    return ItineraryPlan(title='Ideas for Tokyo', summary='Suggestions costing $1,200.', activities=list(items), notes=[])


def draft(client, application, monkeypatch, owned, generated, request=TOKYO_REQUEST):
    headers, trip, _ = owned
    application.state.settings.ai_mode = 'ollama'
    async def provider(*args, **kwargs):
        return generated
    monkeypatch.setattr('app.services.planning.request_ai_plan', provider)
    return client.post(f"/api/trips/{trip['id']}/proposals", headers=headers, json={'request': request})


@pytest.mark.parametrize('item,detail', [
    (stop('Gion District', 'Higashiyama, Kyoto'), 'destination'),
    (stop('Omoide Yokocho', 'Shibuya, Tokyo', kind='food'), 'Shinjuku'),
    (stop(start='08:00', end='09:30'), '09:00'),
])
def test_geo_and_requested_window_are_enforced_before_a_draft_is_stored(client, application, monkeypatch, owned, item, detail):
    response = draft(client, application, monkeypatch, owned, plan(item))
    assert response.status_code == 422, response.text
    assert detail.lower() in response.json()['detail'].lower()
    headers, trip, _ = owned
    assert client.get(f"/api/trips/{trip['id']}/proposals", headers=headers).json() == []
    assert client.get(f"/api/trips/{trip['id']}", headers=headers).json()['itinerary'] == []


def test_duplicate_place_on_different_days_is_not_a_new_attraction(client, application, monkeypatch, owned):
    response = draft(client, application, monkeypatch, owned, plan(stop(), stop(day='2027-05-02')), 'Plan two sightseeing stops. Avoid repeats.')
    assert response.status_code == 422, response.text
    assert 'repeat' in response.json()['detail'].lower()


def test_adjacent_different_places_need_transfer_time(client, application, monkeypatch, owned):
    response = draft(client, application, monkeypatch, owned,
        plan(stop(), stop('Shibuya Crossing', 'Shibuya, Tokyo', start='10:30', end='11:30')), 'Plan two sights.')
    assert response.status_code == 422, response.text
    assert 'buffer' in response.json()['detail'].lower()


def test_unverified_venue_and_prices_are_labeled_and_totals_are_server_calculated(client, application, monkeypatch, owned):
    response = draft(client, application, monkeypatch, owned,
        plan(stop('Unconfirmed cafe', 'Unconfirmed street, Tokyo', start='12:00', end='13:00', cost='40.25', kind='food')), 'Suggest one lunch idea.')
    assert response.status_code == 201, response.text
    data = response.json()
    assert data['quality']['places'][0]['status'] == 'unverified'
    assert data['quality']['cost_basis'] == 'illustrative_group_allowances'
    assert data['quality']['by_category']['food'] == '40.25'
    assert data['estimated_total'] == '40.25'
    assert '$1,200' not in data['summary']
    assert data['quality']['trip_days'] == 6
    assert data['quality']['arrival_departure_times'] == 'unknown'


@pytest.mark.parametrize('route', ['chat', 'direct'])
def test_revoking_account_during_generation_prevents_persisting_a_proposal(client, application, monkeypatch, owned, route):
    headers, trip, _ = owned
    application.state.settings.ai_mode = 'ollama'
    async def provider(*args, **kwargs):
        with application.state.database.session_factory() as session:
            session.execute(update(AccountSession).values(revoked_at=utc_now()))
            session.commit()
        return ConversationTurn('Review this.', plan(stop())) if route == 'chat' else plan(stop())
    if route == 'chat':
        monkeypatch.setattr('app.api.buddy.converse', provider)
        response = client.post('/api/buddy/chat', headers=headers,
            json={'trip_id': trip['id'], 'messages': [{'role': 'user', 'content': 'Plan a day.'}]})
    else:
        monkeypatch.setattr('app.services.planning.request_ai_plan', provider)
        response = client.post(f"/api/trips/{trip['id']}/proposals", headers=headers, json={'request': 'Plan a day.'})
    assert response.status_code == 401, response.text
    with application.state.database.session_factory() as session:
        assert list(session.scalars(select(Proposal))) == []


def test_trip_duration_has_the_same_inclusive_boundary_as_the_form(client, owned):
    headers, _, data = owned
    data = {**data, 'start_date': '2027-01-01', 'end_date': '2028-01-02'}
    assert client.post('/api/trips', headers=headers, json=data).status_code == 422
    data['end_date'] = '2028-01-01'
    assert client.post('/api/trips', headers=headers, json=data).status_code == 201


def test_vault_current_password_is_bounded_without_echoing_it(client, owned):
    headers, _, _ = owned
    assert client.post('/api/private-traveler/create', headers=headers, json={'password': 'Fictional vault passphrase'}).status_code == 200
    secret = 'x' * 1000
    response = client.post('/api/private-traveler/change-password', headers=headers,
        json={'current_password': secret, 'password': 'Changed fictional vault passphrase'})
    assert response.status_code == 422
    assert secret not in response.text


def test_opening_hours_cannot_be_used_as_an_all_day_visit(client, application, monkeypatch, owned):
    response = draft(client, application, monkeypatch, owned, plan(stop(end='21:00')), 'Suggest one Tokyo sight.')
    assert response.status_code == 422
    assert 'duration' in response.json()['detail']


def test_a_luxury_venue_cannot_be_given_a_guessed_budget_quote(client, application, monkeypatch, owned):
    response = draft(client, application, monkeypatch, owned,
        plan(stop('Sushi Saito', 'Roppongi, Tokyo', start='12:00', end='13:00', kind='food', cost='40.00')), 'Suggest one lunch.')
    assert response.status_code == 422
    assert 'verified provider' in response.json()['detail']


def test_specific_venue_in_a_known_area_is_not_mislabeled_as_verified(client, application, monkeypatch, owned):
    response = draft(client, application, monkeypatch, owned,
        plan(stop('Unconfirmed Shibuya cafe', 'Shibuya, Tokyo', kind='food')), 'Suggest one meal idea.')
    assert response.status_code == 201, response.text
    assert response.json()['quality']['places'][0]['status'] == 'area_reference'


def test_api_body_limit_rejects_regular_and_streamed_oversize_without_echo(client):
    for content in ['x' * 140000, iter([b'x' * 70000, b'y' * 70000])]:
        response = client.post('/api/buddy/chat', content=content, headers={'Content-Type': 'application/json'})
        assert response.status_code == 413
        assert len(response.text) < 300
        assert response.headers['cache-control'] == 'no-store, private'


def test_local_inference_is_bounded_and_releases_slots_after_provider_failure(monkeypatch):
    import asyncio
    from unittest.mock import AsyncMock
    from app.services import ollama_ai
    from app.config import Settings
    from fastapi import HTTPException
    settings = Settings(_env_file=None, ai_mode='ollama', openai_api_key=None)
    assert ollama_ai.LOCAL_INFERENCE_SLOTS.acquire(blocking=False)
    try:
        with pytest.raises(HTTPException) as failure:
            asyncio.run(ollama_ai._request(settings, []))
        assert failure.value.status_code == 429
    finally:
        ollama_ai.LOCAL_INFERENCE_SLOTS.release()
    monkeypatch.setattr(ollama_ai, '_perform_request', AsyncMock(side_effect=HTTPException(503, 'Fictional failure')))
    with pytest.raises(HTTPException):
        asyncio.run(ollama_ai._request(settings, []))
    assert ollama_ai.LOCAL_INFERENCE_SLOTS.acquire(blocking=False)
    ollama_ai.LOCAL_INFERENCE_SLOTS.release()


def test_explicit_window_survives_a_conversational_revision_and_cannot_be_weakened_by_model(client, application, monkeypatch, owned):
    from app.services.travel_quality import constraints_for
    rules = constraints_for('Make a six-day plan between 9 AM and 9 PM. Stay within Tokyo.')
    inherited = constraints_for('Make dinner cheaper.', previous=rules)
    assert inherited['start_time'] == '09:00' and inherited['end_time'] == '21:00'
    assert inherited['city_only'] == 'Tokyo' and inherited['cover_all_days']
    changed = constraints_for('Use between 10:00 and 20:00 instead.', previous=inherited)
    assert changed['start_time'] == '10:00' and changed['end_time'] == '20:00'


def test_backend_calculated_context_has_inclusive_days_and_no_authentication_secrets(client, application, monkeypatch, owned):
    headers, trip, _ = owned
    application.state.settings.ai_mode = 'ollama'
    async def capture(messages, feature, settings, context, draft_context):
        assert context['calculated_facts']['calendar_days_inclusive'] == 6
        assert context['calculated_facts']['budget_per_person_allowance'] == '1500.00'
        assert context['calculated_facts']['budget_per_day_group_allowance'] == '500.00'
        assert context['calculated_facts']['arrival_time'] == 'unknown_not_stored'
        import json
        assert headers['X-Profile-Token'] not in json.dumps(context)
        return ConversationTurn('A normal explanation, no draft.')
    monkeypatch.setattr('app.api.buddy.converse', capture)
    response = client.post('/api/buddy/chat', headers=headers, json={'trip_id': trip['id'], 'messages': [{'role': 'user', 'content': 'How long is this trip?'}]})
    assert response.status_code == 200 and response.json()['proposal'] is None
