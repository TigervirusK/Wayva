import json
from copy import deepcopy
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import TravelerVault, TravelerVaultAudit
from app.services.conversational_ai import ConversationTurn
from app.services.traveler_vault import COOKIE, VaultSessions

PASSWORD = "fictional correct horse battery 2026"
NEW_PASSWORD = "another fictional strong password 2026"
BASE = "/api/private-traveler"


@pytest.fixture
def headers(client):
    created = client.post("/api/profiles", json={"display_name": "Private QA"}).json()
    return {"X-Profile-Token": created["token"]}


@pytest.fixture
def unlocked(client, headers):
    response = client.post(BASE + "/create", headers=headers, json={"password": PASSWORD})
    assert response.status_code == 200, response.text
    return response.json()


def sample_data():
    return {"traveler": {"given_names": "Fictional Private Alex", "family_name": "Example-Person", "email": "vault-qa@example.invalid",
                         "phone": "+12025550123", "home_airport": "CMH", "country_of_residence": "US", "preferred_currency": "USD"},
            "bookings": [{"id": str(uuid4()), "trip_id": None, "airline": "UA", "flight_number": "UA123",
                          "departure_date": "2027-05-01", "origin": "ORD", "destination": "HND", "booking_reference": "QA-SECRET-ABC",
                          "original_seller": "travel_agency", "seller_name": "Fictional original seller"}]}


def save(client, headers, unlocked, data=None):
    return client.put(BASE, headers=headers, json={"revision": unlocked["revision"], "data": data or sample_data()})


def test_create_private_cookie_read_and_lock_are_real(client, headers, unlocked):
    assert unlocked["data"]["bookings"] == []
    status = client.get(BASE + "/status", headers=headers).json()
    assert status["exists"] and status["unlocked"] and 0 < status["expires_in_seconds"] <= 900
    response = client.get(BASE, headers=headers)
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store, private"
    assert client.post(BASE + "/lock", headers=headers).status_code == 200
    assert client.get(BASE, headers=headers).status_code == 423
    assert not client.get(BASE + "/status", headers=headers).json()["unlocked"]


def test_sensitive_data_encrypted_at_rest_and_not_in_audit_or_locked_status(client, application, headers, unlocked):
    data = sample_data()
    response = save(client, headers, unlocked, data)
    assert response.status_code == 200, response.text
    assert response.json()["data"] == data
    with application.state.database.session_factory() as session:
        row = session.scalar(select(TravelerVault))
        assert isinstance(row.ciphertext, bytes) and len(row.salt) == 16
        for secret in (PASSWORD, data["traveler"]["given_names"], data["traveler"]["email"], "QA-SECRET-ABC"):
            assert secret.encode() not in row.ciphertext
        audit = session.scalars(select(TravelerVaultAudit)).all()
        assert {entry.action for entry in audit} == {"created", "saved"}
        assert all(entry.result == "success" for entry in audit)
    client.post(BASE + "/lock", headers=headers)
    assert "QA-SECRET-ABC" not in client.get(BASE + "/status", headers=headers).text
    reopened = client.post(BASE + "/unlock", headers=headers, json={"password": PASSWORD})
    assert reopened.status_code == 200 and reopened.json()["data"] == data


def test_no_password_or_data_echo_in_validation_errors(client, headers):
    for payload in [{"password": "too-short-private"[:5]}, {"password": PASSWORD, "card_number": "4111111111111111"}]:
        response = client.post(BASE + "/create", headers=headers, json=payload)
        assert response.status_code == 422 and '"input"' not in response.text
        assert PASSWORD not in response.text and "4111111111111111" not in response.text
        assert response.headers["cache-control"] == "no-store, private"


def test_wrong_password_throttled_and_never_unlocks(client, headers, unlocked):
    client.post(BASE + "/lock", headers=headers)
    for _ in range(5):
        response = client.post(BASE + "/unlock", headers=headers, json={"password": NEW_PASSWORD})
        assert response.status_code == 423 and NEW_PASSWORD not in response.text
    assert client.post(BASE + "/unlock", headers=headers, json={"password": PASSWORD}).status_code == 429
    assert client.get(BASE, headers=headers).status_code == 423


