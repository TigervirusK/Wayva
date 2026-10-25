"""Semantic local-plan correction is bounded, read-only, and never a cloud call."""

import asyncio
from copy import deepcopy
from datetime import date
from decimal import Decimal
import json
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import HTTPException
import httpx
import pytest

from app.config import Settings
from app.models import Trip, utc_now
from app.services import ollama_ai


URL = "http://127.0.0.1:11434/api/chat"


@pytest.fixture
def settings():
    return Settings(_env_file=None, ai_mode="ollama", openai_api_key=None)


def context():
    return {"destination": "Tokyo", "start_date": "2027-10-10", "end_date": "2027-10-10",
            "travelers": 2, "currency": "USD", "budget": "300.00", "itinerary": []}


def envelope():
    return {"reply": "Review this full day before saving.", "requirements": {
        "minimum_activities": 2, "lunch": True, "dinner": True}, "plan": {
        "title": "A full Tokyo day", "summary": "A proposed day with estimated prices and unverified hours.",
        "notes": ["Check hours and transport; these are suggestions, not reservations."],
        "activities": [{"date": "2027-10-10", "start_time": start, "end_time": end,
            "title": title, "description": "Unverified local travel suggestion.", "location": location,
            "estimated_cost": cost, "item_type": kind} for title, start, end, location, cost, kind in [
                ("Morning park walk", "09:00", "10:00", "Ueno Park, Tokyo", "0.00", "activity"),
                ("Lunch at a local restaurant", "12:00", "13:00", "Asakusa Mugitoro, Tokyo", "40.00", "food"),
                ("Afternoon river walk", "14:00", "15:00", "Sumida Park, Tokyo", "0.00", "activity"),
                ("Dinner at a noodle shop", "18:00", "19:00", "AFURI Harajuku, Tokyo", "50.00", "food"),
            ]],
    }}


def response(value):
    return httpx.Response(200, json={"done": True, "done_reason": "stop", "message": {
        "role": "assistant", "content": json.dumps(value)}}, request=httpx.Request("POST", URL))


def mock_responses(monkeypatch, *values):
    post = AsyncMock(side_effect=[response(value) for value in values])
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return post


def run(settings, snapshot):
    return asyncio.run(ollama_ai.local_converse([{"role": "user", "content": "Give us a full day with sights and meal places."}],
                                               None, settings, snapshot))


@pytest.mark.parametrize("problem", ["overlap", "missing-meals", "budget"])
def test_semantic_invalid_first_draft_is_corrected_with_precise_feedback(settings, monkeypatch, problem):
    first, fixed = envelope(), envelope()
    if problem == "overlap":
        first["plan"]["activities"][2].update(start_time="09:30", end_time="10:30")
    elif problem == "missing-meals":
        first["plan"]["activities"] = [item for item in first["plan"]["activities"] if item["item_type"] != "food"]
        first["plan"]["notes"].append("Lunch and dinner ideas are only in these notes.")
    else:
        first["plan"]["activities"][1]["estimated_cost"] = "400.00"
    post = mock_responses(monkeypatch, first, fixed)
    snapshot = context()
    before = deepcopy(snapshot)

    result = run(settings, snapshot)

    assert result.plan.model_dump() == fixed["plan"]
    assert snapshot == before
    assert post.await_count == 2
    feedback = json.loads(post.await_args_list[1].kwargs["json"]["messages"][-1]["content"])
    assert feedback["daily_requirements_to_preserve"] == first["requirements"]
    if problem == "overlap":
        assert "Morning park walk" in feedback["validation_feedback"]
        assert "Afternoon river walk" in feedback["validation_feedback"]
        assert "09:30-10:30" in feedback["validation_feedback"]
    elif problem == "missing-meals":
        assert "lunch" in feedback["validation_feedback"]
    else:
        assert "budget" in feedback["validation_feedback"]
    assert all(call.args == (URL,) for call in post.await_args_list)


def test_corrections_are_bounded_and_cannot_weaken_requested_meals(settings, monkeypatch):
    bad = envelope()
    bad["plan"]["activities"] = [item for item in bad["plan"]["activities"] if item["item_type"] != "food"]
    weakened = deepcopy(bad)
    weakened["requirements"] = {"minimum_activities": 0, "lunch": False, "dinner": False}
    post = mock_responses(monkeypatch, bad, weakened, weakened)
    snapshot = context()
    before = deepcopy(snapshot)

    with pytest.raises(HTTPException) as failure:
        run(settings, snapshot)

    assert failure.value.status_code == 422
    assert "lunch" in failure.value.detail
    assert post.await_count == 3
    assert snapshot == before


def test_ordinary_reply_needs_no_validation_correction_request(settings, monkeypatch):
    post = mock_responses(monkeypatch, {"reply": "The park leaves time to relax.", "plan": None, "requirements": None})
    result = run(settings, context())
    assert result.plan is None
    post.assert_awaited_once()


def test_invalid_action_fields_fail_immediately_without_repair(settings, monkeypatch):
    bad = envelope()
    bad["approved"] = True
    post = mock_responses(monkeypatch, bad)
    with pytest.raises(HTTPException) as failure:
        run(settings, context())
    assert failure.value.status_code == 502
    post.assert_awaited_once()


def test_total_planning_deadline_stops_before_another_provider_call(settings, monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(ollama_ai, "monotonic", lambda: clock[0])
    bad = envelope()
    bad["plan"]["activities"][2].update(start_time="09:30", end_time="10:30")

    async def exhausted_budget(*_args, **_kwargs):
        clock[0] = 241.0
        return response(bad)

    post = AsyncMock(side_effect=exhausted_budget)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    with pytest.raises(HTTPException) as failure:
        run(settings, context())
    assert failure.value.status_code == 504
    post.assert_awaited_once()


def test_correction_preserves_existing_saved_activity_in_context(settings, monkeypatch):
    snapshot = context()
    saved = {**envelope()["plan"]["activities"][0], "title": "My saved museum visit",
             "start_time": "10:00", "end_time": "11:00", "status": "planned"}
    snapshot["itinerary"] = [saved]
    before = deepcopy(snapshot)
    bad, fixed = envelope(), envelope()
    bad["plan"]["activities"][2].update(start_time="10:00", end_time="11:00")
    post = mock_responses(monkeypatch, bad, fixed)

    result = run(settings, snapshot)

    assert result.plan is not None and snapshot == before
    feedback = post.await_args_list[1].kwargs["json"]["messages"][-1]["content"]
    assert "My saved museum visit" in feedback
    assert "10:00-11:00" in feedback


def test_direct_local_plan_uses_the_same_semantic_correction_without_database_writes(settings, monkeypatch):
    bad, fixed = envelope()["plan"], envelope()["plan"]
    bad["activities"][2].update(start_time="09:30", end_time="10:30")
    post = mock_responses(monkeypatch, bad, fixed)
    timestamp = utc_now()
    trip = Trip(id=str(uuid4()), owner_id=str(uuid4()), name="Synthetic local test", destination="Tokyo",
                departure_location="Boston", start_date=date(2027, 10, 10), end_date=date(2027, 10, 10),
                travelers=2, budget=Decimal("300.00"), currency="USD", status="planned",
                created_at=timestamp, updated_at=timestamp, itinerary=[])

    result = asyncio.run(ollama_ai.local_plan(trip, "Two activities each day with lunch and dinner", settings))

    assert result.model_dump() == fixed
    assert trip.itinerary == []
    assert post.await_count == 2
    assert "overlaps" in post.await_args_list[1].kwargs["json"]["messages"][-1]["content"]
