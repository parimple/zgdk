"""Base service implementation with common functionality."""

import logging
from typing import Any

from core.interfaces.base import IService, IUnitOfWork


class BaseService(IService):
    """Base service class providing common functionality for all services."""

    def __init__(self, unit_of_work: IUnitOfWork) -> None:
        self.unit_of_work = unit_of_work
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_operation(self, *args: Any, **kwargs: Any) -> bool:
        """Default validation - override in specific services."""
        return True

    async def _execute_with_transaction(
        self, operation: callable, *args: Any, **kwargs: Any
    ) -> Any:
        """Execute operation within a transaction."""
        async with self.unit_of_work:
            try:
                result = await operation(*args, **kwargs)
                await self.unit_of_work.commit()
                return result
            except Exception as e:
                await self.unit_of_work.rollback()
                self.logger.error(f"Transaction failed in {operation.__name__}: {e}")
                raise

    def _log_operation(self, operation_name: str, **context: Any) -> None:
        """Log service operation with context."""
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        self.logger.info(f"{operation_name}: {context_str}")

    def _log_error(self, operation_name: str, error: Exception, **context: Any) -> None:
        """Log service error with context."""
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        self.logger.error(f"{operation_name} failed: {error} | Context: {context_str}")
