"""
On Setup Event
"""
import logging

import discord
from discord.ext import commands, tasks

from datasources.queries import MemberQueries, RoleQueries

logger = logging.getLogger(__name__)


class OnSetupEvent(commands.Cog):
    """Class for the On Setup Discord Event"""

    def __init__(self, bot):
        self.bot = bot
        self.setup_roles.start()  # pylint: disable=no-member
        self.setup_unknown_inviter.start()  # pylint: disable=no-member

    async def cog_unload(self):
        self.setup_roles.cancel()  # pylint: disable=no-member
        self.setup_unknown_inviter.cancel()  # pylint: disable=no-member

    async def ensure_roles_in_db_and_guild(self, roles: list[dict], role_type: str):
        """Utility function to ensure roles exist in both database and guild"""
        guild = self.bot.guild
        async with self.bot.get_db() as session:
            for role_info in roles:
                role_name = role_info["name"]
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    # Create a new role with the given name
                    role = await guild.create_role(
                        name=role_name,
                        mentionable=False,  # Allow anyone to mention this role
                    )
                # Check if role with given ID already exists in database
                existing_role = await RoleQueries.get_role_by_id(session, role.id)
                if existing_role:
                    logger.info("Role with ID %s already exists in database", role.id)
                    continue
                # Add role to database
                await RoleQueries.add_role(session, role.id, role.name, role_type)
                logger.info(
                    "Ensured role %s (ID: %s) with type %s in database and guild",
                    role.name,
                    role.id,
                    role_type,
                )
            await session.commit()

    @tasks.loop(count=1)  # Run this task only once
    async def setup_roles(self):
        """Setup roles"""
        await self.bot.wait_until_ready()
        logger.info("Setting up roles")
        # Premium roles
        premium_roles = self.bot.config["premium_roles"]
        await self.ensure_roles_in_db_and_guild(premium_roles, "premium")
        # Ranking roles
        rank_role_names = [{"name": str(i)} for i in range(1, 101)]
        await self.ensure_roles_in_db_and_guild(rank_role_names, "rank")
        # Mute roles
        mute_roles = self.bot.config["mute_roles"]
        await self.ensure_roles_in_db_and_guild(mute_roles, "mute")
        # Temporary roles for donations
        temporary_roles = [
            {"name": "$128"},
            {"name": "$64"},
            {"name": "$32"},
            {"name": "$16"},
            {"name": "$8"},
            {"name": "$4"},
            {"name": "$2"},
        ]
        await self.ensure_roles_in_db_and_guild(temporary_roles, "temporary")
        logger.info("Roles setup complete")

    @tasks.loop(count=1)
    async def setup_unknown_inviter(self):
        """Create a special entry for unknown invites."""
        async with self.bot.get_db() as session:
            unknown_inviter_id = self.bot.guild_id
            await MemberQueries.get_or_add_member(session, unknown_inviter_id)
            await session.commit()
            logger.info("Unknown Inviter is set")


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnSetupEvent(bot))
