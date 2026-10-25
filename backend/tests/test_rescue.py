from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import Reservation, Trip
from app.services.rescue import MockBookingProvider, descendants


@pytest.fixture
def owner(client):
    profile = client.post("/api/profiles", json={"display_name": "Rescue QA"}).json()
    return {"X-Profile-Token": profile["token"]}


@pytest.fixture
def scenario(client, owner):
    result = client.post("/api/rescue/demo", headers=owner, json={})
    assert result.status_code == 200, result.text
    return result.json()["trip_id"]


def path(trip):
    return f"/api/trips/{trip}/rescue"


def options(client, owner, scenario):
    response = client.post(path(scenario) + "/simulate-cancellation", headers=owner)
    assert response.status_code == 200, response.text
    response = client.post(path(scenario) + "/options", headers=owner)
    assert response.status_code == 200, response.text
    return response.json()


def approve(client, owner, scenario, plan, **payload):
    return client.post(path(scenario) + f"/plans/{plan}/approve-execute", headers=owner,
                       json={"approved": True, **payload})


def test_demo_is_explicit_owned_and_reopens_without_duplicate_data(client, owner, scenario):
    state = client.get(path(scenario), headers=owner).json()
    assert state["scenario_ready"] and state["simulated"]
    assert len(state["reservations"]) == 4 and len(state["dependencies"]) == 3
    assert state["disruption"] is None and state["plans"] == []
    assert all(row["simulated"] and row["status"] == "confirmed" for row in state["reservations"])
    assert client.post("/api/rescue/demo", headers=owner, json={}).json() == {"trip_id": scenario, "created": False}
    assert len(client.get("/api/trips", headers=owner).json()) == 1
    fresh = client.post("/api/rescue/demo", headers=owner, json={"fresh": True}).json()
    assert fresh["trip_id"] != scenario and fresh["created"]
    assert len(client.get("/api/trips", headers=owner).json()) == 2


def test_cancellation_traverses_chain_and_does_not_duplicate_on_retry(client, owner, scenario):
    a = client.post(path(scenario) + "/simulate-cancellation", headers=owner).json()
    b = client.post(path(scenario) + "/simulate-cancellation", headers=owner).json()
    assert a == b
    assert len(a["disruption"]["details"]["affected_ids"]) == 3
    assert [row["status"] for row in a["reservations"]] == ["cancelled", "at_risk", "at_risk", "at_risk"]
    itinerary = client.get(f"/api/trips/{scenario}", headers=owner).json()["itinerary"]
    assert sum(item["status"] == "cancelled" for item in itinerary) == 1


def test_three_ranked_options_use_distinct_inventory_and_protect_rest(client, owner, scenario):
    state = options(client, owner, scenario)
    plans = {plan["strategy"]: plan for plan in state["plans"]}
    assert set(plans) == {"fastest", "cheapest", "balanced"}
    assert len({plan["flight"] for plan in plans.values()}) == 3
    assert all(plan["available"] for plan in plans.values())
    assert plans["fastest"]["delay_hours"] < plans["balanced"]["delay_hours"] < plans["cheapest"]["delay_hours"]
    assert Decimal(plans["cheapest"]["extra_cost"]) < Decimal(plans["balanced"]["extra_cost"]) < Decimal(plans["fastest"]["extra_cost"])
    assert not plans["fastest"]["tour_moved"] and plans["balanced"]["tour_moved"] and plans["cheapest"]["tour_moved"]
    for plan in plans.values():
        actions = {action["kind"]: action for action in plan["actions"]}
        assert datetime.fromisoformat(actions["tour"]["start_at"]) - datetime.fromisoformat(actions["hotel"]["end_at"]) >= timedelta(hours=10)
    again = client.post(path(scenario) + "/options", headers=owner).json()
    assert {plan["id"] for plan in again["plans"]} == {plan["id"] for plan in plans.values()}


@pytest.mark.parametrize("strategy", ["fastest", "cheapest", "balanced"])
def test_approved_repair_updates_reservations_itinerary_audit_and_survives_reopen(client, application, owner, scenario, strategy):
    state = options(client, owner, scenario)
    plan = next(plan for plan in state["plans"] if plan["strategy"] == strategy)
    result = approve(client, owner, scenario, plan["id"])
    assert result.status_code == 200, result.text
    after = result.json()
    assert after["disruption"]["status"] == "resolved"
    assert all(row["status"] == "confirmed" for row in after["reservations"])
    assert next(row for row in after["plans"] if row["id"] == plan["id"])["status"] == "applied"
    trip = client.get(f"/api/trips/{scenario}", headers=owner).json()
    assert len(trip["itinerary"]) == 4
    assert Decimal(trip["estimated_total"]) == Decimal("1400") + Decimal(plan["extra_cost"])
    assert all(item["status"] == "planned" for item in trip["itinerary"])
    assert after["audit"][-1]["action"] == "repair_completed"
    assert sum(log["action"] == "user_approved" for log in after["audit"]) == 1
    assert approve(client, owner, scenario, plan["id"]).json() == after
    with TestClient(create_app(application.state.settings)) as reopened:
        assert reopened.get(path(scenario), headers=owner).json() == after


