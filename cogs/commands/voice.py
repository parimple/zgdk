"""Voice commands cog for managing voice channel permissions and operations."""

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
from utils.voice.permissions import BasePermissionCommand, PermissionChecker, VoicePermissionManager

logger = logging.getLogger(__name__)


class VoiceCog(commands.Cog):
    """Voice commands cog for managing voice channel permissions and operations."""

    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = VoicePermissionManager(bot)
        self.channel_manager = VoiceChannelManager(bot)
        self.mod_manager = ChannelModManager(bot)
        self.message_sender = MessageSender()
        self.db_manager = DatabaseManager(bot)
        self.permission_checker = PermissionChecker(bot)
        self.autokick_manager = AutoKickManager(bot)
        self.premium_checker = PremiumChecker(bot)

        # Initialize permission commands
        self.permission_commands = {
            "speak": BasePermissionCommand("speak", requires_owner=False),
            "view": BasePermissionCommand("view_channel", requires_owner=False),
            "connect": BasePermissionCommand("connect", requires_owner=False),
            "text": BasePermissionCommand("send_messages", requires_owner=False),
            "live": BasePermissionCommand("stream", requires_owner=False),
            "mod": BasePermissionCommand(
                "manage_messages",
                requires_owner=True,
                default_to_true=True,
                toggle=True,
            ),
            "autokick": BasePermissionCommand(
                "autokick",
                requires_owner=False,
                is_autokick=True,
            ),
            "reset": BasePermissionCommand(
                "reset",
                requires_owner=True,
                is_reset=True,
            ),
        }

    @commands.hybrid_command(aliases=["s"])
    @PermissionChecker.voice_command()
    @PremiumChecker.requires_voice_access("speak")
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_speak="Ustaw uprawnienie mówienia (+ lub -)",
    )
    async def speak(
        self,
        ctx,
        target: Optional[Member] = None,
        can_speak: Optional[Literal["+", "-"]] = None,
    ):
        """Set the speak permission for the target."""
        await self.permission_commands["speak"].execute(self, ctx, target, can_speak)

    @commands.hybrid_command(aliases=["v"])
    @PermissionChecker.voice_command()
    @PremiumChecker.requires_voice_access("view")
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_view="Ustaw uprawnienie widzenia kanału (+ lub -)",
    )
    async def view(
        self,
        ctx,
        target: Optional[Member] = None,
        can_view: Optional[Literal["+", "-"]] = None,
    ):
        """Set the view permission for the target."""
        await self.permission_commands["view"].execute(self, ctx, target, can_view)

    @commands.hybrid_command(aliases=["c"])
    @PermissionChecker.voice_command()
    @PremiumChecker.requires_voice_access("connect")
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_connect="Ustaw uprawnienie połączenia (+ lub -)",
    )
    async def connect(
        self,
        ctx,
        target: Optional[Member] = None,
        can_connect: Optional[Literal["+", "-"]] = None,
    ):
        """Set the connect permission for the target."""
        await self.permission_commands["connect"].execute(self, ctx, target, can_connect)

    @commands.hybrid_command(aliases=["t"])
    @PermissionChecker.voice_command()
    @PremiumChecker.requires_voice_access("text")
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_message="Ustaw uprawnienie pisania (+ lub -)",
    )
    async def text(
        self,
        ctx,
        target: Optional[Member] = None,
        can_message: Optional[Literal["+", "-"]] = None,
    ):
        """Set the message permission for the target."""
        await self.permission_commands["text"].execute(self, ctx, target, can_message)

    @commands.hybrid_command(aliases=["lv"])
    @PermissionChecker.voice_command()
    @PremiumChecker.requires_voice_access("live")
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_stream="Ustaw uprawnienie streamowania (+ lub -)",
    )
    async def live(
        self,
        ctx,
        target: Optional[Member] = None,
        can_stream: Optional[Literal["+", "-"]] = None,
    ):
        """Set the stream permission for the target."""
        await self.permission_commands["live"].execute(self, ctx, target, can_stream)

    @commands.hybrid_command(aliases=["m"])
    @PermissionChecker.voice_command(requires_owner=True)
    @PremiumChecker.requires_voice_access("mod")
    @discord.app_commands.describe(
        target="Użytkownik do dodania lub usunięcia jako moderator kanału",
        can_manage="Dodaj (+) lub usuń (-) uprawnienia moderatora kanału",
    )
    async def mod(
        self,
        ctx,
        target: Optional[Member] = None,
        can_manage: Optional[Literal["+", "-"]] = None,
    ):
        """Add or remove channel moderator permissions for the selected user."""
        # If no arguments provided, show current mod status
        if target is None and can_manage is None:
            voice_channel = ctx.author.voice.channel
            # Get mod limit from user's roles
            mod_limit = 0
            for role in reversed(self.bot.config["premium_roles"]):
                if any(r.name == role["name"] for r in ctx.author.roles):
                    mod_limit = role["moderator_count"]
                    break

            # Get current mods
            current_mods = [
                t
                for t, overwrite in voice_channel.overwrites.items()
                if isinstance(t, discord.Member)
                and overwrite.manage_messages is True
                and not overwrite.priority_speaker
            ]
            # Convert Member objects to mentions string with display names
            current_mods_mentions = (
                ", ".join(f"{member.mention} ({member.display_name})" for member in current_mods)
                or "brak"
            )
            remaining_slots = max(0, mod_limit - len(current_mods))

            await self.message_sender.send_mod_info(
                ctx, current_mods_mentions, mod_limit, remaining_slots
            )
            return

        # Get mod limit from user's roles
        mod_limit = 0
        for role in reversed(self.bot.config["premium_roles"]):
            if any(r.name == role["name"] for r in ctx.author.roles):
                mod_limit = role["moderator_count"]
                break

        # Get current mods count
        voice_channel = ctx.author.voice.channel
        current_mods = [
            t
            for t, overwrite in voice_channel.overwrites.items()
            if isinstance(t, discord.Member)
            and overwrite.manage_messages is True
            and not overwrite.priority_speaker
            and t != target  # Don't count the target if they're already a mod
        ]

        # Check if adding would exceed limit
        if can_manage == "+" and len(current_mods) >= mod_limit:
            await self.message_sender.send_mod_limit_exceeded(ctx, mod_limit, current_mods)
            return

        await self.permission_commands["mod"].execute(self, ctx, target, can_manage)

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
                ctx, info["channel"], info["owner"], info["mods"], info["disabled_perms"]
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
            ctx, info["channel"], info["owner"], info["mods"], info["disabled_perms"], target
        )

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
        cache_hit_rate = (metrics["cache_hits"] / cache_total * 100) if cache_total > 0 else 0

        embed = discord.Embed(title="📊 Statystyki systemu Voice", color=discord.Color.blue())

        embed.add_field(
            name="🏗️ Kanały",
            value=f"Utworzone: {metrics['channels_created']}\nPonownie użyte: {metrics['channels_reused']}",
            inline=True,
        )

        embed.add_field(
            name="🥾 Autokick",
            value=f"Kolejka: {metrics['autokicks_queued']}\nWykonane: {metrics['autokicks_executed']}",
            inline=True,
        )

        embed.add_field(
            name="💾 Cache",
            value=f"Trafienia: {cache_hit_rate:.1f}%\nHits: {metrics['cache_hits']}\nMisses: {metrics['cache_misses']}",
            inline=True,
        )

        # Worker status
        worker_status = (
            "🟢 Aktywny"
            if voice_event.autokick_worker_task and not voice_event.autokick_worker_task.done()
            else "🔴 Nieaktywny"
        )
        embed.add_field(name="⚙️ Worker", value=worker_status, inline=True)

        # Queue size
        queue_size = voice_event.autokick_queue.qsize()
        embed.add_field(name="📋 Kolejka", value=f"{queue_size} zadań", inline=True)

        await ctx.send(embed=embed)


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(VoiceCog(bot))
