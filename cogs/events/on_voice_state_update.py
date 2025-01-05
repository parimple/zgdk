import logging
import random

import discord
from discord.ext import commands
from sqlalchemy.sql import select

from datasources.models import AutoKick
from datasources.queries import AutoKickQueries, ChannelPermissionQueries

logger = logging.getLogger(__name__)


class OnVoiceStateUpdateEvent(commands.Cog):
    """Class for handling the event when a member's voice state is updated."""

    def __init__(self, bot):
        self.bot = bot
        self.guild = bot.get_guild(self.bot.config["guild_id"])
        self.logger = logging.getLogger(__name__)
        # Cache structure: {target_id: set(owner_ids)}
        self._autokick_cache = {}
        self._cache_initialized = False

        # Adjusting for new config structure
        self.mute_roles = {
            role["description"]: self.guild.get_role(role["id"])
            for role in self.bot.config["mute_roles"]
        }

        self.channels_create = self.bot.config["channels_create"]
        self.vc_categories = self.bot.config["vc_categories"]

    async def _initialize_cache(self):
        """Initialize the cache with data from database"""
        if self._cache_initialized:
            return

        async with self.bot.get_db() as session:
            # Get all autokicks using SQLAlchemy ORM
            result = await session.execute(select(AutoKick.target_id, AutoKick.owner_id))
            rows = result.all()

            # Build the cache
            for target_id, owner_id in rows:
                if target_id not in self._autokick_cache:
                    self._autokick_cache[target_id] = set()
                self._autokick_cache[target_id].add(owner_id)

        self._cache_initialized = True

    async def check_autokick(self, member: discord.Member, channel: discord.VoiceChannel) -> bool:
        """Check if a member should be autokicked from a channel."""
        await self._initialize_cache()

        if member.id not in self._autokick_cache:
            return False

        # Check if any channel members have autokick on this member
        for owner_id in self._autokick_cache[member.id]:
            owner = channel.guild.get_member(owner_id)
            if owner and owner in channel.members:
                return True

        return False

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle the event when a member joins or leaves a voice channel."""
        # Check for autokicks when a member joins a voice channel
        if after.channel and before.channel != after.channel:
            if member.id != self.bot.config["owner_id"]:
                await self.handle_autokicks(member, after.channel)

            if after.channel and after.channel.id in self.channels_create:
                await self.handle_create_channel(member, after)
            elif after.channel and after.channel.id == self.bot.config["channels_voice"]["afk"]:
                return

        if (
            before.channel
            and before.channel != after.channel
            and before.channel.type == discord.ChannelType.voice
            and len(before.channel.members) == 0
        ):
            await self.handle_channel_leave(before)

    async def handle_autokicks(self, member, channel):
        """Handle autokicks for a member joining a voice channel"""
        if channel.id == self.bot.config["channels_voice"]["afk"]:
            return

        # Check if member should be autokicked using cached data
        if await self.check_autokick(member, channel):
            try:
                # Kick the member
                await member.move_to(None)

                # Set connect permission to False
                current_perms = channel.overwrites_for(member) or discord.PermissionOverwrite()
                current_perms.connect = False
                await channel.set_permissions(member, overwrite=current_perms)

                # Send message in the voice channel chat
                premium_channel = self.bot.config["channels"]["premium_info"]
                await channel.send(
                    f"{member.mention} został automatycznie wyrzucony z kanału głosowego, "
                    f"ponieważ znajduje się na czyjejś liście autokick.\n"
                    f"Podobną funkcjonalność możesz kupić na kanale <#{premium_channel}>"
                )
            except discord.Forbidden:
                self.logger.warning(f"Failed to autokick {member.id} (no permission)")
            except Exception as e:
                self.logger.error(f"Failed to autokick {member.id}: {str(e)}")

    async def add_remaining_overwrites(self, channel, remaining_overwrites):
        """Add remaining overwrites to the channel."""
        for target, overwrite in remaining_overwrites.items():
            try:
                await channel.set_permissions(target, overwrite=overwrite)
            except discord.errors.NotFound:
                return

    async def add_db_overwrites_to_permissions(self, member_id, permission_overwrites):
        """Fetch permissions from the database and add them to the provided permission_overwrites dict."""
        remaining_overwrites = {}
        async with self.bot.get_db() as session:
            member_permissions = await ChannelPermissionQueries.get_permissions_for_member(
                session, member_id, limit=95
            )

        for permission in member_permissions:
            allow_permissions = discord.Permissions(permission.allow_permissions_value)
            deny_permissions = discord.Permissions(permission.deny_permissions_value)
            overwrite = discord.PermissionOverwrite.from_pair(allow_permissions, deny_permissions)

            # Konwertuj target_id na odpowiedni obiekt Discord
            target = self.guild.get_member(permission.target_id) or self.guild.get_role(
                permission.target_id
            )
            if target:
                if target in permission_overwrites:
                    # Jeśli target już jest w głównych uprawnieniach, dodaj do nich nowe uprawnienia
                    for key, value in overwrite._values.items():
                        if value is not None:
                            setattr(permission_overwrites[target], key, value)
                else:
                    # Jeśli targetu nie ma w głównych uprawnieniach, dodaj do pozostałych
                    remaining_overwrites[target] = overwrite

        return remaining_overwrites

    async def handle_create_channel(self, member, after):
        """
        Handle the creation of a new voice channel when a member joins a creation channel.

        :param member: Member object representing the joining member
        :param after: VoiceState object representing the state after the update
        """
        # Determine channel name based on category
        channel_name = member.display_name
        category_id = after.channel.category.id if after.channel.category else None

        logger.info(f"Creating channel in category: {category_id}")
        logger.info(f"Available formats: {self.bot.config.get('channel_name_formats', {}).keys()}")

        # Check if category has a custom format
        formats = self.bot.config.get("channel_name_formats", {})
        format_key = category_id  # próbuj najpierw jako int
        if format_key not in formats:
            format_key = str(category_id)  # spróbuj jako string

        if format_key in formats:
            # Get random emoji
            emoji = random.choice(self.bot.config.get("channel_emojis", ["🎮"]))
            # Apply the format
            channel_name = formats[format_key].format(emoji=emoji)
            logger.info(f"Using format for category {category_id}: {channel_name}")
        else:
            logger.info(
                f"No format found for category {category_id}, using default name: {channel_name}"
            )

        permission_overwrites = {
            self.mute_roles["stream_off"]: discord.PermissionOverwrite(stream=False),
            self.mute_roles["send_messages_off"]: discord.PermissionOverwrite(send_messages=False),
            self.mute_roles["attach_files_off"]: discord.PermissionOverwrite(
                attach_files=False, embed_links=False, external_emojis=False
            ),
            member: discord.PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                priority_speaker=True,
                manage_messages=True,
            ),
        }

        # Add permissions from database, if applicable
        remaining_overwrites = await self.add_db_overwrites_to_permissions(
            member.id, permission_overwrites
        )

        # Create the new channel
        new_channel = await self.guild.create_voice_channel(
            channel_name,
            category=after.channel.category,
            bitrate=self.guild.bitrate_limit,
            user_limit=after.channel.user_limit,
            overwrites=permission_overwrites,
        )

        # Add any remaining overwrites
        if remaining_overwrites:
            await self.add_remaining_overwrites(new_channel, remaining_overwrites)

        await member.move_to(new_channel)

    async def handle_channel_leave(self, before):
        """
        Handle the deletion of a voice channel when all members leave.

        :param before: VoiceState object representing the state before the update
        """
        # Nie usuwamy kanałów create ani AFK
        if (
            before.channel.id in self.channels_create
            or before.channel.id == self.bot.config["channels_voice"]["afk"]
        ):
            return

        # Usuwamy tylko kanały w kategoriach głosowych
        if before.channel.category and before.channel.category.id in self.vc_categories:
            await before.channel.delete()


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnVoiceStateUpdateEvent(bot))
