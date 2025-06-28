"""
AutoKick repository for managing autokick entries.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from datasources.models import AutoKick
from .base_repository import BaseRepository
from .member_repository import MemberRepository

logger = logging.getLogger(__name__)


class AutoKickRepository(BaseRepository):
    """Repository for AutoKick entity operations."""
    
    def __init__(self, session: AsyncSession):
        """Initialize AutoKick repository.
        
        Args:
            session: Database session
        """
        super().__init__(session, AutoKick)
        self.member_repo = MemberRepository(session)
    
    async def add_autokick(self, owner_id: int, target_id: int) -> AutoKick:
        """Add an autokick entry.
        
        Args:
            owner_id: ID of the channel owner
            target_id: ID of the member to autokick
            
        Returns:
            Created AutoKick entry
        """
        # Ensure both members exist
        await self.member_repo.get_or_create(owner_id)
        await self.member_repo.get_or_create(target_id)
        
        # Create autokick entry
        autokick = AutoKick(
            owner_id=owner_id,
            target_id=target_id,
            created_at=datetime.now(timezone.utc),
        )
        
        self.session.add(autokick)
        await self.session.commit()
        await self.session.refresh(autokick)
        
        logger.info(f"Added autokick: owner={owner_id}, target={target_id}")
        return autokick
    
    async def remove_autokick(self, owner_id: int, target_id: int) -> bool:
        """Remove an autokick entry.
        
        Args:
            owner_id: ID of the channel owner
            target_id: ID of the member to remove from autokick
            
        Returns:
            True if removed, False if not found
        """
        result = await self.session.execute(
            delete(AutoKick).where(
                (AutoKick.owner_id == owner_id) & 
                (AutoKick.target_id == target_id)
            )
        )
        await self.session.commit()
        
        removed = result.rowcount > 0
        if removed:
            logger.info(f"Removed autokick: owner={owner_id}, target={target_id}")
        
        return removed
    
    async def get_all_autokicks(self) -> List[AutoKick]:
        """Get all autokick entries.
        
        Returns:
            List of all AutoKick entries
        """
        result = await self.session.execute(select(AutoKick))
        return list(result.scalars().all())
    
    async def get_owner_autokicks(self, owner_id: int) -> List[AutoKick]:
        """Get all autokicks for a specific owner.
        
        Args:
            owner_id: ID of the channel owner
            
        Returns:
            List of AutoKick entries for the owner
        """
        result = await self.session.execute(
            select(AutoKick).where(AutoKick.owner_id == owner_id)
        )
        return list(result.scalars().all())
    
    async def get_target_autokicks(self, target_id: int) -> List[AutoKick]:
        """Get all autokicks targeting a specific member.
        
        Args:
            target_id: ID of the targeted member
            
        Returns:
            List of AutoKick entries targeting the member
        """
        result = await self.session.execute(
            select(AutoKick).where(AutoKick.target_id == target_id)
        )
        return list(result.scalars().all())
    
    async def is_autokicked(self, owner_id: int, target_id: int) -> bool:
        """Check if a member is autokicked from an owner's channel.
        
        Args:
            owner_id: ID of the channel owner
            target_id: ID of the member to check
            
        Returns:
            True if autokicked, False otherwise
        """
        result = await self.session.scalar(
            select(AutoKick.id).where(
                (AutoKick.owner_id == owner_id) & 
                (AutoKick.target_id == target_id)
            ).limit(1)
        )
        return result is not None