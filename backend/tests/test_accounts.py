import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import create_app
from app.models import Account, AccountAttempt, AccountAudit, AccountSession, TravelerVault, User, utc_now
from app.services import accounts

PASSWORD = "A fictional long account passphrase 2026"
NEXT_PASSWORD = "Another fictional long account passphrase 2026"
BASE = "/api/auth"


def register(client, username="alex.qa", **values):
    return client.post(BASE + "/register", json={"username": username, "password": PASSWORD, "display_name": "Alex QA", **values})


def proof(response):
    return {"X-Profile-Token": accounts.SCOPE_PREFIX + response.json()["csrf_token"]}


def trip_payload():
    return {"name": "Owned Japan", "destination": "Tokyo", "start_date": "2027-05-01", "end_date": "2027-05-05", "travelers": 1, "budget": "3000", "currency": "USD"}


def test_register_hashes_password_and_issues_opaque_cookie_with_csrf(client, application):
    response = register(client, "Alex.QA")
    assert response.status_code == 201, response.text
    assert response.json()["account"]["username"] == "alex.qa"
    assert PASSWORD not in response.text and "password_hash" not in response.text
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=28800" in cookie
    assert response.headers["cache-control"] == "no-store, private"
    assert client.get("/api/profiles/me", headers=proof(response)).status_code == 200
    with application.state.database.session_factory() as session:
        row = session.scalar(select(Account))
        assert row.password_hash.startswith("$argon2id$") and PASSWORD not in row.password_hash
        assert accounts.verify_password(PASSWORD, row.password_hash)
        saved_session = session.scalar(select(AccountSession))
        raw = client.cookies.get(accounts.COOKIE)
        assert saved_session.token_hash == hashlib.sha256(raw.encode()).hexdigest()
        assert raw not in response.text


def test_explicit_link_keeps_owner_trips_and_encrypted_vault_and_retires_legacy_token(client, application):
    local = client.post("/api/profiles", json={"display_name": "Keep my name"}).json()
    legacy = {"X-Profile-Token": local["token"]}
    trip = client.post("/api/trips", headers=legacy, json=trip_payload()).json()
    private = client.post("/api/private-traveler/create", headers=legacy, json={"password": PASSWORD})
    assert private.status_code == 200
    with application.state.database.session_factory() as session:
        ciphertext = session.get(TravelerVault, local["profile"]["id"]).ciphertext
    response = client.post(BASE + "/register", headers=legacy, json={"username": "linked", "password": PASSWORD, "link_current_profile": True})
    assert response.status_code == 201, response.text
    assert response.json()["profile"]["id"] == local["profile"]["id"]
    assert response.json()["profile"]["display_name"] == "Keep my name"
    headers = proof(response)
    assert client.get(f"/api/trips/{trip['id']}", headers=headers).json() == trip
    assert client.get("/api/private-traveler", headers=headers).status_code == 423
    assert client.post("/api/private-traveler/unlock", headers=headers, json={"password": PASSWORD}).status_code == 200
    with application.state.database.session_factory() as session:
        assert session.get(TravelerVault, local["profile"]["id"]).ciphertext == ciphertext
    client.cookies.clear()
    assert client.get(f"/api/trips/{trip['id']}", headers=legacy).status_code == 401
    logged = client.post(BASE + "/login", json={"username": "LINKED", "password": PASSWORD})
    assert logged.status_code == 200
    assert client.get(f"/api/trips/{trip['id']}", headers=proof(logged)).json() == trip


def test_link_requires_current_profile_proof_and_does_not_claim_by_id(client):
    local = client.post("/api/profiles", json={"display_name": "Keep owner"}).json()
    response = register(client, "wrong-owner", link_current_profile=True)
    assert response.status_code == 401
    response = register(client, "wrong-owner", link_current_profile=True, user_id=local["profile"]["id"])
    assert response.status_code == 422
    assert client.get("/api/profiles/me", headers={"X-Profile-Token": local["token"]}).status_code == 200


def test_logout_revokes_cookie_replay_and_new_login_rotates_session(client):
    response = register(client)
    headers = proof(response)
    raw = client.cookies.get(accounts.COOKIE)
    assert client.post(BASE + "/logout", headers=headers, json={}).status_code == 200
    assert client.get(BASE + "/session").status_code == 401
    client.cookies.set(accounts.COOKIE, raw)
    assert client.get("/api/trips", headers=headers).status_code == 401
    client.cookies.clear()
    logged = client.post(BASE + "/login", json={"username": "alex.qa", "password": PASSWORD})
    assert logged.status_code == 200 and client.cookies.get(accounts.COOKIE) != raw


