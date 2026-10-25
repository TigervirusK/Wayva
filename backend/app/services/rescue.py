"""Domino Rescue: deterministic graph analysis and approved mock booking changes.

No airline, payment, or real booking provider is contacted. UTC is stored; the
fictional Tokyo scenario and linked itinerary use Asia/Tokyo local time.
"""
import hashlib
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (DisruptionEvent, ItineraryItem, RecoveryPlan, Reservation,
                        ReservationDependency, RescueAuditLog, Trip, new_id, utc_now)
from app.schemas.trips import ItineraryInput
from app.services.planning import fingerprint
from app.services.trips import aware_timestamp, get_owned_trip, lock_writes, money_string, validate_activity

TOKYO = timezone(timedelta(hours=9), "Asia/Tokyo")
PROVIDER = "triprescue_mock"


def stamp(value: datetime) -> str:
    return aware_timestamp(value).astimezone(timezone.utc).isoformat()


def parse(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(timezone.utc)


def reservations_for(session: Session, trip_id: str) -> list[Reservation]:
    return list(session.scalars(select(Reservation).where(Reservation.trip_id == trip_id).order_by(Reservation.start_at, Reservation.id)))


def serialize_reservation(row: Reservation) -> dict:
    return {"id": row.id, "key": row.key, "kind": row.kind, "title": row.title,
            "location": row.location, "provider": row.provider, "simulated": row.simulated,
            "booking_reference": row.booking_reference, "start_at": stamp(row.start_at),
            "end_at": stamp(row.end_at), "estimated_cost": money_string(row.estimated_cost),
            "status": row.status, "itinerary_item_id": row.itinerary_item_id}


def edges_for(session: Session, trip_id: str) -> list[ReservationDependency]:
    return list(session.scalars(select(ReservationDependency).where(ReservationDependency.trip_id == trip_id).order_by(ReservationDependency.id)))


def descendants(source: str, nodes: set[str], edges: list[tuple[str, str]]) -> list[str]:
    """Traverse a validated DAG, visiting each descendant once (including diamonds)."""
    if source not in nodes or any(a not in nodes or b not in nodes for a, b in edges):
        raise HTTPException(409, "The reservation graph contains an invalid connection.")
    adjacent = {node: [] for node in nodes}
    indegree = dict.fromkeys(nodes, 0)
    for a, b in edges:
        adjacent[a].append(b)
        indegree[b] += 1
    queue = sorted(node for node, degree in indegree.items() if degree == 0)
    ordered = []
    while queue:
        node = queue.pop(0)
        ordered.append(node)
        for child in sorted(adjacent[node]):
            indegree[child] -= 1
            if indegree[child] == 0:
                queue.append(child)
    if len(ordered) != len(nodes):
        raise HTTPException(409, "The reservation graph contains a cycle. No recovery was executed.")
    reached = {source}
    for node in ordered:
        if node in reached:
            reached.update(adjacent[node])
    return [node for node in ordered if node in reached and node != source]


def snapshot(session: Session, trip: Trip, rows: list[Reservation]) -> str:
    state = {"trip": fingerprint(trip), "reservations": [serialize_reservation(row) for row in rows],
             "edges": sorted((edge.source_id, edge.target_id, edge.reason) for edge in edges_for(session, trip.id))}
    return hashlib.sha256(json.dumps(state, sort_keys=True).encode()).hexdigest()


def audit(session: Session, trip: Trip, actor: str, action: str, result: str, message: str,
          event: DisruptionEvent | None = None, plan: RecoveryPlan | None = None, **details):
    session.add(RescueAuditLog(trip_id=trip.id, actor_id=actor, action=action, result=result,
                             disruption_id=event.id if event else None, plan_id=plan.id if plan else None,
                             details={"message": message, **details}))


def create_demo(session: Session, owner: str, fresh: bool = False) -> dict:
    lock_writes(session)
    if not fresh:
        existing = session.scalar(select(Trip).join(Reservation, Reservation.trip_id == Trip.id).where(
            Trip.owner_id == owner, Reservation.provider == PROVIDER, Reservation.key == "connection"
        ).order_by(Trip.created_at.desc(), Trip.id))
        if existing:
            return {"trip_id": existing.id, "created": False}
    trip = Trip(id=new_id(), owner_id=owner, name="Tokyo · Domino Rescue demo", destination="Tokyo",
                departure_location="Columbus via Chicago", start_date=date(2027, 5, 1), end_date=date(2027, 5, 5),
                travelers=1, budget=Decimal("3000"), currency="USD", status="planned")
    session.add(trip)
    session.flush()
    specs = [
        ("connection", "flight", "Arrive · mock Chicago–Tokyo flight", "Tokyo Haneda Airport", "2027-04-30T17:00:00+00:00", "2027-05-01T06:00:00+00:00", "900"),
        ("pickup", "pickup", "Mock airport pickup", "Haneda → Asakusa", "2027-05-01T07:00:00+00:00", "2027-05-01T08:00:00+00:00", "60"),
        ("hotel", "hotel", "Mock hotel check-in", "Fictional Asakusa Garden Hotel", "2027-05-01T08:30:00+00:00", "2027-05-01T09:00:00+00:00", "360"),
        ("tour", "tour", "Mock Asakusa walking tour", "Asakusa, Tokyo", "2027-05-02T01:00:00+00:00", "2027-05-02T03:00:00+00:00", "80"),
    ]
    rows = []
    for key, kind, title, location, start, end, cost in specs:
        row = Reservation(id=new_id(), trip_id=trip.id, key=key, kind=kind, title=title, location=location,
                          provider=PROVIDER, booking_reference=f"DEMO-{key.upper()}-{trip.id[:6]}", simulated=True,
                          start_at=parse(start), end_at=parse(end), estimated_cost=Decimal(cost), status="confirmed")
        local_end = row.end_at.astimezone(TOKYO)
        local_start = (row.end_at - timedelta(hours=1) if kind == "flight" else row.start_at).astimezone(TOKYO)
        item = ItineraryItem(id=new_id(), trip_id=trip.id, date=local_start.date(), start_time=local_start.time().replace(tzinfo=None),
                             end_time=local_end.time().replace(tzinfo=None), title=title, location=location,
                             description="Simulated reservation. No real booking. Flight item shows the arrival window; all times are Tokyo local time.",
                             estimated_cost=Decimal(cost), item_type={"flight": "transport", "pickup": "transport", "hotel": "accommodation", "tour": "activity"}[kind], status="planned")
        session.add(item)
        session.flush()
        row.itinerary_item_id = item.id
        session.add(row)
        rows.append(row)
    session.flush()
    for source, target, reason in [
        (0, 1, "Pickup needs the flight to arrive, plus one hour for arrival formalities."),
        (1, 2, "Check-in follows the pickup, with a 30-minute buffer."),
        (2, 3, "The walking tour needs at least ten hours after check-in for rest."),
    ]:
        session.add(ReservationDependency(trip_id=trip.id, source_id=rows[source].id, target_id=rows[target].id, reason=reason))
    audit(session, trip, owner, "demo_created", "success", "Created a separate fictional Tokyo trip with four simulated reservations.")
    session.commit()
    return {"trip_id": trip.id, "created": True}


def state(session: Session, owner: str, trip_id: str) -> dict:
    trip = get_owned_trip(session, owner, trip_id)
    rows = reservations_for(session, trip_id)
    edges = edges_for(session, trip_id)
    events = list(session.scalars(select(DisruptionEvent).where(DisruptionEvent.trip_id == trip_id).order_by(DisruptionEvent.created_at.desc())))
    plans = list(session.scalars(select(RecoveryPlan).where(RecoveryPlan.trip_id == trip_id).order_by(RecoveryPlan.created_at, RecoveryPlan.id)))
    current = snapshot(session, trip, rows)
    logs = session.scalars(select(RescueAuditLog).where(RescueAuditLog.trip_id == trip_id).order_by(RescueAuditLog.id)).all()
    return {
        "trip_id": trip.id, "trip_name": trip.name, "currency": trip.currency, "timezone": "Asia/Tokyo",
        "simulated": True, "scenario_ready": len(rows) == 4 and all(row.provider == PROVIDER and row.simulated for row in rows),
        "reservations": [serialize_reservation(row) for row in rows],
        "dependencies": [{"source_id": edge.source_id, "target_id": edge.target_id, "reason": edge.reason} for edge in edges],
        "disruption": ({"id": events[0].id, "kind": events[0].kind, "status": events[0].status,
                        "reservation_id": events[0].reservation_id, "details": events[0].details,
                        "created_at": stamp(events[0].created_at)} if events else None),
        "plans": [{"id": plan.id, "strategy": plan.strategy,
                   "status": "stale" if plan.status in ("pending", "failed") and plan.base_fingerprint != current else plan.status,
                   "approved_at": stamp(plan.approved_at) if plan.approved_at else None,
                   "executed_at": stamp(plan.executed_at) if plan.executed_at else None,
                   "error": plan.error, **plan.payload} for plan in plans if not events or plan.disruption_id == events[0].id],
        "audit": [{"id": log.id, "action": log.action, "result": log.result, "details": log.details,
                   "plan_id": log.plan_id, "created_at": stamp(log.created_at)} for log in logs],
    }


def buddy_context(session: Session, trip: Trip) -> dict | None:
    """Small read-only snapshot; caller must already have checked trip ownership."""
    trip_id = trip.id
    rows = reservations_for(session, trip_id)
    if not rows:
        return None
    event = session.scalar(select(DisruptionEvent).where(DisruptionEvent.trip_id == trip_id).order_by(DisruptionEvent.created_at.desc()))
    plans = list(session.scalars(select(RecoveryPlan).where(RecoveryPlan.trip_id == trip_id,
                RecoveryPlan.disruption_id == event.id).order_by(RecoveryPlan.created_at.desc()).limit(12))) if event else []
    current = snapshot(session, trip, rows)
    return {"simulated": True, "timezone": "Asia/Tokyo (JST)", "workspace_path": f"/trips/{trip_id}/rescue",
            "disruption_status": event.status if event else "not_simulated",
            "reservations": [{"title": row.title, "kind": row.kind, "status": row.status,
                              "start_at": stamp(row.start_at), "end_at": stamp(row.end_at)} for row in rows[:20]],
            "recovery_options": [{"strategy": plan.strategy, "status": "stale" if plan.status in ("pending", "failed") and plan.base_fingerprint != current else plan.status,
                                  "extra_cost": plan.payload["extra_cost"], "delay_hours": plan.payload["delay_hours"],
                                  "arrival_tokyo": parse(plan.payload["arrival_at"]).astimezone(TOKYO).strftime("%Y-%m-%d %H:%M JST"),
                                  "tour_tokyo": next(parse(action["start_at"]).astimezone(TOKYO).strftime("%Y-%m-%d %H:%M JST") for action in plan.payload["actions"] if action["kind"] == "tour"),
                                  "tour_moved": plan.payload["tour_moved"],
                                  "tour_day_change": next(
                                      "UNCHANGED original tour time" if not plan.payload["tour_moved"] else
                                      "LATER ON THE SAME DAY, not the next day" if parse(action["start_at"]).astimezone(TOKYO).date() == parse(action["before_start_at"]).astimezone(TOKYO).date() else
                                      "MOVED TO A LATER DAY" for action in plan.payload["actions"] if action["kind"] == "tour"),
                                  "explanation": plan.payload["explanation"], "available_at_generation": plan.payload["available"]}
                                 for plan in plans],
            "capabilities": "Read-only explanation here. Simulate, compare, and approve in the Domino Rescue workspace. No real bookings."}


def simulate(session: Session, owner: str, trip_id: str) -> dict:
    lock_writes(session)
    trip = get_owned_trip(session, owner, trip_id)
    existing = session.scalar(select(DisruptionEvent).where(DisruptionEvent.trip_id == trip_id).order_by(DisruptionEvent.created_at.desc()))
    if existing:
        return state(session, owner, trip_id)  # One cancellation per demo; safe to retry.
    rows = reservations_for(session, trip_id)
    source = next((row for row in rows if row.key == "connection" and row.kind == "flight"), None)
    if not source or len(rows) != 4 or any(not row.simulated or row.provider != PROVIDER for row in rows):
        raise HTTPException(409, "Open a Domino Rescue demo trip to simulate this cancellation. Your other trips are unchanged.")
    edges = edges_for(session, trip_id)
    affected = descendants(source.id, {row.id for row in rows}, [(edge.source_id, edge.target_id) for edge in edges])
    source.status = "cancelled"
    for row in rows:
        if row.id in affected:
            row.status = "at_risk"
    flight_item = next((item for item in trip.itinerary if item.id == source.itinerary_item_id), None)
    if not flight_item:
        raise HTTPException(409, "The demo's linked arrival item is missing. Create a fresh demo.")
    flight_item.status = "cancelled"
    trip.updated_at = utc_now()
    event = DisruptionEvent(id=new_id(), trip_id=trip.id, reservation_id=source.id, kind="flight_cancellation", status="open",
                            details={"message": "Simulated cancellation of the Chicago–Tokyo connection.", "affected_ids": affected})
    session.add(event)
    session.flush()
    audit(session, trip, owner, "flight_cancelled", "success", "Mock flight cancelled; downstream reservations flagged at risk.", event, affected_ids=affected)
    session.commit()
    return state(session, owner, trip_id)


class MockBookingError(Exception):
    pass


class MockBookingProvider:
    """Finite fictional inventory and in-process actions. Never makes HTTP calls."""
    def search_alternative_flights(self, original: Reservation) -> list[dict]:
        arrival = aware_timestamp(original.end_at)
        return [
            {"strategy": "fastest", "flight": "DEMO-EXPRESS", "arrival": arrival + timedelta(hours=3), "extra": Decimal("420"), "explanation": "Arrive three hours later and protect the next-morning tour. Highest additional cost."},
            {"strategy": "cheapest", "flight": "DEMO-NEXT-DAY", "arrival": arrival + timedelta(hours=24), "extra": Decimal("60"), "explanation": "Lowest extra cost, but lose a day in Tokyo and move the tour to the following morning."},
            {"strategy": "balanced", "flight": "DEMO-EVENING", "arrival": arrival + timedelta(hours=8), "extra": Decimal("190"), "explanation": "Arrive tonight for less than the express option. Move the tour later to leave time to rest."},
        ]

    def execute(self, row: Reservation, action: dict, fail: bool = False) -> None:
        if not row.simulated or row.provider != PROVIDER:
            raise MockBookingError("Only Wayva simulated bookings can be changed.")
        if fail:
            raise MockBookingError("The mock pickup provider declined the change. No repair changes were saved. Try a different recovery option.")
        row.start_at = parse(action["start_at"])
        row.end_at = parse(action["end_at"])
        row.estimated_cost = Decimal(action["estimated_cost"])
        row.status = "confirmed"
        row.booking_reference = action["booking_reference"]


def linked_inputs(trip: Trip, rows: list[Reservation], actions: list[dict]) -> list[tuple[ItineraryItem, ItineraryInput]]:
    """Check every linked schedule against both repaired and unrelated saved items."""
    items = {item.id: item for item in trip.itinerary}
    rows_by_id = {row.id: row for row in rows}
    changed_ids = {row.itinerary_item_id for row in rows}
    original = trip.itinerary
    proposed = []
    # validate_activity only reads itinerary; a lightweight view avoids mutating
    # the ORM relationship while validating candidate schedules.
    from types import SimpleNamespace
    view = SimpleNamespace(start_date=trip.start_date, end_date=trip.end_date,
                           itinerary=[item for item in original if item.id not in changed_ids])
    for action in actions:
        row = rows_by_id.get(action["reservation_id"])
        item = items.get(row.itinerary_item_id) if row else None
        if item is None:
            raise HTTPException(409, "A linked itinerary item was removed. Create a fresh demo before repairing it.")
        start, end = parse(action["start_at"]), parse(action["end_at"])
        if row.kind == "flight":
            start = end - timedelta(hours=1)  # Arrival window, not the whole flight.
        start, end = start.astimezone(TOKYO), end.astimezone(TOKYO)
        if start.date() != end.date():
            raise HTTPException(409, "The simulated activity crosses midnight and cannot fit this itinerary format.")
        payload = ItineraryInput(date=start.date().isoformat(), start_time=start.strftime("%H:%M"),
                                 end_time=end.strftime("%H:%M"), title=item.title,
                                 description=item.description, location=item.location, estimated_cost=action["estimated_cost"],
                                 item_type=item.item_type, status="planned")
        validate_activity(view, payload)
        view.itinerary.append(SimpleNamespace(id=item.id, **payload.model_dump()))
        proposed.append((item, payload))
    total = sum((item.estimated_cost for item in original if item.id not in changed_ids and item.status == "planned"), Decimal("0"))
    total += sum((payload.estimated_cost for _, payload in proposed), Decimal("0"))
    if total > trip.budget:
        raise HTTPException(409, "This recovery exceeds the trip budget. Increase the budget or choose a cheaper valid option.")
    return proposed


def candidate(trip: Trip, rows: list[Reservation], alternative: dict) -> dict:
    by_key = {row.key: row for row in rows}
    arrival = alternative["arrival"]
    pickup_start, pickup_end = arrival + timedelta(hours=1), arrival + timedelta(hours=2)
    hotel_start, hotel_end = arrival + timedelta(hours=2, minutes=30), arrival + timedelta(hours=3)
    tour_start = aware_timestamp(by_key["tour"].start_at)
    earliest = hotel_end + timedelta(hours=10)
    if tour_start < earliest:
        local = earliest.astimezone(TOKYO)
        # Mock inventory offers 10:00 and 13:00 starts, not arbitrary availability.
        slots = [datetime.combine(local.date() + timedelta(days=offset), datetime.min.time(), TOKYO).replace(hour=hour)
                 for offset in range(2) for hour in (10, 13)]
        tour_start = next(slot.astimezone(timezone.utc) for slot in slots if slot >= local)
    tour_moved = tour_start != aware_timestamp(by_key["tour"].start_at)
    late_checkin = hotel_start.astimezone(TOKYO).hour < 6
    increments = {"connection": alternative["extra"], "pickup": Decimal("15") if alternative["strategy"] != "cheapest" else Decimal("0"),
                  "hotel": Decimal("25") if late_checkin else Decimal("0"), "tour": Decimal("20") if tour_moved else Decimal("0")}
    schedules = {"connection": (arrival - timedelta(hours=13), arrival), "pickup": (pickup_start, pickup_end),
                 "hotel": (hotel_start, hotel_end), "tour": (tour_start, tour_start + timedelta(hours=2))}
    actions = []
    for key in ("connection", "pickup", "hotel", "tour"):
        row = by_key[key]
        start, end = schedules[key]
        actions.append({"reservation_id": row.id, "kind": row.kind, "title": row.title,
                        "action": {"connection": "change_flight", "pickup": "update_pickup", "hotel": "update_checkin", "tour": "reschedule_tour" if tour_moved else "reconfirm_tour"}[key],
                        "before_start_at": stamp(row.start_at), "before_end_at": stamp(row.end_at),
                        "start_at": stamp(start), "end_at": stamp(end),
                        "estimated_cost": money_string(row.estimated_cost + increments[key]), "extra_cost": money_string(increments[key]),
                        "booking_reference": alternative["flight"] if key == "connection" else row.booking_reference})
    extra = sum(increments.values(), Decimal("0"))
    payload = {"title": {"fastest": "Get there sooner", "cheapest": "Keep costs down", "balanced": "Find the middle ground"}[alternative["strategy"]],
               "explanation": alternative["explanation"], "flight": alternative["flight"], "arrival_at": stamp(arrival),
               "delay_hours": int((arrival - aware_timestamp(by_key["connection"].end_at)).total_seconds() / 3600),
               "extra_cost": money_string(extra), "schedule_changes": sum(action["start_at"] != action["before_start_at"] for action in actions),
               "tour_moved": tour_moved, "actions": actions, "available": True, "blocked_reason": None,
               "tradeoffs": ["All availability, fees, and journey times are fictional demo data.",
                             "One hour before pickup; 30 minutes before check-in; at least ten hours before the tour."]}
    try:
        linked_inputs(trip, rows, actions)
    except HTTPException as exc:
        payload.update(available=False, blocked_reason=exc.detail)
    return payload


def generate_options(session: Session, owner: str, trip_id: str) -> dict:
    lock_writes(session)
    trip = get_owned_trip(session, owner, trip_id)
    event = session.scalar(select(DisruptionEvent).where(DisruptionEvent.trip_id == trip_id, DisruptionEvent.status == "open"))
    if not event:
        raise HTTPException(409, "Simulate a flight cancellation before comparing recovery options.")
    rows = reservations_for(session, trip_id)
    if {row.key for row in rows} != {"connection", "pickup", "hotel", "tour"}:
        raise HTTPException(409, "This demo reservation set is incomplete. Create a fresh demo.")
    current = snapshot(session, trip, rows)
    previous = list(session.scalars(select(RecoveryPlan).where(RecoveryPlan.disruption_id == event.id)))
    if any(plan.base_fingerprint == current and plan.status in ("pending", "failed") for plan in previous):
        return state(session, owner, trip_id)
    for plan in previous:
        if plan.status == "pending":
            plan.status = "stale"
    source = next(row for row in rows if row.id == event.reservation_id)
    descendants(source.id, {row.id for row in rows}, [(edge.source_id, edge.target_id) for edge in edges_for(session, trip_id)])
    alternatives = MockBookingProvider().search_alternative_flights(source)
    # Only distinct inventory entries become options; no synthesized duplicates.
    seen = set()
    for alternative in alternatives:
        if alternative["flight"] in seen:
            continue
        seen.add(alternative["flight"])
        session.add(RecoveryPlan(id=new_id(), trip_id=trip_id, disruption_id=event.id, strategy=alternative["strategy"],
                                 status="pending", base_fingerprint=current, payload=candidate(trip, rows, alternative)))
    audit(session, trip, owner, "options_generated", "success", f"Compared {len(seen)} distinct mock flight alternatives and checked linked schedules and budget.", event)
    session.commit()
    return state(session, owner, trip_id)


def approve_execute(session: Session, owner: str, trip_id: str, plan_id: str, simulate_failure: bool = False) -> dict:
    lock_writes(session)
    trip = get_owned_trip(session, owner, trip_id)
    plan = session.scalar(select(RecoveryPlan).where(RecoveryPlan.id == plan_id, RecoveryPlan.trip_id == trip_id))
    if not plan:
        raise HTTPException(404, "Recovery plan not found for this trip.")
    if plan.status in ("applied", "failed"):
        return state(session, owner, trip_id)  # Never execute an already-attempted action twice.
    event = session.get(DisruptionEvent, plan.disruption_id)
    rows = reservations_for(session, trip_id)
    if plan.status != "pending" or event.status != "open" or plan.base_fingerprint != snapshot(session, trip, rows):
        plan.status = "stale"
        audit(session, trip, owner, "approval_refused", "failed", "The trip changed; this recovery plan is out of date.", event, plan)
        session.commit()
        raise HTTPException(409, "This plan is out of date. Compare recovery options again before approving.")
    if not plan.payload["available"]:
        raise HTTPException(409, plan.payload["blocked_reason"])
    actions = plan.payload["actions"]
    proposed = linked_inputs(trip, rows, actions)
    by_id = {row.id: row for row in rows}
    plan.approved_at = utc_now()
    audit(session, trip, owner, "user_approved", "success", "User approved this simulated repair and its displayed extra costs.", event, plan,
          simulate_failure=simulate_failure, extra_cost=plan.payload["extra_cost"])
    # A local mock batch is atomic. Failed batches retain the cancellation and
    # at-risk flags, with an audit entry; they never report a successful repair.
    try:
        with session.begin_nested():
            for action in actions:
                MockBookingProvider().execute(by_id[action["reservation_id"]], action,
                                              fail=simulate_failure and action["kind"] == "pickup")
            for item, payload in proposed:
                for field, value in payload.model_dump().items():
                    setattr(item, field, value)
            trip.updated_at = utc_now()
            session.flush()
    except MockBookingError as exc:
        plan.status, plan.error = "failed", str(exc)
        plan.executed_at = utc_now()
        audit(session, trip, owner, "repair_failed", "failed", str(exc), event, plan, rolled_back=True)
    else:
        plan.status, plan.executed_at = "applied", utc_now()
        event.status, event.resolved_at = "resolved", utc_now()
        for action in actions:
            audit(session, trip, owner, action["action"], "success", f"Simulated update saved: {action['title']}", event, plan, change=action)
        for other in session.scalars(select(RecoveryPlan).where(RecoveryPlan.disruption_id == event.id, RecoveryPlan.id != plan.id, RecoveryPlan.status == "pending")):
            other.status = "stale"
        audit(session, trip, owner, "repair_completed", "success", "Simulated reservations and linked itinerary updated. No real bookings were changed.", event, plan)
    session.commit()
    return state(session, owner, trip_id)
