"""Discord-related exceptions."""

from typing import Any, Dict, Optional

from .base import BotError


class DiscordError(BotError):
    """Base exception for Discord API errors."""

    def __init__(
        self,
        message: str,
        discord_code: Optional[int] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize Discord error."""
        details = {}
        if discord_code:
            details["discord_code"] = discord_code

        super().__init__(
            message=message,
            code="DISCORD_ERROR",
            details=details,
            user_message=user_message or "Błąd Discord API.",
        )


class CommandError(DiscordError):
    """Raised when a command execution fails."""

    def __init__(
        self,
        command_name: str,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize command error."""
        super().__init__(
            message=message or f"Command '{command_name}' failed",
            user_message=user_message or f"Błąd podczas wykonywania komendy {command_name}.",
        )
        self.command_name = command_name


class InteractionError(DiscordError):
    """Raised when an interaction fails."""

    def __init__(
        self,
        interaction_type: str,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize interaction error."""
        super().__init__(
            message=message or f"Interaction '{interaction_type}' failed",
            user_message=user_message or "Błąd interakcji.",
        )
        self.interaction_type = interaction_type


class RateLimitError(DiscordError):
    """Raised when Discord rate limit is hit."""

    def __init__(
        self,
        retry_after: float,
        endpoint: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize rate limit error."""
        details: Dict[str, Any] = {"retry_after": retry_after}
        if endpoint:
            details["endpoint"] = endpoint

        super().__init__(
            message=f"Rate limited for {retry_after}s",
            user_message=user_message or f"Przekroczono limit zapytań. Spróbuj ponownie za {int(retry_after)} sekund.",
        )
        self.retry_after = retry_after
