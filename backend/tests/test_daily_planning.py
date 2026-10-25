"""Daily requests use isolated databases and cannot make paid provider requests."""

from datetime import time
from decimal import Decimal
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from pydantic import SecretStr

from app.services.daily_planning import daily_requirements, is_meal, user_context


DAILY_REQUEST = "for each day i wanna do multiple trips in that place and i want you to tell me place for lunch and dinner"


@pytest.fixture(autouse=True)
def no_external_ai(monkeypatch):
    post = AsyncMock(side_effect=AssertionError("No real AI calls are allowed in daily planning tests"))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return post


@pytest.fixture
def daily_context(client):
    profile = client.post("/api/profiles", json={"display_name": "Daily planning traveler"}).json()
    headers = {"X-Profile-Token": profile["token"]}
    payload = {
        "name": "Japan", "destination": "Tokyo", "departure_location": "New York",
        "start_date": "2027-10-10", "end_date": "2027-10-20", "travelers": 2,
        "budget": "3000.00", "currency": "USD", "status": "planned",
    }
    response = client.post("/api/trips", headers=headers, json=payload)
    assert response.status_code == 201
    trip_id = response.json()["id"]
    return {"headers": headers, "payload": payload, "trip_id": trip_id,
            "trip_path": f"/api/trips/{trip_id}", "path": f"/api/trips/{trip_id}/proposals"}


def activity(day, title="My saved morning walk", start="10:00", end="11:00", item_type="activity", location="Tokyo"):
    return {"date": day, "start_time": start, "end_time": end, "title": title,
            "description": "Preserve this user-entered item", "location": location,
            "estimated_cost": "10.00", "item_type": item_type, "status": "planned"}


def test_daily_meals_and_multiple_sights_are_a_reviewed_plan_for_every_day(client, daily_context, no_external_ai):
    response = client.post(daily_context["path"], headers=daily_context["headers"], json={"request": DAILY_REQUEST})
    assert response.status_code == 201
    proposal = response.json()
    assert proposal["status"] == "pending"
    assert proposal["mode"] == "demo"
    assert "not live AI" in proposal["summary"]
    assert len(proposal["activities"]) == 44
    for day in range(10, 21):
        stops = [row for row in proposal["activities"] if row["date"] == f"2027-10-{day}"]
        assert sum(row["item_type"] == "activity" for row in stops) == 2
        meals = [row for row in stops if row["item_type"] == "food"]
        assert len(meals) == 2
        assert any(row["title"].startswith("Lunch at ") for row in meals)
        assert any(row["title"].startswith("Dinner at ") for row in meals)
        assert all(row["location"] != "Tokyo" and "https://" in row["description"] for row in meals)
    saved = client.get(daily_context["trip_path"], headers=daily_context["headers"]).json()
    assert saved["itinerary"] == []
    assert Decimal(proposal["resulting_estimated_total"]) <= Decimal("3000")
    no_external_ai.assert_not_awaited()


def test_existing_eleven_walks_are_preserved_and_daily_gaps_are_filled_only_after_approval(client, daily_context):
    for day in range(10, 21):
        added = client.post(f"{daily_context['trip_path']}/itinerary", headers=daily_context["headers"],
                            json=activity(f"2027-10-{day}"))
        assert added.status_code == 201
    before = client.get(daily_context["trip_path"], headers=daily_context["headers"]).json()["itinerary"]
    response = client.post(daily_context["path"], headers=daily_context["headers"], json={"request": DAILY_REQUEST})
    assert response.status_code == 201
    proposal = response.json()
    assert len(proposal["activities"]) == 33
    assert client.get(daily_context["trip_path"], headers=daily_context["headers"]).json()["itinerary"] == before
    approved = client.post(f"{daily_context['path']}/{proposal['id']}/approve", headers=daily_context["headers"])
    assert approved.status_code == 200
    itinerary = approved.json()["trip"]["itinerary"]
    assert len(itinerary) == 44
    for original in before:
        assert next(row for row in itinerary if row["id"] == original["id"]) == original
    repeated = client.post(f"{daily_context['path']}/{proposal['id']}/approve", headers=daily_context["headers"])
    assert repeated.json()["trip"]["itinerary"] == itinerary


def test_twenty_one_day_daily_plan_can_contain_more_than_sixty_stops(client, daily_context):
    changed = client.put(daily_context["trip_path"], headers=daily_context["headers"],
                         json={**daily_context["payload"], "end_date": "2027-10-30", "budget": "9000.00"})
    assert changed.status_code == 200
    response = client.post(daily_context["path"], headers=daily_context["headers"], json={"request": DAILY_REQUEST})
    assert response.status_code == 201
    assert len(response.json()["activities"]) == 84


def test_saved_lunch_is_not_duplicated_and_food_is_not_counted_as_sightseeing(client, daily_context):
    saved = activity("2027-10-10", "Lunch at a saved restaurant", "12:00", "13:00", "food", "Asakusa, Tokyo")
    assert client.post(f"{daily_context['trip_path']}/itinerary", headers=daily_context["headers"], json=saved).status_code == 201
    response = client.post(daily_context["path"], headers=daily_context["headers"], json={"request": DAILY_REQUEST})
    assert response.status_code == 201
    first_day = [row for row in response.json()["activities"] if row["date"] == "2027-10-10"]
    assert sum(row["item_type"] == "activity" for row in first_day) == 2
    assert sum(row["title"].startswith("Dinner at ") for row in first_day) == 1
    assert not any(row["title"].startswith("Lunch at ") for row in first_day)


