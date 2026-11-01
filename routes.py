"""Health and identity routes.

No secrets are exposed: the database name and latency are the only internals shown.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from config import APP_NAME, APP_VERSION
from utils.helpers import uptime_seconds

router = APIRouter()


@router.get("/", include_in_schema=False)
async def index() -> dict[str, str]:
    """Brand response."""
    return {"service": APP_NAME, "version": APP_VERSION}


@router.get("/health")
async def health(request: Request) -> JSONResponse:
    """Liveness: cheap, always 200 while the process serves HTTP."""
    state = request.app.state
    db = getattr(state, "db", None)
    service = getattr(state, "bot_service", None)

    payload: dict[str, Any] = {
        "status": "degraded" if getattr(state, "degraded", False) else "ok",
        "version": APP_VERSION,
        "uptime_s": uptime_seconds(),
        "database_connected": bool(db is not None and db.is_connected),
        "bot_running": bool(service is not None and service.is_running),
    }
    return JSONResponse(payload, status_code=200)


@router.get("/health/ready")
async def readiness(request: Request) -> JSONResponse:
    """Readiness: 503 until the database and the bot are both usable."""
    state = request.app.state
    db = getattr(state, "db", None)
    service = getattr(state, "bot_service", None)

    database: dict[str, Any] = {"connected": False}
    if db is not None:
        database = await db.health_snapshot()

    bot_running = bool(service is not None and service.is_running)
    ready = bool(database.get("connected")) and bot_running

    payload: dict[str, Any] = {
        "ready": ready,
        "version": APP_VERSION,
        "bot_running": bot_running,
        "database": database,
    }
    return JSONResponse(payload, status_code=200 if ready else 503)
