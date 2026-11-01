"""Process entry point.

One process, one event loop: uvicorn serves the health plane and the lifespan
starts the bot. Railway runs exactly this file.
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI

from api.server import create_app
from config import APP_NAME, APP_VERSION, get_settings
from utils.logger import configure_logging, get_logger

logger = get_logger(__name__)


def _build_app() -> FastAPI:
    """Configure logging, prepare the media directory, build the app."""
    settings = get_settings()
    configure_logging(settings.log_level)
    settings.ensure_media_dir()
    logger.info("booting %s v%s (env=%s)", APP_NAME, APP_VERSION, settings.environment)
    return create_app(settings)


app = _build_app()


def main() -> None:
    """Run uvicorn with Railway-compatible settings."""
    settings = get_settings()
    uvicorn.run(
        app,
        host=settings.host,
        port=settings.port,
        log_config=None,          # our JSON logger owns the output
        access_log=False,         # the middleware logs access instead
        server_header=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
        timeout_graceful_shutdown=20,
    )


if __name__ == "__main__":
    main()
