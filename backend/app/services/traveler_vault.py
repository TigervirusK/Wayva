"""Password-derived encryption with bounded, short-lived in-memory unlock sessions.

Local foundation, not a production identity system. No provider is called; no
vault data is added to the existing models used by chat or public trip responses.
"""
import base64
import hashlib
import json
import secrets
from collections import OrderedDict
from dataclasses import dataclass
from threading import BoundedSemaphore, RLock
from time import monotonic

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Reservation, TravelerVault, TravelerVaultAudit, new_id, utc_now
from app.schemas.traveler import VaultData
from app.services.trips import get_owned_trip, lock_writes

TTL = 900
COOKIE = "triprescue_vault_session"
KDF_SLOTS = BoundedSemaphore(2)


def derive_key(password: str, salt: bytes) -> bytes:
    if not KDF_SLOTS.acquire(blocking=False):
        raise HTTPException(503, "The private vault is busy. Try unlocking again shortly.")
    try:
        return base64.urlsafe_b64encode(Argon2id(salt=salt, length=32, iterations=3, lanes=1,
                                              memory_cost=64 * 1024).derive(password.encode("utf-8")))
    finally:
        KDF_SLOTS.release()


@dataclass
class UnlockSession:
    owner: str
    key: bytes
    revision: str
    expires: float


class VaultSessions:
    def __init__(self):
        self.entries = OrderedDict()
        self.attempts = OrderedDict()
        self.lock = RLock()

    def _prune(self):
        now = monotonic()
        for key in [key for key, value in self.entries.items() if value.expires <= now]:
            del self.entries[key]
        for owner in [owner for owner, times in self.attempts.items() if not any(t > now - 300 for t in times)]:
            del self.attempts[owner]

    def try_unlock(self, owner):
        with self.lock:
            self._prune()
            times = [t for t in self.attempts.get(owner, []) if t > monotonic() - 300]
            if len(times) >= 5:
                raise HTTPException(429, "Too many vault unlock attempts. Wait five minutes before trying again.")
            self.attempts[owner] = [*times, monotonic()]
            self.attempts.move_to_end(owner)
            while len(self.attempts) > 1024:
                self.attempts.popitem(last=False)

    def issue(self, owner, key, revision):
        with self.lock:
            self._prune()
            existing = [token for token, value in self.entries.items() if value.owner == owner]
            for token in existing[:-3]:
                self.entries.pop(token, None)
            token = secrets.token_urlsafe(32)
            self.entries[hashlib.sha256(token.encode()).hexdigest()] = UnlockSession(owner, key, revision, monotonic() + TTL)
            while len(self.entries) > 128:
                self.entries.popitem(last=False)
            self.attempts.pop(owner, None)
            return token

    def get(self, token, owner, revision):
        with self.lock:
            self._prune()
            entry = self.entries.get(hashlib.sha256((token or "").encode()).hexdigest())
            if not entry or entry.owner != owner or entry.revision != revision:
                raise HTTPException(423, "Your private traveler details are locked. Unlock them in Settings.")
            return entry

    def forget(self, token):
        with self.lock:
            self.entries.pop(hashlib.sha256((token or "").encode()).hexdigest(), None)

    def forget_owner(self, owner):
        with self.lock:
            for token in [token for token, value in self.entries.items() if value.owner == owner]:
                del self.entries[token]

    def clear(self):
        with self.lock:
            self.entries.clear()
            self.attempts.clear()

    def prune_expired(self):
        with self.lock:
            self._prune()


def log(session, owner, action, result="success"):
    # No names, references, email addresses, passwords, or payloads in this log.
    session.add(TravelerVaultAudit(user_id=owner, action=action, result=result))


def encrypt(owner: str, data: VaultData, key: bytes) -> bytes:
    # Bind the encrypted payload to its owner to reject whole-record transplants.
    payload = {"schema": 1, "owner": owner, "data": data.model_dump(mode="json")}
    return Fernet(key).encrypt(json.dumps(payload, separators=(",", ":")).encode())


def decrypt(row: TravelerVault, key: bytes) -> VaultData:
    try:
        payload = json.loads(Fernet(key).decrypt(row.ciphertext))
        if not isinstance(payload, dict) or set(payload) != {"schema", "owner", "data"} or payload["schema"] != 1 or payload["owner"] != row.user_id:
            raise ValueError("Invalid private envelope")
        return VaultData.model_validate(payload["data"])
    except (InvalidToken, ValidationError, ValueError, TypeError):
        raise HTTPException(423, "The vault could not be unlocked. Check your password; damaged data also cannot be opened.") from None


