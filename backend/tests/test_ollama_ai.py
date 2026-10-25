"""Local AI uses mocked loopback calls and isolated migrated databases only."""

import asyncio
from copy import deepcopy
import json
import re
from unittest.mock import AsyncMock

from fastapi import HTTPException
import httpx
import pytest
from pydantic import ValidationError

from app.config import Settings
from app.models import Proposal
from app.services.buddy import openai_reply
from app.services.conversational_ai import converse
from app.services.ollama_ai import local_converse, local_plan, local_reply
from app.services.planning import store_generated_proposal
from app.services.trips import get_owned_trip
from app.schemas.planning import ItineraryPlan
from sqlalchemy import select
from sqlalchemy.orm import Session


URL = "http://127.0.0.1:11434/api/chat"


@pytest.fixture
def settings():
    return Settings(_env_file=None, ai_mode="ollama", openai_api_key=None)


def plan():
    return {"title": "A local Tokyo idea", "summary": "Suggestions with unverified prices and hours.",
            "activities": [{"date": "2027-10-10", "start_time": "10:00", "end_time": "11:00",
                "title": "Asakusa neighborhood walk", "description": "A suggested walk, not a booking.",
                "location": "Asakusa, Tokyo", "estimated_cost": "0.00", "item_type": "activity"}],
            "notes": ["Check hours and transport. No reservation was made."]}


def arguments():
    return {"reply": "Here is an idea to review.", "plan": plan(),
            "requirements": {"minimum_activities": 0, "lunch": False, "dinner": False}}


def response(message=None, *, status=200, done=True, reason="stop"):
    body = {"done": done, "done_reason": reason,
            "message": message or {"role": "assistant", "content": "Try a quiet riverside walk."}}
    return httpx.Response(status, json=body, request=httpx.Request("POST", URL))


def mock(monkeypatch, result=None, error=None):
    post = AsyncMock(return_value=result or response(), side_effect=error)
    monkeypatch.setattr(httpx.AsyncClient, "post", post)
    return post


def test_general_chat_uses_local_loopback_without_a_key_or_cloud_headers(settings, monkeypatch):
    post = mock(monkeypatch)
    messages = [{"role": "user", "content": "Where can we take a quiet walk?"}]

    reply = asyncio.run(openai_reply(messages, None, settings))

    assert reply == "Try a quiet riverside walk."
    post.assert_awaited_once()
    call = post.await_args
    assert call.args == (URL,)
    assert "Authorization" not in call.kwargs.get("headers", {})
    payload = call.kwargs["json"]
    assert payload["stream"] is False and payload["think"] is False
    assert payload["model"] == "qwen3:4b-q4_K_M"
    assert payload["options"]["num_ctx"] == 8192
    assert payload["messages"][-1] == messages[-1]
    assert "tools" not in payload
    assert "OPENAI_API_KEY" not in json.dumps(payload)


def test_local_conversation_lets_model_answer_without_creating_a_draft(settings, monkeypatch):
    data = {"reply": "The park leaves more quiet time.", "plan": None, "requirements": None}
    post = mock(monkeypatch, response({"role": "assistant", "content": json.dumps(data)}))

    turn = asyncio.run(converse([{"role": "user", "content": "Why that park?"}], None, settings,
                               {"destination": "Tokyo", "itinerary_truncated": False}))

    assert turn.plan is None and turn.reply == data["reply"]
    payload = post.await_args.kwargs["json"]
    assert "tools" not in payload
    assert set(payload["format"]["properties"]) == {"reply", "plan", "requirements"}
    assert payload["format"]["additionalProperties"] is False
    post.assert_awaited_once()


