"""Natural live conversation chooses reviewed tools; all provider calls are mocked."""

import asyncio
from copy import deepcopy
import json
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from pydantic import SecretStr
from app.services.conversational_ai import converse


PROVIDER_URL = "https://api.openai.com/v1/responses"
FICTIONAL_KEY = "fictional-natural-chat-key-not-a-real-secret"


@pytest.fixture(autouse=True)
def block_real_provider(monkeypatch):
    post = AsyncMock(side_effect=AssertionError("Natural-chat tests cannot call a live provider"))
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return post


@pytest.fixture
def natural_context(client, application):
    created = client.post("/api/profiles", json={"display_name": "Natural conversation test"})
    assert created.status_code == 201
    headers = {"X-Profile-Token": created.json()["token"]}
    fields = {
        "name": "A Tokyo day", "destination": "Tokyo", "departure_location": "Boston",
        "start_date": "2027-10-10", "end_date": "2027-10-10", "travelers": 2,
        "budget": "2000.00", "currency": "USD", "status": "planned",
    }
    response = client.post("/api/trips", json=fields, headers=headers)
    assert response.status_code == 201
    application.state.settings.ai_mode = "openai"
    application.state.settings.openai_api_key = SecretStr(FICTIONAL_KEY)
    trip = response.json()
    return {"trip": trip, "fields": fields, "headers": headers,
            "path": f"/api/trips/{trip['id']}", "application": application}


def example_plan():
    return {
        "title": "A quieter day with affordable meals",
        "summary": "A draft with neighborhood walks and meal ideas; prices and hours are unverified.",
        "activities": [{
            "date": "2027-10-10", "start_time": start, "end_time": end,
            "title": title, "description": "An unverified travel suggestion, not a reservation.",
            "location": location, "estimated_cost": cost, "item_type": kind,
        } for title, start, end, location, cost, kind in [
            ("Asakusa photography walk", "09:30", "10:30", "Asakusa, Tokyo", "0.00", "activity"),
            ("Lunch at Asakusa Mugitoro", "12:00", "13:00", "Asakusa Mugitoro, Kaminarimon, Tokyo", "40.00", "food"),
            ("Sumida riverside stroll", "14:00", "15:00", "Sumida Park, Tokyo", "0.00", "activity"),
            ("Dinner at a neighborhood noodle shop", "18:00", "19:00", "AFURI Harajuku, Sendagaya, Tokyo", "50.00", "food"),
        ]],
        "notes": ["Estimated group costs only; check transport, opening hours and dietary suitability."],
    }


