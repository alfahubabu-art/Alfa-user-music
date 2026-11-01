"""Published command catalogue.

Descriptions are short because Telegram truncates them in the client UI.
"""

from __future__ import annotations

from typing import Final

from aiogram import Bot
from aiogram.types import BotCommand, BotCommandScopeDefault

BOT_COMMANDS: Final[tuple[BotCommand, ...]] = (
    BotCommand(command="start", description="Open the main menu"),
    BotCommand(command="help", description="Commands and instructions"),
    BotCommand(command="connect", description="Authorize your Telegram account"),
    BotCommand(command="disconnect", description="Remove your authorized account"),
    BotCommand(command="account", description="Show account status"),
    BotCommand(command="play", description="Play a track or URL"),
    BotCommand(command="pause", description="Pause playback"),
    BotCommand(command="resume", description="Resume playback"),
    BotCommand(command="skip", description="Skip the current track"),
    BotCommand(command="stop", description="Stop playback"),
    BotCommand(command="queue", description="Show your queue"),
    BotCommand(command="clear", description="Clear your queue"),
    BotCommand(command="volume", description="Set playback volume"),
    BotCommand(command="settings", description="Your personal settings"),
    BotCommand(command="privacy", description="Security and privacy"),
    BotCommand(command="ping", description="Service health"),
)


async def register(bot: Bot) -> None:
    """Publish the command list for the default scope."""
    await bot.set_my_commands(list(BOT_COMMANDS), scope=BotCommandScopeDefault())
