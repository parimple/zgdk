"""Voice admin commands."""

import logging
from typing import Literal, Optional

import discord
from discord import Member
from discord.ext import commands

from utils.database.voice_manager import DatabaseManager
from utils.message_sender import MessageSender
from utils.premium_checker import PremiumChecker
from utils.voice.autokick import AutoKickManager
from utils.voice.channel import ChannelModManager, VoiceChannelManager
from utils.voice.permissions import (
    BasePermissionCommand,
    PermissionChecker,
    VoicePermissionManager,
)

logger = logging.getLogger(__name__)


class AdminCommands:
    """Voice admin commands for autokick, reset, and debugging."""
    
    def __init__(self, bot):
        """Initialize admin commands."""
        self.bot = bot
        self.permission_manager = VoicePermissionManager(bot)
        self.channel_manager = VoiceChannelManager(bot)
        self.mod_manager = ChannelModManager(bot)
        self.message_sender = MessageSender(bot)
        self.db_manager = DatabaseManager(bot)
        self.permission_checker = PermissionChecker(bot)
        self.autokick_manager = AutoKickManager(bot)
        self.premium_checker = PremiumChecker(bot)
        
        # Initialize admin permission commands
        self.permission_commands = {
            "autokick": BasePermissionCommand(
                "autokick",
                requires_owner=True,
                default_to_true=False,
                toggle=True,
                is_autokick=True
            ),
            "reset": BasePermissionCommand(
                "all",
                requires_owner=True,
                default_to_true=True,
                toggle=False,
                is_reset=True
            ),
        }

    @commands.hybrid_command(aliases=["ak"])
    @PremiumChecker.requires_premium_tier("autokick")
    @discord.app_commands.describe(
        target="Użytkownik do dodania/usunięcia z listy autokick",
        action="Dodaj (+) lub usuń (-) użytkownika z listy autokick",
    )
    async def autokick(
        self,
        ctx,
        target: Optional[Member] = None,
        action: Optional[Literal["+", "-"]] = None,
    ):
        """Zarządzaj listą autokick - dodawaj lub usuwaj użytkowników."""
        await self.permission_commands["autokick"].execute(self, ctx, target, action)

    @commands.hybrid_command(aliases=["r"])
    @PermissionChecker.voice_command(requires_owner=True)
    @PremiumChecker.requires_voice_access("reset")
    @discord.app_commands.describe(
        target="Użytkownik, którego uprawnienia mają zostać zresetowane (opcjonalne)",
    )
    async def reset(
        self,
        ctx,
        target: Optional[Member] = None,
    ):
        """Reset channel permissions or specific user permissions."""
        await self.permission_commands["reset"].execute(self, ctx, target, None)

    async def reset_channel_permissions(self, ctx):
        """Reset all channel permissions to default."""
        await self.permission_manager.reset_channel_permissions(
            ctx.author.voice.channel, ctx.author
        )
        await self.message_sender.send_channel_reset(ctx)

    async def reset_user_permissions(self, ctx, target):
        """Reset permissions for a specific user."""
        await self.permission_manager.reset_user_permissions(
            ctx.author.voice.channel, ctx.author, target
        )
        await self.message_sender.send_permission_reset(ctx, target)

    @commands.hybrid_command(
        name="debug_access", description="Sprawdza alternatywny dostęp dla użytkownika"
    )
    @discord.app_commands.describe(
        target="Użytkownik do sprawdzenia (opcjonalnie, domyślnie sprawdza ciebie)",
    )
    async def debug_access(self, ctx, target: Optional[Member] = None):
        """Sprawdza alternatywny dostęp dla użytkownika."""
        target_user = target or ctx.author

        # Tymczasowo podmieniamy autora w kontekście
        original_author = ctx.author
        ctx.author = target_user

        try:
            debug_info = await self.premium_checker.debug_alternative_access(ctx)
            await ctx.send(f"```\n{debug_info}\n```")
        finally:
            # Przywracamy oryginalnego autora
            ctx.author = original_author

    @commands.hybrid_command(name="voice_stats", description="Statystyki systemu voice")
    @commands.has_permissions(administrator=True)
    async def voice_stats(self, ctx):
        """Wyświetla statystyki systemu voice."""
        # Pobierz event handler
        voice_event = None
        for cog in self.bot.cogs.values():
            if hasattr(cog, "metrics"):
                voice_event = cog
                break

        if not voice_event:
            await ctx.send("❌ Nie znaleziono handlera voice events")
            return

        metrics = voice_event.metrics

        # Cache statistics
        cache_total = metrics["cache_hits"] + metrics["cache_misses"]
        cache_hit_rate = (
            (metrics["cache_hits"] / cache_total * 100) if cache_total > 0 else 0
        )

        embed = discord.Embed(
            title="📊 Voice System Statistics",
            color=discord.Color.blue(),
            timestamp=ctx.message.created_at,
        )

        # Events statistics
        embed.add_field(
            name="🔄 Voice State Updates",
            value=f"Total: {metrics['voice_state_updates']:,}\n"
            f"Joins: {metrics['voice_joins']:,}\n"
            f"Switches: {metrics['voice_switches']:,}\n"
            f"Leaves: {metrics['voice_leaves']:,}",
            inline=True,
        )

        # Channel statistics
        embed.add_field(
            name="🎤 Channel Operations",
            value=f"Created: {metrics['channels_created']:,}\n"
            f"Deleted: {metrics['channels_deleted']:,}\n"
            f"Active: {len(metrics['active_channels']):,}",
            inline=True,
        )

        # Processing statistics
        embed.add_field(
            name="⚡ Processing Stats",
            value=f"Processed: {metrics['events_processed']:,}\n"
            f"Errors: {metrics['errors']:,}\n"
            f"Avg Time: {metrics['avg_processing_time']:.2f}ms",
            inline=True,
        )

        # Cache statistics
        embed.add_field(
            name="💾 Cache Performance",
            value=f"Hits: {metrics['cache_hits']:,}\n"
            f"Misses: {metrics['cache_misses']:,}\n"
            f"Hit Rate: {cache_hit_rate:.1f}%",
            inline=True,
        )

        # Active channels list
        if metrics["active_channels"]:
            active_list = []
            for channel_id in list(metrics["active_channels"])[:10]:
                channel = self.bot.get_channel(channel_id)
                if channel:
                    active_list.append(f"• {channel.name} ({len(channel.members)} users)")
            
            if active_list:
                embed.add_field(
                    name="🔊 Active Channels (Top 10)",
                    value="\n".join(active_list) or "None",
                    inline=False,
                )

        await ctx.send(embed=embed)