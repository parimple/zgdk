"""Voice commands cog for managing voice channel permissions and operations."""

import logging
from typing import Literal, Optional

import discord
from discord import Member
from discord.ext import commands

from utils.database.voice_manager import DatabaseManager
from utils.message_sender import MessageSender
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
    # @commands.has_permissions(administrator=True)
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
    # @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_view="Ustaw uprawnienie wyświetlania (+ lub -)",
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
    # @commands.has_permissions(administrator=True)
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
    # @commands.has_permissions(administrator=True)
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
    # @commands.has_permissions(administrator=True)
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
    # @commands.has_permissions(administrator=True)
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
        if not await self.permission_checker.check_voice_channel(ctx):
            return

        voice_channel = ctx.author.voice.channel
        mod_limit = await self.permission_manager.get_premium_role_limit(ctx.author)

        # If no target is provided, just show current mod information
        if target is None:
            await self.mod_manager.show_mod_status(ctx, voice_channel, mod_limit)
            return

        await self.permission_commands["mod"].execute(self, ctx, target, can_manage)

    @commands.hybrid_command(aliases=["j"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe()
    async def join(self, ctx):
        """Dołącz do kanału głosowego osoby, która użyła komendy."""
        await self.channel_manager.join_channel(ctx)

    @commands.hybrid_command(aliases=["l"])
    # @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        max_members="Maksymalna liczba członków (1-99 dla konkretnej wartości)"
    )
    async def limit(self, ctx, max_members: int):
        """Zmień maksymalną liczbę członków, którzy mogą dołączyć do bieżącego kanału głosowego."""
        await self.channel_manager.set_channel_limit(ctx, max_members)

    @commands.hybrid_command(aliases=["vc"])
    # @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Użytkownik do sprawdzenia kanału głosowego (ID, wzmianka lub nazwa użytkownika)",
    )
    async def voicechat(self, ctx, target: Optional[Member] = None):
        """Wyślij link do kanału głosowego użytkownika i informacje o uprawnieniach."""
        member = target or ctx.author

        if not member.voice or not member.voice.channel:
            await self.message_sender.send_not_in_voice_channel(ctx)
            return

        channel = member.voice.channel
        info = await self.channel_manager.get_channel_info(channel, member)
        await self.message_sender.send_voice_channel_info(
            ctx, info["channel"], info["owner"], info["mods"], info["disabled_perms"]
        )

    @commands.hybrid_command(aliases=["ak"])
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
    # @commands.has_permissions(administrator=True)
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


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(VoiceCog(bot))
