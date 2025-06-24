"""
Service layer for the ZGDK application.

This layer acts as an interface between the presentation layer (commands, events)
and the business logic layer (managers). It coordinates operations and handles
error management.
"""

from typing import Any, Dict, Generic, List, Optional, Tuple, TypeVar

T = TypeVar("T")


class ServiceResult(Generic[T]):
    """Standard result object for service operations."""

    def __init__(
        self,
        success: bool = True,
        data: Optional[T] = None,
        message: str = "",
        error_code: Optional[str] = None,
    ):
        """Initialize a service result.

        Args:
            success: Whether the operation was successful
            data: The operation result data (if any)
            message: A human-readable message
            error_code: An optional error code for categorizing errors
        """
        self.success = success
        self.data = data
        self.message = message
        self.error_code = error_code

    @classmethod
    def success(cls, data: Optional[T] = None, message: str = "Operation successful"):
        """Create a successful result."""
        return cls(success=True, data=data, message=message)

    @classmethod
    def failure(
        cls, message: str, error_code: Optional[str] = None, data: Optional[T] = None
    ):
        """Create a failed result."""
        return cls(success=False, message=message, error_code=error_code, data=data)


class BaseService:
    """Base class for all services."""

    def __init__(self, bot):
        """Initialize the service with a bot instance."""
        self.bot = bot
