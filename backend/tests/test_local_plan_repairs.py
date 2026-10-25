"""Local model drafts get bounded scheduling feedback before any saved action."""
import asyncio
from copy import deepcopy
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from app.config import Settings
from app.services import ollama_ai


def activity(title, start, end, kind='activity'):
    return {'date': '2027-10-10', 'start_time': start, 'end_time': end, 'title': title,
            'description': 'Unverified suggestion.', 'location': f'{title}, Tokyo',
            'estimated_cost': '10.00', 'item_type': kind}


def draft(items):
    return {'title': 'A proposed Tokyo day', 'summary': 'Ideas to review, with estimated costs.',
            'activities': items, 'notes': ['Prices and opening hours are unverified.']}


def response(plan=None, requirements=None):
    turn = {'reply': 'Here is a draft to review.' if plan else 'We can discuss that.',
            'plan': plan, 'requirements': requirements}
    return httpx.Response(200, json={'done': True, 'done_reason': 'stop',
        'message': {'role': 'assistant', 'content': json.dumps(turn)}},
        request=httpx.Request('POST', 'http://127.0.0.1:11434/api/chat'))


@pytest.fixture
def local_settings():
    return Settings(_env_file=None, ai_mode='ollama', openai_api_key=None)


@pytest.fixture
def context():
    return {'destination': 'Tokyo', 'start_date': '2027-10-10', 'end_date': '2027-10-10',
            'budget': '500.00', 'itinerary': []}


def ask(settings, context):
    return ollama_ai.local_converse([{'role': 'user', 'content': 'Help me plan the day.'}],
                                    None, settings, context)


def test_overlapping_suggestions_receive_specific_feedback_and_saved_items_stay_fixed(local_settings, context, monkeypatch):
    saved = activity('My saved walk', '10:00', '11:00')
    context['itinerary'] = [{**saved, 'status': 'planned'}]
    before = deepcopy(context)
    requirements = {'minimum_activities': 0, 'lunch': False, 'dinner': False}
    invalid = draft([activity('Proposed museum', '10:30', '11:30')])
    corrected = draft([activity('Proposed museum', '12:00', '13:00')])
    post = AsyncMock(side_effect=[response(invalid, requirements), response(corrected, requirements)])
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)

    turn = asyncio.run(ask(local_settings, context))

    assert turn.plan.model_dump() == corrected
    assert post.await_count == 2
    feedback = post.await_args.kwargs['json']['messages'][-1]['content']
    assert 'My saved walk' in feedback and 'Proposed museum' in feedback
    assert '10:00-11:00' in feedback and '10:30-11:30' in feedback
    assert context == before


def test_meals_in_notes_do_not_count_and_corrections_cannot_weaken_daily_requirements(local_settings, context, monkeypatch):
    sights = [activity('Morning walk', '09:00', '10:00'), activity('Afternoon park', '14:00', '15:00')]
    incomplete = draft(sights)
    incomplete['notes'].append('Have lunch and dinner somewhere nearby.')
    complete = draft([sights[0], activity('Lunch restaurant', '12:00', '13:00', 'food'),
                      sights[1], activity('Dinner restaurant', '18:00', '19:00', 'food')])
    required = {'minimum_activities': 2, 'lunch': True, 'dinner': True}
    weakened = {'minimum_activities': 0, 'lunch': False, 'dinner': False}
    post = AsyncMock(side_effect=[response(incomplete, required), response(incomplete, weakened),
                                 response(complete, weakened)])
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)

    turn = asyncio.run(ask(local_settings, context))

    assert len(turn.plan.activities) == 4
    assert turn.requirements.minimum_activities == 2
    assert turn.requirements.lunch and turn.requirements.dinner
    assert post.await_count == 3
    assert 'missing lunch' in post.await_args_list[1].kwargs['json']['messages'][-1]['content']


def test_an_unrepairable_plan_stops_after_two_corrections(local_settings, context, monkeypatch):
    conflicting = draft([activity('Walk one', '10:00', '11:00'), activity('Walk two', '10:30', '11:30')])
    post = AsyncMock(return_value=response(conflicting, {'minimum_activities': 0, 'lunch': False, 'dinner': False}))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(ask(local_settings, context))
    assert failure.value.status_code == 409
    assert post.await_count == 3


def test_expired_overall_budget_prevents_another_model_request(local_settings, context, monkeypatch):
    conflicting = draft([activity('Walk one', '10:00', '11:00'), activity('Walk two', '10:30', '11:30')])
    post = AsyncMock(return_value=response(conflicting, {'minimum_activities': 0, 'lunch': False, 'dinner': False}))
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    ticks = iter([0.0, 0.0, 241.0])
    monkeypatch.setattr(ollama_ai, 'monotonic', lambda: next(ticks))
    with pytest.raises(HTTPException) as failure:
        asyncio.run(ask(local_settings, context))
    assert failure.value.status_code == 504
    post.assert_awaited_once()


def test_ordinary_answer_does_not_start_repair_requests(local_settings, context, monkeypatch):
    post = AsyncMock(return_value=response())
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)
    assert asyncio.run(ask(local_settings, context)).plan is None
    post.assert_awaited_once()


def test_repaired_local_draft_still_requires_profile_approval_before_saving(client, application, monkeypatch):
    application.state.settings.ai_mode = 'ollama'
    profile = client.post('/api/profiles', json={'display_name': 'Repair test traveler'}).json()
    headers = {'X-Profile-Token': profile['token']}
    trip = client.post('/api/trips', headers=headers, json={
        'name': 'Repair test', 'destination': 'Tokyo', 'departure_location': 'Boston',
        'start_date': '2027-10-10', 'end_date': '2027-10-10', 'travelers': 2,
        'budget': '500.00', 'currency': 'USD', 'status': 'planned'}).json()
    sights = [activity('Morning walk', '09:00', '10:00'), activity('Afternoon park', '14:00', '15:00')]
    valid = draft([sights[0], activity('Lunch restaurant', '12:00', '13:00', 'food'),
                   sights[1], activity('Dinner restaurant', '18:00', '19:00', 'food')])
    required = {'minimum_activities': 2, 'lunch': True, 'dinner': True}
    # The new reference-backed path first classifies intent semantically. Keep
    # exercising the original invalid-draft/correction and approval assertions.
    intent = httpx.Response(200, json={'done': True, 'done_reason': 'stop',
        'message': {'role': 'assistant', 'content': '{"intent":"plan"}'}},
        request=httpx.Request('POST', 'http://127.0.0.1:11434/api/chat'))
    post = AsyncMock(side_effect=[intent, response(draft(sights), required), response(valid, required)])
    monkeypatch.setattr(httpx.AsyncClient, 'post', post)

    result = client.post('/api/buddy/chat', headers=headers, json={'trip_id': trip['id'],
        'messages': [{'role': 'user', 'content': 'Help us fill out each day, including our meals.'}]})

    assert result.status_code == 200
    proposal = result.json()['proposal']
    assert proposal['mode'] == 'ollama' and proposal['status'] == 'pending'
    assert post.await_count == 3
    path = f"/api/trips/{trip['id']}"
    assert client.get(path, headers=headers).json()['itinerary'] == []
    approved = client.post(f"{path}/proposals/{proposal['id']}/approve", headers=headers)
    assert approved.status_code == 200
    assert len(approved.json()['trip']['itinerary']) == 4
