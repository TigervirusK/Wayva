"""Readiness check used by the frontend and local setup checks."""

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db

router = APIRouter(tags=["Health"])
logger = logging.getLogger(__name__)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "triprescue-api"
    database: Literal["connected"] = "connected"
    version: str = "0.1.0"


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"description": "The SQLite database is unavailable."}},
)
def check_health(session: Annotated[Session, Depends(get_db)]) -> HealthResponse:
    """Confirm the API can query SQLite. This does not create application tables."""
    try:
        session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        # Exception text may contain database URLs, SQL, or sensitive values.
        logger.warning("Database health check failed (%s).", type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable. Check the backend configuration.",
        ) from None
    return HealthResponse()
