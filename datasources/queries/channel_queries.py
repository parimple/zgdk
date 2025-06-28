"""
Channel permission-related queries for the database.
"""

import logging
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.expression import case

from ..models import ChannelPermission

logger = logging.getLogger(__name__)


class ChannelPermissionQueries:
    """Class for Channel Permission Queries"""

    @staticmethod
    async def add_or_update_permission(
        session: AsyncSession,
        member_id: int,
        target_id: int,
        allow_permissions_value: int,
        deny_permissions_value: int,
        guild_id: int,
    ):
        """Add or update channel permissions for a specific member or role."""
        permission = await session.get(ChannelPermission, (member_id, target_id))
        if permission is None:
            permission = ChannelPermission(
                member_id=member_id,
                target_id=target_id,
                allow_permissions_value=allow_permissions_value,
                deny_permissions_value=deny_permissions_value,
                last_updated_at=datetime.now(timezone.utc),
            )
            session.add(permission)
        else:
            permission.allow_permissions_value = (
                permission.allow_permissions_value | allow_permissions_value
            ) & ~deny_permissions_value
            permission.deny_permissions_value = (
                permission.deny_permissions_value | deny_permissions_value
            ) & ~allow_permissions_value
            permission.last_updated_at = datetime.now(timezone.utc)

        # Count permissions excluding default ones (which are not in database)
        permissions_count = await session.scalar(
            select(func.count()).select_from(ChannelPermission).where(ChannelPermission.member_id == member_id)
        )

        # If we're about to exceed the limit
        if permissions_count > 95:
            # Find the oldest permission that:
            # 1. Belongs to this owner
            # 2. Is not a moderator permission (no manage_messages)
            # 3. Is not an @everyone permission
            oldest_permission = await session.execute(
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
                await session.delete(oldest_permission)
                logger.info(f"Deleted oldest permission for member {member_id} (target: {oldest_permission.target_id})")

    @staticmethod
    async def remove_permission(session: AsyncSession, member_id: int, target_id: int):
        """Remove channel permissions for a specific member or role."""
        permission = await session.get(ChannelPermission, (member_id, target_id))
        if permission:
            await session.delete(permission)
            logger.info(f"Removed permission for member {member_id} and target {target_id}")
        else:
            logger.warning(f"No permission found for member {member_id} and target {target_id}")

    @staticmethod
    async def get_permission(session: AsyncSession, member_id: int, target_id: int) -> Optional[ChannelPermission]:
        """Get channel permissions for a specific member or role."""
        return await session.get(ChannelPermission, (member_id, target_id))

    @staticmethod
    async def get_permissions_for_target(session: AsyncSession, target_id: int) -> List[ChannelPermission]:
        """Get all channel permissions for a specific target (member or role)."""
        result = await session.execute(select(ChannelPermission).where(ChannelPermission.target_id == target_id))
        return result.scalars().all()

    @staticmethod
    async def get_permissions_for_member(
        session: AsyncSession, member_id: int, limit: int = 95
    ) -> List[ChannelPermission]:
        """Get channel permissions for a specific member, limited to the most recent ones."""
        result = await session.execute(
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
        return result.scalars().all()

    @staticmethod
    async def remove_all_permissions(session: AsyncSession, owner_id: int):
        """Remove all permissions for a specific owner."""
        result = await session.execute(select(ChannelPermission).where(ChannelPermission.member_id == owner_id))
        permissions = result.scalars().all()

        for permission in permissions:
            await session.delete(permission)

        logger.info(f"Removed all {len(permissions)} permissions for owner {owner_id}")

    @staticmethod
    async def remove_mod_permissions_granted_by_member(session: AsyncSession, owner_id: int):
        """
        Remove only moderator permissions granted by a specific member.

        This method finds and removes permissions where:
        1. The specified user is the owner (member_id)
        2. The permission includes manage_messages (moderator permission)

        This preserves all other permissions the user has granted.

        Args:
            session: The database session
            owner_id: The ID of the member who granted the permissions
        """
        # Znajdujemy wszystkie uprawnienia gdzie użytkownik jest właścicielem (member_id)
        permissions = await session.execute(select(ChannelPermission).where(ChannelPermission.member_id == owner_id))
        permissions = permissions.scalars().all()

        # Sprawdzamy każde uprawnienie, czy zawiera manage_messages (bit 15 w Discord Permissions)
        mod_permissions_removed = 0
        for permission in permissions:
            # Sprawdź czy uprawnienie zawiera manage_messages (0x00002000)
            if permission.allow_permissions_value & 0x00002000:
                # Usuń uprawnienie, które zawiera manage_messages
                await session.delete(permission)
                mod_permissions_removed += 1
                logger.info(f"Removed moderator permission granted by {owner_id} to target {permission.target_id}")

        logger.info(f"Total moderator permissions removed for owner {owner_id}: {mod_permissions_removed}")

    @staticmethod
    async def remove_mod_permissions_for_target(session: AsyncSession, target_id: int):
        """
        Remove all moderator permissions for a specific target.

        This method removes all permissions where the user (target_id) has been
        granted manage_messages permission (moderator permission) by any channel owner.

        Args:
            session: The database session
            target_id: The ID of the user whose moderator permissions should be removed
        """
        # Znajdujemy wszystkie uprawnienia gdzie użytkownik jest celem (target_id)
        permissions = await session.execute(select(ChannelPermission).where(ChannelPermission.target_id == target_id))
        permissions = permissions.scalars().all()

        # Sprawdzamy każde uprawnienie, czy zawiera manage_messages (bit 15 w Discord Permissions)
        for permission in permissions:
            # Sprawdź czy uprawnienie zawiera manage_messages (0x00002000)
            if permission.allow_permissions_value & 0x00002000:
                # Usuń uprawnienie, które zawiera manage_messages
                await session.delete(permission)
                logger.info(f"Removed moderator permission for target {target_id} from owner {permission.member_id}")
