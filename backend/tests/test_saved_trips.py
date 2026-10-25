import hashlib
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import User


@pytest.fixture
def profile(client):
    response = client.post("/api/profiles", json={"display_name": "Alex"})
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def headers(profile):
    return {"X-Profile-Token": profile["token"]}


@pytest.fixture
def trip_payload():
    return {
        "name": "Japan with friends", "destination": "Tokyo", "departure_location": "Columbus",
        "start_date": "2027-05-01", "end_date": "2027-05-05", "travelers": 3,
        "budget": "1200.00", "currency": "USD", "status": "planned",
    }


@pytest.fixture
def saved_trip(client, headers, trip_payload):
    response = client.post("/api/trips", json=trip_payload, headers=headers)
    assert response.status_code == 201
    return response.json()


@pytest.fixture
def item_payload():
    return {
        "date": "2027-05-02", "start_time": "10:00", "end_time": "11:30",
        "title": "Garden walk", "description": "Take photographs", "location": "Tokyo",
        "estimated_cost": "10.25", "item_type": "activity", "status": "planned",
    }


def add_item(client, headers, trip_id, payload):
    return client.post(f"/api/trips/{trip_id}/itinerary", json=payload, headers=headers)


def test_profile_create_get_rename_and_only_hashed_token_is_stored(client, application, profile, headers):
    assert len(profile["token"]) >= 43
    assert profile["profile"]["communication_style"] == "friendly"
    assert "token" not in profile["profile"]
    response = client.get("/api/profiles/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["display_name"] == "Alex"
    assert "token" not in response.text

    renamed = client.patch("/api/profiles/me", json={"display_name": "Alex Morgan"}, headers=headers)
    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "Alex Morgan"
    with application.state.database.session_factory() as session:
        row = session.scalar(select(User))
        assert row.token_hash == hashlib.sha256(profile["token"].encode()).hexdigest()
        assert profile["token"] != row.token_hash


def test_profiles_cannot_be_publicly_listed(client):
    assert client.get("/api/profiles").status_code == 405


@pytest.mark.parametrize("display_name", ["", "   ", "x" * 81])
def test_profile_names_are_validated(client, display_name):
    assert client.post("/api/profiles", json={"display_name": display_name}).status_code == 422


def test_profile_and_trip_data_survive_database_and_app_reopen(client, application, headers, saved_trip, item_payload):
    created = add_item(client, headers, saved_trip["id"], item_payload)
    assert created.status_code == 201
    with TestClient(create_app(application.state.settings)) as reopened:
        profile = reopened.get("/api/profiles/me", headers=headers)
        trip = reopened.get(f"/api/trips/{saved_trip['id']}", headers=headers)
    assert profile.status_code == 200
    assert trip.status_code == 200
    assert trip.json()["name"] == saved_trip["name"]
    assert trip.json()["itinerary"][0]["title"] == item_payload["title"]
    assert trip.json()["estimated_total"] == "10.25"


@pytest.mark.parametrize("token", [None, "", "unknown-profile-token", "x" * 257])
def test_profile_and_trip_reads_require_valid_local_token(client, token):
    headers = {"X-Profile-Token": token} if token is not None else {}
    assert client.get("/api/profiles/me", headers=headers).status_code == 401
    assert client.get("/api/trips", headers=headers).status_code == 401


def test_trip_create_list_get_and_edit(client, headers, profile, saved_trip, trip_payload):
    assert saved_trip["owner_id"] == profile["profile"]["id"]
    assert saved_trip["itinerary"] == []
    assert saved_trip["estimated_total"] == "0.00"
    assert saved_trip["remaining_budget"] == "1200.00"
    assert saved_trip["item_count"] == 0
    assert saved_trip["created_at"].endswith("Z")
    listed = client.get("/api/trips", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert "itinerary" not in listed.json()[0]

    changed = {**trip_payload, "name": "A slower Japan trip", "budget": "1000", "status": "active"}
    edited = client.put(f"/api/trips/{saved_trip['id']}", json=changed, headers=headers)
    assert edited.status_code == 200
    assert edited.json()["name"] == changed["name"]
    assert edited.json()["budget"] == "1000.00"
    assert edited.json()["updated_at"] >= saved_trip["updated_at"]


def test_other_profile_cannot_read_edit_or_add_to_owned_trip(client, headers, saved_trip, trip_payload, item_payload):
    outsider = client.post("/api/profiles", json={"display_name": "Jordan"}).json()
    outsider_headers = {"X-Profile-Token": outsider["token"]}
    assert client.get("/api/trips", headers=outsider_headers).json() == []
    url = f"/api/trips/{saved_trip['id']}"
    assert client.get(url, headers=outsider_headers).status_code == 404
    assert client.put(url, json=trip_payload, headers=outsider_headers).status_code == 404
    assert client.post(url + "/itinerary", json=item_payload, headers=outsider_headers).status_code == 404
    original = client.get(url, headers=headers)
    assert original.status_code == 200
    assert original.json()["itinerary"] == []


@pytest.mark.parametrize("field,value", [
    ("name", "   "), ("destination", ""), ("travelers", 0), ("travelers", 51),
    ("travelers", True), ("travelers", 1.5), ("budget", "-1"), ("budget", "1.001"),
    ("budget", "10000000.01"), ("budget", "NaN"), ("budget", 20),
    ("currency", "XYZ"), ("status", "booked"), ("start_date", "2027-02-30"),
    ("end_date", "2027-04-30"), ("end_date", "2028-05-02"),
    ("start_date", "2027-05-01T00:00:00Z"),
])
def test_trip_input_validation(client, headers, trip_payload, field, value):
    payload = {**trip_payload, field: value}
    assert client.post("/api/trips", json=payload, headers=headers).status_code == 422
    assert client.get("/api/trips", headers=headers).json() == []


def test_trip_owner_cannot_be_injected_in_input(client, headers, trip_payload):
    payload = {**trip_payload, "owner_id": str(uuid4())}
    assert client.post("/api/trips", json=payload, headers=headers).status_code == 422


def test_itinerary_crud_budget_and_chronological_order(client, headers, saved_trip, item_payload):
    trip_id = saved_trip["id"]
    first = add_item(client, headers, trip_id, item_payload)
    assert first.status_code == 201
    first_item_id = first.json()["itinerary"][0]["id"]
    assert first.json()["estimated_total"] == "10.25"
    assert first.json()["remaining_budget"] == "1189.75"

    earlier = {**item_payload, "title": "Earlier breakfast", "start_time": "08:00", "end_time": "09:00", "estimated_cost": "4.10", "item_type": "food"}
    second = add_item(client, headers, trip_id, earlier)
    assert second.status_code == 201
    assert [item["title"] for item in second.json()["itinerary"]] == ["Earlier breakfast", "Garden walk"]
    assert second.json()["estimated_total"] == "14.35"

    updated = client.put(
        f"/api/trips/{trip_id}/itinerary/{first_item_id}",
        json={**item_payload, "estimated_cost": "12.20", "title": "Updated walk"}, headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["estimated_total"] == "16.30"
    removed = client.delete(f"/api/trips/{trip_id}/itinerary/{first_item_id}", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["item_count"] == 1
    assert removed.json()["estimated_total"] == "4.10"
    assert client.get(f"/api/trips/{trip_id}", headers=headers).json()["itinerary"] == removed.json()["itinerary"]


@pytest.mark.parametrize("field,value", [
    ("date", "2027-05-06"), ("date", "2027-04-30"), ("date", "2027-02-30"),
    ("end_time", "10:00"), ("end_time", "09:00"), ("start_time", "25:00"),
    ("start_time", "10:00:01"), ("estimated_cost", "-1"), ("estimated_cost", "0.001"),
    ("title", " "), ("item_type", "reservation"), ("status", "confirmed"),
])
def test_itinerary_validation(client, headers, saved_trip, item_payload, field, value):
    response = add_item(client, headers, saved_trip["id"], {**item_payload, field: value})
    assert response.status_code == 422
    assert client.get(f"/api/trips/{saved_trip['id']}", headers=headers).json()["itinerary"] == []


def test_overlap_rejected_but_adjacent_or_cancelled_items_allowed(client, headers, saved_trip, item_payload):
    trip_id = saved_trip["id"]
    assert add_item(client, headers, trip_id, item_payload).status_code == 201
    overlap = {**item_payload, "title": "Conflicting stop", "start_time": "11:00", "end_time": "12:00"}
    response = add_item(client, headers, trip_id, overlap)
    assert response.status_code == 409
    assert response.json()["detail"] == "This activity overlaps another planned activity."
    adjacent = {**item_payload, "start_time": "11:30", "end_time": "12:00"}
    assert add_item(client, headers, trip_id, adjacent).status_code == 201
    cancelled = add_item(client, headers, trip_id, {**overlap, "status": "cancelled", "estimated_cost": "999"})
    assert cancelled.status_code == 201
    assert cancelled.json()["estimated_total"] == "20.50"


def test_cancelled_item_cannot_be_reactivated_into_a_conflict(client, headers, saved_trip, item_payload):
    trip_id = saved_trip["id"]
    assert add_item(client, headers, trip_id, item_payload).status_code == 201
    cancelled = add_item(client, headers, trip_id, {**item_payload, "status": "cancelled"})
    item_id = next(item["id"] for item in cancelled.json()["itinerary"] if item["status"] == "cancelled")
    response = client.put(f"/api/trips/{trip_id}/itinerary/{item_id}", json=item_payload, headers=headers)
    assert response.status_code == 409
    assert client.get(f"/api/trips/{trip_id}", headers=headers).json()["estimated_total"] == "10.25"


def test_concurrent_overlapping_activity_saves_cannot_both_succeed(client, headers, saved_trip, item_payload):
    trip_id = saved_trip["id"]
    with ThreadPoolExecutor(max_workers=2) as executor:
        requests = [executor.submit(add_item, client, headers, trip_id, item_payload) for _ in range(2)]
        responses = [request.result() for request in requests]

    assert sorted(response.status_code for response in responses) == [201, 409]
    trip = client.get(f"/api/trips/{trip_id}", headers=headers).json()
    assert trip["item_count"] == 1
    assert trip["estimated_total"] == "10.25"


def test_date_or_currency_edits_cannot_invalidate_existing_items(client, headers, saved_trip, trip_payload, item_payload):
    trip_id = saved_trip["id"]
    assert add_item(client, headers, trip_id, item_payload).status_code == 201
    date_edit = client.put(f"/api/trips/{trip_id}", json={**trip_payload, "start_date": "2027-05-03"}, headers=headers)
    assert date_edit.status_code == 409
    currency_edit = client.put(f"/api/trips/{trip_id}", json={**trip_payload, "currency": "JPY"}, headers=headers)
    assert currency_edit.status_code == 409
    unchanged = client.get(f"/api/trips/{trip_id}", headers=headers).json()
    assert unchanged["currency"] == "USD"
    assert unchanged["start_date"] == "2027-05-01"


def test_activity_ids_cannot_cross_trip_or_profile_boundaries(client, headers, saved_trip, trip_payload, item_payload):
    first = add_item(client, headers, saved_trip["id"], item_payload).json()
    item_id = first["itinerary"][0]["id"]
    other_trip = client.post("/api/trips", json=trip_payload, headers=headers).json()
    url = f"/api/trips/{other_trip['id']}/itinerary/{item_id}"
    assert client.put(url, json=item_payload, headers=headers).status_code == 404
    assert client.delete(url, headers=headers).status_code == 404

    outsider = client.post("/api/profiles", json={"display_name": "Sam"}).json()
    outsider_headers = {"X-Profile-Token": outsider["token"]}
    owned_url = f"/api/trips/{saved_trip['id']}/itinerary/{item_id}"
    assert client.put(owned_url, json=item_payload, headers=outsider_headers).status_code == 404
    assert client.delete(owned_url, headers=outsider_headers).status_code == 404
    assert client.get(f"/api/trips/{saved_trip['id']}", headers=headers).json()["item_count"] == 1


def test_estimated_spending_can_exceed_budget_without_becoming_a_booking(client, headers, saved_trip, item_payload):
    response = add_item(client, headers, saved_trip["id"], {**item_payload, "estimated_cost": "1300"})
    assert response.status_code == 201
    assert response.json()["remaining_budget"] == "-100.00"
    assert response.json()["itinerary"][0]["status"] == "planned"


def test_cors_allows_profile_header_and_manual_mutations(client):
    for method in ("PATCH", "PUT", "DELETE"):
        response = client.options(
            "/api/trips", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": method,
                                    "Access-Control-Request-Headers": "content-type,x-profile-token"},
        )
        assert response.status_code == 200
        assert "x-profile-token" in response.headers["access-control-allow-headers"].lower()
