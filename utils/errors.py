"""
Custom exceptions for the ZGDK application.

This module defines application-specific exceptions that provide
consistent error handling and messaging throughout the application.
"""

from typing import Dict, Any, Optional


class ZGDKError(Exception):
    """Base exception for all application errors."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        """Initialize the exception with a message and optional details."""
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class PermissionError(ZGDKError):
    """Raised when a user does not have permission to perform an action."""
    pass


class ResourceNotFoundError(ZGDKError):
    """Raised when a requested resource is not found."""
    pass


class InvalidInputError(ZGDKError):
    """Raised when user input is invalid."""
    pass


class BusinessRuleViolationError(ZGDKError):
    """Raised when a business rule is violated."""
    pass


class DatabaseError(ZGDKError):
    """Raised when a database operation fails."""
    pass


class ExternalServiceError(ZGDKError):
    """Raised when an external service operation fails."""
    pass