def test_account_and_session_survive_app_restart(client, application):
    response = register(client)
    headers = proof(response)
    trip = client.post("/api/trips", headers=headers, json=trip_payload()).json()
    with TestClient(create_app(application.state.settings)) as reopened:
        reopened.cookies.update(client.cookies)
        current = reopened.get(BASE + "/session")
        assert current.status_code == 200
        assert reopened.get(f"/api/trips/{trip['id']}", headers=proof(current)).json() == trip


@pytest.mark.parametrize("kind", ["idle", "absolute", "revoked"])
def test_expired_or_revoked_sessions_cannot_access_data(client, application, kind):
    response = register(client)
    with application.state.database.session_factory() as session:
        row = session.scalar(select(AccountSession))
        if kind == "idle":
            row.last_seen_at = utc_now() - timedelta(minutes=31)
        elif kind == "absolute":
            row.expires_at = utc_now() - timedelta(seconds=1)
        else:
            row.revoked_at = utc_now()
        session.commit()
    assert client.get("/api/trips", headers=proof(response)).status_code == 401
    assert client.get(BASE + "/session").status_code == 401


def test_missing_or_wrong_csrf_and_cross_origin_changes_are_rejected(client):
    response = register(client)
    assert client.get("/api/trips").status_code == 401
    assert client.get("/api/trips", headers={"X-Profile-Token": "account-session:wrong"}).status_code == 401
    assert client.post("/api/trips", json=trip_payload()).status_code == 401
    assert client.post(BASE + "/logout", json={}).status_code == 401
    assert client.post(BASE + "/logout", headers={**proof(response), "Origin": "https://evil.invalid"}, json={}).status_code == 403
    assert client.get(BASE + "/session").status_code == 200


def test_cookie_scope_cannot_be_mixed_with_another_accounts_proof(client):
    first = register(client, "first")
    old_proof = proof(first)
    trip = client.post("/api/trips", headers=old_proof, json=trip_payload()).json()
    client.post(BASE + "/logout", headers=old_proof, json={})
    second = register(client, "second")
    assert client.get("/api/trips", headers=old_proof).status_code == 401
    assert client.get(f"/api/trips/{trip['id']}", headers=proof(second)).status_code == 404
    assert client.get("/api/trips", headers=proof(second)).json() == []


def test_password_change_invalidates_other_sessions_and_keeps_owned_data(client, application):
    first = register(client)
    headers = proof(first)
    trip = client.post("/api/trips", headers=headers, json=trip_payload()).json()
    with TestClient(create_app(application.state.settings)) as other:
        second = other.post(BASE + "/login", json={"username": "alex.qa", "password": PASSWORD})
        changed = client.post(BASE + "/change-password", headers=headers, json={"current_password": PASSWORD, "new_password": NEXT_PASSWORD})
        assert changed.status_code == 200, changed.text
        assert other.get("/api/trips", headers=proof(second)).status_code == 401
    assert client.get(f"/api/trips/{trip['id']}", headers=proof(changed)).json() == trip
    client.post(BASE + "/logout", headers=proof(changed), json={})
    assert client.post(BASE + "/login", json={"username": "alex.qa", "password": PASSWORD}).status_code == 401
    assert client.post(BASE + "/login", json={"username": "alex.qa", "password": NEXT_PASSWORD}).status_code == 200


def test_failed_password_change_keeps_current_account(client):
    response = register(client)
    failed = client.post(BASE + "/change-password", headers=proof(response), json={"current_password": "wrong", "new_password": NEXT_PASSWORD})
    assert failed.status_code == 401
    assert client.get("/api/trips", headers=proof(response)).status_code == 200


def test_wrong_password_and_unknown_user_have_same_error_and_failures_persist(client, application):
    response = register(client)
    client.post(BASE + "/logout", headers=proof(response), json={})
    known = client.post(BASE + "/login", json={"username": "alex.qa", "password": "wrong"})
    unknown = client.post(BASE + "/login", json={"username": "unknown", "password": "wrong"})
    assert known.status_code == unknown.status_code == 401
    assert known.json() == unknown.json()
    for _ in range(4):
        assert client.post(BASE + "/login", json={"username": "alex.qa", "password": "wrong"}).status_code == 401
    assert client.post(BASE + "/login", json={"username": "alex.qa", "password": PASSWORD}).status_code == 429
    with TestClient(create_app(application.state.settings)) as reopened:
        assert reopened.post(BASE + "/login", json={"username": "alex.qa", "password": PASSWORD}).status_code == 429


