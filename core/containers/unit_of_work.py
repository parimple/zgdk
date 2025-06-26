"""Unit of Work implementation for transaction management."""

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.interfaces.base import IUnitOfWork
from core.repositories.member_repository import (
    ActivityRepository,
    InviteRepository, 
    MemberRepository,
    ModerationRepository,
)
from core.repositories.role_repository import RoleRepository


class UnitOfWork(IUnitOfWork):
    """Unit of Work implementation using SQLAlchemy async session."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.logger = logging.getLogger(self.__class__.__name__)
        self._transaction_started = False
        
        # Initialize repositories with shared session
        self.members = MemberRepository(session)
        self.activities = ActivityRepository(session)
        self.invites = InviteRepository(session)
        self.moderation = ModerationRepository(session)
        self.roles = RoleRepository(session)

    async def __aenter__(self) -> "UnitOfWork":
        """Enter async context manager."""
        try:
            if not self._transaction_started:
                # Session should already be in a transaction, but we can track it
                self._transaction_started = True
                self.logger.debug("Unit of Work context entered")
            return self
        except Exception as e:
            self.logger.error(f"Error entering Unit of Work context: {e}")
            raise

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit async context manager."""
        try:
            if exc_type is not None:
                await self.rollback()
            self._transaction_started = False
            self.logger.debug("Unit of Work context exited")
        except Exception as e:
            self.logger.error(f"Error exiting Unit of Work context: {e}")
            raise

    async def commit(self) -> None:
        """Commit transaction."""
        try:
            await self.session.commit()
            self.logger.debug("Transaction committed successfully")
        except Exception as e:
            self.logger.error(f"Error committing transaction: {e}")
            await self.rollback()
            raise

    async def rollback(self) -> None:
        """Rollback transaction."""
        try:
            await self.session.rollback()
            self.logger.debug("Transaction rolled back")
        except Exception as e:
            self.logger.error(f"Error rolling back transaction: {e}")
            raise

    async def flush(self) -> None:
        """Flush pending changes without committing."""
        try:
            await self.session.flush()
            self.logger.debug("Session flushed")
        except Exception as e:
            self.logger.error(f"Error flushing session: {e}")
            raise
