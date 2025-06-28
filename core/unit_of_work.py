"""Unit of Work implementation for transaction management."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.interfaces.unit_of_work import IUnitOfWork
from core.repositories.member_repository import (
    ActivityRepository,
    InviteRepository,
    MemberRepository,
    ModerationRepository,
)
from core.repositories.role_repository import RoleRepository

logger = logging.getLogger(__name__)


class UnitOfWork(IUnitOfWork):
    """Concrete Unit of Work implementation."""

    def __init__(self, session: AsyncSession):
        self._session = session
        self._committed = False

        # Initialize repositories with shared session
        self.members = MemberRepository(session)
        self.activities = ActivityRepository(session)
        self.invites = InviteRepository(session)
        self.moderation = ModerationRepository(session)
        self.roles = RoleRepository(session)

    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context."""
        if exc_type is not None:
            # Exception occurred, rollback
            await self.rollback()
        elif not self._committed:
            # No explicit commit was called, rollback to be safe
            await self.rollback()
            logger.warning("Unit of Work exiting without explicit commit - rolling back")

    async def commit(self) -> None:
        """Commit the transaction."""
        try:
            await self._session.commit()
            self._committed = True
            logger.debug("Unit of Work committed successfully")
        except Exception as e:
            logger.error(f"Error committing Unit of Work: {e}")
            await self.rollback()
            raise

    async def rollback(self) -> None:
        """Rollback the transaction."""
        try:
            await self._session.rollback()
            logger.debug("Unit of Work rolled back")
        except Exception as e:
            logger.error(f"Error rolling back Unit of Work: {e}")
            raise

    async def refresh(self, instance: Any) -> None:
        """Refresh instance from database."""
        try:
            await self._session.refresh(instance)
        except Exception as e:
            logger.error(f"Error refreshing instance: {e}")
            raise

    async def flush(self) -> None:
        """Flush pending changes to database."""
        try:
            await self._session.flush()
        except Exception as e:
            logger.error(f"Error flushing Unit of Work: {e}")
            raise

    @property
    def session(self) -> AsyncSession:
        """Get the underlying database session."""
        return self._session
