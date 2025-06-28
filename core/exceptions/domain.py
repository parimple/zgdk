"""Domain-specific exceptions."""

from datetime import datetime, timedelta
from typing import Optional

from .base import BotError


class DomainError(BotError):
    """Base exception for domain logic errors."""

    def __init__(
        self,
        message: str,
        domain: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize domain error."""
        details = {}
        if domain:
            details["domain"] = domain

        super().__init__(
            message=message,
            code="DOMAIN_ERROR",
            details=details,
            user_message=user_message or "Błąd logiki biznesowej.",
        )


class BusinessRuleViolation(DomainError):
    """Raised when a business rule is violated."""

    def __init__(
        self,
        rule: str,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize business rule violation."""
        super().__init__(
            message=message or f"Business rule violated: {rule}",
            domain="business_rules",
            user_message=user_message or "Naruszenie reguły biznesowej.",
        )
        self.rule = rule


class InsufficientBalanceError(DomainError):
    """Raised when user has insufficient balance."""

    def __init__(
        self,
        required: int,
        available: int,
        currency: str = "G",
        user_message: Optional[str] = None,
    ):
        """Initialize insufficient balance error."""
        super().__init__(
            message=f"Insufficient balance: required {required}, available {available}",
            domain="economy",
            user_message=user_message
            or f"Niewystarczający balans. Potrzebujesz {required} {currency}, masz {available} {currency}.",
        )
        self.required = required
        self.available = available
        self.currency = currency


class CooldownError(DomainError):
    """Raised when an action is on cooldown."""

    def __init__(
        self,
        action: str,
        retry_after: timedelta,
        next_available: Optional[datetime] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize cooldown error."""
        seconds = int(retry_after.total_seconds())
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60

        if hours > 0:
            time_str = f"{hours}h {minutes}m"
        else:
            time_str = f"{minutes}m"

        details = {
            "action": action,
            "retry_after_seconds": seconds,
        }
        if next_available:
            details["next_available"] = next_available.isoformat()

        super().__init__(
            message=f"Action '{action}' on cooldown for {seconds}s",
            domain="cooldowns",
            user_message=user_message or f"Musisz poczekać {time_str} przed ponownym użyciem.",
        )
        self.action = action
        self.retry_after = retry_after
        self.next_available = next_available


class LimitExceededError(DomainError):
    """Raised when a limit is exceeded."""

    def __init__(
        self,
        resource: str,
        limit: int,
        current: Optional[int] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize limit exceeded error."""
        details = {
            "resource": resource,
            "limit": limit,
        }
        if current is not None:
            details["current"] = current

        super().__init__(
            message=f"Limit exceeded for {resource}: {limit}",
            domain="limits",
            user_message=user_message or f"Przekroczono limit {resource}: {limit}.",
        )
        self.resource = resource
        self.limit = limit
        self.current = current
