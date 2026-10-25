"""Device-local profile access, not a production sign-in system."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas.trips import Profile, ProfileCreated, ProfileInput
from app.services.trips import create_profile, require_profile, serialize_profile

router = APIRouter(tags=["Local profiles"])
SessionDependency = Annotated[Session, Depends(get_db)]
TokenHeader = Annotated[str | None, Header(alias="X-Profile-Token")]


def current_profile(request: Request, session: SessionDependency, token: TokenHeader = None) -> User:
    return require_profile(session, token, request)


ProfileDependency = Annotated[User, Depends(current_profile)]


@router.post("", response_model=ProfileCreated, status_code=201)
def add_profile(payload: ProfileInput, session: SessionDependency) -> ProfileCreated:
    return create_profile(session, payload.display_name)


@router.get("/me", response_model=Profile)
def get_profile(profile: ProfileDependency) -> Profile:
    return serialize_profile(profile)


@router.patch("/me", response_model=Profile)
def update_profile(payload: ProfileInput, session: SessionDependency, profile: ProfileDependency) -> Profile:
    profile.display_name = payload.display_name
    session.commit()
    return serialize_profile(profile)
