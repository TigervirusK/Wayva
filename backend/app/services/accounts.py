"""Password accounts, persistent opaque sessions, CSRF, and owned-profile linking."""
import hashlib
import secrets
from collections import OrderedDict
from datetime import timedelta
from threading import BoundedSemaphore, RLock
from time import monotonic

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from fastapi import HTTPException, Request
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, AccountAttempt, AccountAudit, AccountSession, User, new_id, utc_now

COOKIE = "triprescue_account_session"
SCOPE_PREFIX = "account-session:"
ABSOLUTE_SECONDS = 8 * 60 * 60
IDLE_SECONDS = 30 * 60
HASH_SLOTS = BoundedSemaphore(2)


def aware(value):
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def hash_password(password):
    if not HASH_SLOTS.acquire(blocking=False):
        raise HTTPException(503, "Account authentication is busy. Try again shortly.")
    try:
        return Argon2id(salt=secrets.token_bytes(16), length=32, iterations=3, lanes=1,
                        memory_cost=64 * 1024).derive_phc_encoded(password.encode())
    finally:
        HASH_SLOTS.release()


def verify_password(password, encoded):
    if not HASH_SLOTS.acquire(blocking=False):
        raise HTTPException(503, "Account authentication is busy. Try again shortly.")
    try:
        Argon2id.verify_phc_encoded(password.encode(), encoded)
        return True
    except (InvalidKey, ValueError):
        return False
    finally:
        HASH_SLOTS.release()


DUMMY_PASSWORD_HASH = hash_password(secrets.token_urlsafe(32))


class AuthLimiter:
    """Bound memory and hashing volume; per-name failures also persist in SQLite."""
    def __init__(self):
        self.entries = OrderedDict()
        self.lock = RLock()
        self.dummy_hash = DUMMY_PASSWORD_HASH

    def reserve(self, ip):
        with self.lock:
            now = monotonic()
            for key in [key for key, times in self.entries.items() if not any(t > now - 60 for t in times)]:
                del self.entries[key]
            key = digest(ip)
            times = [t for t in self.entries.get(key, []) if t > now - 60]
            if len(times) >= 30:
                raise HTTPException(429, "Too many account requests. Wait a minute before trying again.")
            self.entries[key] = [*times, now]
            self.entries.move_to_end(key)
            while len(self.entries) > 1024:
                self.entries.popitem(last=False)


def audit(session, owner, action, result="success"):
    session.add(AccountAudit(user_id=owner, action=action, result=result))


def session_for_cookie(session: Session, cookie: str | None):
    if not cookie or len(cookie) > 256:
        return None
    row = session.scalar(select(AccountSession).where(AccountSession.token_hash == digest(cookie)).execution_options(populate_existing=True))
    now = utc_now()
    if not row or row.revoked_at is not None or aware(row.expires_at) <= now or aware(row.last_seen_at) + timedelta(seconds=IDLE_SECONDS) <= now:
        return None
    return row