def test_duplicate_case_insensitive_username_does_not_replace_account(client, application):
    response = register(client)
    client.post(BASE + "/logout", headers=proof(response), json={})
    assert register(client, "ALEX.QA").status_code == 409
    with application.state.database.session_factory() as session:
        assert len(session.scalars(select(Account)).all()) == 1
        assert len(session.scalars(select(User)).all()) == 1


@pytest.mark.parametrize("password", ["short", "passwordpassword", "123456789012345", "p" * 129])
def test_weak_or_oversized_passwords_are_rejected_without_echo(client, password):
    response = register(client, password=password)
    assert response.status_code == 422 and password not in response.text and '"input"' not in response.text


def test_passwords_and_cookie_secrets_do_not_appear_in_profile_trip_or_audit_data(client, application):
    response = register(client)
    headers = proof(response)
    raw = client.cookies.get(accounts.COOKIE)
    body = client.get("/api/profiles/me", headers=headers).text
    assert PASSWORD not in body and raw not in body and "password_hash" not in body
    with application.state.database.session_factory() as session:
        logs = session.scalars(select(AccountAudit)).all()
        assert {row.action for row in logs} == {"registered"}
        assert all(PASSWORD not in row.action and raw not in row.action for row in logs)


def test_concurrent_registration_only_creates_one_account(client, application):
    def attempt(_):
        with TestClient(create_app(application.state.settings)) as other:
            return register(other, "concurrent").status_code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(attempt, range(2)))
    assert results == [201, 409]
    with application.state.database.session_factory() as session:
        assert len(session.scalars(select(Account)).all()) == 1


def test_cookie_secure_flag_can_be_enabled_for_https_hosting(client, application):
    application.state.settings.auth_cookie_secure = True
    response = register(client)
    assert "; secure" in response.headers["set-cookie"].lower()


def test_account_can_use_the_existing_demo_repair_workflow(client):
    response = register(client)
    headers = proof(response)
    demo = client.post("/api/rescue/demo", headers=headers, json={}).json()["trip_id"]
    path = f"/api/trips/{demo}/rescue"
    assert client.post(path + "/simulate-cancellation", headers=headers).status_code == 200
    choices = client.post(path + "/options", headers=headers).json()
    repaired = client.post(path + f"/plans/{choices['plans'][0]['id']}/approve-execute", headers=headers, json={"approved": True})
    assert repaired.status_code == 200 and repaired.json()["disruption"]["status"] == "resolved"


def test_linking_does_not_invalidate_an_existing_reviewed_itinerary_proposal(client):
    local = client.post("/api/profiles", json={"display_name": "Keep draft"}).json()
    legacy = {"X-Profile-Token": local["token"]}
    trip = client.post("/api/trips", headers=legacy, json=trip_payload()).json()
    draft = client.post(f"/api/trips/{trip['id']}/proposals", headers=legacy, json={"request": "Create an itinerary."})
    assert draft.status_code == 201, draft.text
    linked = client.post(BASE + "/register", headers=legacy, json={"username": "keep.draft", "password": PASSWORD, "link_current_profile": True})
    assert linked.status_code == 201
    saved = client.post(f"/api/trips/{trip['id']}/proposals/{draft.json()['id']}/approve", headers=proof(linked))
    assert saved.status_code == 200, saved.text


def test_selected_trip_chat_uses_account_ownership_without_sending_credentials(client, application, monkeypatch):
    from app.services.conversational_ai import ConversationTurn
    response = register(client)
    headers = proof(response)
    trip = client.post("/api/trips", headers=headers, json=trip_payload()).json()
    captured = []
    async def converse(messages, feature, settings, context, draft):
        captured.append(json.dumps(context))
        return ConversationTurn("Your saved trip is available.")
    monkeypatch.setattr("app.api.buddy.converse", converse)
    application.state.settings.ai_mode = "ollama"
    result = client.post("/api/buddy/chat", headers=headers, json={"trip_id": trip["id"], "messages": [{"role": "user", "content": "Tell me about my trip."}]})
    assert result.status_code == 200
    for secret in (PASSWORD, response.json()["csrf_token"], client.cookies.get(accounts.COOKIE), "password_hash"):
        assert secret not in captured[0]
