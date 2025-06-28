"""Unit of Work interface for transaction management."""

from abc import ABC, abstractmethod
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.interfaces.member_interfaces import (
    IActivityRepository,
    IInviteRepository,
    IMemberRepository,
    IModerationRepository,
)
from core.interfaces.role_interfaces import IRoleRepository


class IUnitOfWork(ABC):
    """Abstract Unit of Work interface for transaction management."""

    # Repository properties
    members: IMemberRepository
    activities: IActivityRepository
    invites: IInviteRepository
    moderation: IModerationRepository
    roles: IRoleRepository

    @abstractmethod
    async def __aenter__(self) -> "IUnitOfWork":
        """Enter async context."""
        pass

    @abstractmethod
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the transaction."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the transaction."""
        pass

    @abstractmethod
    async def refresh(self, instance: Any) -> None:
        """Refresh instance from database."""
        pass

    @abstractmethod
    async def flush(self) -> None:
        """Flush pending changes to database."""
        pass

    @property
    @abstractmethod
    def session(self) -> AsyncSession:
        """Get the underlying database session."""
        pass
