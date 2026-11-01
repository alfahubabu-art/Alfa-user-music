"""MongoDB access layer built on the pymongo async driver.

Motor is deprecated (EOL 2026-05-14), so this uses ``pymongo.AsyncMongoClient``.
The unique index plan below is what actually enforces the isolation guarantees:
one account per owner, one player state and one queue per owner+chat pair.
"""

from __future__ import annotations

import time
from typing import Any, Final

from pymongo import ASCENDING, AsyncMongoClient
from pymongo.errors import PyMongoError

from config import Settings
from core.exceptions import DatabaseError
from utils.logger import get_logger

logger = get_logger(__name__)

SERVER_SELECTION_TIMEOUT_MS: Final[int] = 10_000
CONNECT_TIMEOUT_MS: Final[int] = 10_000
MAX_POOL_SIZE: Final[int] = 50

IndexSpec = dict[str, Any]

INDEX_PLAN: Final[dict[str, list[IndexSpec]]] = {
    "users": [
        {"keys": [("telegram_id", ASCENDING)], "name": "uq_users_telegram_id", "unique": True},
        {"keys": [("first_seen", ASCENDING)], "name": "ix_users_first_seen"},
        {"keys": [("account_status", ASCENDING)], "name": "ix_users_account_status"},
    ],
    "accounts": [
        {"keys": [("owner_telegram_id", ASCENDING)], "name": "uq_accounts_owner", "unique": True},
        {"keys": [("authorization_status", ASCENDING)], "name": "ix_accounts_status"},
        {"keys": [("last_active", ASCENDING)], "name": "ix_accounts_last_active"},
    ],
    "player_states": [
        {
            "keys": [("owner_telegram_id", ASCENDING), ("chat_id", ASCENDING)],
            "name": "uq_player_owner_chat",
            "unique": True,
        },
        {"keys": [("chat_id", ASCENDING)], "name": "ix_player_chat"},
    ],
    "queues": [
        {
            "keys": [("owner_telegram_id", ASCENDING), ("chat_id", ASCENDING)],
            "name": "uq_queue_owner_chat",
            "unique": True,
        }
    ],
    "settings": [
        {"keys": [("owner_telegram_id", ASCENDING)], "name": "uq_settings_owner", "unique": True}
    ],
    "meta": [],
}


class Database:
    """Owns the client, the database handle and the index bootstrap."""

    def __init__(self, settings: Settings) -> None:
        self._uri = settings.mongodb_uri.get_secret_value()
        self._database_name = settings.database_name
        self._client: AsyncMongoClient[dict[str, Any]] | None = None
        self._database: Any = None
        self._connected_at: float | None = None

    # ── Lifecycle ───────────────────────────────────────────────────────
    @property
    def is_connected(self) -> bool:
        """True once ``connect`` succeeded."""
        return self._database is not None

    async def connect(self) -> None:
        """Open the pool, verify reachability, then build indexes."""
        if self._database is not None:
            return

        client: AsyncMongoClient[dict[str, Any]] = AsyncMongoClient(
            self._uri,
            appname="alfa-user-music",
            tz_aware=True,
            connectTimeoutMS=CONNECT_TIMEOUT_MS,
            serverSelectionTimeoutMS=SERVER_SELECTION_TIMEOUT_MS,
            maxPoolSize=MAX_POOL_SIZE,
            retryWrites=True,
        )

        try:
            await client.admin.command("ping")
        except PyMongoError as exc:
            await client.close()
            logger.error("MongoDB ping failed during connect", exc_info=exc)
            raise DatabaseError("MongoDB is not reachable") from exc

        self._client = client
        self._database = client[self._database_name]
        self._connected_at = time.time()

        await self.ensure_indexes()
        logger.info("MongoDB connected (database=%s)", self._database_name)

    async def close(self) -> None:
        """Close the pool; safe to call twice."""
        client, self._client = self._client, None
        self._database = None
        self._connected_at = None
        if client is not None:
            await client.close()
            logger.info("MongoDB connection closed")

    # ── Access ──────────────────────────────────────────────────────────
    def collection(self, name: str) -> Any:
        """Return a collection handle, raising when disconnected."""
        if self._database is None:
            raise DatabaseError("MongoDB is not connected")
        return self._database[name]

    async def ensure_indexes(self) -> None:
        """Create the index plan; idempotent."""
        for collection_name, specs in INDEX_PLAN.items():
            if not specs:
                continue
            collection = self.collection(collection_name)
            for spec in specs:
                try:
                    await collection.create_index(
                        spec["keys"],
                        name=spec["name"],
                        unique=spec.get("unique", False),
                        background=True,
                    )
                except PyMongoError as exc:
                    logger.error(
                        "index creation failed (collection=%s, index=%s)",
                        collection_name,
                        spec["name"],
                        exc_info=exc,
                    )
                    raise DatabaseError(f"Index creation failed for {collection_name}") from exc
        logger.info("index plan ensured (%d collections)", len(INDEX_PLAN))

    # ── Health ──────────────────────────────────────────────────────────
    async def ping(self) -> float:
        """Round-trip ping in milliseconds."""
        if self._client is None:
            raise DatabaseError("MongoDB is not connected")
        started = time.perf_counter()
        try:
            await self._client.admin.command("ping")
        except PyMongoError as exc:
            raise DatabaseError("MongoDB ping failed") from exc
        return round((time.perf_counter() - started) * 1000, 2)

    async def health_snapshot(self) -> dict[str, Any]:
        """Sanitized health data for the readiness endpoint."""
        snapshot: dict[str, Any] = {
            "connected": self.is_connected,
            "database": self._database_name,
            "latency_ms": None,
            "uptime_s": round(time.time() - self._connected_at, 3) if self._connected_at else None,
        }
        if self.is_connected:
            try:
                snapshot["latency_ms"] = await self.ping()
            except DatabaseError:
                snapshot["connected"] = False
        return snapshot
