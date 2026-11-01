"""FastAPI application factory and lifespan wiring.

Startup order: database → bot. A bot failure does not kill the process; the app
stays up in degraded mode so `/health/ready` reports the problem to Railway and
to admins. Shutdown unwinds in reverse and drains background tasks.
"""

from __future__ import annotations

import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from api import routes
from bot import BotService
from config import APP_NAME, APP_VERSION, Settings, get_settings
from core.exceptions import DatabaseError
from database.connection import Database
from utils.helpers import drain_tasks, spawn
from utils.logger import get_logger, reset_request_id, set_request_id

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Attach a request id, log the access line, never log headers or query secrets."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID") or uuid4().hex[:12]
        token = set_request_id(request_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration = round((time.perf_counter() - started) * 1000, 2)
            logger.exception(
                "request failed",
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "duration_ms": duration,
                    "request_id": request_id,
                },
            )
            reset_request_id(token)
            raise
        duration = round((time.perf_counter() - started) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request",
            extra={
                "path": request.url.path,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": duration,
                "request_id": request_id,
            },
        )
        reset_request_id(token)
        return response


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Bring the service up and take it down cleanly."""
    settings: Settings = app.state.settings
    app.state.started_at = time.time()
    app.state.degraded = False

    database = Database(settings)
    try:
        await database.connect()
    except DatabaseError:
        logger.critical("startup aborted: database unreachable")
        raise
    app.state.db = database

    service = BotService(settings, database)
    app.state.bot_service = service
    try:
        await service.start()
    except Exception as exc:  # noqa: BLE001 - keep serving health in degraded mode
        app.state.degraded = True
        logger.critical("bot startup failed, serving degraded", exc_info=exc)

    logger.info("%s v%s started (degraded=%s)", APP_NAME, APP_VERSION, app.state.degraded)

    try:
        yield
    finally:
        logger.info("shutdown started")
        with suppress(Exception):
            await service.stop()
        with suppress(Exception):
            await database.close()
        await drain_tasks(5.0)
        logger.info("shutdown complete")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI app."""
    resolved = settings or get_settings()

    app = FastAPI(
        title=APP_NAME,
        version=APP_VERSION,
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )
    app.state.settings = resolved
    app.add_middleware(RequestContextMiddleware)
    app.include_router(routes.router)
    return app
