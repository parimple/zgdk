"""Voice permission commands."""

import logging
from typing import Literal, Optional

import discord
from discord import Member
from discord.ext import commands

from core.interfaces.premium_interfaces import IPremiumService
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


class PermissionCommands:
    """Voice permission commands for speak, view, connect, text, live, and mod."""
    
    def __init__(self, bot):
        """Initialize permission commands."""
        self.bot = bot
        self.permission_manager = VoicePermissionManager(bot)
        self.channel_manager = VoiceChannelManager(bot)
        self.mod_manager = ChannelModManager(bot)
        self.message_sender = MessageSender(bot)
        self.db_manager = DatabaseManager(bot)
        self.permission_checker = PermissionChecker(bot)
        self.autokick_manager = AutoKickManager(bot)
        self.premium_checker = PremiumChecker(bot)

        # Initialize permission command handlers
        self.speak_handler = BasePermissionCommand("speak", requires_owner=False)
        self.view_handler = BasePermissionCommand("view_channel", requires_owner=False)
        self.connect_handler = BasePermissionCommand("connect", requires_owner=False)
        self.text_handler = BasePermissionCommand("send_messages", requires_owner=False)
        self.live_handler = BasePermissionCommand("stream", requires_owner=False)
        self.mod_handler = BasePermissionCommand(
            "manage_messages",
            requires_owner=True,
            default_to_true=True,
            toggle=True
        )
        self.reset_handler = BasePermissionCommand(
            "all",
            requires_owner=True,
            default_to_true=True,
            toggle=False,
            is_reset=True
        )

    @commands.hybrid_command(aliases=["s"])
    @PermissionChecker.voice_command()
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
        # Check premium access using the new service
        async with self.bot.get_db() as session:
            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_service.set_guild(ctx.guild)
            
            # Check if user has access to speak command
            has_access, message = await premium_service.check_command_access(ctx.author, "speak")
            if not has_access:
                await self.message_sender.send_error(ctx, message)
                return
        
        await self.speak_handler.execute(self, ctx, target, can_speak)

    @commands.hybrid_command(aliases=["v"])
    @PermissionChecker.voice_command()
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
        await self.view_handler.execute(self, ctx, target, can_view)

    @commands.hybrid_command(aliases=["c"])
    @PermissionChecker.voice_command()
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
        await self.connect_handler.execute(
            self, ctx, target, can_connect
        )

    @commands.hybrid_command(aliases=["t"])
    @PermissionChecker.voice_command()
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
        await self.text_handler.execute(self, ctx, target, can_message)

    @commands.hybrid_command(aliases=["lv"])
    @PermissionChecker.voice_command()
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
        await self.live_handler.execute(self, ctx, target, can_stream)

    @commands.hybrid_command(aliases=["m"])
    @PermissionChecker.voice_command(requires_owner=True)
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
                ", ".join(
                    f"{member.mention} ({member.display_name})"
                    for member in current_mods
                )
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

        # Check if adding a mod would exceed the limit
        if can_manage == "+":
            voice_channel = ctx.author.voice.channel
            
            # Count current mods (members with manage_messages permission)
            current_mods = []
            for target_obj, overwrite in voice_channel.overwrites.items():
                if isinstance(target_obj, discord.Member):
                    if overwrite.manage_messages is True:
                        if not (overwrite.priority_speaker is True):
                            current_mods.append(target_obj)
            
            if len(current_mods) >= mod_limit:
                await self.message_sender.send_error(
                    ctx,
                    f"Osiągnięto limit moderatorów kanału ({mod_limit}/{mod_limit}).",
                )
                return

        await self.mod_handler.execute(self, ctx, target, can_manage)