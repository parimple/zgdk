"""
Channel permission repository for managing channel permissions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import case

from datasources.models import ChannelPermission

from .base_repository import BaseRepository

logger = logging.getLogger(__name__)


class ChannelRepository(BaseRepository):
    """Repository for ChannelPermission entity operations."""

    def __init__(self, session: AsyncSession):
        """Initialize channel repository.

        Args:
            session: Database session
        """
        super().__init__(ChannelPermission, session)

    async def add_or_update_permission(
        self,
        member_id: int,
        target_id: int,
        allow_permissions_value: int,
        deny_permissions_value: int,
        guild_id: int,
    ) -> ChannelPermission:
        """Add or update channel permissions for a specific member or role.

        Args:
            member_id: ID of the member who owns the channel
            target_id: ID of the member or role getting permissions
            allow_permissions_value: Allowed permissions bitmask
            deny_permissions_value: Denied permissions bitmask
            guild_id: Guild ID for @everyone checks

        Returns:
            Updated ChannelPermission
        """
        permission = await self.session.get(ChannelPermission, (member_id, target_id))
        if permission is None:
            permission = ChannelPermission(
                member_id=member_id,
                target_id=target_id,
                allow_permissions_value=allow_permissions_value,
                deny_permissions_value=deny_permissions_value,
                last_updated_at=datetime.now(timezone.utc),
            )
            self.session.add(permission)
        else:
            permission.allow_permissions_value = (
                permission.allow_permissions_value | allow_permissions_value
            ) & ~deny_permissions_value
            permission.deny_permissions_value = (
                permission.deny_permissions_value | deny_permissions_value
            ) & ~allow_permissions_value
            permission.last_updated_at = datetime.now(timezone.utc)

        # Count permissions excluding default ones
        permissions_count = await self.session.scalar(
            select(func.count()).select_from(ChannelPermission).where(ChannelPermission.member_id == member_id)
        )

        # If we're about to exceed the limit
        if permissions_count > 95:
            # Find the oldest permission that:
            # 1. Belongs to this owner
            # 2. Is not a moderator permission (no manage_messages)
            # 3. Is not an @everyone permission
            oldest_permission = await self.session.execute(
                select(ChannelPermission)
                .where(
                    (ChannelPermission.member_id == member_id)
                    & (ChannelPermission.allow_permissions_value.bitwise_and(0x00002000) == 0)  # not manage_messages
                    & (ChannelPermission.target_id != guild_id)  # not @everyone
                )
                .order_by(ChannelPermission.last_updated_at.asc())
                .limit(1)
            )
            oldest_permission = oldest_permission.scalar_one_or_none()
            if oldest_permission:
                await self.session.delete(oldest_permission)
                logger.info(
                    f"Deleted oldest permission for member {member_id} " f"(target: {oldest_permission.target_id})"
                )

        await self.session.commit()
        await self.session.refresh(permission)

        logger.info(
            f"Updated permission: member={member_id}, target={target_id}, "
            f"allow={allow_permissions_value}, deny={deny_permissions_value}"
        )
        return permission

    async def remove_permission(self, member_id: int, target_id: int) -> bool:
        """Remove channel permissions for a specific member or role.

        Args:
            member_id: ID of the member who owns the channel
            target_id: ID of the member or role

        Returns:
            True if removed, False if not found
        """
        permission = await self.session.get(ChannelPermission, (member_id, target_id))
        if permission:
            await self.session.delete(permission)
            await self.session.commit()
            logger.info(f"Removed permission for member {member_id} and target {target_id}")
            return True
        else:
            logger.warning(f"No permission found for member {member_id} and target {target_id}")
            return False

    async def get_permission(self, member_id: int, target_id: int) -> Optional[ChannelPermission]:
        """Get channel permissions for a specific member or role.

        Args:
            member_id: ID of the member who owns the channel
            target_id: ID of the member or role

        Returns:
            ChannelPermission if found, None otherwise
        """
        return await self.session.get(ChannelPermission, (member_id, target_id))

    async def get_permissions_for_target(self, target_id: int) -> List[ChannelPermission]:
        """Get all channel permissions for a specific target.

        Args:
            target_id: ID of the member or role

        Returns:
            List of ChannelPermission entries
        """
        result = await self.session.execute(select(ChannelPermission).where(ChannelPermission.target_id == target_id))
        return list(result.scalars().all())

    async def get_permissions_for_member(self, member_id: int, limit: int = 95) -> List[ChannelPermission]:
        """Get channel permissions for a specific member.

        Limited to the most recent ones, prioritizing moderator permissions.

        Args:
            member_id: ID of the member who owns the channel
            limit: Maximum number of permissions to return

        Returns:
            List of ChannelPermission entries
        """
        result = await self.session.execute(
            select(ChannelPermission)
            .where(ChannelPermission.member_id == member_id)
            .order_by(
                case(
                    (
                        ChannelPermission.allow_permissions_value.bitwise_and(0x00002000) != 0,
                        0,
                    ),  # manage_messages
                    (
                        ChannelPermission.target_id == member_id,
                        0,
                    ),  # everyone permissions
                    else_=1,
                ),
                ChannelPermission.last_updated_at.desc(),
            )
            .limit(limit)
        )
        return list(result.scalars().all())

    async def remove_all_permissions(self, owner_id: int) -> int:
        """Remove all permissions for a specific owner.

        Args:
            owner_id: ID of the channel owner

        Returns:
            Number of permissions removed
        """
        result = await self.session.execute(select(ChannelPermission).where(ChannelPermission.member_id == owner_id))
        permissions = result.scalars().all()

        for permission in permissions:
            await self.session.delete(permission)

        await self.session.commit()

        count = len(permissions)
        logger.info(f"Removed all {count} permissions for owner {owner_id}")
        return count

    async def remove_mod_permissions_granted_by_member(self, owner_id: int) -> int:
        """Remove only moderator permissions granted by a specific member.

        This method finds and removes permissions where:
        1. The specified user is the owner (member_id)
        2. The permission includes manage_messages (moderator permission)

        Args:
            owner_id: The ID of the member who granted the permissions

        Returns:
            Number of permissions removed
        """
        # Find all permissions where user is the owner
        permissions = await self.session.execute(
            select(ChannelPermission).where(ChannelPermission.member_id == owner_id)
        )
        permissions = permissions.scalars().all()

        # Check each permission for manage_messages (0x00002000)
        mod_permissions_removed = 0
        for permission in permissions:
            if permission.allow_permissions_value & 0x00002000:
                # Remove permission that contains manage_messages
                await self.session.delete(permission)
                mod_permissions_removed += 1
                logger.info(f"Removed moderator permission granted by {owner_id} " f"to target {permission.target_id}")

        await self.session.commit()

        logger.info(f"Total moderator permissions removed for owner {owner_id}: " f"{mod_permissions_removed}")
        return mod_permissions_removed

    async def remove_mod_permissions_for_target(self, target_id: int) -> int:
        """Remove all moderator permissions for a specific target.

        This method removes all permissions where the user (target_id) has been
        granted manage_messages permission (moderator permission) by any channel owner.

        Args:
            target_id: The ID of the user whose moderator permissions should be removed

        Returns:
            Number of permissions removed
        """
        # Find all permissions where user is the target
        permissions = await self.session.execute(
            select(ChannelPermission).where(ChannelPermission.target_id == target_id)
        )
        permissions = permissions.scalars().all()

        # Check each permission for manage_messages (0x00002000)
        removed_count = 0
        for permission in permissions:
            if permission.allow_permissions_value & 0x00002000:
                # Remove permission that contains manage_messages
                await self.session.delete(permission)
                removed_count += 1
                logger.info(
                    f"Removed moderator permission for target {target_id} " f"from owner {permission.member_id}"
                )

        await self.session.commit()

        logger.info(f"Total moderator permissions removed for target {target_id}: " f"{removed_count}")
        return removed_count

    async def add_voice_channel(
        self,
        channel_id: int,
        guild_id: int,
        owner_id: int,
        category_id: int,
    ) -> bool:
        """Add a voice channel to the database.

        Args:
            channel_id: Discord channel ID
            guild_id: Discord guild ID
            owner_id: Member ID of the channel owner
            category_id: Discord category ID

        Returns:
            True if added successfully
        """
        try:
            # For now, we'll store this in channel permissions with a special marker
            # In the future, this should use a dedicated VoiceChannel model
            await self.add_or_update_permission(
                member_id=owner_id,
                target_id=channel_id,  # Store channel ID as target
                allow_permissions_value=0xFFFFFFFF,  # Full permissions marker
                deny_permissions_value=0,
                guild_id=guild_id
            )
            return True
        except Exception as e:
            logger.error(f"Error adding voice channel: {e}")
            return False

    async def remove_voice_channel(self, channel_id: int) -> bool:
        """Remove a voice channel from the database.

        Args:
            channel_id: Discord channel ID

        Returns:
            True if removed successfully
        """
        try:
            # Find and remove the channel entry
            result = await self.session.execute(
                select(ChannelPermission).where(
                    ChannelPermission.target_id == channel_id,
                    ChannelPermission.allow_permissions_value == 0xFFFFFFFF
                )
            )
            permission = result.scalar_one_or_none()
            
            if permission:
                await self.session.delete(permission)
                await self.session.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Error removing voice channel: {e}")
            return False

    async def get_member_channels(self, member_id: int) -> List[ChannelPermission]:
        """Get all voice channels owned by a member.

        Args:
            member_id: Member ID

        Returns:
            List of channel entries
        """
        try:
            result = await self.session.execute(
                select(ChannelPermission).where(
                    ChannelPermission.member_id == member_id,
                    ChannelPermission.allow_permissions_value == 0xFFFFFFFF
                )
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting member channels: {e}")
            return []

    async def set_channel_permission(
        self,
        channel_id: int,
        member_id: int,
        permission_type: str,
        value: str
    ) -> bool:
        """Set channel permission for a member.

        Args:
            channel_id: Discord channel ID
            member_id: Member ID
            permission_type: Type of permission
            value: Permission value (allow/deny/neutral)

        Returns:
            True if set successfully
        """
        # This is handled by the existing add_or_update_permission method
        # Just return True for now as the actual Discord permissions are managed by Discord API
        return True

    # Auto-kick methods
    async def add_autokick(
        self,
        channel_id: int,
        target_id: int,
        added_by: int
    ) -> bool:
        """Add an auto-kick entry for a channel.

        Args:
            channel_id: Discord channel ID
            target_id: Member ID to auto-kick
            added_by: Member ID who added the auto-kick

        Returns:
            True if added successfully
        """
        try:
            # Store auto-kick as a special permission entry
            # Use channel_id as member_id and target_id as target
            await self.add_or_update_permission(
                member_id=channel_id,
                target_id=target_id,
                allow_permissions_value=0,
                deny_permissions_value=0xFFFFFFFF,  # All denied = auto-kick marker
                guild_id=added_by  # Store who added it in guild_id field
            )
            return True
        except Exception as e:
            logger.error(f"Error adding autokick: {e}")
            return False

    async def remove_autokick(self, channel_id: int, target_id: int) -> bool:
        """Remove an auto-kick entry for a channel.

        Args:
            channel_id: Discord channel ID
            target_id: Member ID to remove from auto-kick

        Returns:
            True if removed successfully
        """
        try:
            return await self.remove_permission(channel_id, target_id)
        except Exception as e:
            logger.error(f"Error removing autokick: {e}")
            return False

    async def get_autokick_entry(
        self, channel_id: int, target_id: int
    ) -> Optional[ChannelPermission]:
        """Get auto-kick entry for a specific user in a channel.

        Args:
            channel_id: Discord channel ID
            target_id: Member ID

        Returns:
            Auto-kick entry if exists
        """
        try:
            permission = await self.get_permission(channel_id, target_id)
            # Check if it's an auto-kick entry (all permissions denied)
            if permission and permission.deny_permissions_value == 0xFFFFFFFF:
                return permission
            return None
        except Exception as e:
            logger.error(f"Error getting autokick entry: {e}")
            return None

    async def get_channel_autokicks(self, channel_id: int) -> List[ChannelPermission]:
        """Get all auto-kick entries for a channel.

        Args:
            channel_id: Discord channel ID

        Returns:
            List of auto-kick entries
        """
        try:
            result = await self.session.execute(
                select(ChannelPermission).where(
                    ChannelPermission.member_id == channel_id,
                    ChannelPermission.deny_permissions_value == 0xFFFFFFFF
                )
            )
            return list(result.scalars().all())
        except Exception as e:
            logger.error(f"Error getting channel autokicks: {e}")
            return []
