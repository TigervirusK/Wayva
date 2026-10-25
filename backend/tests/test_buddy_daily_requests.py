"""Natural daily/meal requests must create proposals, never silent saved changes."""

from unittest.mock import AsyncMock

import httpx
import pytest

from app.services.buddy import wants_itinerary_proposal


EXACT_REQUEST = (
    "for each day i wanna do multiple trips in that place and i want you to tell me "
    "place for lunch and dinner"
)


@pytest.mark.parametrize("text", [
    EXACT_REQUEST,
    "I want several places to visit every day, plus lunch and dinner",
    "and lunch and dinner each day",
    "Where should we go for lunch and dinner?",
    "What restaurants would you recommend?",
    "Each day: two attractions, lunch and dinner",
    "I’d like food spots for my trip",
    "Add lunch and dinner to the plan",
    "Tell me places for lunch",
    "Show me restaurants for lunch and dinner",
    "Show me activities and lunch places for my trip",
    "create a itinearary",
])
def test_daily_and_meal_ideas_route_to_a_reviewable_proposal(text):
    assert wants_itinerary_proposal(text)


@pytest.mark.parametrize("text", [
    "Show my itinerary",
    "List my saved activities",
    "What restaurants are already saved?",
    "Where is lunch on my saved itinerary?",
    "What is currently scheduled for dinner?",
    "Where is dinner in my plan?",
    "Do not generate an itinerary",
    "Don't add lunch and dinner to my itinerary",
    "I don't want to generate a plan",
    "No need to create a trip",
    "What is my budget?",
])
@pytest.mark.parametrize("feature", [None, "dream"])
def test_saved_plan_questions_and_refusals_remain_read_only(text, feature):
    assert not wants_itinerary_proposal(text, feature)


@pytest.fixture
def daily_trip(client, monkeypatch):
    provider = AsyncMock(side_effect=AssertionError("No real provider calls in daily-request tests"))
    monkeypatch.setattr(httpx.AsyncClient, "post", provider)
    profile = client.post("/api/profiles", json={"display_name": "Daily request traveler"})
    assert profile.status_code == 201
    headers = {"X-Profile-Token": profile.json()["token"]}
    created = client.post("/api/trips", headers=headers, json={
        "name": "Japan daily visits", "destination": "Tokyo", "departure_location": "Columbus",
        "start_date": "2027-10-10", "end_date": "2027-10-20", "travelers": 2,
        "budget": "3000.00", "currency": "USD", "status": "planned",
    })
    assert created.status_code == 201
    trip_id = created.json()["id"]
    existing = client.post(f"/api/trips/{trip_id}/itinerary", headers=headers, json={
        "date": "2027-10-10", "start_time": "10:00", "end_time": "11:00",
        "title": "Keep my existing walk", "description": "", "location": "Ueno Park",
        "estimated_cost": "10.00", "item_type": "activity", "status": "planned",
    })
    assert existing.status_code == 201
    return trip_id, headers, existing.json(), provider


@pytest.mark.parametrize("message", [EXACT_REQUEST, "and lunch and dinner each day", "Where should we go for lunch?"])
def test_selected_trip_meal_requests_return_pending_proposal_and_preserve_saved_records(client, daily_trip, message):
    trip_id, headers, before, provider = daily_trip
    response = client.post("/api/buddy/chat", headers=headers, json={
        "trip_id": trip_id,
        "messages": [{"role": "user", "content": message}],
    })
    assert response.status_code == 200
    result = response.json()
    assert result["proposal"]["status"] == "pending"
    assert result["proposal"]["trip_id"] == trip_id
    assert result["proposal"]["activities"]
    assert result["proposal"]["mode"] == "demo"
    assert "saved itinerary item(s)" not in result["reply"]
    after = client.get(f"/api/trips/{trip_id}", headers=headers)
    assert after.status_code == 200
    assert after.json() == before
    provider.assert_not_awaited()


@pytest.mark.parametrize("message", ["Show my itinerary", "Do not generate an itinerary"])
def test_read_only_questions_do_not_create_a_proposal_even_in_dream_tab(client, daily_trip, message):
    trip_id, headers, before, provider = daily_trip
    response = client.post("/api/buddy/chat", headers=headers, json={
        "trip_id": trip_id, "feature": "dream",
        "messages": [{"role": "user", "content": message}],
    })
    assert response.status_code == 200
    assert response.json()["proposal"] is None
    assert client.get(f"/api/trips/{trip_id}/proposals", headers=headers).json() == []
    assert client.get(f"/api/trips/{trip_id}", headers=headers).json() == before
    provider.assert_not_awaited()


def test_natural_daily_request_still_requires_trip_ownership(client, daily_trip):
    trip_id, owner_headers, before, provider = daily_trip
    another = client.post("/api/profiles", json={"display_name": "Another traveler"})
    foreign_headers = {"X-Profile-Token": another.json()["token"]}
    request = {"trip_id": trip_id, "messages": [{"role": "user", "content": EXACT_REQUEST}]}
    assert client.post("/api/buddy/chat", json=request).status_code == 401
    assert client.post("/api/buddy/chat", json=request, headers=foreign_headers).status_code == 404
    assert client.get(f"/api/trips/{trip_id}/proposals", headers=owner_headers).json() == []
    assert client.get(f"/api/trips/{trip_id}", headers=owner_headers).json() == before
    provider.assert_not_awaited()