def tool_output(arguments=None, name="propose_itinerary"):
    if arguments is None:
        arguments = {
            "reply": "Here is a calmer draft with cheaper meal ideas. Review it before saving.",
            "plan": example_plan(),
            "requirements": {"minimum_activities": 2, "lunch": True, "dinner": True},
        }
    return {"type": "function_call", "name": name, "call_id": "call_natural_test",
            "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments)}


def mock_provider(monkeypatch, *output, status=200, raw_body=None):
    if raw_body is None:
        response = httpx.Response(status, json={"status": "completed", "output": list(output)},
                                  request=httpx.Request("POST", PROVIDER_URL))
    else:
        response = httpx.Response(status, text=raw_body, request=httpx.Request("POST", PROVIDER_URL))
    post = AsyncMock(return_value=response)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return post


def text_output(text):
    return {"type": "message", "content": [{"type": "output_text", "text": text}]}


def chat(client, context, content, *, history=None, headers=None, selected=True):
    payload = {"messages": history or [{"role": "user", "content": content}]}
    if selected:
        payload["trip_id"] = context["trip"]["id"]
    return client.post("/api/buddy/chat", json=payload,
                       headers=context["headers"] if headers is None else headers)


def saved_trip(client, context):
    response = client.get(context["path"], headers=context["headers"])
    assert response.status_code == 200
    return response.json()


def proposals(client, context):
    response = client.get(f"{context['path']}/proposals", headers=context["headers"])
    assert response.status_code == 200
    return response.json()


def seed_demo_draft(client, context):
    settings = context["application"].state.settings
    settings.ai_mode = "demo"
    try:
        response = client.post(f"{context['path']}/proposals", headers=context["headers"],
                               json={"request": "Create an itinerary"})
        assert response.status_code == 201
        return response.json()
    finally:
        settings.ai_mode = "openai"


@pytest.mark.parametrize("message", [
    "That's too pricey, something calmer instead please",
    "nah, not feeling those, what else have you got?",
    "more of that vibe but with less walking",
])
def test_model_can_propose_for_followups_without_drafting_keywords(client, natural_context, monkeypatch, message):
    post = mock_provider(monkeypatch, tool_output())
    before = saved_trip(client, natural_context)

    response = chat(client, natural_context, message)

    assert response.status_code == 200
    proposal = response.json()["proposal"]
    assert proposal["status"] == "pending"
    assert proposal["mode"] == "openai"
    assert proposal["request"] == message
    assert proposal["activities"] == example_plan()["activities"]
    assert saved_trip(client, natural_context) == before
    post.assert_awaited_once()
    payload = post.await_args.kwargs["json"]
    assert payload["store"] is False
    assert message in json.dumps(payload)
    assert any(tool.get("name") == "propose_itinerary" for tool in payload["tools"])
    assert natural_context["headers"]["X-Profile-Token"] not in json.dumps(payload)
    assert natural_context["trip"]["owner_id"] not in json.dumps(payload)
    assert FICTIONAL_KEY not in response.text


@pytest.mark.parametrize("unexpected_tool", [False, True])
def test_truncated_trip_context_allows_factual_chat_but_not_a_planning_tool(
    natural_context, monkeypatch, unexpected_tool,
):
    post = mock_provider(monkeypatch, tool_output() if unexpected_tool else text_output("I can discuss the visible saved facts."))
    call = converse(
        [{"role": "user", "content": "What can we do?"}], None,
        natural_context["application"].state.settings,
        {"destination": "Tokyo", "itinerary_truncated": True},
    )
    if unexpected_tool:
        with pytest.raises(HTTPException) as failure:
            asyncio.run(call)
        assert failure.value.status_code == 502
    else:
        assert asyncio.run(call).plan is None
    assert "tools" not in post.await_args.kwargs["json"]


def test_model_can_answer_an_idea_question_without_being_forced_to_create_a_card(client, natural_context, monkeypatch):
    answer = "The river walk leaves more quiet time between meals. Would you prefer a park instead?"
    post = mock_provider(monkeypatch, text_output(answer))
    before = saved_trip(client, natural_context)

    response = chat(client, natural_context, "Why did you suggest that restaurant?")

    assert response.status_code == 200
    assert response.json()["reply"] == answer
    assert response.json()["proposal"] is None
    assert proposals(client, natural_context) == []
    assert saved_trip(client, natural_context) == before
    post.assert_awaited_once()


def test_valid_draft_and_conversation_are_supplied_for_a_revision_and_old_draft_cannot_be_saved(
    client, natural_context, monkeypatch,
):
    original = seed_demo_draft(client, natural_context)
    post = mock_provider(monkeypatch, tool_output())
    history = [
        {"role": "user", "content": "We prefer quiet walks and inexpensive food."},
        {"role": "assistant", "content": "We can keep the day relaxed."},
        {"role": "user", "content": "That dinner feels too expensive. Something cheaper?"},
    ]
    before = saved_trip(client, natural_context)

    response = chat(client, natural_context, history[-1]["content"], history=history)

    assert response.status_code == 200
    newer = response.json()["proposal"]
    assert newer["id"] != original["id"] and newer["status"] == "pending"
    encoded = json.dumps(post.await_args.kwargs["json"])
    assert original["id"] in encoded
    assert original["title"] in encoded
    assert history[0]["content"] in encoded
    assert saved_trip(client, natural_context) == before
    previous = client.get(f"{natural_context['path']}/proposals/{original['id']}",
                          headers=natural_context["headers"]).json()
    assert previous["status"] == "rejected"
    assert previous["superseded_by"] == newer["id"]
    obsolete_approval = client.post(f"{natural_context['path']}/proposals/{original['id']}/approve",
                                    headers=natural_context["headers"])
    assert obsolete_approval.status_code == 409
    assert saved_trip(client, natural_context) == before
    approved = client.post(f"{natural_context['path']}/proposals/{newer['id']}/approve",
                           headers=natural_context["headers"])
    assert approved.status_code == 200
    assert approved.json()["trip"]["item_count"] == len(newer["activities"])
    repeated = client.post(f"{natural_context['path']}/proposals/{newer['id']}/approve",
                           headers=natural_context["headers"])
    assert repeated.status_code == 200
    assert repeated.json()["trip"]["itinerary"] == approved.json()["trip"]["itinerary"]


@pytest.mark.parametrize("old_state", ["stale", "approved", "foreign"])
def test_only_a_current_owned_pending_draft_enters_model_context(client, natural_context, monkeypatch, old_state):
    original = seed_demo_draft(client, natural_context)
    selected_context = natural_context
    if old_state == "stale":
        updated = client.put(natural_context["path"], headers=natural_context["headers"],
                             json={**natural_context["fields"], "budget": "2100.00"})
        assert updated.status_code == 200
    elif old_state == "approved":
        assert client.post(f"{natural_context['path']}/proposals/{original['id']}/approve",
                           headers=natural_context["headers"]).status_code == 200
    else:
        other = client.post("/api/trips", headers=natural_context["headers"],
                            json={**natural_context["fields"], "name": "A different owned trip"})
        assert other.status_code == 201
        selected_context = {**natural_context, "trip": other.json(), "path": f"/api/trips/{other.json()['id']}"}
    post = mock_provider(monkeypatch, text_output("We can talk through a quieter option."))

    response = chat(client, selected_context, "Can we talk through the options?")

    assert response.status_code == 200
    assert response.json()["proposal"] is None
    assert original["id"] not in json.dumps(post.await_args.kwargs["json"])


@pytest.mark.parametrize("kind", ["malformed-json", "unknown-tool", "multiple-tools", "extra-id", "extra-approval", "invalid-requirements"])
def test_untrusted_or_ambiguous_tool_calls_never_create_proposals_or_change_the_trip(
    client, natural_context, monkeypatch, kind,
):
    output = tool_output()
    arguments = json.loads(output["arguments"])
    if kind == "malformed-json":
        output["arguments"] = "not valid JSON"
    elif kind == "unknown-tool":
        output["name"] = "save_trip"
    elif kind == "extra-id":
        arguments["trip_id"] = natural_context["trip"]["id"]
        output["arguments"] = json.dumps(arguments)
    elif kind == "extra-approval":
        arguments["approved"] = True
        output["arguments"] = json.dumps(arguments)
    elif kind == "invalid-requirements":
        arguments["requirements"]["minimum_activities"] = 7
        output["arguments"] = json.dumps(arguments)
    outputs = [output, deepcopy(output)] if kind == "multiple-tools" else [output]
    mock_provider(monkeypatch, *outputs)
    before = saved_trip(client, natural_context)

    response = chat(client, natural_context, "Could it be a little different?")

    assert response.status_code == 502
    assert "proposal" not in response.json()
    assert proposals(client, natural_context) == []
    assert saved_trip(client, natural_context) == before


@pytest.mark.parametrize("kind,expected", [("over-budget", 422), ("outside-dates", 422), ("overlap", 409)])
def test_model_decisions_still_obey_backend_budget_dates_and_schedule(client, natural_context, monkeypatch, kind, expected):
    output = tool_output()
    arguments = json.loads(output["arguments"])
    activities = arguments["plan"]["activities"]
    if kind == "over-budget":
        activities[1]["estimated_cost"] = "9999.00"
    elif kind == "outside-dates":
        activities[0]["date"] = "2027-10-11"
    else:
        activities[2].update(start_time="09:30", end_time="10:30")
    mock_provider(monkeypatch, tool_output(arguments))
    before = saved_trip(client, natural_context)

    response = chat(client, natural_context, "That sounds nice, another version?")

    assert response.status_code == expected
    assert proposals(client, natural_context) == []
    assert saved_trip(client, natural_context) == before


def test_trip_ownership_is_checked_before_any_model_request(client, natural_context, block_real_provider):
    outsider = client.post("/api/profiles", json={"display_name": "Another test traveler"}).json()
    assert chat(client, natural_context, "Something calmer?", headers={}).status_code == 401
    assert chat(client, natural_context, "Something calmer?",
                headers={"X-Profile-Token": outsider["token"]}).status_code == 404
    block_real_provider.assert_not_awaited()
    assert proposals(client, natural_context) == []


def test_general_chat_has_no_proposal_tool_and_cannot_execute_a_provider_tool_call(client, natural_context, monkeypatch):
    post = mock_provider(monkeypatch, tool_output())
    before = saved_trip(client, natural_context)

    response = chat(client, natural_context, "Something calmer?", selected=False)

    assert response.status_code == 502
    assert "tools" not in post.await_args.kwargs["json"]
    assert proposals(client, natural_context) == []
    assert saved_trip(client, natural_context) == before


def test_invalid_live_key_returns_private_setup_guidance_without_demo_or_partial_draft(
    client, natural_context, monkeypatch, caplog,
):
    original = seed_demo_draft(client, natural_context)
    mock_provider(monkeypatch, status=401, raw_body="private-provider-body-with-credential")
    before = saved_trip(client, natural_context)

    response = chat(client, natural_context, "Could that be cheaper?")

    assert response.status_code == 503
    assert "configure_ai.py" in response.json()["detail"]
    assert "proposal" not in response.json()
    assert FICTIONAL_KEY not in response.text + caplog.text
    assert "private-provider-body-with-credential" not in response.text + caplog.text
    current = proposals(client, natural_context)
    assert len(current) == 1 and current[0]["id"] == original["id"]
    assert current[0]["status"] == "pending"
    assert saved_trip(client, natural_context) == before


def test_a_trip_edit_during_ai_generation_cannot_persist_a_stale_revision(client, natural_context, monkeypatch):
    original = seed_demo_draft(client, natural_context)

    async def provider_after_trip_edit(*_args, **_kwargs):
        changed = await asyncio.to_thread(
            client.put, natural_context["path"], headers=natural_context["headers"],
            json={**natural_context["fields"], "budget": "1900.00"},
        )
        assert changed.status_code == 200
        return httpx.Response(200, json={"status": "completed", "output": [tool_output()]},
                              request=httpx.Request("POST", PROVIDER_URL))

    post = AsyncMock(side_effect=provider_after_trip_edit)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)

    response = chat(client, natural_context, "Something calmer instead?")

    assert response.status_code == 409
    assert saved_trip(client, natural_context)["budget"] == "1900.00"
    assert saved_trip(client, natural_context)["itinerary"] == []
    current = proposals(client, natural_context)
    assert len(current) == 1 and current[0]["id"] == original["id"]
    post.assert_awaited_once()
