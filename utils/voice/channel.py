"""Voice channel management utilities."""

import logging

import discord

from utils.message_sender import MessageSender
from utils.voice.permissions import VoicePermissionManager

logger = logging.getLogger(__name__)


class VoiceChannelManager:
    """Manages voice channel operations."""

    def __init__(self, bot) -> None:
        self.bot = bot
        self.message_sender = MessageSender()

    async def join_channel(self, ctx) -> None:
        """Joins the voice channel of the command author."""
        if ctx.author.voice is None:
            await self.message_sender.send_not_in_voice_channel(ctx)
            return

        channel = ctx.author.voice.channel

        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

        await self.message_sender.send_joined_channel(ctx, channel)

    async def set_channel_limit(self, ctx, max_members: int) -> None:
        """Sets the member limit for the current voice channel."""
        if ctx.author.voice is None:
            await self.message_sender.send_not_in_voice_channel(ctx)
            return

        if max_members > 99:
            max_members = 0  # Set to 0 for unlimited
        elif max_members < 1:
            max_members = 1  # Set to 1 as the minimum

        voice_channel = ctx.author.voice.channel
        await voice_channel.edit(user_limit=max_members)

        limit_text = "brak limitu" if max_members == 0 else str(max_members)
        await self.message_sender.send_member_limit_set(ctx, voice_channel, limit_text)

    async def get_channel_info(
        self, channel: discord.VoiceChannel, member: discord.Member
    ) -> dict[str, object]:
        """Get voice channel information including permissions and roles."""
        # Lista uprawnień do sprawdzenia
        permissions_to_check = {
            "connect": "połączenia",
            "speak": "mówienia",
            "stream": "streamowania",
            "view_channel": "widzenia kanału",
            "send_messages": "pisania",
        }

        # Sprawdź uprawnienia dla roli @everyone
        everyone_perms = channel.overwrites_for(channel.guild.default_role)

        # Zbierz wyłączone uprawnienia
        disabled_perms = []
        for perm_name, perm_display in permissions_to_check.items():
            if getattr(everyone_perms, perm_name) is False:
                disabled_perms.append(perm_display)

        # Znajdź właściciela i moderatorów kanału
        owner = None
        mods = []
        for member, overwrite in channel.overwrites.items():
            if not isinstance(member, discord.Member):
                continue
            if overwrite.priority_speaker:
                owner = member
            elif overwrite.manage_messages:
                mods.append(member)

        return {
            "channel": channel,
            "owner": owner,
            "mods": mods,
            "disabled_perms": disabled_perms,
        }


class ChannelModManager:
    """Manages channel moderators."""

    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = VoicePermissionManager(bot)
        self.message_sender = MessageSender()
        self.logger = logging.getLogger(__name__)

    async def show_mod_status(self, ctx, voice_channel, mod_limit) -> None:
        """Shows current mod status."""
        # Get current mods from channel overwrites only
        current_mods = [
            t
            for t, overwrite in voice_channel.overwrites.items()
            if isinstance(t, discord.Member)
            and overwrite.manage_messages
            is True  # Musi być dokładnie True (nie None ani False)
            and not (
                overwrite.priority_speaker is True and t == ctx.author
            )  # Wykluczamy tylko właściciela kanału
        ]

        current_mods_mentions = ", ".join(
            [member.mention for member in current_mods if member != ctx.author]
        )
        if not current_mods_mentions:
            current_mods_mentions = "brak"

        remaining_slots = max(0, mod_limit - len(current_mods))
        await self.message_sender.send_mod_info(
            ctx, current_mods_mentions, mod_limit, remaining_slots
        )

    async def check_prerequisites(self, ctx, target, can_manage):
        """Checks prerequisites for assigning channel mod."""
        author = ctx.author
        voice_channel = author.voice.channel if author.voice else None

        if not voice_channel:
            await self.message_sender.send_not_in_voice_channel(ctx)
            return False

        if not await self.permission_manager.can_assign_channel_mod(
            author, voice_channel
        ):
            await self.message_sender.send_no_mod_permission(ctx)
            return False

        if author == target and can_manage == "-":
            await self.message_sender.send_cant_remove_self_mod(ctx)
            return False

        return True

    async def can_add_mod(
        self, user: discord.Member, voice_channel: discord.VoiceChannel
    ) -> bool:
        """
        Check if user can add another moderator (limit not exceeded).

        Args:
            user: The user trying to add a moderator
            voice_channel: The voice channel to check

        Returns:
            bool: True if user can add another mod, False if limit reached
        """
        # Get user's mod limit from their highest premium role
        mod_limit = 0
        for role in reversed(self.bot.config["premium_roles"]):
            if any(r.name == role["name"] for r in user.roles):
                mod_limit = role["moderator_count"]
                self.logger.info("Found matching role: %s, limit: %d", role, mod_limit)
                break

        # Count current mods (excluding owner)
        current_mods = [
            t
            for t, overwrite in voice_channel.overwrites.items()
            if isinstance(t, discord.Member)
            and overwrite.manage_messages is True
            and not overwrite.priority_speaker
        ]

        return len(current_mods) < mod_limit

    async def validate_channel_mod(self, ctx, target, can_manage):
        """Validates prerequisites and mod limit for channel mod action."""
        if not await self.check_prerequisites(ctx, target, can_manage):
            return False

        # Nie sprawdzamy limitu przy usuwaniu moda
        if can_manage == "-":
            return True

        # Sprawdzamy limit tylko przy dodawaniu moda
        if not await self.can_add_mod(ctx.author, ctx.author.voice.channel):
            mod_limit = await self.permission_manager.get_premium_role_limit(ctx.author)
            logger.info(f"Mod limit exceeded. Current limit: {mod_limit}")
            return False

        return True

    async def get_mod_limit(self, ctx):
        """Get the mod limit for the user based on their roles."""
        premium_roles = self.bot.config["premium_roles"]
        member_roles = [role.name for role in ctx.author.roles]
        logger.info(f"Member roles: {member_roles}")

        # Sprawdź role od najwyższej do najniższej
        for role_config in reversed(premium_roles):
            if role_config["name"] in member_roles:
                logger.info(
                    f"Found matching role: {role_config}, limit: {role_config['moderator_count']}"
                )
                return role_config["moderator_count"]

        return 0
