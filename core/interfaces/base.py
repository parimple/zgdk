"""Base interfaces for the application architecture."""

from abc import ABC, abstractmethod
from typing import Any, Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class IRepository(Protocol):
    """Base repository interface for data access operations."""
    
    session: AsyncSession
    
    async def get_by_id(self, entity_id: Any) -> Any:
        """Get entity by ID."""
        ...

    async def create(self, entity: Any) -> Any:
        """Create new entity."""
        ...

    async def update(self, entity: Any) -> Any:
        """Update existing entity."""
        ...

    async def delete(self, entity_id: Any) -> bool:
        """Delete entity by ID."""
        ...


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
