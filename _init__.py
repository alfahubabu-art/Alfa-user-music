"""Bot service: builds the aiogram dispatcher and owns its polling lifecycle.

Shared objects (database, settings) are injected through dispatcher workflow data
so handlers receive them as keyword arguments instead of importing globals.
"""

from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError

from bot import callbacks, commands, handlers
from config import Settings
from core.exceptions import ConfigurationError
from database.connection import Database
from utils.helpers import spawn
from utils.logger import get_logger

logger = get_logger(__name__)

POLLING_STOP_TIMEOUT: float = 10.0


class BotService:
    """Owns the bot, the dispatcher and the polling task."""

    def __init__(self, settings: Settings, db: Database) -> None:
        self._settings = settings
        self._db = db
        self.bot = Bot(
            token=settings.bot_token.get_secret_value(),
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dispatcher = Dispatcher()
        self.dispatcher["db"] = db
        self.dispatcher["settings"] = settings
        self.dispatcher.include_router(handlers.router)
        self.dispatcher.include_router(callbacks.router)
        self._task: asyncio.Task[Any] | None = None
        self._ready = False

    # ── State ───────────────────────────────────────────────────────────
    @property
    def is_running(self) -> bool:
        """True while the polling task is alive and the token was accepted."""
        return self._ready and self._task is not None and not self._task.done()

    @property
    def username(self) -> str | None:
        """Bot username once ``get_me`` succeeded."""
        return self.bot.username if self.bot else None

    # ── Lifecycle ───────────────────────────────────────────────────────
    async def start(self) -> None:
        """Validate the token, publish the command list, then poll."""
        if self._task is not None:
            return

        try:
            me = await self.bot.get_me()
        except TelegramUnauthorizedError as exc:
            logger.error("BOT_TOKEN rejected by Telegram", exc_info=exc)
            raise ConfigurationError("BOT_TOKEN is invalid") from exc
        except TelegramAPIError as exc:
            logger.error("get_me failed", exc_info=exc)
            raise ConfigurationError("Telegram Bot API unreachable") from exc

        logger.info("bot identity verified (@%s, id=%s)", me.username, me.id)

        try:
            await commands.register(self.bot)
        except TelegramAPIError as exc:
            # Non-fatal: commands can still be typed manually.
            logger.warning("command registration failed", exc_info=exc)

        self._ready = True
        self._task = spawn(self._poll(), name="bot-polling")
        logger.info("polling started")

    async def _poll(self) -> None:
        """Run long polling until cancelled."""
        try:
            await self.dispatcher.start_polling(
                self.bot,
                handle_signals=False,
                close_bot_session=False,
                allowed_updates=self.dispatcher.resolve_used_update_types(),
            )
        finally:
            self._ready = False
            logger.info("polling stopped")

    async def stop(self) -> None:
        """Stop polling, drain the task and close the HTTP session."""
        self._ready = False

        if self._task is not None and not self._task.done():
            try:
                await self.dispatcher.stop_polling()
            except Exception as exc:  # noqa: BLE001 - shutdown must not raise
                logger.warning("stop_polling failed", exc_info=exc)
            try:
                await asyncio.wait_for(self._task, timeout=POLLING_STOP_TIMEOUT)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
            except Exception as exc:  # noqa: BLE001
                logger.warning("polling task ended with error", exc_info=exc)

        self._task = None

        try:
            await self.bot.session.close()
        except Exception as exc:  # noqa: BLE001
            logger.warning("bot session close failed", exc_info=exc)
