"""Owned travel plans, reviewed proposals, and simulated booking recovery records."""

from datetime import date as DateValue, datetime, time as TimeValue, timezone
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, LargeBinary, Numeric, String, Text, Time, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def new_id() -> str:
    return str(uuid4())


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("communication_style IN ('friendly','professional','enthusiastic','concise')", name="ck_users_style"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    display_name: Mapped[str] = mapped_column(String(80))
    communication_style: Mapped[str] = mapped_column(String(20), default="friendly", server_default="friendly")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.current_timestamp())
    trips: Mapped[list["Trip"]] = relationship(back_populates="owner")


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("end_date >= start_date AND julianday(end_date) - julianday(start_date) <= 366", name="ck_trips_dates"),
        CheckConstraint("travelers >= 1 AND travelers <= 50", name="ck_trips_travelers"),
        CheckConstraint("budget >= 0 AND budget <= 10000000", name="ck_trips_budget"),
        CheckConstraint("currency IN ('USD','EUR','GBP','JPY','CAD','AUD','INR')", name="ck_trips_currency"),
        CheckConstraint("status IN ('planned','active','completed')", name="ck_trips_status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    destination: Mapped[str] = mapped_column(String(120))
    departure_location: Mapped[str] = mapped_column(String(120), default="", server_default="")
    start_date: Mapped[DateValue] = mapped_column(Date)
    end_date: Mapped[DateValue] = mapped_column(Date)
    travelers: Mapped[int] = mapped_column(Integer)
    budget: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    status: Mapped[str] = mapped_column(String(20), default="planned", server_default="planned")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, server_default=func.current_timestamp())
    owner: Mapped[User] = relationship(back_populates="trips")
    itinerary: Mapped[list["ItineraryItem"]] = relationship(
        back_populates="trip", lazy="selectin",
        order_by="(ItineraryItem.date, ItineraryItem.start_time, ItineraryItem.id)",
    )


class ItineraryItem(Base):
    __tablename__ = "itinerary_items"
    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_itinerary_times"),
        CheckConstraint("estimated_cost >= 0 AND estimated_cost <= 10000000", name="ck_itinerary_cost"),
        CheckConstraint("item_type IN ('activity','food','transport','accommodation','other')", name="ck_itinerary_type"),
        CheckConstraint("status IN ('planned','cancelled')", name="ck_itinerary_status"),
        Index("ix_itinerary_items_trip_schedule", "trip_id", "date", "start_time"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"), index=True)
    date: Mapped[DateValue] = mapped_column(Date)
    start_time: Mapped[TimeValue] = mapped_column(Time)
    end_time: Mapped[TimeValue] = mapped_column(Time)
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    location: Mapped[str] = mapped_column(String(200), default="", server_default="")
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    item_type: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="planned", server_default="planned")
    trip: Mapped[Trip] = relationship(back_populates="itinerary")


class Proposal(Base):
    __tablename__ = "proposals"
    __table_args__ = (
        CheckConstraint("status IN ('pending','approved','rejected','stale')", name="ck_proposals_status"),
        CheckConstraint("mode IN ('demo','openai')", name="ck_proposals_mode"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"), index=True)
    request: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    base_fingerprint: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    mode: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Reservation(Base):
    """Explicitly simulated bookings; existing itinerary rows remain compatible."""
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("kind IN ('flight','pickup','hotel','tour')", name="ck_reservation_kind"),
        CheckConstraint("status IN ('confirmed','at_risk','cancelled')", name="ck_reservation_status"),
        CheckConstraint("end_at > start_at", name="ck_reservation_times"),
        CheckConstraint("estimated_cost >= 0", name="ck_reservation_cost"),
        Index("ix_reservation_trip_key", "trip_id", "key", unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"), index=True)
    itinerary_item_id: Mapped[str | None] = mapped_column(ForeignKey("itinerary_items.id", ondelete="SET NULL"), nullable=True)
    key: Mapped[str] = mapped_column(String(30))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(160))
    location: Mapped[str] = mapped_column(String(200))
    provider: Mapped[str] = mapped_column(String(40), default="triprescue_mock")
    booking_reference: Mapped[str] = mapped_column(String(80))
    simulated: Mapped[bool] = mapped_column(default=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    status: Mapped[str] = mapped_column(String(20), default="confirmed")


class ReservationDependency(Base):
    __tablename__ = "reservation_dependencies"
    __table_args__ = (
        CheckConstraint("source_id != target_id", name="ck_dependency_not_self"),
        Index("ix_dependency_pair", "source_id", "target_id", unique=True),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("reservations.id", ondelete="RESTRICT"))
    target_id: Mapped[str] = mapped_column(ForeignKey("reservations.id", ondelete="RESTRICT"))
    reason: Mapped[str] = mapped_column(String(240))


class DisruptionEvent(Base):
    __tablename__ = "disruption_events"
    __table_args__ = (CheckConstraint("status IN ('open','resolved')", name="ck_disruption_status"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"), index=True)
    reservation_id: Mapped[str] = mapped_column(ForeignKey("reservations.id", ondelete="RESTRICT"))
    kind: Mapped[str] = mapped_column(String(30), default="flight_cancellation")
    status: Mapped[str] = mapped_column(String(20), default="open")
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RecoveryPlan(Base):
    __tablename__ = "recovery_plans"
    __table_args__ = (
        CheckConstraint("status IN ('pending','applied','failed','stale')", name="ck_recovery_status"),
        CheckConstraint("strategy IN ('fastest','cheapest','balanced')", name="ck_recovery_strategy"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"), index=True)
    disruption_id: Mapped[str] = mapped_column(ForeignKey("disruption_events.id", ondelete="RESTRICT"), index=True)
    strategy: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="pending")
    base_fingerprint: Mapped[str] = mapped_column(String(64))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)


class RescueAuditLog(Base):
    __tablename__ = "rescue_audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trip_id: Mapped[str] = mapped_column(ForeignKey("trips.id", ondelete="RESTRICT"), index=True)
    disruption_id: Mapped[str | None] = mapped_column(ForeignKey("disruption_events.id", ondelete="RESTRICT"), nullable=True)
    plan_id: Mapped[str | None] = mapped_column(ForeignKey("recovery_plans.id", ondelete="RESTRICT"), nullable=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    action: Mapped[str] = mapped_column(String(60))
    result: Mapped[str] = mapped_column(String(20))
    details: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TravelerVault(Base):
    """User-entered private details, authenticated-encrypted at rest; never AI context."""
    __tablename__ = "traveler_vaults"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    salt: Mapped[bytes] = mapped_column(LargeBinary)
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary)
    revision: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class TravelerVaultAudit(Base):
    __tablename__ = "traveler_vault_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    action: Mapped[str] = mapped_column(String(30))
    result: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class Account(Base):
    __tablename__ = "accounts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True)
    username: Mapped[str] = mapped_column(String(30), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    password_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class AccountSession(Base):
    __tablename__ = "account_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("accounts.user_id", ondelete="RESTRICT"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccountAttempt(Base):
    __tablename__ = "account_attempts"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    failures: Mapped[int] = mapped_column(Integer, default=0)
    window_started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    blocked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AccountAudit(Base):
    __tablename__ = "account_audit"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(30))
    result: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
