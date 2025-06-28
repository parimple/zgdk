"""Gender role management commands."""

import logging

import discord
from discord.ext import commands

from utils.moderation import GenderManager, GenderType
from utils.permissions import is_mod_or_admin

logger = logging.getLogger(__name__)


class GenderCommands(commands.Cog):
    """Commands for managing gender roles."""
    
    def __init__(self, bot):
        """Initialize gender commands."""
        self.bot = bot
        self.gender_manager = GenderManager(bot)
    
    @commands.command(
        name="male", description="Nadaje rolę mężczyzny użytkownikowi"
    )
    @is_mod_or_admin()
    async def male(self, ctx: commands.Context, user: discord.Member):
        """Assign male role to a user."""
        await self.gender_manager.assign_gender_role(ctx, user, GenderType.MALE)
    
    @commands.command(
        name="female", description="Nadaje rolę kobiety użytkownikowi"
    )
    @is_mod_or_admin()
    async def female(self, ctx: commands.Context, user: discord.Member):
        """Assign female role to a user."""
        await self.gender_manager.assign_gender_role(ctx, user, GenderType.FEMALE)