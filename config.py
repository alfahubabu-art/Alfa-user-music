"""Environment-driven configuration for ALFA USER MUSIC.

Every value is read from Railway service variables or a local ``.env`` file.
Validation runs once, at import time, so a misconfigured deploy dies immediately
instead of starting half-broken and failing on the first user request.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR: Path = Path(__file__).resolve().parent

APP_NAME: str = "ALFA USER MUSIC"
APP_VERSION: str = "0.1.0"

_BOT_TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")
_API_HASH_RE = re.compile(r"^[0-9a-fA-F]{32}$")
_DB_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_ALLOWED_LOG_LEVELS = frozenset({"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"})


class Settings(BaseSettings):
    """Validated application settings."""

    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Telegram Bot API (control plane) ────────────────────────────────
    bot_token: SecretStr = Field(description="BotFather token for the control bot")

    # ── Telegram MTProto (playback plane) ───────────────────────────────
    api_id: int = Field(ge=1, description="Application api_id from my.telegram.org")
    api_hash: SecretStr = Field(description="Application api_hash from my.telegram.org")

    # ── MongoDB ─────────────────────────────────────────────────────────
    mongodb_uri: SecretStr = Field(description="mongodb:// or mongodb+srv:// URI")
    database_name: str = "alfa_user_music"

    # ── Security ────────────────────────────────────────────────────────
    session_encryption_key: SecretStr = Field(
        description="Master key (>=32 chars) for encrypting session strings at rest"
    )

    # ── Access control ──────────────────────────────────────────────────
    admin_ids: str = Field(default="", description="Comma separated admin Telegram IDs")

    # ── Runtime ─────────────────────────────────────────────────────────
    environment: str = "production"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = Field(default=8080, ge=1, le=65535)
    media_dir: Path = BASE_DIR / "media"
    max_concurrent_downloads: int = Field(default=2, ge=1, le=10)
    pending_auth_ttl: int = Field(default=300, ge=60, le=1800)

    # ── Validators ──────────────────────────────────────────────────────
    @field_validator("bot_token", mode="before")
    @classmethod
    def _check_bot_token(cls, value: object) -> str:
        token = str(value).strip()
        if not _BOT_TOKEN_RE.match(token):
            raise ValueError("BOT_TOKEN must look like '123456789:AA...' (BotFather token)")
        return token

    @field_validator("api_hash", mode="before")
    @classmethod
    def _check_api_hash(cls, value: object) -> str:
        digest = str(value).strip().lower()
        if not _API_HASH_RE.match(digest):
            raise ValueError("API_HASH must be the 32 character hex value from my.telegram.org")
        return digest

    @field_validator("session_encryption_key", mode="before")
    @classmethod
    def _check_encryption_key(cls, value: object) -> str:
        key = str(value).strip()
        if len(key) < 32:
            raise ValueError("SESSION_ENCRYPTION_KEY must be at least 32 characters")
        return key

    @field_validator("database_name")
    @classmethod
    def _check_database_name(cls, value: str) -> str:
        if not _DB_NAME_RE.match(value):
            raise ValueError("DATABASE_NAME may only contain letters, digits, '_' and '-'")
        return value

    @field_validator("log_level")
    @classmethod
    def _check_log_level(cls, value: str) -> str:
        level = value.strip().upper()
        if level not in _ALLOWED_LOG_LEVELS:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(_ALLOWED_LOG_LEVELS)}")
        return level

    @field_validator("admin_ids")
    @classmethod
    def _check_admin_ids(cls, value: str) -> str:
        for chunk in value.replace(";", ",").split(","):
            chunk = chunk.strip()
            if chunk and not chunk.lstrip("-").isdigit():
                raise ValueError("ADMIN_IDS must be a comma separated list of numeric Telegram IDs")
        return value

    # ── Derived helpers ─────────────────────────────────────────────────
    @property
    def admin_id_set(self) -> frozenset[int]:
        """Admin IDs as a frozen set for O(1) membership tests."""
        parsed: set[int] = set()
        for chunk in self.admin_ids.replace(";", ",").split(","):
            chunk = chunk.strip()
            if chunk:
                parsed.add(int(chunk))
        return frozenset(parsed)

    def is_admin(self, telegram_id: int) -> bool:
        """Return True when ``telegram_id`` may use admin commands."""
        return telegram_id in self.admin_id_set

    @property
    def is_production(self) -> bool:
        """True for production-like environments."""
        return self.environment.strip().lower() in {"production", "prod"}

    def ensure_media_dir(self) -> Path:
        """Create the media scratch directory and return it."""
        self.media_dir.mkdir(parents=True, exist_ok=True)
        return self.media_dir


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()  # type: ignore[call-arg]
