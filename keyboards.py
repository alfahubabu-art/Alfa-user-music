"""Inline keyboard builders.

Telegram keyboards cannot carry colour, so the red accent lives in the message
text and the buttons stay monochrome with symbol prefixes.
"""

from __future__ import annotations

from enum import StrEnum

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.callbacks import MenuCB


class MenuAction(StrEnum):
    """Actions addressable from the main menu."""

    CONNECT = "connect"
    STATUS = "status"
    PLAY = "play"
    QUEUE = "queue"
    SETTINGS = "settings"
    HELP = "help"
    BACK = "back"


def main_menu() -> InlineKeyboardMarkup:
    """Two-column main menu in the fixed brand order."""
    builder = InlineKeyboardBuilder()
    builder.button(text="◉ CONNECT ACCOUNT", callback_data=MenuCB(action=MenuAction.CONNECT))
    builder.button(text="▤ ACCOUNT STATUS", callback_data=MenuCB(action=MenuAction.STATUS))
    builder.button(text="▶ PLAY MUSIC", callback_data=MenuCB(action=MenuAction.PLAY))
    builder.button(text="≡ MY QUEUE", callback_data=MenuCB(action=MenuAction.QUEUE))
    builder.button(text="⚙ MUSIC SETTINGS", callback_data=MenuCB(action=MenuAction.SETTINGS))
    builder.button(text="? HELP & SUPPORT", callback_data=MenuCB(action=MenuAction.HELP))
    builder.adjust(2, 2, 2)
    return builder.as_markup()


def back_menu() -> InlineKeyboardMarkup:
    """Single back button."""
    builder = InlineKeyboardBuilder()
    builder.button(text="‹ BACK", callback_data=MenuCB(action=MenuAction.BACK))
    return builder.as_markup()
