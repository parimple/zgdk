"""Database management for voice features."""

import logging
from typing import Literal, Optional

import discord
from discord import Permissions
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.channel_repository import ChannelRepository

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    async def should_update_db(self, member: discord.Member, voice_channel: Optional[discord.VoiceChannel]) -> bool:
        """
        Determine if the database should be updated based on the member's roles and voice channel.

        :param member: The member to check
        :param voice_channel: The voice channel the member is in (if any)
        :return: True if the database should be updated, False otherwise
        """
        has_premium = any(role["name"] in [r.name for r in member.roles] for role in self.bot.config["premium_roles"])
        is_in_specific_category = voice_channel and voice_channel.category_id in self.bot.config.get(
            "vc_categories", []
        )
        self.logger.info(
            f"Checking database update conditions for {member}: has_premium={has_premium}, is_in_specific_category={is_in_specific_category}"
        )
        return has_premium and is_in_specific_category

    async def update_permission(
        self,
        session: AsyncSession,
        member_id: int,
        target_id: int,
        allow_permissions_value: Permissions,
        deny_permissions_value: Permissions,
        update_db: Optional[Literal["+", "-"]],
    ):
        """Updates the permission in the database."""
        self.logger.info(
            f"Attempting to update permission: member_id={member_id}, target_id={target_id}, update_db={update_db}"
        )

        if update_db is None:
            self.logger.info("Skipping database update as update_db is None")
            return

        try:
            channel_repo = ChannelRepository(session)
            if update_db == "+":
                self.logger.info(f"Adding/updating permission: member_id={member_id}, target_id={target_id}")
                # Note: add_or_update_permission needs guild_id parameter
                # For now, pass 0 as we don't have guild_id in this context
                await channel_repo.add_or_update_permission(
                    member_id,
                    target_id,
                    allow_permissions_value,
                    deny_permissions_value,
                    guild_id=0,  # TODO: Pass actual guild_id
                )
                self.logger.info("Permission successfully added/updated in database")
            elif update_db == "-":
                self.logger.info(f"Removing permission: member_id={member_id}, target_id={target_id}")
                await channel_repo.remove_permission(member_id, target_id)
                self.logger.info("Permission successfully removed from database")
        except Exception as e:
            self.logger.error(f"Error updating permission in database: {str(e)}", exc_info=True)
            raise

    async def get_member_permissions(self, session: AsyncSession, member_id: int):
        """Retrieves permissions for a member from the database."""
        self.logger.info(f"Retrieving permissions for member_id={member_id}")
        try:
            channel_repo = ChannelRepository(session)
            permissions = await channel_repo.get_permissions_for_member(member_id)
            self.logger.info(f"Retrieved {len(permissions) if permissions else 0} permissions for member")
            return permissions
        except Exception as e:
            self.logger.error(f"Error retrieving permissions from database: {str(e)}", exc_info=True)
            raise
