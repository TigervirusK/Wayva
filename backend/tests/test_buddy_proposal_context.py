"""The selected trip and recent conversation reach reviewed planning together."""

from unittest.mock import AsyncMock

import httpx

from app.api import buddy as buddy_api


def test_chat_passes_recent_conversation_without_replacing_the_current_request(client, monkeypatch):
    blocked_provider = AsyncMock(side_effect=AssertionError("No live provider calls in this test"))
    monkeypatch.setattr(httpx.AsyncClient, "post", blocked_provider)
    generate = AsyncMock(wraps=buddy_api.generate_proposal)
    monkeypatch.setattr(buddy_api, "generate_proposal", generate)
    profile = client.post("/api/profiles", json={"display_name": "Context test"}).json()
    headers = {"X-Profile-Token": profile["token"]}
    trip = client.post("/api/trips", headers=headers, json={
        "name": "Tokyo context test", "destination": "Tokyo", "departure_location": "Boston",
        "start_date": "2027-10-10", "end_date": "2027-10-10", "travelers": 2,
        "budget": "300.00", "currency": "USD", "status": "planned",
    }).json()
    messages = [
        {"role": "user", "content": "We enjoy photography and quiet parks."},
        {"role": "assistant", "content": "We can keep those interests in mind."},
        {"role": "user", "content": "Make an itinerary."},
    ]

    response = client.post("/api/buddy/chat", headers=headers, json={
        "trip_id": trip["id"], "messages": messages,
    })

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["status"] == "pending"
    assert proposal["request"] == messages[-1]["content"]
    generate.assert_awaited_once()
    assert generate.await_args.kwargs["conversation"] == messages
    assert client.get(f"/api/trips/{trip['id']}", headers=headers).json()["itinerary"] == []
    blocked_provider.assert_not_awaited()
