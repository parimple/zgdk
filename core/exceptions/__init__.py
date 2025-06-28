"""Core exceptions for the bot."""

from .base import (
    BotError,
    ValidationError,
    NotFoundError,
    PermissionError,
    ConfigurationError,
    ExternalServiceError,
    ServiceException,
    TransactionException,
    ValidationException,
    ResourceNotFoundException,
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

from .service import (
    InsufficientFundsException,
    CooldownException,
    RateLimitException,
)

__all__ = [
    # Base
    "BotError",
    "ValidationError",
    "NotFoundError",
    "PermissionError",
    "ConfigurationError",
    "ExternalServiceError",
    "ServiceException",
    "TransactionException",
    "ValidationException",
    "ResourceNotFoundException",
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
    # Service (compatibility)
    "InsufficientFundsException",
    "CooldownException",
    "RateLimitException",
    "BotException",
    "PermissionException",
    "ResourceNotFoundException",
    "ValidationException",
    "DatabaseException",
    "ErrorCodes",
]