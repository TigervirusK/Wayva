"""Owned Domino Rescue demo, comparison, and explicitly approved execution."""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, field_validator

from app.api.profiles import ProfileDependency, SessionDependency
from app.services import rescue

router = APIRouter(tags=["Domino Rescue · simulated bookings"])


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fresh: bool = False


class ApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: Literal[True]
    simulate_failure: bool = False

    @field_validator("approved", mode="before")
    @classmethod
    def explicit_approval(cls, value):
        if value is not True:
            raise ValueError("Approval must be the JSON boolean true.")
        return value


@router.post("/rescue/demo")
def demo(payload: DemoRequest, session: SessionDependency, profile: ProfileDependency):
    return rescue.create_demo(session, profile.id, payload.fresh)


@router.get("/trips/{trip_id}/rescue")
def get_state(trip_id: UUID, session: SessionDependency, profile: ProfileDependency):
    return rescue.state(session, profile.id, str(trip_id))


@router.post("/trips/{trip_id}/rescue/simulate-cancellation")
def simulate(trip_id: UUID, session: SessionDependency, profile: ProfileDependency):
    return rescue.simulate(session, profile.id, str(trip_id))


@router.post("/trips/{trip_id}/rescue/options")
def options(trip_id: UUID, session: SessionDependency, profile: ProfileDependency):
    return rescue.generate_options(session, profile.id, str(trip_id))


@router.post("/trips/{trip_id}/rescue/plans/{plan_id}/approve-execute")
def approve(trip_id: UUID, plan_id: UUID, payload: ApprovalRequest, session: SessionDependency, profile: ProfileDependency):
    return rescue.approve_execute(session, profile.id, str(trip_id), str(plan_id), payload.simulate_failure)