def test_schema_guided_local_plan_constrains_dates_times_and_costs(settings, monkeypatch):
    data = arguments()
    post = mock(monkeypatch, response({"role": "assistant", "content": json.dumps(data)}))

    turn = asyncio.run(local_converse([{"role": "user", "content": "Something calmer instead?"}],
        None, settings, {"destination": "Tokyo", "start_date": "2027-10-10", "end_date": "2027-10-11"},
        {"id": "current-draft", "plan": plan()}))

    assert turn.plan.model_dump() == plan()
    assert turn.requirements.minimum_activities == 0
    assert turn.reply == data["reply"]
    schema = post.await_args.kwargs["json"]["format"]
    assert "$ref" not in json.dumps(schema) and "$defs" not in schema
    fields = schema["properties"]["plan"]["anyOf"][0]["properties"]["activities"]["items"]["properties"]
    assert fields["date"]["enum"] == ["2027-10-10", "2027-10-11"]
    assert re.fullmatch(fields["start_time"]["pattern"], "09:00")
    assert not re.fullmatch(fields["start_time"]["pattern"], "9:00")
    assert re.fullmatch(fields["estimated_cost"]["pattern"], "10.50")
    assert not re.fullmatch(fields["estimated_cost"]["pattern"], "NaN")
    assert fields["location"]["maxLength"] == 200
    post.assert_awaited_once()


@pytest.mark.parametrize("kind", ["unknown-tool", "multiple-tools", "extra-action", "malformed-json",
    "flat-tool-arguments", "unpaired-requirements", "empty", "truncated", "unfinished", "wrong-role"])
def test_untrusted_local_responses_never_become_an_action(settings, monkeypatch, kind):
    data = arguments()
    message = {"role": "assistant", "content": json.dumps(data)}
    extra = {}
    if kind in {"unknown-tool", "multiple-tools"}:
        call = {"function": {"name": "approve_booking", "arguments": {}}}
        message["tool_calls"] = [call] if kind == "unknown-tool" else [call, deepcopy(call)]
    elif kind == "extra-action":
        data["approved"] = True
        message["content"] = json.dumps(data)
    elif kind == "malformed-json":
        message["content"] = "{broken"
    elif kind == "flat-tool-arguments":
        message["content"] = json.dumps({"requirements": data["requirements"], "activities": data["plan"]["activities"]})
    elif kind == "unpaired-requirements":
        data["requirements"] = None
        message["content"] = json.dumps(data)
    elif kind == "empty":
        message["content"] = ""
    elif kind == "truncated":
        extra["reason"] = "length"
    elif kind == "unfinished":
        extra["done"] = False
    elif kind == "wrong-role":
        message["role"] = "system"
    post = mock(monkeypatch, response(message, **extra))

    with pytest.raises(HTTPException) as failure:
        asyncio.run(local_converse([{"role": "user", "content": "Make a plan"}], None, settings, {}))
    assert failure.value.status_code == 502
    post.assert_awaited_once()


@pytest.mark.parametrize("unexpected_plan", [False, True])
def test_truncated_saved_schedule_cannot_generate_a_local_plan(settings, monkeypatch, unexpected_plan):
    data = arguments() if unexpected_plan else {"reply": "I can discuss the visible facts.", "plan": None, "requirements": None}
    post = mock(monkeypatch, response({"role": "assistant", "content": json.dumps(data)}))
    call = local_converse([{"role": "user", "content": "What is saved?"}], None,
                          settings, {"itinerary_truncated": True})
    if unexpected_plan:
        with pytest.raises(HTTPException) as failure:
            asyncio.run(call)
        assert failure.value.status_code == 502
    else:
        assert asyncio.run(call).plan is None
    schema = post.await_args.kwargs["json"]["format"]
    assert schema["properties"]["plan"] == {"type": "null"}
    assert schema["properties"]["requirements"] == {"type": "null"}
    assert "tools" not in post.await_args.kwargs["json"]


@pytest.mark.parametrize("status,expected", [(404, 503), (429, 429), (400, 503), (500, 503), (302, 503)])
def test_local_provider_errors_are_clear_and_do_not_expose_raw_response(settings, monkeypatch, status, expected):
    post = mock(monkeypatch, httpx.Response(status, text="private-server-detail", request=httpx.Request("POST", URL)))
    with pytest.raises(HTTPException) as failure:
        asyncio.run(local_reply([{"role": "user", "content": "Hello"}], None, settings))
    assert failure.value.status_code == expected
    assert "private-server-detail" not in str(failure.value.detail)
    post.assert_awaited_once()