def test_restart_requires_password_but_preserves_encrypted_details(client, application, headers, unlocked):
    saved = save(client, headers, unlocked)
    assert saved.status_code == 200
    with TestClient(create_app(application.state.settings)) as reopened:
        reopened.cookies.update(client.cookies)
        assert reopened.get(BASE, headers=headers).status_code == 423
        response = reopened.post(BASE + "/unlock", headers=headers, json={"password": PASSWORD})
        assert response.status_code == 200 and response.json()["data"] == saved.json()["data"]


def test_private_session_is_expiring_and_bound_to_profile(client, application, headers, unlocked):
    other = client.post("/api/profiles", json={"display_name": "Other"}).json()
    other_headers = {"X-Profile-Token": other["token"]}
    assert client.get(BASE, headers=other_headers).status_code == 423
    assert not client.get(BASE + "/status", headers=other_headers).json()["exists"]
    for entry in application.state.vault_sessions.entries.values():
        entry.expires = 0
    assert client.get(BASE, headers=headers).status_code == 423
    assert not application.state.vault_sessions.entries


def test_password_rotation_keeps_data_and_rejects_old_password(client, headers, unlocked):
    saved = save(client, headers, unlocked).json()
    response = client.post(BASE + "/change-password", headers=headers,
                           json={"current_password": PASSWORD, "password": NEW_PASSWORD})
    assert response.status_code == 200, response.text
    assert response.json()["data"] == saved["data"]
    client.post(BASE + "/lock", headers=headers)
    assert client.post(BASE + "/unlock", headers=headers, json={"password": PASSWORD}).status_code == 423
    assert client.post(BASE + "/unlock", headers=headers, json={"password": NEW_PASSWORD}).status_code == 200


def test_stale_revision_and_double_creation_do_not_overwrite_details(client, headers, unlocked):
    first = save(client, headers, unlocked)
    assert first.status_code == 200
    assert save(client, headers, unlocked).status_code == 409
    assert client.get(BASE, headers=headers).json()["data"] == first.json()["data"]
    assert client.post(BASE + "/create", headers=headers, json={"password": PASSWORD}).status_code == 409


def test_tampered_ciphertext_is_rejected(client, application, headers, unlocked):
    with application.state.database.session_factory() as session:
        row = session.scalar(select(TravelerVault))
        row.ciphertext = row.ciphertext[:-10] + b"tampered!!"
        session.commit()
    assert client.get(BASE, headers=headers).status_code == 423


def test_encrypted_record_is_bound_to_its_owner_even_with_same_password(client, application, headers, unlocked):
    other = client.post("/api/profiles", json={"display_name": "Same password different owner"}).json()
    other_headers = {"X-Profile-Token": other["token"]}
    assert client.post(BASE + "/create", headers=other_headers, json={"password": PASSWORD}).status_code == 200
    with application.state.database.session_factory() as session:
        target = session.get(TravelerVault, other["profile"]["id"])
        source = session.scalar(select(TravelerVault).where(TravelerVault.user_id != target.user_id))
        target.salt, target.ciphertext = source.salt, source.ciphertext
        session.commit()
    assert client.post(BASE + "/unlock", headers=other_headers, json={"password": PASSWORD}).status_code == 423


@pytest.mark.parametrize("field,value", [("email", "bad-email"), ("phone", "9998887776"), ("home_airport", "<AA>"), ("country_of_residence", "USA")])
def test_contact_fields_are_validated_without_echoing_values(client, headers, unlocked, field, value):
    data = sample_data()
    data["traveler"][field] = value
    response = save(client, headers, unlocked, data)
    assert response.status_code == 422 and '"input"' not in response.text
    assert value not in response.text


def test_raw_cards_passports_provider_flags_and_duplicate_booking_ids_rejected(client, headers, unlocked):
    for extra in ("passport_number", "card_number", "airline_password"):
        data = sample_data()
        data["traveler"][extra] = "private-do-not-echo"
        response = save(client, headers, unlocked, data)
        assert response.status_code == 422 and "private-do-not-echo" not in response.text
    data = sample_data()
    data["bookings"][0]["provider_confirmed"] = True
    assert save(client, headers, unlocked, data).status_code == 422
    data = sample_data()
    data["bookings"].append(deepcopy(data["bookings"][0]))
    assert save(client, headers, unlocked, data).status_code == 422


