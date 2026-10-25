"""AI suggestions are validated proposals, never confirmed reservations."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.trips import TripDetail


class PlanningRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request: str = Field(min_length=1, max_length=2000)


class ProposedActivity(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    date: str
    start_time: str
    end_time: str
    title: str
    description: str
    location: str
    estimated_cost: str
    item_type: Literal["activity", "food", "transport", "accommodation", "other"]


class ItineraryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    title: str
    summary: str
    activities: list[ProposedActivity]
    notes: list[str]


class ProposalResponse(ItineraryPlan):
    id: str
    trip_id: str
    request: str
    currency: str
    status: Literal["pending", "approved", "rejected", "stale"]
    mode: Literal["demo", "openai", "ollama"]
    estimated_total: str
    resulting_estimated_total: str
    remaining_budget: str
    created_at: datetime
    approved_at: datetime | None
    superseded_by: str | None = None
    quality: dict | None = None


class ApprovalResponse(BaseModel):
    proposal: ProposalResponse
    trip: TripDetail
