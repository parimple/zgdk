"""Core exceptions for the bot."""

from .base import (
    BotError,
    ConfigurationError,
    ExternalServiceError,
    NotFoundError,
    PermissionError,
    ResourceNotFoundException,
    ServiceException,
    TransactionException,
    ValidationError,
    ValidationException,
)
from .database import ConnectionError, DatabaseError, EntityNotFoundError, IntegrityError
from .discord import CommandError, DiscordError, InteractionError, RateLimitError
from .domain import BusinessRuleViolation, CooldownError, DomainError, InsufficientBalanceError, LimitExceededError
from .service import CooldownException, InsufficientFundsException, RateLimitException

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
