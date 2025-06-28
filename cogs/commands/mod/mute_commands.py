"""Mute/unmute commands for moderation."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from utils.message_sender import MessageSender
from utils.permissions import is_mod_or_admin
from utils.moderation.mute_manager import MuteManager
from .utils import parse_duration

logger = logging.getLogger(__name__)


class MuteCommands(commands.Cog):
    """Commands for muting and unmuting users."""
    
    def __init__(self, bot):
        """Initialize mute commands."""
        self.bot = bot
        self.message_sender = MessageSender(bot)
        self.mute_manager = MuteManager(bot)
        self.parse_duration = parse_duration
    
    async def send_subcommand_help(self, ctx, command_name):
        """Display help for group commands with premium info."""
        base_text = "Użyj jednej z podkomend: nick, img, txt, live, rank"
        
        # Add premium info
        _, premium_text = self.message_sender._get_premium_text(ctx)
        if premium_text:
            base_text = f"{base_text}\n{premium_text}"
        
        embed = self.message_sender._create_embed(description=base_text, ctx=ctx)
        await self.message_sender._send_embed(ctx, embed, reply=True)
        logger.debug(f"Sent subcommand help for {command_name}")
    
    @commands.hybrid_group(
        name="mute", description="Komendy związane z wyciszaniem użytkowników."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik do wyciszenia (opcjonalnie, działa jak mute txt)",
        duration="Czas trwania blokady, np. 1h, 30m, 1d (puste = blokada stała)",
    )
    async def mute(
        self,
        ctx: commands.Context,
        user: Optional[discord.Member] = None,
        duration: str = "",
    ):
        """Mute commands group."""
        if ctx.invoked_subcommand is None:
            if user is not None:
                # If user provided but no subcommand, act as 'mute txt'
                await self.mute_txt(ctx, user, duration)
            else:
                await self.send_subcommand_help(ctx, "mute")
    
    @mute.command(
        name="nick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik z niewłaściwym nickiem")
    async def mute_nick(self, ctx: commands.Context, user: discord.Member):
        """Remove inappropriate nickname and apply punishment."""
        await self.mute_manager.mute_user(ctx, user, "nick")
    
    @mute.command(
        name="img", description="Blokuje możliwość wysyłania obrazków i linków."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość wysyłania obrazków",
        duration="Czas trwania blokady, np. 1h, 30m, 1d (puste = blokada stała)",
    )
    async def mute_img(
        self, ctx: commands.Context, user: discord.Member, duration: str = ""
    ):
        """Block ability to send images and links."""
        duration_td = self.mute_manager.parse_duration(duration) if duration else None
        await self.mute_manager.mute_user(ctx, user, "img", duration_td)
    
    @mute.command(name="txt", description="Blokuje możliwość wysyłania wiadomości.")
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość wysyłania wiadomości",
        duration="Czas trwania blokady, np. 1h, 30m, 1d (puste = blokada stała)",
    )
    async def mute_txt(
        self, ctx: commands.Context, user: discord.Member, duration: str = ""
    ):
        """Block ability to send messages."""
        duration_td = self.mute_manager.parse_duration(duration) if duration else None
        await self.mute_manager.mute_user(ctx, user, "txt", duration_td)
    
    @mute.command(name="live", description="Blokuje możliwość streamowania.")
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość streamowania"
    )
    async def mute_live(self, ctx: commands.Context, user: discord.Member):
        """Block ability to stream."""
        await self.mute_manager.mute_user(ctx, user, "live")
    
    @mute.command(
        name="rank", description="Blokuje możliwość zdobywania punktów rankingowych."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość zdobywania punktów"
    )
    async def mute_rank(self, ctx: commands.Context, user: discord.Member):
        """Block ability to earn ranking points."""
        await self.mute_manager.mute_user(ctx, user, "rank")
    
    @commands.hybrid_group(
        name="unmute", description="Komendy związane z odwyciszaniem użytkowników."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik do odwyciszenia (opcjonalnie, działa jak unmute txt)"
    )
    async def unmute(
        self, ctx: commands.Context, user: Optional[discord.Member] = None
    ):
        """Unmute commands group."""
        if ctx.invoked_subcommand is None:
            if user is not None:
                # If user provided but no subcommand, act as 'unmute txt'
                await self.unmute_txt(ctx, user)
            else:
                await self.send_subcommand_help(ctx, "unmute")
    
    @unmute.command(
        name="nick", description="Przywraca możliwość zmiany nicku użytkownikowi."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odmutowania nicku")
    async def unmute_nick(self, ctx: commands.Context, user: discord.Member):
        """Restore ability to change nickname."""
        await self.mute_manager.unmute_user(ctx, user, "nick")
    
    @unmute.command(
        name="img",
        description="Przywraca możliwość wysyłania obrazków i linków użytkownikowi.",
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odmutowania obrazków")
    async def unmute_img(self, ctx: commands.Context, user: discord.Member):
        """Restore ability to send images and links."""
        await self.mute_manager.unmute_user(ctx, user, "img")
    
    @unmute.command(
        name="txt", description="Przywraca możliwość wysyłania wiadomości użytkownikowi."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odmutowania tekstów")
    async def unmute_txt(self, ctx: commands.Context, user: discord.Member):
        """Restore ability to send messages."""
        await self.mute_manager.unmute_user(ctx, user, "txt")
    
    @unmute.command(
        name="live", description="Przywraca możliwość streamowania użytkownikowi."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odmutowania streamów")
    async def unmute_live(self, ctx: commands.Context, user: discord.Member):
        """Restore ability to stream."""
        await self.mute_manager.unmute_user(ctx, user, "live")
    
    @unmute.command(
        name="rank",
        description="Przywraca możliwość zdobywania punktów rankingowych użytkownikowi.",
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odmutowania rankingu")
    async def unmute_rank(self, ctx: commands.Context, user: discord.Member):
        """Restore ability to earn ranking points."""
        await self.mute_manager.unmute_user(ctx, user, "rank")


async def setup(bot):
    """Setup function to add cog to bot."""
    await bot.add_cog(MuteCommands(bot))