"""Base repository implementation with common CRUD operations."""

import logging
from typing import Any, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.interfaces.base import IRepository

T = TypeVar("T")


class BaseRepository(IRepository[T]):
    """Base repository class providing common CRUD operations."""

    def __init__(self, session: AsyncSession, entity_class: Type[T]) -> None:
        super().__init__(session)
        self.entity_class = entity_class
        self.logger = logging.getLogger(self.__class__.__name__)

    async def get_by_id(self, entity_id: Any) -> Optional[T]:
        """Get entity by ID."""
        try:
            result = await self.session.get(self.entity_class, entity_id)
            if result:
                self.logger.debug(
                    f"Found {self.entity_class.__name__} with ID: {entity_id}"
                )
            else:
                self.logger.debug(
                    f"No {self.entity_class.__name__} found with ID: {entity_id}"
                )
            return result
        except Exception as e:
            self.logger.error(
                f"Error getting {self.entity_class.__name__} by ID {entity_id}: {e}"
            )
            raise

    async def get_all(
        self, limit: Optional[int] = None, offset: Optional[int] = None
    ) -> List[T]:
        """Get all entities with optional pagination."""
        try:
            stmt = select(self.entity_class)
            if offset:
                stmt = stmt.offset(offset)
            if limit:
                stmt = stmt.limit(limit)

            result = await self.session.execute(stmt)
            entities = result.scalars().all()
            self.logger.debug(
                f"Retrieved {len(entities)} {self.entity_class.__name__} entities"
            )
            return list(entities)
        except Exception as e:
            self.logger.error(f"Error getting all {self.entity_class.__name__}: {e}")
            raise

    async def create(self, entity: T) -> T:
        """Create new entity."""
        try:
            self.session.add(entity)
            await self.session.flush()  # Get the ID without committing
            self.logger.debug(f"Created {self.entity_class.__name__} entity")
            return entity
        except Exception as e:
            self.logger.error(f"Error creating {self.entity_class.__name__}: {e}")
            raise

    async def update(self, entity: T) -> T:
        """Update existing entity."""
        try:
            # Entity should already be tracked by session
            await self.session.flush()
            self.logger.debug(f"Updated {self.entity_class.__name__} entity")
            return entity
        except Exception as e:
            self.logger.error(f"Error updating {self.entity_class.__name__}: {e}")
            raise

    async def delete(self, entity_id: Any) -> bool:
        """Delete entity by ID."""
        try:
            entity = await self.get_by_id(entity_id)
            if entity:
                await self.session.delete(entity)
                await self.session.flush()
                self.logger.debug(
                    f"Deleted {self.entity_class.__name__} with ID: {entity_id}"
                )
                return True
            else:
                self.logger.warning(
                    f"Cannot delete {self.entity_class.__name__} - not found: {entity_id}"
                )
                return False
        except Exception as e:
            self.logger.error(
                f"Error deleting {self.entity_class.__name__} with ID {entity_id}: {e}"
            )
            raise

    async def exists(self, entity_id: Any) -> bool:
        """Check if entity exists by ID."""
        try:
            entity = await self.get_by_id(entity_id)
            return entity is not None
        except Exception as e:
            self.logger.error(
                f"Error checking existence of {self.entity_class.__name__} with ID {entity_id}: {e}"
            )
            raise