def test_assistance_uses_fixed_official_link_and_never_claims_booking(client, headers, unlocked):
    data = sample_data()
    assert save(client, headers, unlocked, data).status_code == 200
    response = client.post(BASE + "/rescue-assistance", headers=headers, json={"booking_id": data["bookings"][0]["id"]})
    assert response.status_code == 200
    handoff = response.json()
    assert handoff["official_airline_url"] == "https://www.united.com/en/us/manageres/mytrips"
    assert "QA-SECRET-ABC" not in response.text and "vault-qa@example.invalid" not in response.text
    assert handoff["contact_original_seller"] and not handoff["provider_confirmed"]
    assert handoff["booking_status"] == "not_booked_by_triprescue"
    assert response.headers["cache-control"] == "no-store, private"
    assert client.post(BASE + "/rescue-assistance", headers=headers, json={"booking_id": str(uuid4())}).status_code == 404


def test_real_capabilities_never_depend_on_a_key_or_claim_live_features(client, application, monkeypatch):
    monkeypatch.setenv("DUFFEL_ACCESS_TOKEN", "fictional-do-not-show")
    response = client.get("/api/rescue/real/capabilities")
    assert response.status_code == 200 and "fictional-do-not-show" not in response.text
    result = response.json()
    assert result["assisted_handoff"] and result["encrypted_settings"]
    assert not any(result[key] for key in ("provider_connected", "flight_monitoring", "live_flight_search", "rebooking", "provider_confirmation", "automatic_itinerary_repair", "external_changes", "production_account_ready"))


def test_private_routes_require_profile_and_reject_cross_origin_writes(client, headers, unlocked):
    assert client.get(BASE).status_code == 401
    assert client.get(BASE + "/status").status_code == 401
    assert client.post(BASE + "/lock", headers={**headers, "Origin": "https://evil.invalid"}).status_code == 403
    response = client.post(BASE + "/unlock", headers={**headers, "Origin": "http://127.0.0.1:5173"}, json={"password": PASSWORD})
    assert response.status_code == 200
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=900" in cookie
    assert COOKIE in client.cookies


def test_private_bookings_cannot_link_to_other_profiles_or_demo_trips(client, headers, unlocked):
    other = client.post("/api/profiles", json={"display_name": "Other"}).json()
    other_headers = {"X-Profile-Token": other["token"]}
    other_demo = client.post("/api/rescue/demo", headers=other_headers, json={}).json()["trip_id"]
    data = sample_data()
    data["bookings"][0]["trip_id"] = other_demo
    assert save(client, headers, unlocked, data).status_code == 404
    own_demo = client.post("/api/rescue/demo", headers=headers, json={}).json()["trip_id"]
    data["bookings"][0]["trip_id"] = own_demo
    assert save(client, headers, unlocked, data).status_code == 409


def test_private_details_are_never_automatically_added_to_pip(client, application, headers, unlocked, monkeypatch):
    assert save(client, headers, unlocked).status_code == 200
    trip = client.post("/api/trips", headers=headers, json={"name": "Public trip facts", "destination": "Tokyo", "start_date": "2027-05-01", "end_date": "2027-05-05", "travelers": 1, "budget": "3000", "currency": "USD"}).json()
    captured = []
    async def converse(messages, feature, settings, context, draft):
        captured.append(json.dumps(context))
        return ConversationTurn("Only your normal trip facts are available here.")
    monkeypatch.setattr("app.api.buddy.converse", converse)
    application.state.settings.ai_mode = "ollama"
    response = client.post("/api/buddy/chat", headers=headers, json={"trip_id": trip["id"], "messages": [{"role": "user", "content": "What do you know about this trip?"}]})
    assert response.status_code == 200
    assert "QA-SECRET-ABC" not in captured[0] and "vault-qa@example.invalid" not in captured[0]
    assert "Fictional Private Alex" not in captured[0] and PASSWORD not in captured[0]


def test_bounded_session_cache_and_profile_binding():
    sessions = VaultSessions()
    for _ in range(6):
        sessions.issue("owner", b"key", "revision")
    assert len(sessions.entries) == 4
    for owner in range(140):
        sessions.issue(str(owner), b"key", "revision")
    assert len(sessions.entries) == 128
    sessions.clear()
    assert not sessions.entries and not sessions.attempts
