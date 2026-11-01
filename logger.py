"""Structured JSON logging with secret redaction.

Nothing sensitive may reach the logs, so a redaction filter rewrites bot tokens,
MTProto session strings and phone numbers before a record is formatted.
"""

from __future__ import annotations

import contextvars
import json
import logging
import re
import sys
from datetime import UTC, datetime
from typing import Any

REQUEST_ID: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)

_REDACTIONS: tuple[tuple[re.Pattern[str], str], ...] = (
    # Session strings are long base64url blobs starting with the auth-key marker.
    (re.compile(r"\b1[A-Za-z0-9_\-]{250,}\b"), "<session>"),
    # Bot API tokens: <bot_id>:<secret>
    (re.compile(r"\b\d{6,12}:[A-Za-z0-9_-]{30,}\b"), "<bot_token>"),
    # E.164-ish phone numbers
    (re.compile(r"\+\d{7,15}\b"), "<phone>"),
)

_NOISY_LOGGERS = ("aiogram.event", "pymongo", "telethon", "telethon.network", "httpx")


def set_request_id(value: str) -> contextvars.Token[str | None]:
    """Bind a request id to the current context."""
    return REQUEST_ID.set(value)


def reset_request_id(token: contextvars.Token[str | None]) -> None:
    """Restore the previous request id."""
    REQUEST_ID.reset(token)


def redact(text: str) -> str:
    """Return ``text`` with known secret patterns masked."""
    for pattern, replacement in _REDACTIONS:
        text = pattern.sub(replacement, text)
    return text


class RedactionFilter(logging.Filter):
    """Rewrite the record message in place before formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact(record.getMessage())
            record.args = ()
        except Exception:  # noqa: BLE001 - logging must never raise
            pass
        return True


class JsonFormatter(logging.Formatter):
    """Render records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": redact(record.getMessage()),
        }

        request_id = getattr(record, "request_id", None) or REQUEST_ID.get()
        if request_id:
            payload["request_id"] = request_id

        for key in ("path", "method", "status", "duration_ms", "telegram_id", "chat_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value

        if record.exc_info:
            payload["exc"] = redact(self.formatException(record.exc_info))

        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    """Install the JSON handler on the root logger exactly once."""
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(RedactionFilter())
    root.addHandler(handler)

    for name in _NOISY_LOGGERS:
        logging.getLogger(name).setLevel(max(logging.WARNING, logging.getLogger().level))

    logging.captureWarnings(True)


def get_logger(name: str) -> logging.Logger:
    """Return a module-scoped logger."""
    return logging.getLogger(name)
