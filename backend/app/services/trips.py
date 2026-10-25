"""Ownership, persistence, money, and schedule rules shared by API and buddy."""

import hashlib
import secrets
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import HTTPException, Request
from sqlalchemy import select, text
from sqlalchemy.orm import Session, selectinload

from app.models import Account, ItineraryItem, Trip, User, utc_now
from app.schemas.trips import ItineraryInput, ItineraryItemResponse, Profile, ProfileCreated, TripDetail, TripInput, TripSummary


def aware_timestamp(value: datetime) -> datetime:
    # SQLite stores DateTime without a timezone; application timestamps are UTC.
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def serialize_profile(profile: User) -> Profile:
    return Profile(
        id=profile.id, display_name=profile.display_name,
        communication_style=profile.communication_style,
        created_at=aware_timestamp(profile.created_at),
    )


def create_profile(session: Session, display_name: str) -> ProfileCreated:
    token = secrets.token_urlsafe(32)
    profile = User(display_name=display_name, token_hash=hashlib.sha256(token.encode()).hexdigest())
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return ProfileCreated(profile=serialize_profile(profile), token=token)


def require_profile(session: Session, token: str | None, request: Request | None = None, *, touch: bool = True) -> User:
    if request is not None:
        from app.services.accounts import COOKIE, require_account
        if request.cookies.get(COOKIE):
            return require_account(session, request, token, touch=touch)[0]
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Select a local traveler profile to continue.")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    profile = session.scalar(select(User).where(User.token_hash == token_hash))
    if profile is None:
        raise HTTPException(status_code=401, detail="This local profile is unavailable. Create a new profile on this device.")
    if session.get(Account, profile.id) is not None:
        raise HTTPException(401, "This profile is protected by an account. Sign in with your username and password.")
    return profile


def get_owned_trip(session: Session, profile_id: str, trip_id: str) -> Trip:
    trip = session.scalar(
        select(Trip).where(Trip.id == trip_id, Trip.owner_id == profile_id)
        .options(selectinload(Trip.itinerary))
    )
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found for this profile.")
    return trip


def money_string(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def serialize_summary(trip: Trip) -> TripSummary:
    estimated_total = sum(
        (item.estimated_cost for item in trip.itinerary if item.status == "planned"), Decimal("0")
    )
    return TripSummary(
        id=trip.id, owner_id=trip.owner_id, name=trip.name, destination=trip.destination,
        departure_location=trip.departure_location, start_date=trip.start_date,
        end_date=trip.end_date, travelers=trip.travelers, budget=money_string(trip.budget),
        currency=trip.currency, status=trip.status, created_at=aware_timestamp(trip.created_at),
        updated_at=aware_timestamp(trip.updated_at), estimated_total=money_string(estimated_total),
        remaining_budget=money_string(trip.budget - estimated_total), item_count=len(trip.itinerary),
    )


def serialize_trip(trip: Trip) -> TripDetail:
    items = sorted(trip.itinerary, key=lambda item: (item.date, item.start_time, item.id))
    return TripDetail(
        **serialize_summary(trip).model_dump(),
        itinerary=[ItineraryItemResponse(
            id=item.id, trip_id=item.trip_id, date=item.date,
            start_time=item.start_time.strftime("%H:%M"), end_time=item.end_time.strftime("%H:%M"),
            title=item.title, description=item.description, location=item.location,
            estimated_cost=money_string(item.estimated_cost), item_type=item.item_type, status=item.status,
        ) for item in items],
    )


def list_trips(session: Session, profile_id: str) -> list[TripSummary]:
    trips = session.scalars(
        select(Trip).where(Trip.owner_id == profile_id).options(selectinload(Trip.itinerary))
        .order_by(Trip.updated_at.desc(), Trip.id)
    ).all()
    return [serialize_summary(trip) for trip in trips]


def lock_writes(session: Session) -> None:
    # SQLite's write lock protects read-validate-write scheduling from concurrent changes.
    # Token lookup performs only a SELECT, so the DBAPI has not begun a write transaction.
    session.execute(text("BEGIN IMMEDIATE"))


def create_trip(session: Session, profile_id: str, payload: TripInput) -> TripDetail:
    trip = Trip(owner_id=profile_id, **payload.model_dump())
    session.add(trip)
    session.commit()
    return serialize_trip(trip)


def update_trip(session: Session, profile_id: str, trip_id: str, payload: TripInput) -> TripDetail:
    lock_writes(session)
    trip = get_owned_trip(session, profile_id, trip_id)
    if trip.currency != payload.currency and trip.itinerary:
        raise HTTPException(status_code=409, detail="Currency cannot change while the trip has itinerary items.")
    if any(not payload.start_date <= item.date <= payload.end_date for item in trip.itinerary):
        raise HTTPException(status_code=409, detail="These dates would leave an activity outside the trip. Move or remove it first.")
    for field, value in payload.model_dump().items():
        setattr(trip, field, value)
    trip.updated_at = utc_now()
    session.commit()
    return serialize_trip(trip)


def validate_activity(trip: Trip, payload: ItineraryInput, exclude_id: str | None = None) -> None:
    if not trip.start_date <= payload.date <= trip.end_date:
        raise HTTPException(status_code=422, detail="Activity date must be within the trip dates.")
    if payload.status == "cancelled":
        return
    for existing in trip.itinerary:
        if (
            existing.id != exclude_id and existing.status == "planned"
            and existing.date == payload.date
            and payload.start_time < existing.end_time and payload.end_time > existing.start_time
        ):
            raise HTTPException(status_code=409, detail="This activity overlaps another planned activity.")


def add_activity(session: Session, profile_id: str, trip_id: str, payload: ItineraryInput) -> TripDetail:
    lock_writes(session)
    trip = get_owned_trip(session, profile_id, trip_id)
    validate_activity(trip, payload)
    trip.itinerary.append(ItineraryItem(**payload.model_dump()))
    trip.updated_at = utc_now()
    session.commit()
    return serialize_trip(trip)


def owned_activity(trip: Trip, item_id: str) -> ItineraryItem:
    item = next((item for item in trip.itinerary if item.id == item_id), None)
    if item is None:
        raise HTTPException(status_code=404, detail="Activity not found in this trip.")
    return item


def update_activity(session: Session, profile_id: str, trip_id: str, item_id: str, payload: ItineraryInput) -> TripDetail:
    lock_writes(session)
    trip = get_owned_trip(session, profile_id, trip_id)
    item = owned_activity(trip, item_id)
    validate_activity(trip, payload, exclude_id=item.id)
    for field, value in payload.model_dump().items():
        setattr(item, field, value)
    trip.updated_at = utc_now()
    session.commit()
    return serialize_trip(trip)


def delete_activity(session: Session, profile_id: str, trip_id: str, item_id: str) -> TripDetail:
    lock_writes(session)
    trip = get_owned_trip(session, profile_id, trip_id)
    item = owned_activity(trip, item_id)
    session.delete(item)
    trip.updated_at = utc_now()
    session.commit()
    session.expire(trip, ["itinerary"])
    return serialize_trip(trip)
