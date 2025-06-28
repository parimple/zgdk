"""Clear/message deletion commands for moderation."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from utils.message_sender import MessageSender
from utils.moderation import MessageCleaner
from utils.permissions import is_mod_or_admin

logger = logging.getLogger(__name__)


class ClearCommands(commands.Cog):
    """Commands for clearing messages."""
    
    def __init__(self, bot):
        """Initialize clear commands."""
        self.bot = bot
        self.message_sender = MessageSender(bot)
        self.message_cleaner = MessageCleaner(bot)
    
    @commands.hybrid_command(
        name="clear", description="Usuwa wiadomości użytkownika z ostatnich X godzin."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, którego wiadomości mają być usunięte",
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
    )
    async def clear_messages(
        self, ctx: commands.Context, user: discord.Member, hours: Optional[int] = 1
    ):
        """Clear messages from a specific user in the current channel."""
        await self.message_cleaner.clear_messages(ctx, hours, user, all_channels=False)
    
    @commands.hybrid_command(
        name="clearall",
        description="Usuwa wiadomości użytkownika ze wszystkich kanałów z ostatnich X godzin.",
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, którego wiadomości mają być usunięte",
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
    )
    async def clear_all_channels(
        self, ctx: commands.Context, user: discord.Member, hours: Optional[int] = 1
    ):
        """Clear messages from a specific user in all channels."""
        await self.message_cleaner.clear_messages(ctx, hours, user, all_channels=True)
    
    @commands.hybrid_command(
        name="clearimg",
        description="Usuwa wszystkie obrazy z kanału z ostatnich X godzin.",
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        hours="Liczba godzin wstecz, z których usunąć obrazy (domyślnie 1)",
    )
    async def clear_images(
        self, ctx: commands.Context, hours: Optional[int] = 1
    ):
        """Clear all images from the current channel."""
        await self.message_cleaner.clear_images(ctx, hours)
    
    @commands.command(name="modsync", hidden=True)
    @is_mod_or_admin()
    async def modsync(self, ctx: commands.Context):
        """Sync moderation commands (for hybrid commands)."""
        logger.info("Syncing moderation commands...")
        try:
            await self.bot.tree.sync()
            await self.message_sender.send_success(
                ctx, "Komendy moderacyjne zostały zsynchronizowane!"
            )
            logger.info("Moderation commands synced successfully")
        except Exception as e:
            logger.error(f"Error syncing moderation commands: {e}")
            await self.message_sender.send_error(
                ctx, f"Błąd podczas synchronizacji komend: {str(e)}"
            )