"""Typed, bounded conversation. This API never executes travel actions."""

from typing import Annotated, Literal
from uuid import UUID

import httpx

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.services.buddy import guided_demo_reply, openai_reply, wants_itinerary_proposal, has_itinerary_word
from app.services.conversational_ai import converse
from app.schemas.planning import ProposalResponse
from app.services.planning import fingerprint, generate_proposal, latest_pending_draft, store_generated_proposal
from app.database import get_db
from app.services.trips import get_owned_trip, require_profile, serialize_trip
from app.services.rescue import buddy_context
from app.services.travel_quality import constraints_for, reference_context, trip_facts
from sqlalchemy.orm import Session

MAX_MESSAGE_LENGTH = 2000
FeatureName = Literal["dream", "memory", "rescue", "sidequest", "harmony", "split"]
MessageContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_MESSAGE_LENGTH)
]

router = APIRouter(tags=["Travel Buddy"])


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: MessageContent


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    messages: list[ChatMessage] = Field(min_length=1, max_length=20)
    feature: FeatureName | None = None
    trip_id: UUID | None = None

    @model_validator(mode="after")
    def validate_history(self):
        if self.messages[-1].role != "user":
            raise ValueError("The final message must be from the user.")
        if sum(len(message.content) for message in self.messages) > 12000:
            raise ValueError("Conversation context must be at most 12000 characters.")
        return self


class BuddyConfig(BaseModel):
    mode: Literal["demo", "openai", "ollama"]
    name: Literal["Way"] = "Way"
    max_message_length: int = MAX_MESSAGE_LENGTH
    ai_ready: bool
    setup_required: bool


class ChatResponse(BaseModel):
    reply: str
    mode: Literal["demo", "openai", "ollama"]
    proposal: ProposalResponse | None = None


@router.get("/config", response_model=BuddyConfig)
async def get_buddy_config(request: Request) -> BuddyConfig:
    """Expose the selected conversation mode, never provider credentials."""
    settings = request.app.state.settings
    ready = settings.ai_mode == "openai" and bool(settings.openai_api_key and settings.openai_api_key.get_secret_value().strip())
    if settings.ai_mode == "ollama":
        ready = False
        try:
            async with httpx.AsyncClient(timeout=3.0, trust_env=False, follow_redirects=False) as client:
                response = await client.get(settings.ollama_base_url.rstrip("/") + "/api/tags")
            data = response.json() if response.is_success else {}
            models = data.get("models", []) if isinstance(data, dict) else []
            ready = isinstance(models, list) and any(
                isinstance(model, dict) and settings.ollama_model in {model.get("name"), model.get("model")}
                for model in models
            )
        except (httpx.RequestError, ValueError, TypeError):
            pass
    return BuddyConfig(mode=settings.ai_mode, ai_ready=ready, setup_required=not ready)


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    session: Annotated[Session, Depends(get_db)],
    profile_token: Annotated[str | None, Header(alias="X-Profile-Token")] = None,
) -> ChatResponse:
    settings = request.app.state.settings
    messages = [message.model_dump() for message in payload.messages]
    trip_context = None
    if payload.trip_id is not None:
        profile = require_profile(session, profile_token, request)
        trip_record = get_owned_trip(session, profile.id, str(payload.trip_id))
        if settings.ai_mode == "demo" and wants_itinerary_proposal(messages[-1]["content"], payload.feature):
            proposal = await generate_proposal(
                session, profile.id, str(payload.trip_id), messages[-1]["content"], settings,
                conversation=messages,
                authorize=lambda: require_profile(session, profile_token, request, touch=False),
            )
            reply = "Here’s an itinerary idea for your saved trip. Review the activities and estimated costs, then approve it to add these suggestions. Existing activities will be kept."
            if proposal.mode == "demo":
                reply = "Real AI isn’t connected yet. Here is a clearly labeled curated demo itinerary to preview the review flow. For personalized AI ideas, run the private backend AI setup command."
            return ChatResponse(reply=reply, mode=settings.ai_mode, proposal=proposal)
        trip = serialize_trip(trip_record).model_dump(mode="json")
        # Credentials, owner identifiers, and unrelated trips never enter AI context.
        trip_context = {key: trip[key] for key in (
            "id", "name", "destination", "departure_location", "start_date", "end_date",
            "travelers", "budget", "currency", "status", "estimated_total", "remaining_budget", "item_count",
        )}
        planned_items = [item for item in trip["itinerary"] if item["status"] == "planned"]
        context_limit = 200 if settings.ai_mode in {"openai", "ollama"} else 30
        trip_context["itinerary"] = [{key: item[key] for key in (
            "date", "start_time", "end_time", "title", "location", "estimated_cost", "item_type", "status",
        )} for item in planned_items[:context_limit]]
        trip_context["itinerary_scope"] = f"First {context_limit} planned items; cancelled items are omitted."
        trip_context["itinerary_truncated"] = len(planned_items) > context_limit
        trip_context['calculated_facts'] = trip_facts(trip_context)
        recovery = buddy_context(session, trip_record)
        if recovery is not None:
            trip_context["domino_rescue"] = recovery
        if settings.ai_mode in {"openai", "ollama"}:
            base = fingerprint(trip_record)
            draft = latest_pending_draft(session, profile.id, str(payload.trip_id))
            draft_id = draft.id if draft is not None else None
            draft_context = ({"id": draft.id, "request": draft.request, "plan": draft.payload["plan"],
                              "planning_constraints": draft.payload.get('planning_constraints')}
                             if draft is not None else None)
            rules = constraints_for(messages[-1]['content'], messages, draft.payload.get('planning_constraints') if draft else None)
            trip_context['planning_constraints'] = rules
            trip_context['place_references'] = reference_context(trip_context['destination'])
            turn = await converse(messages, payload.feature, settings, trip_context, draft_context)
            proposal = None
            if turn.plan is not None:
                proposal = store_generated_proposal(
                    session, profile.id, str(payload.trip_id), messages[-1]["content"], turn.plan, settings.ai_mode,
                    requirements=turn.requirements, expected_fingerprint=base, supersedes_id=draft_id,
                    constraints=rules, authorize=lambda: require_profile(session, profile_token, request, touch=False),
                )
            reply = ("I prepared a draft for you to review below. Nothing has been added to your itinerary. "
                     "Costs are illustrative whole-group allowances; check the place references and assumptions before approving."
                     if proposal is not None else turn.reply)
            return ChatResponse(reply=reply, mode=settings.ai_mode, proposal=proposal)
    if payload.trip_id is None and settings.ai_mode == "demo" and has_itinerary_word(messages[-1]["content"]) and wants_itinerary_proposal(messages[-1]["content"], payload.feature):
        return ChatResponse(
            mode="demo",
            reply="I can prepare an itinerary proposal using your destination, dates, and budget. Select your saved trip in the chat's 'Plan for' menu, then ask me to create an itinerary. Real AI needs the private backend key setup; demo proposals are curated examples, not AI.",
        )
    if settings.ai_mode == "demo":
        reply = guided_demo_reply(messages, payload.feature, trip_context)
    else:
        reply = await openai_reply(messages, payload.feature, settings, trip_context)
    return ChatResponse(reply=reply, mode=settings.ai_mode)
