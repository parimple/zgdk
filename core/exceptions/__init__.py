"""Core exceptions for the bot."""

from .base import (
    BotError,
    ValidationError,
    NotFoundError,
    PermissionError,
    ConfigurationError,
    ExternalServiceError,
)

from .database import (
    DatabaseError,
    EntityNotFoundError,
    IntegrityError,
    ConnectionError,
)

from .discord import (
    DiscordError,
    CommandError,
    InteractionError,
    RateLimitError,
)

from .domain import (
    DomainError,
    BusinessRuleViolation,
    InsufficientBalanceError,
    CooldownError,
    LimitExceededError,
)

__all__ = [
    # Base
    "BotError",
    "ValidationError",
    "NotFoundError",
    "PermissionError",
    "ConfigurationError",
    "ExternalServiceError",
    # Database
    "DatabaseError",
    "EntityNotFoundError",
    "IntegrityError",
    "ConnectionError",
    # Discord
    "DiscordError",
    "CommandError",
    "InteractionError",
    "RateLimitError",
    # Domain
    "DomainError",
    "BusinessRuleViolation",
    "InsufficientBalanceError",
    "CooldownError",
    "LimitExceededError",
]