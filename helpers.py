"""Small, dependency-free helpers shared across modules."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Iterable, Sequence
from datetime import UTC, datetime
from typing import Any, TypeVar

from utils.logger import get_logger

logger = get_logger(__name__)

T = TypeVar("T")

PROCESS_STARTED_AT: float = time.monotonic()

_background_tasks: set[asyncio.Task[Any]] = set()


def utcnow() -> datetime:
    """Timezone-aware current UTC timestamp."""
    return datetime.now(tz=UTC)


def uptime_seconds() -> float:
    """Seconds since this process started."""
    return round(time.monotonic() - PROCESS_STARTED_AT, 3)


def humanize_seconds(total: int | float) -> str:
    """Format a duration as ``1h 02m 03s`` style text."""
    total = max(0, int(total))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def truncate(text: str, limit: int = 60, suffix: str = "…") -> str:
    """Shorten ``text`` to ``limit`` characters."""
    clean = " ".join(text.split())
    if len(clean) <= limit:
        return clean
    return clean[: max(0, limit - len(suffix))].rstrip() + suffix


def chunk_list(items: Sequence[T], size: int) -> Iterable[Sequence[T]]:
    """Yield ``items`` in slices of at most ``size``."""
    for start in range(0, len(items), size):
        yield items[start : start + size]


def spawn(coro: Awaitable[Any], *, name: str | None = None) -> asyncio.Task[Any]:
    """Run ``coro`` as a tracked background task.

    The task is kept in a module-level set so it cannot be garbage collected and
    can be awaited during shutdown.
    """
    task = asyncio.create_task(coro, name=name)
    _background_tasks.add(task)
    task.add_done_callback(_on_task_done)
    return task


def _on_task_done(task: asyncio.Task[Any]) -> None:
    _background_tasks.discard(task)
    if task.cancelled():
        return
    error = task.exception()
    if error is not None:
        logger.error("background task %s failed", task.get_name(), exc_info=error)


async def drain_tasks(timeout: float = 5.0) -> None:
    """Cancel and await every tracked background task."""
    pending = [task for task in _background_tasks if not task.done()]
    for task in pending:
        task.cancel()
    if pending:
        await asyncio.wait(pending, timeout=timeout)


async def run_blocking(func: Any, *args: Any, **kwargs: Any) -> Any:
    """Execute a blocking callable in a worker thread."""
    return await asyncio.to_thread(func, *args, **kwargs)
