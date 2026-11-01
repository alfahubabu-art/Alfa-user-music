"""User documents: registration, lookup, counters."""

from __future__ import annotations

from typing import Any, Final

from pymongo.errors import PyMongoError

from core.exceptions import DatabaseError
from database.connection import Database
from utils.helpers import utcnow
from utils.logger import get_logger

logger = get_logger(__name__)

COLLECTION: Final[str] = "users"

DEFAULT_USER_SETTINGS: Final[dict[str, Any]] = {
    "volume": 100,
    "autoplay": True,
    "stream_quality": "high",
}


async def upsert_user(
    db: Database,
    *,
    telegram_id: int,
    username: str | None,
    first_name: str | None,
) -> tuple[dict[str, Any], bool]:
    """Register or refresh a user; returns the document and a ``created`` flag."""
    now = utcnow()
    try:
        result = await db.collection(COLLECTION).update_one(
            {"telegram_id": telegram_id},
            {
                "$set": {"username": username, "first_name": first_name, "last_seen": now},
                "$setOnInsert": {
                    "first_seen": now,
                    "account_status": "disconnected",
                    "settings": dict(DEFAULT_USER_SETTINGS),
                },
            },
            upsert=True,
        )
    except PyMongoError as exc:
        logger.error("upsert_user failed", exc_info=exc, extra={"telegram_id": telegram_id})
        raise DatabaseError("Could not register user") from exc

    document = await get_user(db, telegram_id)
    if document is None:
        raise DatabaseError("Registered user could not be read back")
    return document, result.upserted_id is not None


async def get_user(db: Database, telegram_id: int) -> dict[str, Any] | None:
    """Fetch a user document by Telegram ID."""
    try:
        return await db.collection(COLLECTION).find_one({"telegram_id": telegram_id})
    except PyMongoError as exc:
        logger.error("get_user failed", exc_info=exc, extra={"telegram_id": telegram_id})
        raise DatabaseError("Could not read user") from exc


async def set_account_status(db: Database, telegram_id: int, status: str) -> None:
    """Store the account connection status (``connected``/``disconnected``/...)."""
    try:
        await db.collection(COLLECTION).update_one(
            {"telegram_id": telegram_id},
            {"$set": {"account_status": status, "updated_at": utcnow()}},
            upsert=False,
        )
    except PyMongoError as exc:
        logger.error("set_account_status failed", exc_info=exc, extra={"telegram_id": telegram_id})
        raise DatabaseError("Could not update account status") from exc


async def count_users(db: Database) -> int:
    """Total registered users."""
    try:
        return int(await db.collection(COLLECTION).count_documents({}))
    except PyMongoError as exc:
        logger.error("count_users failed", exc_info=exc)
        raise DatabaseError("Could not count users") from exc


async def count_by_account_status(db: Database, status: str) -> int:
    """Number of users in a given account status."""
    try:
        return int(await db.collection(COLLECTION).count_documents({"account_status": status}))
    except PyMongoError as exc:
        logger.error("count_by_account_status failed", exc_info=exc)
        raise DatabaseError("Could not count users by status") from exc
