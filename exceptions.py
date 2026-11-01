"""Domain exception hierarchy.

Every error carries a stable machine ``code`` and a Telegram-safe
``user_message`` so handlers never leak internals to users while logs keep the
full cause chain.
"""

from __future__ import annotations


class AlfaError(Exception):
    """Base class for all application errors."""

    code: str = "alfa_error"
    user_message: str = "Something went wrong. Please try again."

    def __init__(self, detail: str | None = None, *, user_message: str | None = None) -> None:
        self.detail = detail
        if user_message is not None:
            self.user_message = user_message
        super().__init__(detail or self.user_message)

    def __str__(self) -> str:
        return self.detail or self.user_message


class ConfigurationError(AlfaError):
    """Invalid or missing configuration."""

    code = "configuration_error"
    user_message = "The service is misconfigured."


class DatabaseError(AlfaError):
    """MongoDB unreachable or a query failed."""

    code = "database_error"
    user_message = "The database is not reachable right now. Try again shortly."


class UnauthorizedUser(AlfaError):
    """Action attempted by a user who does not own the resource."""

    code = "unauthorized"
    user_message = "You are not allowed to do that."


class AdminOnly(AlfaError):
    """Admin command used by a non-admin."""

    code = "admin_only"
    user_message = "This command is restricted to administrators."


class AuthorizationError(AlfaError):
    """Generic MTProto authorization failure."""

    code = "authorization_error"
    user_message = "Authorization failed. Start over with /connect."


class PhoneInvalid(AuthorizationError):
    """Phone number rejected by Telegram."""

    code = "phone_invalid"
    user_message = "Telegram rejected that phone number. Use international format, e.g. +4915112345678."


class OTPInvalid(AuthorizationError):
    """Wrong or expired login code."""

    code = "otp_invalid"
    user_message = "That code is wrong or expired."


class TwoFactorRequired(AuthorizationError):
    """Account is protected by a cloud password."""

    code = "two_factor_required"
    user_message = "Two-step verification is enabled. Send your cloud password."


class SessionRevoked(AlfaError):
    """Stored session was revoked from another device."""

    code = "session_revoked"
    user_message = "The stored session was revoked. Reconnect with /connect."


class DuplicateConnection(AlfaError):
    """Account already authorized."""

    code = "duplicate_connection"
    user_message = "An account is already connected. Disconnect it first with /disconnect."


class MaintenanceMode(AlfaError):
    """New connections or playback are disabled by an admin."""

    code = "maintenance"
    user_message = "The service is in maintenance mode. Try again later."


class ChatPermissionError(AlfaError):
    """Bot or user lacks required chat rights."""

    code = "chat_permission"
    user_message = "Missing permissions in that chat."


class VoiceChatUnavailable(AlfaError):
    """No joinable voice chat in the target group."""

    code = "voice_chat_unavailable"
    user_message = "There is no active voice chat in that group."


class UnsupportedSource(AlfaError):
    """Audio source cannot be resolved."""

    code = "unsupported_source"
    user_message = "That source is not supported."


class DownloadError(AlfaError):
    """Media download failed."""

    code = "download_error"
    user_message = "Download failed."


class FFmpegError(AlfaError):
    """FFmpeg processing failed."""

    code = "ffmpeg_error"
    user_message = "Audio processing failed."


class PlayerNotActive(AlfaError):
    """Control issued while nothing plays."""

    code = "player_not_active"
    user_message = "Nothing is playing right now."


class QueueEmpty(AlfaError):
    """Queue operation on an empty queue."""

    code = "queue_empty"
    user_message = "The queue is empty."


class NotConnected(AlfaError):
    """User has no authorized account."""

    code = "not_connected"
    user_message = "No account connected. Use /connect first."
