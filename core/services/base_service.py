"""Base service implementation with common functionality and error handling."""

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional, TypeVar

from core.error_handler import handle_service_errors
from core.exceptions import PermissionError as PermissionException
from core.exceptions import ResourceNotFoundException, ServiceException, TransactionException, ValidationException
from core.interfaces.base import IService, IUnitOfWork

T = TypeVar("T")


class ServiceResult:
    """
    Generic result wrapper for service operations.

    Provides a consistent way to return results with metadata.
    """

    def __init__(
        self,
        data: Optional[Any] = None,
        success: bool = True,
        message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.data = data
        self.success = success
        self.message = message
        self.metadata = metadata or {}

    @classmethod
    def success(cls, data: Any, message: Optional[str] = None, **metadata):
        """Create a successful result."""
        return cls(data=data, success=True, message=message, metadata=metadata)

    @classmethod
    def failure(cls, message: str, **metadata):
        """Create a failure result."""
        return cls(data=None, success=False, message=message, metadata=metadata)

    def __bool__(self):
        """Allow result to be used in boolean context."""
        return self.success

    def __repr__(self):
        return f"ServiceResult(success={self.success}, data={self.data}, message={self.message})"


class BaseService(IService):
    """Base service class providing common functionality for all services."""

    def __init__(self, unit_of_work: IUnitOfWork) -> None:
        self.unit_of_work = unit_of_work
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_operation(self, *args: Any, **kwargs: Any) -> bool:
        """Default validation - override in specific services."""
        return True

    @handle_service_errors
    async def _execute_with_transaction(self, operation: callable, *args: Any, **kwargs: Any) -> Any:
        """Execute operation within a transaction with error handling."""
        async with self.unit_of_work:
            try:
                # Start metrics
                metrics = self.create_metrics(operation.__name__)

                # Execute operation
                result = await operation(*args, **kwargs)
                await self.unit_of_work.commit()

                # Finalize metrics
                self.finalize_metrics(metrics, success=True)

                return result
            except Exception as e:
                await self.unit_of_work.rollback()
                self.logger.error(f"Transaction failed in {operation.__name__}: {e}")

                # Wrap in TransactionException if not already a BotError
                from core.exceptions import BotError

                if not isinstance(e, BotError):
                    raise TransactionException(f"Transaction failed in {operation.__name__}", original_error=e) from e
                raise

    @asynccontextmanager
    async def transaction(self):
        """
        Context manager for handling database transactions.

        Usage:
            async with self.transaction():
                # Perform operations
                # Auto-commit on success, rollback on error
        """
        async with self.unit_of_work:
            try:
                yield self.unit_of_work
                await self.unit_of_work.commit()
                self.logger.debug("Transaction committed successfully")
            except Exception as e:
                await self.unit_of_work.rollback()
                self.logger.error(f"Transaction rolled back due to error: {e}")
                raise TransactionException("Transaction failed and was rolled back", original_error=e) from e

    def _log_operation(self, operation_name: str, **context: Any) -> None:
        """Log service operation with context."""
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        self.logger.info(f"{operation_name}: {context_str}")

    def _log_error(self, operation_name: str, error: Exception, **context: Any) -> None:
        """Log service error with context."""
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        self.logger.error(f"{operation_name} failed: {error} | Context: {context_str}")

    @handle_service_errors
    async def validate_input(self, data: Dict[str, Any], validators: Dict[str, Callable]) -> Dict[str, Any]:
        """
        Validate input data using provided validators.

        Args:
            data: Input data to validate
            validators: Dictionary of field_name -> validator_function

        Returns:
            Validated data

        Raises:
            ValidationException: If validation fails
        """
        validated = {}

        for field, validator in validators.items():
            if field not in data:
                continue

            try:
                validated[field] = (
                    await validator(data[field]) if asyncio.iscoroutinefunction(validator) else validator(data[field])
                )
            except Exception as e:
                raise ValidationException(f"Validation failed for field '{field}': {str(e)}")

        return validated

    async def ensure_resource_exists(self, resource_type: str, resource_id: Any, fetch_func: Callable) -> Any:
        """
        Ensure a resource exists or raise an exception.

        Args:
            resource_type: Type of resource (for error message)
            resource_id: ID of the resource
            fetch_func: Async function to fetch the resource

        Returns:
            The fetched resource

        Raises:
            ResourceNotFoundException: If resource doesn't exist
        """
        resource = await fetch_func(resource_id)
        if not resource:
            raise ResourceNotFoundException(resource_type, resource_id)

        return resource

    def create_metrics(self, operation: str) -> Dict[str, Any]:
        """
        Create metrics for an operation.

        Args:
            operation: Name of the operation

        Returns:
            Metrics dictionary
        """
        return {
            "operation": operation,
            "service": self.__class__.__name__,
            "start_time": time.time(),
            "end_time": None,
            "duration": None,
            "success": False,
            "error": None,
        }

    def finalize_metrics(self, metrics: Dict[str, Any], success: bool = True, error: Optional[Exception] = None):
        """
        Finalize metrics for an operation.

        Args:
            metrics: Metrics dictionary to update
            success: Whether operation succeeded
            error: Optional error that occurred
        """
        metrics["end_time"] = time.time()
        metrics["duration"] = metrics["end_time"] - metrics["start_time"]
        metrics["success"] = success
        metrics["error"] = str(error) if error else None

        # Log metrics
        self.logger.info(f"Operation metrics: {metrics}")