def test_approval_is_required_and_arbitrary_actions_are_not_accepted(client, owner, scenario):
    state = options(client, owner, scenario)
    target = path(scenario) + f"/plans/{state['plans'][0]['id']}/approve-execute"
    for payload in ({}, {"approved": False}, {"approved": 1}, {"approved": "true"}, {"approved": True, "actions": []}):
        assert client.post(target, headers=owner, json=payload).status_code == 422
    assert client.get(path(scenario), headers=owner).json() == state


def test_failure_is_atomic_honest_audited_and_not_executed_twice(client, owner, scenario):
    before = options(client, owner, scenario)
    plan = before["plans"][0]
    result = approve(client, owner, scenario, plan["id"], simulate_failure=True)
    assert result.status_code == 200, result.text
    after = result.json()
    failed = next(row for row in after["plans"] if row["id"] == plan["id"])
    assert failed["status"] == "failed" and "No repair changes were saved" in failed["error"]
    assert after["disruption"]["status"] == "open" and after["reservations"] == before["reservations"]
    assert after["audit"][-1]["action"] == "repair_failed" and after["audit"][-1]["details"]["rolled_back"]
    assert approve(client, owner, scenario, plan["id"]).json() == after
    other = next(row for row in after["plans"] if row["status"] == "pending")
    assert approve(client, owner, scenario, other["id"]).json()["disruption"]["status"] == "resolved"


def test_stale_trip_changes_are_rejected_and_can_be_regenerated(client, application, owner, scenario):
    state = options(client, owner, scenario)
    with application.state.database.session_factory() as session:
        trip = session.get(Trip, scenario)
        trip.budget = Decimal("3500")
        session.commit()
    assert approve(client, owner, scenario, state["plans"][0]["id"]).status_code == 409
    refreshed = client.post(path(scenario) + "/options", headers=owner).json()
    pending = [plan for plan in refreshed["plans"] if plan["status"] == "pending"]
    assert len(pending) == 3
    assert approve(client, owner, scenario, pending[0]["id"]).status_code == 200


def test_budget_limits_and_existing_schedule_conflicts_disable_unusable_options(client, application, owner, scenario):
    with application.state.database.session_factory() as session:
        session.get(Trip, scenario).budget = Decimal("1500")
        session.commit()
    state = options(client, owner, scenario)
    assert sum(plan["available"] for plan in state["plans"]) == 1
    blocked = next(plan for plan in state["plans"] if not plan["available"])
    assert "budget" in blocked["blocked_reason"]
    assert approve(client, owner, scenario, blocked["id"]).status_code == 409


def test_manual_itinerary_conflicts_and_missing_links_are_not_overwritten(client, owner, scenario):
    conflict = {"date": "2027-05-01", "start_time": "18:30", "end_time": "19:30", "title": "Keep my dinner",
                "location": "Tokyo", "estimated_cost": "15", "item_type": "food", "status": "planned"}
    assert client.post(f"/api/trips/{scenario}/itinerary", headers=owner, json=conflict).status_code == 201
    state = options(client, owner, scenario)
    fastest = next(plan for plan in state["plans"] if plan["strategy"] == "fastest")
    assert not fastest["available"] and "overlap" in fastest["blocked_reason"]
    row = state["reservations"][-1]
    assert client.delete(f"/api/trips/{scenario}/itinerary/{row['itinerary_item_id']}", headers=owner).status_code == 200
    refreshed = client.post(path(scenario) + "/options", headers=owner).json()
    assert not any(plan["available"] for plan in refreshed["plans"] if plan["status"] == "pending")


def test_ownership_and_missing_profile_cover_all_rescue_operations(client, owner, scenario):
    state = options(client, owner, scenario)
    other = client.post("/api/profiles", json={"display_name": "Other"}).json()
    for headers, expected in [({}, 401), ({"X-Profile-Token": other["token"]}, 404)]:
        assert client.get(path(scenario), headers=headers).status_code == expected
        assert client.post(path(scenario) + "/simulate-cancellation", headers=headers).status_code == expected
        assert client.post(path(scenario) + "/options", headers=headers).status_code == expected
        assert approve(client, headers, scenario, state["plans"][0]["id"]).status_code == expected
    assert client.post("/api/rescue/demo", json={}).status_code == 401


def test_ordinary_trips_are_not_seeded_or_disrupted(client, owner):
    trip = client.post("/api/trips", headers=owner, json={"name": "Keep this", "destination": "Paris", "start_date": "2027-01-01",
                       "end_date": "2027-01-02", "travelers": 1, "budget": "100", "currency": "EUR"}).json()
    assert client.get(path(trip["id"]), headers=owner).json()["reservations"] == []
    assert client.post(path(trip["id"]) + "/simulate-cancellation", headers=owner).status_code == 409
    assert client.get(f"/api/trips/{trip['id']}", headers=owner).json() == trip


