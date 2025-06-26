"""Base interfaces for the application architecture."""

from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, TypeVar

from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class IRepository(ABC):
    """Base repository interface for data access operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @abstractmethod
    async def get_by_id(self, entity_id: Any) -> T | None:
        """Get entity by ID."""
        pass

    @abstractmethod
    async def create(self, entity: T) -> T:
        """Create new entity."""
        pass

    @abstractmethod
    async def update(self, entity: T) -> T:
        """Update existing entity."""
        pass

    @abstractmethod
    async def delete(self, entity_id: Any) -> bool:
        """Delete entity by ID."""
        pass


class IService(ABC):
    """Base service interface for business logic operations."""

    @abstractmethod
    async def validate_operation(self, *args: Any, **kwargs: Any) -> bool:
        """Validate if operation can be performed."""
        pass


class IUnitOfWork(ABC):
    """Unit of work interface for transaction management."""

    @abstractmethod
    async def __aenter__(self) -> "IUnitOfWork":
        """Enter async context manager."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback transaction."""
        pass
