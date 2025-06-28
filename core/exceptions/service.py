"""Service-specific exceptions."""

from typing import Optional

from .base import BotError


class InsufficientFundsException(BotError):
    """Raised when a user has insufficient funds for an operation."""

    def __init__(
        self,
        required: int,
        available: int,
        currency: str = "coins",
        user_message: Optional[str] = None,
    ):
        """Initialize insufficient funds error."""
        details = {
            "required": required,
            "available": available,
            "currency": currency,
            "deficit": required - available,
        }

        if not user_message:
            user_message = f"Niewystarczające środki. Potrzebujesz {required} {currency}, masz {available}."

        super().__init__(
            message=f"Insufficient {currency}: required {required}, available {available}",
            code="INSUFFICIENT_FUNDS",
            details=details,
            user_message=user_message,
        )


class CooldownException(BotError):
    """Raised when an action is on cooldown."""

    def __init__(
        self,
        cooldown_seconds: int,
        action: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize cooldown error."""
        details = {
            "cooldown_seconds": cooldown_seconds,
        }
        if action:
            details["action"] = action

        if not user_message:
            user_message = f"⏱️ Musisz poczekać {cooldown_seconds} sekund przed ponownym użyciem."

        super().__init__(
            message=f"Action on cooldown for {cooldown_seconds} seconds",
            code="COOLDOWN",
            details=details,
            user_message=user_message,
        )


class RateLimitException(BotError):
    """Raised when a rate limit is exceeded."""

    def __init__(
        self,
        retry_after: Optional[int] = None,
        limit: Optional[int] = None,
        window: Optional[int] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize rate limit error."""
        details = {}
        if retry_after is not None:
            details["retry_after"] = retry_after
        if limit is not None:
            details["limit"] = limit
        if window is not None:
            details["window"] = window

        if not user_message:
            if retry_after:
                user_message = f"⚠️ Limit zapytań przekroczony. Spróbuj ponownie za {retry_after} sekund."
            else:
                user_message = "⚠️ Limit zapytań przekroczony. Spróbuj ponownie później."

        super().__init__(
            message="Rate limit exceeded",
            code="RATE_LIMIT",
            details=details,
            user_message=user_message,
        )


# Aliases for backward compatibility
BotException = BotError
PermissionException = BotError
ResourceNotFoundException = BotError
ValidationException = BotError
DatabaseException = BotError
ErrorCodes = type("ErrorCodes", (), {"INTERNAL": "INTERNAL"})