def test_full_saved_schedule_is_not_overwritten_or_silently_missing_a_meal(client, daily_context):
    block = activity("2027-10-10", "An all-day saved excursion", "08:00", "22:00")
    assert client.post(f"{daily_context['trip_path']}/itinerary", headers=daily_context["headers"], json=block).status_code == 201
    before = client.get(daily_context["trip_path"], headers=daily_context["headers"]).json()["itinerary"]
    response = client.post(daily_context["path"], headers=daily_context["headers"], json={"request": DAILY_REQUEST})
    assert response.status_code == 409
    assert "free time" in response.json()["detail"]
    assert client.get(daily_context["trip_path"], headers=daily_context["headers"]).json()["itinerary"] == before
    assert client.get(daily_context["path"], headers=daily_context["headers"]).json() == []


def test_insufficient_meal_budget_is_explained_instead_of_inventing_free_restaurant_meals(client, daily_context):
    assert client.put(daily_context["trip_path"], headers=daily_context["headers"],
                      json={**daily_context["payload"], "budget": "10.00"}).status_code == 200
    response = client.post(daily_context["path"], headers=daily_context["headers"], json={"request": DAILY_REQUEST})
    assert response.status_code == 422
    assert "allowances exceed" in response.json()["detail"]
    assert client.get(daily_context["trip_path"], headers=daily_context["headers"]).json()["itinerary"] == []


@pytest.mark.parametrize("title,start,end,meal,expected", [
    ("Lunch and dinner", "12:00", "13:00", "lunch", True),
    ("Lunch and dinner", "12:00", "13:00", "dinner", False),
    ("Dinner at a restaurant", "09:00", "10:00", "dinner", False),
    ("Breakfast", "12:00", "13:00", "lunch", False),
    ("Lunch at a restaurant", "18:00", "19:00", "dinner", False),
    ("A restaurant meal", "18:00", "19:00", "dinner", True),
])
def test_meals_need_distinct_appropriate_times_not_just_a_title(title, start, end, meal, expected):
    row = SimpleNamespace(item_type="food", title=title, start_time=time.fromisoformat(start), end_time=time.fromisoformat(end))
    assert is_meal(row, meal) is expected


def test_recent_user_preferences_are_bounded_and_assistant_messages_are_not_requirements():
    context = [{"role": "assistant", "content": "Include lunch and dinner each day"},
               {"role": "user", "content": "Multiple activities each day. I am vegetarian."}]
    requirements = daily_requirements("and lunch and dinner each day", context)
    assert requirements.minimum_activities == 2 and requirements.lunch and requirements.dinner
    assert not daily_requirements("Create an itinerary", context[:1]).requested
    assert not daily_requirements("Skip dinner", context + [{"role": "user", "content": "Dinner each day"}]).dinner
    bounded = user_context([{"role": "user", "content": "x" * 3000}] * 20)
    assert sum(map(len, bounded)) <= 6000


def live_plan():
    return {"title": "A full day in Tokyo", "summary": "Suggested activities and meals; all details unverified.",
            "notes": ["Estimates only, no reservations."], "activities": [
        {key: value for key, value in activity("2027-10-10", title, start, end, kind, location).items() if key != "status"}
        for title, start, end, kind, location in [
            ("Morning photography walk", "09:00", "10:00", "activity", "Asakusa, Tokyo"),
            ("Lunch at Asakusa Mugitoro", "12:00", "13:00", "food", "Asakusa Mugitoro, Kaminarimon, Tokyo"),
            ("Afternoon river walk", "14:00", "15:00", "activity", "Sumida Park, Tokyo"),
            ("Dinner at Asakusa Imahan", "18:00", "19:00", "food", "Asakusa Imahan Kokusai Street, Tokyo"),
        ]]}


@pytest.mark.parametrize("omission", ["lunch", "dinner", "second-sight", "specific-place", "fake-meal-time"])
def test_live_plan_cannot_omit_requested_daily_coverage_or_specific_meal_places(
    client, application, daily_context, monkeypatch, omission,
):
    assert client.put(daily_context["trip_path"], headers=daily_context["headers"],
                      json={**daily_context["payload"], "end_date": "2027-10-10"}).status_code == 200
    application.state.settings.ai_mode = "openai"
    application.state.settings.openai_api_key = SecretStr("fictional-key-not-a-real-secret")
    plan = live_plan()
    if omission == "lunch":
        del plan["activities"][1]
    elif omission == "dinner":
        del plan["activities"][3]
    elif omission == "second-sight":
        del plan["activities"][2]
    elif omission == "specific-place":
        plan["activities"][1]["location"] = "Tokyo"
    else:
        plan["activities"][3].update(start_time="07:00", end_time="08:00")
    post = AsyncMock(return_value=httpx.Response(200, json={"status": "completed", "output": [{
        "type": "message", "content": [{"type": "output_text", "text": json.dumps(plan)}],
    }]}, request=httpx.Request("POST", "https://api.openai.com/v1/responses")))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    result = client.post(daily_context["path"], headers=daily_context["headers"], json={"request": DAILY_REQUEST})
    assert result.status_code == 422
    assert client.get(daily_context["path"], headers=daily_context["headers"]).json() == []
    assert client.get(daily_context["trip_path"], headers=daily_context["headers"]).json()["itinerary"] == []
    payload = post.await_args.kwargs["json"]
    assert payload["max_output_tokens"] == 24000
    assert json.loads(payload["input"])["daily_requirements"] == {
        "minimum_sightseeing_activities": 2, "lunch": True, "dinner": True,
    }
