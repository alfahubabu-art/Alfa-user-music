"""Callback data factories and menu navigation.

Screens whose engine lands in a later phase say so explicitly instead of
pretending the feature works.
"""

from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.keyboards import MenuAction, back_menu, main_menu
from config import APP_NAME, APP_VERSION, Settings
from database.connection import Database
from database.users import get_user
from utils.helpers import humanize_seconds, uptime_seconds

router = Router(name="menu-callbacks")


class MenuCB(CallbackData := __import__("aiogram").types.CallbackData, prefix="menu"):
    """Callback payload for menu buttons."""

    action: str


TEXT_CONNECT = (
    f"<b>ALFA USER MUSIC</b>\n"
    f"<blockquote>Connect your own Telegram account</blockquote>\n"
    "Account authorization lands in <b>Phase 2</b>: phone or QR login, 2FA handling, "
    "encrypted session storage.\n\n"
    "Use /connect once it is deployed."
)

TEXT_PLAY = (
    f"<b>ALFA USER MUSIC</b>\n"
    f"<blockquote>Playback</blockquote>\n"
    "The player engine arrives in <b>Phase 3</b> (download, queue, voice-chat join)."
)

TEXT_QUEUE = (
    f"<b>ALFA USER MUSIC</b>\n"
    f"<blockquote>Your queue</blockquote>\n"
    "Queues are per user and per chat. Engine arrives in <b>Phase 3</b>."
)

TEXT_SETTINGS = (
    f"<b>ALFA USER MUSIC</b>\n"
    f"<blockquote>Personal settings</blockquote>\n"
    "Volume, autoplay and quality are stored per user. Editor arrives in <b>Phase 3</b>."
)

TEXT_HELP = (
    f"<b>ALFA USER MUSIC</b>\n"
    f"<blockquote>Help & support</blockquote>\n"
    "/start — main menu\n"
    "/help — this overview\n"
    "/privacy — security and privacy\n"
    "/ping — service health\n\n"
    "Phase 2 adds /connect, /disconnect, /account.\n"
    "Phase 3 adds /play, /pause, /resume, /skip, /stop, /queue, /clear, /volume, /settings."
)

TEXT_DB_DOWN = "Database unavailable — try again in a moment."


async def _render_status(db: Database, settings: Settings, telegram_id: int) -> str:
    """Compose the account status screen for one user."""
    user = await get_user(db, telegram_id)
    if user is None:
        return "No user record yet. Send /start."

    status = user.get("account_status", "disconnected")
    badge = "◉ connected" if status == "connected" else "○ not connected"
    return (
        f"<b>ALFA USER MUSIC</b>\n"
        f"<blockquote>Account status</blockquote>\n"
        f"State: {badge}\n"
        f"Registered: {user.get('first_seen')}\n"
        f"Volume: {user.get('settings', {}).get('volume', 100)}%\n"
        f"Service uptime: {humanize_seconds(uptime_seconds())}\n\n"
        "Connect or remove an account in <b>Phase 2</b>."
    )


@router.callback_query(MenuCB.filter())
async def on_menu(query: CallbackQuery, callback_data: MenuCB, db: Database, settings: Settings) -> None:
    """Dispatch a menu button."""
    await query.answer()

    if query.from_user is None or query.message is None:
        return

    action = callback_data.action

    if action == MenuAction.BACK:
        await query.message.edit_text(
            f"<b>{APP_NAME}</b>\n<blockquote>Main menu</blockquote>\nChoose an action.",
            reply_markup=main_menu(),
        )
        return

    if action == MenuAction.CONNECT:
        await query.message.edit_text(TEXT_CONNECT, reply_markup=back_menu())
        return

    if action == MenuAction.STATUS:
        try:
            text = await _render_status(db, settings, query.from_user.id)
        except Exception:  # noqa: BLE001 - DatabaseError surfaces to the user
            text = TEXT_DB_DOWN
        await query.message.edit_text(text, reply_markup=back_menu())
        return

    screens = {
        MenuAction.PLAY: TEXT_PLAY,
        MenuAction.QUEUE: TEXT_QUEUE,
        MenuAction.SETTINGS: TEXT_SETTINGS,
        MenuAction.HELP: TEXT_HELP,
    }
    await query.message.edit_text(
        screens.get(action, f"<b>{APP_NAME}</b>\nUnknown action."),
        reply_markup=back_menu(),
    )


@router.message(Command("version"))
async def cmd_version(message: Message) -> None:
    """Report the build version."""
    builder = InlineKeyboardBuilder()
    await message.answer(f"<b>{APP_NAME}</b> v{APP_VERSION}", reply_markup=builder.as_markup())


@router.message(F.text == "menu")
async def cmd_menu_text(message: Message) -> None:
    """Reopen the menu with the literal word ``menu``."""
    await message.answer("Main menu:", reply_markup=main_menu())
