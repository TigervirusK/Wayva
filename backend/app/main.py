"""FastAPI application factory and resource lifecycle."""

import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.buddy import router as buddy_router
from app.api.health import router as health_router
from app.api.profiles import router as profiles_router
from app.api.trips import router as trips_router
from app.config import Settings
from app.database import Database
from app.api.planning import router as planning_router
from app.api.rescue import router as rescue_router
from app.api.traveler import router as traveler_router, capability_router
from app.services.traveler_vault import VaultSessions
from app.services.accounts import AuthLimiter
from app.api.accounts import router as accounts_router
from app.api.body_limit import ApiBodyLimit


def create_app(settings: Settings | None = None) -> FastAPI:
    configuration = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        database = Database(configuration.database_url)
        application.state.database = database
        application.state.vault_sessions = VaultSessions()
        application.state.auth_limiter = AuthLimiter()
        async def expire_private_sessions():
            while True:
                await asyncio.sleep(30)
                application.state.vault_sessions.prune_expired()
        private_cleanup = asyncio.create_task(expire_private_sessions())
        try:
            yield
        finally:
            private_cleanup.cancel()
            with suppress(asyncio.CancelledError):
                await private_cleanup
            application.state.vault_sessions.clear()
            database.dispose()

    application = FastAPI(
        title="Wayva API",
        description=(
            "Wayva with local AI or optional cloud conversation, owned saved trips, "
            "reviewed itinerary proposals, and Domino Rescue simulated booking recovery. "
            "Recovery requires approval and persists mock changes and an audit trail. "
            "No real bookings are executed."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )
    application.state.settings = configuration
    @application.middleware("http")
    async def private_api_responses(request, call_next):
        response = await call_next(request)
        if request.url.path.startswith("/api"):
            response.headers["Cache-Control"] = "no-store, private"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    application.add_middleware(
        CORSMiddleware,
        allow_origins=configuration.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Accept", "Content-Type", "X-Profile-Token"],
    )
    application.add_middleware(ApiBodyLimit)
    application.include_router(health_router, prefix="/api")
    application.include_router(buddy_router, prefix="/api/buddy")
    application.include_router(planning_router, prefix="/api/trips")
    application.include_router(profiles_router, prefix="/api/profiles")
    application.include_router(trips_router, prefix="/api/trips")
    application.include_router(rescue_router, prefix="/api")
    application.include_router(traveler_router, prefix="/api/private-traveler")
    application.include_router(capability_router, prefix="/api/rescue/real")
    application.include_router(accounts_router, prefix="/api/auth")
    return application


app = create_app()
