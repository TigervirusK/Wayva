"""Shared no-cache routes with origin checks and redacted validation errors."""
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

NO_CACHE = {"Cache-Control": "no-store, private", "Pragma": "no-cache"}


class PrivateRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()
        async def private_handler(request: Request):
            try:
                origin = request.headers.get("origin")
                if request.method != "GET" and origin and origin not in request.app.state.settings.cors_origins:
                    raise HTTPException(403, "This private request must come from the Wayva website.")
                response = await handler(request)
            except RequestValidationError as exc:
                response = JSONResponse(status_code=422, content={"detail": [
                    {"loc": list(error["loc"]), "msg": error["msg"], "type": error["type"]} for error in exc.errors()
                ]})
            except HTTPException as exc:
                response = JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
            response.headers.update(NO_CACHE)
            return response
        return private_handler