def status(session: Session, owner: str, sessions: VaultSessions, cookie: str | None) -> dict:
    row = session.get(TravelerVault, owner)
    unlocked = False
    remaining = 0
    if row:
        try:
            entry = sessions.get(cookie, owner, row.revision)
            unlocked = True
            remaining = max(0, int(entry.expires - monotonic()))
        except HTTPException:
            pass
    return {"exists": row is not None, "unlocked": unlocked, "expires_in_seconds": remaining,
            "production_account_ready": False}


def create(session: Session, owner: str, password: str, sessions: VaultSessions) -> tuple[dict, str]:
    sessions.try_unlock(owner)
    salt = secrets.token_bytes(16)
    key = derive_key(password, salt)
    lock_writes(session)
    if session.get(TravelerVault, owner):
        raise HTTPException(409, "Private traveler details already exist. Unlock them instead.")
    row = TravelerVault(user_id=owner, salt=salt, ciphertext=encrypt(owner, VaultData(), key), revision=new_id())
    session.add(row)
    log(session, owner, "created")
    session.commit()
    cookie = sessions.issue(owner, key, row.revision)
    return {"revision": row.revision, "data": VaultData().model_dump(mode="json")}, cookie


def unlock(session: Session, owner: str, password: str, sessions: VaultSessions) -> tuple[dict, str]:
    sessions.try_unlock(owner)
    row = session.get(TravelerVault, owner)
    if not row:
        raise HTTPException(404, "Create your private traveler details first.")
    key = derive_key(password, row.salt)
    try:
        data = decrypt(row, key)
    except HTTPException:
        log(session, owner, "unlock", "failed")
        session.commit()
        raise
    log(session, owner, "unlock")
    session.commit()
    return {"revision": row.revision, "data": data.model_dump(mode="json")}, sessions.issue(owner, key, row.revision)


def read(session: Session, owner: str, sessions: VaultSessions, cookie: str | None) -> tuple[TravelerVault, UnlockSession, VaultData]:
    row = session.get(TravelerVault, owner)
    if not row:
        raise HTTPException(423, "Create and unlock your private traveler details in Settings first.")
    entry = sessions.get(cookie, owner, row.revision)
    return row, entry, decrypt(row, entry.key)


def save(session: Session, owner: str, sessions: VaultSessions, cookie: str | None, revision: str, data: VaultData) -> dict:
    lock_writes(session)
    row, entry, _ = read(session, owner, sessions, cookie)
    if revision != row.revision:
        raise HTTPException(409, "Your private details changed in another tab. Reload them before saving again.")
    for booking in data.bookings:
        if booking.trip_id is not None:
            trip_id = str(booking.trip_id)
            get_owned_trip(session, owner, trip_id)
            if session.scalar(select(Reservation.id).where(Reservation.trip_id == trip_id, Reservation.simulated.is_(True)).limit(1)):
                raise HTTPException(409, "Keep real booking details separate from simulated demo trips. Select another trip or leave it unassigned.")
    row.ciphertext = encrypt(owner, data, entry.key)
    row.revision, row.updated_at = new_id(), utc_now()
    log(session, owner, "saved")
    session.commit()
    # Other unlocked tabs become locked instead of silently overwriting a new revision.
    entry.revision = row.revision
    return {"revision": row.revision, "data": data.model_dump(mode="json")}


def change_password(session: Session, owner: str, sessions: VaultSessions, cookie: str | None, current: str, new: str) -> tuple[dict, str]:
    sessions.try_unlock(owner)
    lock_writes(session)
    row, _, data = read(session, owner, sessions, cookie)
    decrypt(row, derive_key(current, row.salt))
    salt = secrets.token_bytes(16)
    key = derive_key(new, salt)
    row.salt, row.ciphertext = salt, encrypt(owner, data, key)
    row.revision, row.updated_at = new_id(), utc_now()
    log(session, owner, "password_changed")
    session.commit()
    sessions.forget_owner(owner)
    return {"revision": row.revision, "data": data.model_dump(mode="json")}, sessions.issue(owner, key, row.revision)
