"""Manual trip and itinerary changes initiated by the traveler."""

from uuid import UUID

from fastapi import APIRouter

from app.api.profiles import ProfileDependency, SessionDependency
from app.schemas.trips import ItineraryInput, TripDetail, TripInput, TripSummary
from app.services import trips as service

router = APIRouter(tags=["Saved trips"])


@router.get("", response_model=list[TripSummary])
def get_trips(session: SessionDependency, profile: ProfileDependency) -> list[TripSummary]:
    return service.list_trips(session, profile.id)


@router.post("", response_model=TripDetail, status_code=201)
def add_trip(payload: TripInput, session: SessionDependency, profile: ProfileDependency) -> TripDetail:
    return service.create_trip(session, profile.id, payload)


@router.get("/{trip_id}", response_model=TripDetail)
def get_trip(trip_id: UUID, session: SessionDependency, profile: ProfileDependency) -> TripDetail:
    return service.serialize_trip(service.get_owned_trip(session, profile.id, str(trip_id)))


@router.put("/{trip_id}", response_model=TripDetail)
def edit_trip(trip_id: UUID, payload: TripInput, session: SessionDependency, profile: ProfileDependency) -> TripDetail:
    return service.update_trip(session, profile.id, str(trip_id), payload)


@router.post("/{trip_id}/itinerary", response_model=TripDetail, status_code=201)
def add_item(trip_id: UUID, payload: ItineraryInput, session: SessionDependency, profile: ProfileDependency) -> TripDetail:
    return service.add_activity(session, profile.id, str(trip_id), payload)


@router.put("/{trip_id}/itinerary/{item_id}", response_model=TripDetail)
def edit_item(trip_id: UUID, item_id: UUID, payload: ItineraryInput, session: SessionDependency, profile: ProfileDependency) -> TripDetail:
    return service.update_activity(session, profile.id, str(trip_id), str(item_id), payload)


@router.delete("/{trip_id}/itinerary/{item_id}", response_model=TripDetail)
def remove_item(trip_id: UUID, item_id: UUID, session: SessionDependency, profile: ProfileDependency) -> TripDetail:
    return service.delete_activity(session, profile.id, str(trip_id), str(item_id))
