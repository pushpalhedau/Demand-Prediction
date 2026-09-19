"""
Application factory. Security posture, in one place:

  * No CORS: the browser only ever talks to the frontend's own origin, which proxies /api here.
  * Every state-changing request must carry `X-Requested-With: predictax` (a header a cross-site form cannot set),
    on top of SameSite=Strict cookies.
  * Errors never carry internals: expected ones show their safe message, the rest are logged with a reference.
  * Responses are never cached, and carry the standard hardening headers.
"""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.api.routers import auth, overview, workspace
from backend.core.config import get_settings
from backend.core.errors import AppError, AuthError
from backend.core.log import configure_logging, get_logger

_log = get_logger("predictax.api")
_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "predictax"


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    settings.assert_production_ready()

    app = FastAPI(title="PredictaX API", version="1.0.0", docs_url=None if settings.is_production else "/api/docs",
                  redoc_url=None, openapi_url=None if settings.is_production else "/api/openapi.json")

    @app.middleware("http")
    async def harden(request: Request, call_next):
        if request.method not in _SAFE_METHODS and request.headers.get(CSRF_HEADER) != CSRF_VALUE:
            return JSONResponse({"detail": "Missing request header."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(AuthError)
    async def _auth(_: Request, exc: AuthError):
        return JSONResponse({"detail": str(exc)}, status_code=401)

    @app.exception_handler(AppError)
    async def _expected(_: Request, exc: AppError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception):
        reference = uuid.uuid4().hex[:8]
        _log.error("Unhandled error [ref=%s]", reference, exc_info=exc)
        return JSONResponse({"detail": "Something went wrong on our side.", "reference": reference}, status_code=500)

    @app.get("/api/health", include_in_schema=False)
    def health():
        return {"status": "ok"}

    for router in (auth.router, workspace.router, overview.router):
        app.include_router(router, prefix="/api")
    return app


app = create_app()
