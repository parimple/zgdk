"""On Ready Event"""

import logging

import discord
from discord.ext import commands, tasks

from datasources.queries import RoleQueries

logger = logging.getLogger(__name__)


class OnSetupEvent(commands.Cog):
    """Class for the On Ready Discord Event"""

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.setup_roles.start()  # pylint: disable=no-member

    async def cog_unload(self):
        self.setup_roles.cancel()  # pylint: disable=no-member

    @tasks.loop(count=1)  # Run this task only once
    async def setup_roles(self):
        """Setup roles"""
        await self.bot.wait_until_ready()
        logger.info("Setting up roles")
        guild = self.bot.guild
        role_names = ["$2", "$4", "$6", "$8", "$16", "$32", "$64", "$128"]
        async with self.bot.session() as session:
            for name in role_names:
                role = discord.utils.get(guild.roles, name=name)
                if not role:
                    # Create a new role with the given name
                    role = await guild.create_role(
                        name=name,
                        # permissions=discord.Permissions(send_messages=True, read_messages=True),
                        # colour=discord.Colour.blue(),
                        # hoist=True,  # Display role members separately from online members
                        mentionable=False,  # Allow anyone to mention this role
                    )
                # Add role to database
                await RoleQueries.add_role(session, role.id, role.name, "premium")
                logger.info("Added role %s (ID: %s) to the database", role.name, role.id)
            await session.commit()
        logger.info("Roles setup complete")


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnSetupEvent(bot))
