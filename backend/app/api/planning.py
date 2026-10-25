"""Owned itinerary suggestions and explicit approval endpoints."""
from uuid import UUID
from fastapi import APIRouter, Request
from app.api.profiles import ProfileDependency, SessionDependency
from app.schemas.planning import ApprovalResponse, PlanningRequest, ProposalResponse
from app.services import planning
from app.services.trips import require_profile

router = APIRouter(tags=["Dream-to-Trip"])


@router.post("/{trip_id}/proposals", response_model=ProposalResponse, status_code=201)
async def generate(trip_id: UUID, payload: PlanningRequest, session: SessionDependency, profile: ProfileDependency, request: Request):
    return await planning.generate_proposal(session, profile.id, str(trip_id), payload.request, request.app.state.settings,
        authorize=lambda: require_profile(session, request.headers.get('X-Profile-Token'), request, touch=False))


@router.get("/{trip_id}/proposals", response_model=list[ProposalResponse])
def list_owned(trip_id: UUID, session: SessionDependency, profile: ProfileDependency):
    return planning.list_proposals(session, profile.id, str(trip_id))


@router.get("/{trip_id}/proposals/{proposal_id}", response_model=ProposalResponse)
def get_owned(trip_id: UUID, proposal_id: UUID, session: SessionDependency, profile: ProfileDependency):
    return planning.serialize_proposal(planning.get_owned_proposal(session, profile.id, str(trip_id), str(proposal_id)))


@router.post("/{trip_id}/proposals/{proposal_id}/approve", response_model=ApprovalResponse)
def approve(trip_id: UUID, proposal_id: UUID, session: SessionDependency, profile: ProfileDependency):
    return planning.approve_proposal(session, profile.id, str(trip_id), str(proposal_id))


@router.post("/{trip_id}/proposals/{proposal_id}/reject", response_model=ProposalResponse)
def reject(trip_id: UUID, proposal_id: UUID, session: SessionDependency, profile: ProfileDependency):
    return planning.reject_proposal(session, profile.id, str(trip_id), str(proposal_id))