def test_dag_traversal_handles_diamonds_unrelated_nodes_cycles_and_foreign_edges():
    assert set(descendants("a", set("abcde"), [("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")])) == set("bcd")
    for edges in [[("a", "b"), ("b", "a")], [("a", "z")]]:
        with pytest.raises(HTTPException):
            descendants("a", set("abc"), edges)


def test_inventory_is_not_expanded_into_fake_distinct_options(client, owner, scenario, monkeypatch):
    search = MockBookingProvider.search_alternative_flights
    monkeypatch.setattr(MockBookingProvider, "search_alternative_flights", lambda self, original: [search(self, original)[0]] * 3)
    assert len(options(client, owner, scenario)["plans"]) == 1


def test_concurrent_approval_executes_one_batch(client, application, owner, scenario):
    state = options(client, owner, scenario)
    plan = state["plans"][0]
    def attempt(_):
        with TestClient(create_app(application.state.settings)) as concurrent:
            return approve(concurrent, owner, scenario, plan["id"]).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(attempt, range(2))) == [200, 200]
    after = client.get(path(scenario), headers=owner).json()
    assert sum(log["action"] == "repair_completed" for log in after["audit"]) == 1


def test_pip_receives_only_owned_readonly_recovery_context(client, application, owner, scenario, monkeypatch):
    import json
    from app.services.conversational_ai import ConversationTurn
    captured = []
    async def explain(messages, feature, settings, context, draft):
        captured.append(context)
        return ConversationTurn("These are simulated choices. Open Domino Rescue to approve a repair.")
    monkeypatch.setattr("app.api.buddy.converse", explain)
    application.state.settings.ai_mode = "ollama"
    payload = {"trip_id": scenario, "feature": "rescue", "messages": [{"role": "user", "content": "What happened to my pickup?"}]}
    before = options(client, owner, scenario)
    assert client.post("/api/buddy/chat", headers=owner, json=payload).status_code == 200
    recovery = captured[-1]["domino_rescue"]
    assert recovery["simulated"] and recovery["disruption_status"] == "open"
    assert len(recovery["recovery_options"]) == 3
    assert "owner_id" not in json.dumps(captured) and owner["X-Profile-Token"] not in json.dumps(captured)
    assert client.get(path(scenario), headers=owner).json() == before
    other = client.post("/api/profiles", json={"display_name": "Another owner"}).json()
    assert client.post("/api/buddy/chat", headers={"X-Profile-Token": other["token"]}, json=payload).status_code == 404
    assert len(captured) == 1
    assert approve(client, owner, scenario, before["plans"][0]["id"]).status_code == 200
    assert client.post("/api/buddy/chat", headers=owner, json=payload).status_code == 200
    assert captured[-1]["domino_rescue"]["disruption_status"] == "resolved"


def test_failed_old_plans_do_not_hide_new_options_after_trip_edits(client, application, owner, scenario):
    before = options(client, owner, scenario)
    assert approve(client, owner, scenario, before["plans"][0]["id"], simulate_failure=True).status_code == 200
    with application.state.database.session_factory() as session:
        session.get(Trip, scenario).budget = Decimal("3500")
        session.commit()
    stale = client.get(path(scenario), headers=owner).json()
    assert all(plan["status"] == "stale" for plan in stale["plans"])
    refreshed = client.post(path(scenario) + "/options", headers=owner).json()
    assert sum(plan["status"] == "pending" for plan in refreshed["plans"]) == 3


def test_changed_reservation_prevents_outdated_approval(client, application, owner, scenario):
    before = options(client, owner, scenario)
    with application.state.database.session_factory() as session:
        row = session.scalar(select(Reservation).where(Reservation.trip_id == scenario, Reservation.kind == "pickup"))
        row.start_at += timedelta(minutes=15)
        session.commit()
    assert approve(client, owner, scenario, before["plans"][0]["id"]).status_code == 409
    assert client.get(path(scenario), headers=owner).json()["disruption"]["status"] == "open"


def test_recovery_refuses_to_change_non_simulated_provider_reservations(client, application, owner, scenario):
    options(client, owner, scenario)
    with application.state.database.session_factory() as session:
        row = session.scalar(select(Reservation).where(Reservation.trip_id == scenario, Reservation.kind == "pickup"))
        row.simulated = False
        session.commit()
    updated = client.post(path(scenario) + "/options", headers=owner).json()
    plan = next(plan for plan in updated["plans"] if plan["status"] == "pending")
    response = approve(client, owner, scenario, plan["id"])
    assert response.status_code == 200
    assert next(item for item in response.json()["plans"] if item["id"] == plan["id"])["status"] == "failed"
    assert response.json()["disruption"]["status"] == "open"


def test_concurrent_option_generation_does_not_duplicate_inventory(client, application, owner, scenario):
    client.post(path(scenario) + "/simulate-cancellation", headers=owner)
    def attempt(_):
        with TestClient(create_app(application.state.settings)) as concurrent:
            return concurrent.post(path(scenario) + "/options", headers=owner).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(attempt, range(2))) == [200, 200]
    assert len(client.get(path(scenario), headers=owner).json()["plans"]) == 3
