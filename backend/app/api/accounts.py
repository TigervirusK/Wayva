"""Username/password accounts with cookie sessions and explicit local-profile linking."""
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import JSONResponse

from app.api.private_route import PrivateRoute
from app.api.profiles import SessionDependency
from app.schemas.accounts import PasswordChange, Register, SignIn
from app.services import accounts
from app.services.traveler_vault import COOKIE as VAULT_COOKIE

router = APIRouter(tags=["Accounts"], route_class=PrivateRoute)


def check_json(request):
    if request.headers.get("content-type", "").split(";", 1)[0].strip().lower() != "application/json":
        raise HTTPException(415, "Account changes require an application/json request.")


def cookie_response(request: Request, response: Response, raw: str):
    response.set_cookie(accounts.COOKIE, raw, max_age=accounts.ABSOLUTE_SECONDS, httponly=True,
                        secure=request.app.state.settings.auth_cookie_secure or request.url.scheme == "https",
                        samesite="strict", path="/api")
    request.app.state.vault_sessions.forget(request.cookies.get(VAULT_COOKIE))
    response.delete_cookie(VAULT_COOKIE, path="/api", httponly=True, samesite="strict")


@router.post("/register", status_code=201)
def register(payload: Register, request: Request, response: Response, session: SessionDependency):
    check_json(request)
    result, raw = accounts.register(session, request, payload, request.headers.get("X-Profile-Token"))
    cookie_response(request, response, raw)
    return result


@router.post("/login")
def login(payload: SignIn, request: Request, response: Response, session: SessionDependency):
    check_json(request)
    result, raw = accounts.login(session, request, payload)
    cookie_response(request, response, raw)
    return result


@router.get("/session")
def current_session(request: Request, session: SessionDependency):
    # This passive check does not keep an idle account signed in indefinitely.
    row = accounts.session_for_cookie(session, request.cookies.get(accounts.COOKIE))
    if row is None:
        response = JSONResponse({"detail": "Sign in to open your account."}, status_code=401)
        response.delete_cookie(accounts.COOKIE, path="/api", httponly=True, samesite="strict")
        return response
    return accounts.response_data(session, row)


@router.post("/logout")
def logout(request: Request, response: Response, session: SessionDependency):
    check_json(request)
    accounts.logout(session, request)
    response.delete_cookie(accounts.COOKIE, path="/api", httponly=True, samesite="strict")
    response.delete_cookie(VAULT_COOKIE, path="/api", httponly=True, samesite="strict")
    return {"signed_out": True}


@router.post("/change-password")
def change_password(payload: PasswordChange, request: Request, response: Response, session: SessionDependency):
    check_json(request)
    result, raw = accounts.change_password(session, request, payload)
    cookie_response(request, response, raw)
    return result
