"""Planning integration tests use isolated migrated fixture databases and mocked AI."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
import json
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient
import httpx
import pytest
from pydantic import SecretStr

from app.main import create_app


@pytest.fixture(autouse=True)
def no_real_provider_calls(monkeypatch):
    """An accidental paid/network request must fail this test, never leave the suite."""
    blocked = AsyncMock(side_effect=AssertionError("Real provider calls are disabled in planning tests"))
    monkeypatch.setattr(httpx.AsyncClient, "post", blocked)
    return blocked


@pytest.fixture
def planning_context(client):
    profile_response = client.post("/api/profiles", json={"display_name": "Planning test traveler"})
    assert profile_response.status_code == 201
    headers = {"X-Profile-Token": profile_response.json()["token"]}
    payload = {
        "name": "A thoughtful Tokyo trip", "destination": "Tokyo", "departure_location": "Columbus",
        "start_date": "2027-05-01", "end_date": "2027-05-05", "travelers": 3,
        "budget": "1200.00", "currency": "USD", "status": "planned",
    }
    response = client.post("/api/trips", json=payload, headers=headers)
    assert response.status_code == 201
    return {"headers": headers, "trip": response.json(), "payload": payload}


@pytest.fixture
def live_planning_settings(application):
    application.state.settings.ai_mode = "openai"
    application.state.settings.openai_api_key = SecretStr("fictional-planning-test-key")
    return application.state.settings


@pytest.fixture
def structured_plan():
    return {
        "title": "A relaxed Tokyo itinerary",
        "summary": "A proposed photography walk each day, leaving room for meals and rest.",
        "activities": [{
            "date": f"2027-05-{day:02d}", "start_time": "09:00", "end_time": "10:00",
            "title": f"Tokyo photography walk, day {day}",
            "description": "A planning suggestion; hours, travel times, and prices are unverified.",
            "location": "Ueno Park, Tokyo", "estimated_cost": "5.00", "item_type": "activity",
        } for day in range(1, 6)],
        "notes": ["All costs are estimates in the trip currency. No reservations are created."],
    }


def proposal_path(context, proposal_id=None, action=None):
    path = f"/api/trips/{context['trip']['id']}/proposals"
    if proposal_id:
        path += f"/{proposal_id}"
    return f"{path}/{action}" if action else path


def generate(client, context, text="Create a relaxed itinerary with photography and food."):
    return client.post(proposal_path(context), json={"request": text}, headers=context["headers"])


def read_trip(client, context):
    response = client.get(f"/api/trips/{context['trip']['id']}", headers=context["headers"])
    assert response.status_code == 200
    return response.json()


def assert_no_items(client, context):
    assert read_trip(client, context)["itinerary"] == []


def provider_response(status=200, output=None, raw_text=None):
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    if raw_text is not None:
        return httpx.Response(status, text=raw_text, request=request)
    payload = {"status": "completed", "output": [{
        "type": "message", "content": [{"type": "output_text", "text": json.dumps(output)}],
    }]}
    return httpx.Response(status, json=payload, request=request)


def mock_provider(monkeypatch, response=None, error=None):
    post = AsyncMock(return_value=response, side_effect=error)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return post


def test_demo_generation_creates_a_structured_pending_proposal_without_applying_it(client, planning_context, no_real_provider_calls):
    response = generate(client, planning_context, "create a itinearary")

    assert response.status_code == 201
    proposal = response.json()
    assert proposal["trip_id"] == planning_context["trip"]["id"]
    assert proposal["status"] == "pending"
    assert proposal["mode"] == "demo"
    assert proposal["currency"] == "USD"
    assert proposal["approved_at"] is None
    assert proposal["activities"]
    assert proposal["title"].strip()
    assert proposal["notes"]
    assert Decimal(proposal["estimated_total"]) == sum(
        (Decimal(item["estimated_cost"]) for item in proposal["activities"]), Decimal("0")
    )
    assert Decimal(proposal["remaining_budget"]) == Decimal("1200.00") - Decimal(proposal["resulting_estimated_total"])
    for item in proposal["activities"]:
        assert "2027-05-01" <= item["date"] <= "2027-05-05"
        assert item["start_time"] < item["end_time"]
    listed = client.get(proposal_path(planning_context), headers=planning_context["headers"])
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == proposal["id"]
    assert client.get(proposal_path(planning_context, proposal["id"]), headers=planning_context["headers"]).json() == proposal
    assert_no_items(client, planning_context)
    no_real_provider_calls.assert_not_awaited()


def test_exact_misspelled_chat_request_generates_a_reviewable_proposal_for_the_selected_trip(client, planning_context):
    response = client.post("/api/buddy/chat", headers=planning_context["headers"], json={
        "messages": [{"role": "user", "content": "create a itinearary"}],
        "feature": None, "trip_id": planning_context["trip"]["id"],
    })

    assert response.status_code == 200
    result = response.json()
    assert result["proposal"]["status"] == "pending"
    assert result["proposal"]["trip_id"] == planning_context["trip"]["id"]
    assert result["proposal"]["activities"]
    assert result["mode"] == "demo"
    assert "can't change" not in result["reply"]
    assert_no_items(client, planning_context)


def test_itinerary_request_without_a_selected_trip_explains_the_prerequisite_honestly(client):
    response = client.post("/api/buddy/chat", json={
        "messages": [{"role": "user", "content": "create a itinearary"}], "feature": None,
    })

    assert response.status_code == 200
    result = response.json()
    assert result.get("proposal") is None
    assert "can't generate or save a full itinerary yet" not in result["reply"]
    assert "trip" in result["reply"].lower()
    assert any(word in result["reply"].lower() for word in ("select", "choose", "save", "create"))


def test_reject_keeps_the_itinerary_unchanged_and_cannot_later_be_approved(client, planning_context):
    proposal = generate(client, planning_context).json()

    response = client.post(proposal_path(planning_context, proposal["id"], "reject"), headers=planning_context["headers"])

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"
    assert_no_items(client, planning_context)
    later = client.post(proposal_path(planning_context, proposal["id"], "approve"), headers=planning_context["headers"])
    assert later.status_code == 409
    assert_no_items(client, planning_context)


def test_approval_appends_real_persisted_activities_and_survives_application_reopen(client, application, planning_context):
    proposal = generate(client, planning_context).json()

    response = client.post(proposal_path(planning_context, proposal["id"], "approve"), headers=planning_context["headers"])

    assert response.status_code == 200
    result = response.json()
    assert result["proposal"]["status"] == "approved"
    assert result["proposal"]["approved_at"] is not None
    assert len(result["trip"]["itinerary"]) == len(proposal["activities"])
    assert all(item["status"] == "planned" for item in result["trip"]["itinerary"])
    assert result["trip"]["estimated_total"] == proposal["resulting_estimated_total"]
    with TestClient(create_app(application.state.settings)) as reopened:
        persisted = read_trip(reopened, planning_context)
        saved = reopened.get(proposal_path(planning_context, proposal["id"]), headers=planning_context["headers"])
    assert persisted["itinerary"] == result["trip"]["itinerary"]
    assert saved.json()["status"] == "approved"


def test_repeated_approval_is_idempotent(client, planning_context):
    proposal = generate(client, planning_context).json()
    path = proposal_path(planning_context, proposal["id"], "approve")

    first = client.post(path, headers=planning_context["headers"])
    second = client.post(path, headers=planning_context["headers"])

    assert first.status_code == second.status_code == 200
    assert second.json()["trip"]["itinerary"] == first.json()["trip"]["itinerary"]
    assert read_trip(client, planning_context)["item_count"] == len(proposal["activities"])


def test_concurrent_approval_cannot_execute_the_same_proposal_twice(client, planning_context):
    proposal = generate(client, planning_context).json()
    path = proposal_path(planning_context, proposal["id"], "approve")
    with ThreadPoolExecutor(max_workers=2) as executor:
        pending = [executor.submit(client.post, path, headers=planning_context["headers"]) for _ in range(2)]
        results = [request.result() for request in pending]

    assert [response.status_code for response in results] == [200, 200]
    assert read_trip(client, planning_context)["item_count"] == len(proposal["activities"])


def test_manual_trip_edit_makes_a_proposal_stale_instead_of_applying_old_data(client, planning_context):
    proposal = generate(client, planning_context).json()
    updated = client.put(f"/api/trips/{planning_context['trip']['id']}", headers=planning_context["headers"],
                         json={**planning_context["payload"], "budget": "1300.00"})
    assert updated.status_code == 200

    response = client.post(proposal_path(planning_context, proposal["id"], "approve"), headers=planning_context["headers"])

    assert response.status_code == 409
    assert client.get(proposal_path(planning_context, proposal["id"]), headers=planning_context["headers"]).json()["status"] == "stale"
    assert_no_items(client, planning_context)
    assert read_trip(client, planning_context)["budget"] == "1300.00"


def test_new_manual_activity_makes_an_existing_proposal_stale(client, planning_context):
    proposal = generate(client, planning_context).json()
    item = {
        "date": "2027-05-02", "start_time": "20:00", "end_time": "21:00", "title": "An existing dinner",
        "description": "User-entered planning estimate", "location": "Tokyo", "estimated_cost": "12.50",
        "item_type": "food", "status": "planned",
    }
    created = client.post(f"/api/trips/{planning_context['trip']['id']}/itinerary", headers=planning_context["headers"], json=item)
    assert created.status_code == 201

    response = client.post(proposal_path(planning_context, proposal["id"], "approve"), headers=planning_context["headers"])

    assert response.status_code == 409
    assert read_trip(client, planning_context)["itinerary"] == created.json()["itinerary"]


def test_generation_and_approval_preserve_existing_activities_and_avoid_conflicts(client, planning_context):
    item = {
        "date": "2027-05-01", "start_time": "09:00", "end_time": "10:00", "title": "My original morning walk",
        "description": "Do not replace this saved activity", "location": "Ueno Park", "estimated_cost": "20.00",
        "item_type": "activity", "status": "planned",
    }
    created = client.post(f"/api/trips/{planning_context['trip']['id']}/itinerary", headers=planning_context["headers"], json=item)
    assert created.status_code == 201
    original = created.json()["itinerary"][0]

    proposal_response = generate(client, planning_context)
    assert proposal_response.status_code == 201
    proposal = proposal_response.json()
    for activity in proposal["activities"]:
        assert not (activity["date"] == original["date"] and activity["start_time"] < original["end_time"]
                    and activity["end_time"] > original["start_time"])
    assert Decimal(proposal["resulting_estimated_total"]) == Decimal("20.00") + Decimal(proposal["estimated_total"])
    approved = client.post(proposal_path(planning_context, proposal["id"], "approve"), headers=planning_context["headers"])
    assert approved.status_code == 200
    assert next(activity for activity in approved.json()["trip"]["itinerary"] if activity["id"] == original["id"]) == original
    assert approved.json()["trip"]["item_count"] == len(proposal["activities"]) + 1


def test_approving_one_proposal_invalidates_an_older_draft(client, planning_context):
    older = generate(client, planning_context).json()
    newer = generate(client, planning_context).json()
    approved = client.post(proposal_path(planning_context, newer["id"], "approve"), headers=planning_context["headers"])
    assert approved.status_code == 200

    stale = client.post(proposal_path(planning_context, older["id"], "approve"), headers=planning_context["headers"])

    assert stale.status_code == 409
    assert read_trip(client, planning_context)["itinerary"] == approved.json()["trip"]["itinerary"]


def test_proposals_are_scoped_to_the_owning_profile_and_trip(client, planning_context):
    proposal = generate(client, planning_context).json()
    outsider = client.post("/api/profiles", json={"display_name": "Another traveler"}).json()
    outsider_headers = {"X-Profile-Token": outsider["token"]}
    for headers, expected in [({}, 401), (outsider_headers, 404)]:
        assert client.post(proposal_path(planning_context), json={"request": "Make a plan"}, headers=headers).status_code == expected
        assert client.get(proposal_path(planning_context), headers=headers).status_code == expected
        assert client.get(proposal_path(planning_context, proposal["id"]), headers=headers).status_code == expected
        assert client.post(proposal_path(planning_context, proposal["id"], "approve"), headers=headers).status_code == expected
        assert client.post(proposal_path(planning_context, proposal["id"], "reject"), headers=headers).status_code == expected
    another_trip = client.post("/api/trips", json=planning_context["payload"], headers=planning_context["headers"]).json()
    wrong = {**planning_context, "trip": another_trip}
    assert client.get(proposal_path(wrong, proposal["id"]), headers=planning_context["headers"]).status_code == 404
    assert client.post(proposal_path(wrong, proposal["id"], "approve"), headers=planning_context["headers"]).status_code == 404
    assert_no_items(client, planning_context)


@pytest.mark.parametrize("body", [
    {"request": ""}, {"request": "   "}, {"request": "x" * 2001},
    {"request": "Make a plan", "mode": "openai"},
    {"request": "Make a plan", "approved": True},
])
def test_generation_request_validation_cannot_inject_execution_or_provider_mode(client, planning_context, body):
    response = client.post(proposal_path(planning_context), json=body, headers=planning_context["headers"])
    assert response.status_code == 422
    assert client.get(proposal_path(planning_context), headers=planning_context["headers"]).json() == []
    assert_no_items(client, planning_context)


def test_demo_does_not_invent_a_tokyo_plan_for_an_unsupported_destination(client, planning_context, no_real_provider_calls):
    changed = client.put(f"/api/trips/{planning_context['trip']['id']}", headers=planning_context["headers"],
                         json={**planning_context["payload"], "destination": "Paris"})
    assert changed.status_code == 200

    response = generate(client, planning_context)

    assert response.status_code == 503
    assert "Tokyo" in response.json()["detail"]
    assert_no_items(client, planning_context)
    no_real_provider_calls.assert_not_awaited()


def test_live_generation_uses_strict_structured_outputs_and_keeps_ai_as_a_pending_proposal(
    client, planning_context, live_planning_settings, structured_plan, monkeypatch,
):
    post = mock_provider(monkeypatch, provider_response(output=structured_plan))

    response = generate(client, planning_context)

    assert response.status_code == 201
    proposal = response.json()
    assert proposal["mode"] == "openai"
    assert proposal["status"] == "pending"
    assert proposal["activities"] == structured_plan["activities"]
    assert proposal["estimated_total"] == "25.00"
    assert_no_items(client, planning_context)
    post.assert_awaited_once()
    request = post.await_args
    assert request.args[0] == "https://api.openai.com/v1/responses"
    assert request.kwargs["headers"]["Authorization"] == "Bearer fictional-planning-test-key"
    payload = request.kwargs["json"]
    assert payload["model"] == live_planning_settings.openai_model
    assert payload["store"] is False
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert "Tokyo" in json.dumps(payload)
    assert "fictional-planning-test-key" not in json.dumps(payload)
    assert "fictional-planning-test-key" not in response.text


def test_missing_live_key_is_an_explicit_error_without_demo_fallback(client, application, planning_context, no_real_provider_calls):
    application.state.settings.ai_mode = "openai"
    application.state.settings.openai_api_key = None

    response = generate(client, planning_context)

    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]
    assert "activities" not in response.json()
    assert client.get(proposal_path(planning_context), headers=planning_context["headers"]).json() == []
    assert_no_items(client, planning_context)
    no_real_provider_calls.assert_not_awaited()


@pytest.mark.parametrize("status,expected", [(401, 503), (403, 503), (429, 429), (400, 502), (500, 502)])
def test_provider_errors_never_expose_details_or_silently_create_demo_plans(
    client, planning_context, live_planning_settings, monkeypatch, caplog, status, expected,
):
    post = mock_provider(monkeypatch, provider_response(status=status, raw_text="private-provider-detail"))

    response = generate(client, planning_context)

    assert response.status_code == expected
    assert "private-provider-detail" not in response.text + caplog.text
    assert "fictional-planning-test-key" not in response.text + caplog.text
    assert client.get(proposal_path(planning_context), headers=planning_context["headers"]).json() == []
    assert_no_items(client, planning_context)
    post.assert_awaited_once()


@pytest.mark.parametrize("error,expected", [
    (httpx.ReadTimeout("private-provider-timeout"), 504),
    (httpx.ConnectError("private-provider-network"), 502),
])
def test_provider_network_failure_leaves_the_trip_unchanged(
    client, planning_context, live_planning_settings, monkeypatch, error, expected,
):
    mock_provider(monkeypatch, error=error)

    response = generate(client, planning_context)

    assert response.status_code == expected
    assert "private-provider" not in response.text
    assert_no_items(client, planning_context)


@pytest.mark.parametrize("kind", ["malformed-json", "missing-title", "extra-action", "invalid-cost", "outside-trip", "overlap", "empty-plan", "over-budget"])
def test_invalid_structured_provider_plans_never_become_approved_or_saved_activities(
    client, planning_context, live_planning_settings, structured_plan, monkeypatch, kind,
):
    plan = deepcopy(structured_plan)
    if kind == "missing-title":
        del plan["title"]
    elif kind == "extra-action":
        plan["execute_booking"] = True
    elif kind == "invalid-cost":
        plan["activities"][0]["estimated_cost"] = "NaN"
    elif kind == "outside-trip":
        plan["activities"][0]["date"] = "2027-05-10"
    elif kind == "overlap":
        plan["activities"].append({**plan["activities"][0], "title": "A conflicting suggestion"})
    elif kind == "empty-plan":
        plan["activities"] = []
    elif kind == "over-budget":
        plan["activities"][0]["estimated_cost"] = "1300.00"
    response = provider_response(output=plan)
    if kind == "malformed-json":
        response = provider_response(output=plan)
        response = httpx.Response(200, json={"status": "completed", "output": [{
            "type": "message", "content": [{"type": "output_text", "text": "not valid JSON"}],
        }]}, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    mock_provider(monkeypatch, response)

    rejected = generate(client, planning_context)

    expected_status = {
        "invalid-cost": 422, "outside-trip": 422, "overlap": 409, "empty-plan": 422, "over-budget": 422,
    }.get(kind, 502)
    assert rejected.status_code == expected_status
    assert client.get(proposal_path(planning_context), headers=planning_context["headers"]).json() == []
    assert_no_items(client, planning_context)


@pytest.mark.parametrize("payload", [
    {"status": "incomplete", "output": []},
    {"status": "completed", "output": [{"type": "message", "content": [{"type": "refusal", "refusal": "Cannot provide this plan"}]}]},
])
def test_incomplete_or_refused_provider_output_never_becomes_a_demo_or_saved_plan(
    client, planning_context, live_planning_settings, monkeypatch, payload,
):
    response = httpx.Response(200, json=payload, request=httpx.Request("POST", "https://api.openai.com/v1/responses"))
    mock_provider(monkeypatch, response)

    result = generate(client, planning_context)

    assert result.status_code == 502
    assert client.get(proposal_path(planning_context), headers=planning_context["headers"]).json() == []
    assert_no_items(client, planning_context)