@pytest.mark.parametrize("error,expected", [(httpx.ConnectError("private-error"), 503), (httpx.ReadTimeout("private-error"), 504)])
def test_unavailable_or_slow_local_ai_does_not_fall_back_to_paid_provider(settings, monkeypatch, error, expected):
    post = mock(monkeypatch, error=error)
    with pytest.raises(HTTPException) as failure:
        asyncio.run(local_reply([{"role": "user", "content": "Hello"}], None, settings))
    assert failure.value.status_code == expected
    assert "private-error" not in str(failure.value.detail)
    post.assert_awaited_once()


@pytest.mark.parametrize("address", [
    "https://api.ollama.com", "http://example.com:11434", "http://127.0.0.1:11434/remote",
    "http://user:pass@localhost:11434", "http://localhost:11434?remote=true",
    "http://localhost:11434#remote", "http://localhost:99999", "file:///tmp/model",
])
def test_local_endpoint_cannot_be_redirected_to_a_remote_provider(address):
    with pytest.raises(ValidationError, match="loopback HTTP"):
        Settings(_env_file=None, ollama_base_url=address)


@pytest.mark.parametrize("address", ["http://localhost:11434/", "http://127.0.0.1:11434", "http://[::1]:11434"])
def test_loopback_endpoints_are_supported(address):
    assert Settings(_env_file=None, ollama_base_url=address).ollama_base_url == address.rstrip("/")


@pytest.mark.parametrize("model", ["gpt-oss:120b-cloud", "qwen3:cloud"])
def test_cloud_model_tags_are_not_local_free_inference(model):
    with pytest.raises(ValidationError, match="local Ollama"):
        Settings(_env_file=None, ollama_model=model)


@pytest.fixture
def owned_trip(client, application):
    profile = client.post("/api/profiles", json={"display_name": "Local AI test"}).json()
    headers = {"X-Profile-Token": profile["token"]}
    trip = client.post("/api/trips", headers=headers, json={
        "name": "Local Tokyo", "destination": "Tokyo", "departure_location": "Boston",
        "start_date": "2027-10-10", "end_date": "2027-10-10", "travelers": 2,
        "budget": "500.00", "currency": "USD", "status": "planned",
    }).json()
    return trip, headers, profile["profile"]["id"]


def test_direct_local_plan_uses_json_schema_without_sending_owner_id(settings, client, application, owned_trip, monkeypatch):
    trip, _, profile_id = owned_trip
    post = mock(monkeypatch, response({"role": "assistant", "content": json.dumps(plan())}))
    with Session(application.state.database.engine) as session:
        row = get_owned_trip(session, profile_id, trip["id"])
        result = asyncio.run(local_plan(row, "Create a peaceful plan", settings))
    assert result.model_dump() == plan()
    payload = post.await_args.kwargs["json"]
    assert payload["format"]["type"] == "object"
    assert "tools" not in payload
    assert profile_id not in json.dumps(payload)


def test_local_proposal_round_trip_preserves_database_compatibility_and_approval(client, application, owned_trip):
    trip, headers, profile_id = owned_trip
    with Session(application.state.database.engine) as session:
        result = store_generated_proposal(session, profile_id, trip["id"], "Something peaceful", ItineraryPlan(**plan()), "ollama")
        row = session.scalar(select(Proposal).where(Proposal.id == result.id))
        assert row.mode == "openai" and row.payload["provider"] == "ollama"
        assert result.mode == "ollama"
    assert client.get(f"/api/trips/{trip['id']}", headers=headers).json()["itinerary"] == []
    approved = client.post(f"/api/trips/{trip['id']}/proposals/{result.id}/approve", headers=headers)
    assert approved.status_code == 200
    assert approved.json()["proposal"]["mode"] == "ollama"
    assert approved.json()["trip"]["item_count"] == 1
    repeated = client.post(f"/api/trips/{trip['id']}/proposals/{result.id}/approve", headers=headers)
    assert repeated.json()["trip"]["item_count"] == 1