def require_account(session: Session, request: Request, proof: str | None = None, *, touch: bool = True):
    row = session_for_cookie(session, request.cookies.get(COOKIE))
    if row is None:
        raise HTTPException(401, "Your account session has ended. Sign in again.")
    if proof is None:
        proof = request.headers.get("X-Profile-Token")
    if not proof or not proof.startswith(SCOPE_PREFIX) or not secrets.compare_digest(proof[len(SCOPE_PREFIX):], row.csrf_token):
        raise HTTPException(401, "Your account session changed. Reload or sign in again.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("origin")
        if origin and origin not in request.app.state.settings.cors_origins:
            raise HTTPException(403, "This change must come from the Wayva website.")
    # Refresh activity at most once per minute, before caller's write transaction.
    if touch and aware(row.last_seen_at) + timedelta(seconds=60) < utc_now():
        row.last_seen_at = utc_now()
        session.commit()
    profile = session.get(User, row.user_id)
    if profile is None:
        raise HTTPException(401, "Your account could not be opened. Sign in again.")
    return profile, row


def response_data(session, row):
    from app.services.trips import serialize_profile
    account = session.get(Account, row.user_id)
    profile = session.get(User, row.user_id)
    return {"account": {"username": account.username}, "profile": serialize_profile(profile).model_dump(mode="json"),
            "csrf_token": row.csrf_token, "expires_at": aware(row.expires_at).isoformat(),
            "idle_timeout_seconds": IDLE_SECONDS}


def new_session(session, owner):
    now = utc_now()
    raw = secrets.token_urlsafe(32)
    row = AccountSession(id=new_id(), user_id=owner, token_hash=digest(raw), csrf_token=secrets.token_urlsafe(32),
                         created_at=now, last_seen_at=now, expires_at=now + timedelta(seconds=ABSOLUTE_SECONDS))
    session.add(row)
    # Limit active sessions per account without affecting another account.
    current = session.scalars(select(AccountSession).where(AccountSession.user_id == owner,
              AccountSession.revoked_at.is_(None)).order_by(AccountSession.created_at.desc())).all()
    for old in current[10:]:
        if old.id != row.id:
            old.revoked_at = now
    return row, raw


def register(session: Session, request: Request, payload, legacy_token: str | None):
    from app.services.trips import lock_writes, require_profile
    request.app.state.auth_limiter.reserve(request.client.host if request.client else "local")
    if session_for_cookie(session, request.cookies.get(COOKIE)):
        raise HTTPException(409, "Sign out before creating another account.")
    encoded = hash_password(payload.password.get_secret_value())
    lock_writes(session)
    if session.scalar(select(Account.user_id).where(Account.username == payload.username)):
        raise HTTPException(409, "That username is unavailable. Choose another one.")
    if payload.link_current_profile:
        profile = require_profile(session, legacy_token)
        if session.get(Account, profile.id):
            raise HTTPException(409, "This profile already has an account. Sign in instead.")
        # Retire the old browser bearer token only as part of the explicit claim.
        profile.token_hash = digest(secrets.token_urlsafe(32))
    else:
        profile = User(id=new_id(), display_name=payload.display_name or payload.username,
                       token_hash=digest(secrets.token_urlsafe(32)))
        session.add(profile)
        session.flush()
    account = Account(user_id=profile.id, username=payload.username, password_hash=encoded)
    session.add(account)
    try:
        session.flush()
        row, raw = new_session(session, profile.id)
        audit(session, profile.id, "registered")
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "That username or profile is already linked. Sign in or choose another username.") from None
    request.app.state.vault_sessions.forget_owner(profile.id)
    return response_data(session, row), raw


def login(session: Session, request: Request, payload):
    from app.services.trips import lock_writes
    ip = request.client.host if request.client else "local"
    request.app.state.auth_limiter.reserve(ip)
    lock_writes(session)
    key = digest("login:" + payload.username + ":" + ip)
    attempt = session.get(AccountAttempt, key)
    now = utc_now()
    if attempt and attempt.blocked_until and aware(attempt.blocked_until) > now:
        raise HTTPException(429, "Too many failed sign-ins. Wait fifteen minutes before trying again.")
    account = session.scalar(select(Account).where(Account.username == payload.username))
    encoded = account.password_hash if account else request.app.state.auth_limiter.dummy_hash
    valid = verify_password(payload.password.get_secret_value(), encoded)
    if account is None or not valid:
        if attempt is None:
            attempt = AccountAttempt(key=key, failures=0, window_started_at=now)
            session.add(attempt)
        if aware(attempt.window_started_at) + timedelta(minutes=15) <= now:
            attempt.failures, attempt.window_started_at, attempt.blocked_until = 0, now, None
        attempt.failures += 1
        if attempt.failures >= 5:
            attempt.blocked_until = now + timedelta(minutes=15)
        audit(session, None, "login", "failed")
        session.commit()
        raise HTTPException(401, "The username or password is incorrect.")
    if attempt:
        session.delete(attempt)
    previous = session_for_cookie(session, request.cookies.get(COOKIE))
    if previous:
        previous.revoked_at = now
    row, raw = new_session(session, account.user_id)
    audit(session, account.user_id, "login")
    session.commit()
    return response_data(session, row), raw


def logout(session, request):
    row = session_for_cookie(session, request.cookies.get(COOKIE))
    if row:
        _, row = require_account(session, request)
        row.revoked_at = utc_now()
        audit(session, row.user_id, "logout")
        session.commit()
    request.app.state.vault_sessions.forget(request.cookies.get("triprescue_vault_session"))


def change_password(session, request, payload):
    from app.services.trips import lock_writes
    owner, _ = require_account(session, request)
    request.app.state.auth_limiter.reserve(request.client.host if request.client else "local")
    lock_writes(session)
    account = session.get(Account, owner.id)
    if not verify_password(payload.current_password.get_secret_value(), account.password_hash):
        audit(session, owner.id, "password_change", "failed")
        session.commit()
        raise HTTPException(401, "The current account password is incorrect.")
    account.password_hash = hash_password(payload.new_password.get_secret_value())
    account.password_changed_at = utc_now()
    session.execute(update(AccountSession).where(AccountSession.user_id == owner.id,
                    AccountSession.revoked_at.is_(None)).values(revoked_at=utc_now()))
    row, raw = new_session(session, owner.id)
    audit(session, owner.id, "password_changed")
    session.commit()
    request.app.state.vault_sessions.forget_owner(owner.id)
    return response_data(session, row), raw
