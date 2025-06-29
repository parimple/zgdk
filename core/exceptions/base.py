"""Base exceptions for the bot."""

from typing import Any, Dict, Optional


class BotError(Exception):
    """Base exception for all bot errors."""

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize bot error.

        Args:
            message: Error message for logging
            code: Error code for identification
            details: Additional error details
            user_message: User-friendly message in Polish
        """
        super().__init__(message)
        self.code = code or self.__class__.__name__
        self.details = details or {}
        self.user_message = user_message or "Wystąpił błąd podczas przetwarzania żądania."


class ValidationError(BotError):
    """Raised when input validation fails."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        value: Any = None,
        user_message: Optional[str] = None,
    ):
        """Initialize validation error."""
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)

        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details=details,
            user_message=user_message or "Nieprawidłowe dane wejściowe.",
        )


class NotFoundError(BotError):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource: str,
        identifier: Any = None,
        user_message: Optional[str] = None,
    ):
        """Initialize not found error."""
        details = {"resource": resource}
        if identifier is not None:
            details["identifier"] = str(identifier)

        super().__init__(
            message=f"{resource} not found",
            code="NOT_FOUND",
            details=details,
            user_message=user_message or f"Nie znaleziono {resource}.",
        )


class PermissionError(BotError):
    """Raised when user lacks required permissions."""

    def __init__(
        self,
        action: str,
        required_permission: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize permission error."""
        details = {"action": action}
        if required_permission:
            details["required_permission"] = required_permission

        super().__init__(
            message=f"Permission denied for action: {action}",
            code="PERMISSION_DENIED",
            details=details,
            user_message=user_message or "Brak uprawnień do wykonania tej akcji.",
        )


class ConfigurationError(BotError):
    """Raised when there's an issue with bot configuration."""

    def __init__(
        self,
        config_key: str,
        message: Optional[str] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize configuration error."""
        super().__init__(
            message=message or f"Invalid configuration for: {config_key}",
            code="CONFIG_ERROR",
            details={"config_key": config_key},
            user_message=user_message or "Błąd konfiguracji bota.",
        )


class ExternalServiceError(BotError):
    """Raised when an external service fails."""

    def __init__(
        self,
        service: str,
        message: Optional[str] = None,
        status_code: Optional[int] = None,
        user_message: Optional[str] = None,
    ):
        """Initialize external service error."""
        details = {"service": service}
        if status_code:
            details["status_code"] = str(status_code)

        super().__init__(
            message=message or f"External service error: {service}",
            code="EXTERNAL_SERVICE_ERROR",
            details=details,
            user_message=user_message or "Błąd zewnętrznego serwisu.",
        )


class ServiceException(BotError):
    """Raised when a service operation fails."""


class TransactionException(BotError):
    """Raised when a database transaction fails."""


class ValidationException(ValidationError):
    """Alias for ValidationError for backward compatibility."""


class ResourceNotFoundException(NotFoundError):
    """Alias for NotFoundError for backward compatibility."""
