"""Voice channel management commands."""

import logging
from typing import Optional

import discord
from discord import Member
from discord.ext import commands

from utils.database.voice_manager import DatabaseManager
from utils.message_sender import MessageSender
from utils.premium_checker import PremiumChecker
from utils.voice.channel import ChannelModManager, VoiceChannelManager
from utils.voice.permissions import PermissionChecker

logger = logging.getLogger(__name__)


class ChannelCommands:
    """Voice channel management commands for join, limit, voicechat."""
    
    def __init__(self, bot):
        """Initialize channel commands."""
        self.bot = bot
        self.channel_manager = VoiceChannelManager(bot)
        self.mod_manager = ChannelModManager(bot)
        self.message_sender = MessageSender(bot)
        self.db_manager = DatabaseManager(bot)
        self.permission_checker = PermissionChecker(bot)
        self.premium_checker = PremiumChecker(bot)

    @commands.hybrid_command(aliases=["j"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe()
    async def join(self, ctx):
        """Dołącz do kanału głosowego osoby, która użyła komendy."""
        await self.channel_manager.join_channel(ctx)

    @commands.hybrid_command(aliases=["l"])
    @PermissionChecker.voice_command()
    @PremiumChecker.requires_voice_access("limit")
    @discord.app_commands.describe(
        max_members="Maksymalna liczba członków (1-99 dla konkretnej wartości)"
    )
    async def limit(self, ctx, max_members: int):
        """Zmień maksymalną liczbę członków, którzy mogą dołączyć do bieżącego kanału głosowego."""
        await self.channel_manager.set_channel_limit(ctx, max_members)

    @commands.hybrid_command(aliases=["vc"])
    @PremiumChecker.requires_voice_access("voicechat")
    @discord.app_commands.describe(
        target="Użytkownik do sprawdzenia kanału głosowego (ID, wzmianka lub nazwa użytkownika)",
    )
    async def voicechat(self, ctx, target: Optional[Member] = None):
        """
        Wyślij link do kanału głosowego użytkownika i informacje o uprawnieniach.
        Jeśli nie podano targetu, sprawdza kanał aktualnie wywołującego.
        """
        # 1. Jeśli **nie ma** targetu => używamy starej logiki
        if target is None:
            # W tej sytuacji chcemy wymagać, by wywołujący był na kanale
            if not ctx.author.voice or not ctx.author.voice.channel:
                await self.message_sender.send_not_in_voice_channel(ctx)
                return

            channel = ctx.author.voice.channel
            info = await self.channel_manager.get_channel_info(channel, ctx.author)
            await self.message_sender.send_voice_channel_info(
                ctx,
                info["channel"],
                info["owner"],
                info["mods"],
                info["disabled_perms"],
            )
            return

        # 2. Jeśli **jest** target => sprawdzamy kanał, w którym on jest
        if not target.voice or not target.voice.channel:
            # Jeśli target w ogóle nie jest na kanale
            await self.message_sender.send_not_in_voice_channel(ctx, target)
            return

        # 3. Pobieramy kanał docelowy i wyświetlamy informacje
        channel = target.voice.channel
        info = await self.channel_manager.get_channel_info(channel, target)
        await self.message_sender.send_voice_channel_info(
            ctx,
            info["channel"],
            info["owner"],
            info["mods"],
            info["disabled_perms"],
            target,
        )