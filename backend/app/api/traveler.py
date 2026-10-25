"""Private local traveler settings; no booking or payment execution endpoints."""
from time import monotonic

from fastapi import APIRouter, Request, Response

from app.api.profiles import ProfileDependency, SessionDependency
from app.schemas.traveler import AssistanceRequest, VaultPassword, VaultPasswordChange, VaultSave
from app.services import real_travel, traveler_vault as vault

from app.api.private_route import NO_CACHE, PrivateRoute


router = APIRouter(tags=["Private traveler settings"], route_class=PrivateRoute)
capability_router = APIRouter(tags=["Real Travel · assisted only"])


def sessions(request: Request):
    return request.app.state.vault_sessions


def cookie(request: Request):
    return request.cookies.get(vault.COOKIE)


def issue_cookie(request: Request, response: Response, value: str):
    response.set_cookie(vault.COOKIE, value, max_age=vault.TTL, httponly=True, samesite="strict",
                        secure=request.app.state.settings.auth_cookie_secure or request.url.scheme == "https", path="/api")


def with_expiry(request: Request, owner: str, result: dict, token: str | None = None):
    entry = sessions(request).get(token or cookie(request), owner, result["revision"])
    return {**result, "expires_in_seconds": max(0, int(entry.expires - monotonic()))}


@router.get("/status")
def status(request: Request, session: SessionDependency, profile: ProfileDependency):
    return vault.status(session, profile.id, sessions(request), cookie(request))


@router.post("/create")
def create(payload: VaultPassword, request: Request, response: Response, session: SessionDependency, profile: ProfileDependency):
    result, token = vault.create(session, profile.id, payload.password.get_secret_value(), sessions(request))
    issue_cookie(request, response, token)
    return with_expiry(request, profile.id, result, token)


@router.post("/unlock")
def unlock(payload: VaultPassword, request: Request, response: Response, session: SessionDependency, profile: ProfileDependency):
    result, token = vault.unlock(session, profile.id, payload.password.get_secret_value(), sessions(request))
    issue_cookie(request, response, token)
    return with_expiry(request, profile.id, result, token)


@router.post("/lock")
def lock(request: Request, response: Response, session: SessionDependency, profile: ProfileDependency):
    sessions(request).forget_owner(profile.id)
    response.delete_cookie(vault.COOKIE, path="/api", httponly=True, samesite="strict")
    vault.log(session, profile.id, "locked")
    session.commit()
    return {"locked": True}


@router.get("")
def get_data(request: Request, session: SessionDependency, profile: ProfileDependency):
    row, _, data = vault.read(session, profile.id, sessions(request), cookie(request))
    return with_expiry(request, profile.id, {"revision": row.revision, "data": data.model_dump(mode="json")})


@router.put("")
def save(payload: VaultSave, request: Request, session: SessionDependency, profile: ProfileDependency):
    result = vault.save(session, profile.id, sessions(request), cookie(request), str(payload.revision), payload.data)
    return with_expiry(request, profile.id, result)


@router.post("/change-password")
def change_password(payload: VaultPasswordChange, request: Request, response: Response, session: SessionDependency, profile: ProfileDependency):
    result, token = vault.change_password(session, profile.id, sessions(request), cookie(request),
                                           payload.current_password.get_secret_value(), payload.password.get_secret_value())
    issue_cookie(request, response, token)
    return with_expiry(request, profile.id, result, token)


@router.post("/rescue-assistance")
def assistance(payload: AssistanceRequest, request: Request, session: SessionDependency, profile: ProfileDependency):
    _, _, data = vault.read(session, profile.id, sessions(request), cookie(request))
    return real_travel.assistance(data, str(payload.booking_id))


@capability_router.get("/capabilities")
def capabilities(response: Response):
    response.headers.update(NO_CACHE)
    return real_travel.capabilities()
