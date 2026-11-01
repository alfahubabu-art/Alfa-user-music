"""Command handlers.

Private-chat only: every screen here is per user, so group usage would be noise.
"""

from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.enums import ChatType
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.keyboards import main_menu
from config import APP_NAME, APP_VERSION, Settings
from core.exceptions import DatabaseError
from database.connection import Database
from database.users import upsert_user
from utils.helpers import humanize_seconds, uptime_seconds
from utils.logger import get_logger

logger = get_logger(__name__)

router = Router(name="core-commands")
router.message.filter(F.chat.type == ChatType.PRIVATE)
router.callback_query.filter(F.message.chat.type == ChatType.PRIVATE)

TEXT_WELCOME = (
    f"<b>{APP_NAME}</b>\n"
    f"<blockquote>Multi-user Telegram music platform</blockquote>\n"
    "Each account, queue and player stays isolated per user.\n\n"
    "Start by connecting your own Telegram account, then play into a group voice chat."
)

TEXT_WELCOME_BACK = (
    f"<b>{APP_NAME}</b>\n"
    f"<blockquote>Welcome back</blockquote>\n"
    "Pick up where you left off."
)

TEXT_HELP = (
    f"<b>{APP_NAME}</b> — commands\n\n"
    "<b>Account</b>\n"
    "/connect · /disconnect · /account\n\n"
    "<b>Playback</b>\n"
    "/play · /pause · /resume · /skip · /stop · /queue · /clear · /volume\n\n"
    "<b>General</b>\n"
    "/start · /help · /settings · /privacy · /ping\n\n"
    "Phase 1 (current build) serves /start, /help, /privacy, /ping, /version and the menu. "
    "Account and playback commands are wired in the next phases."
)

TEXT_PRIVACY = (
    f"<b>{APP_NAME}</b> — security & privacy\n\n"
    "• Authorization uses Telegram's own MTProto login flow; codes and cloud passwords "
    "are only accepted in this private chat.\n"
    "• Session strings are stored encrypted with a server-side master key.\n"
    "• Raw session strings are never printed to chats or logs.\n"
    "• Each user has a separate client, queue and player; nobody can control another "
    "user's playback.\n"
    "• /disconnect revokes the stored session and logs the account out.\n\n"
    "Changing the server master key invalidates every stored session — users reconnect once."
)

TEXT_DB_DOWN = "Database unavailable — try again in a moment."


@router.message(CommandStart())
async def cmd_start(message: Message, db: Database, settings: Settings) -> None:
    """Register the user and show the main menu."""
    user = message.from_user
    if user is None:
        return

    try:
        _, created = await upsert_user(
            db,
            telegram_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )
    except DatabaseError:
        await message.answer(TEXT_DB_DOWN)
        return

    header = TEXT_WELCOME if created else TEXT_WELCOME_BACK
    if settings.is_admin(user.id):
        header += "\n\n<blockquote>Admin access active.</blockquote>"

    await message.answer(header, reply_markup=main_menu())

    logger.info(
        "user started the bot (new=%s)",
        created,
        extra={"telegram_id": user.id},
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    """Show the command overview."""
    await message.answer(TEXT_HELP, reply_markup=main_menu())


@router.message(Command("privacy"))
async def cmd_privacy(message: Message) -> None:
    """Explain security and privacy handling."""
    await message.answer(TEXT_PRIVACY)


@router.message(Command("ping"))
async def cmd_ping(message: Message, db: Database) -> None:
    """Report service health and database round-trip."""
    try:
        latency = await db.ping()
        database_line = f"database: <b>online</b> ({latency} ms)"
    except DatabaseError:
        database_line = "database: <b>offline</b>"

    await message.answer(
        f"<b>{APP_NAME}</b> v{APP_VERSION}\n"
        f"{database_line}\n"
        f"uptime: {humanize_seconds(uptime_seconds())}"
    )


@router.message(Command("version"))
async def cmd_version(message: Message) -> None:
    """Report the running build version."""
    await message.answer(f"<b>{APP_NAME}</b> v{APP_VERSION}")


@router.message(F.text == "menu")
async def cmd_menu_text(message: Message) -> None:
    """Reopen the menu with the literal word ``menu``."""
    await message.answer("Main menu:", reply_markup=main_menu())


@router.message()
async def cmd_fallback(message: Message) -> None:
    """Catch-all for unknown text in private chat."""
    preview = escape((message.text or "")[:40])
    await message.answer(
        f"Unknown input: <code>{preview}</code>\nUse /help or the menu below.",
        reply_markup=main_menu(),
    )
