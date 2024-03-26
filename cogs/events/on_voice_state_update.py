import logging
from random import choice

import discord
from discord.ext import commands

from datasources.queries import ChannelPermissionQueries

logger = logging.getLogger(__name__)


class OnVoiceStateUpdateEvent(commands.Cog):
    """Class for handling the event when a member's voice state is updated."""

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.guild = bot.get_guild(self.bot.config["guild_id"])
        self.stream_off = self.guild.get_role(self.bot.config["roles"]["stream_off"])
        self.send_messages_off = self.guild.get_role(self.bot.config["roles"]["send_messages_off"])
        self.attach_files_off = self.guild.get_role(self.bot.config["roles"]["attach_files_off"])
        self.channels_create = self.bot.config["channels_create"]

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle the event when a member joins or leaves a voice channel."""
        if member.id != self.bot.config["owner_id"]:
            return
        if after.channel and before.channel != after.channel:
            if after.channel.id in self.channels_create:
                await self.handle_create_channel(member, after)
            elif after.channel.id == self.bot.config["channels_voice"]["afk"]:
                return
        if (
            before.channel
            and before.channel != after.channel
            and before.channel.type == discord.ChannelType.voice
            and len(before.channel.members) == 0
        ):
            await self.handle_channel_leave(before)

    async def add_remaining_overwrites(self, channel, remaining_overwrites):
        """Add remaining overwrites to the channel."""
        for target, overwrite in remaining_overwrites.items():
            try:
                await channel.set_permissions(target, overwrite=overwrite)
            except discord.errors.NotFound:
                return

    async def add_db_overwrites_to_permissions(self, member_id, permission_overwrites):
        """Fetch permissions from the database
        and add them to the provided permission_overwrites dict."""
        member_permissions = await ChannelPermissionQueries.get_permissions_for_member(
            self.session, member_id
        )
        db_overwrites = {}
        for permission in member_permissions:
            overwrite = discord.PermissionOverwrite.from_pair(
                permission.permissions_value, discord.Permissions(0)
            )
            db_overwrites[permission.target_id] = overwrite

        if len(db_overwrites) > 95:
            first_95_overwrites = {k: db_overwrites[k] for k in list(db_overwrites.keys())[:95]}
            remaining_overwrites = {k: db_overwrites[k] for k in list(db_overwrites.keys())[95:]}
            permission_overwrites.update(first_95_overwrites)
            return remaining_overwrites
        else:
            permission_overwrites.update(db_overwrites)
            return None

    async def handle_create_channel(self, member, after):
        """
        Handle the creation of a new voice channel when a member joins a creation channel.

        :param member: Member object representing the joining member
        :param after: VoiceState object representing the state after the update
        """
        channel_name = member.display_name
        permission_overwrites = {
            self.stream_off: discord.PermissionOverwrite(stream=False),
            self.send_messages_off: discord.PermissionOverwrite(send_messages=False),
            self.attach_files_off: discord.PermissionOverwrite(
                attach_files=False, embed_links=False, external_emojis=False
            ),
            member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
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
        if (
            before.channel.id in self.channels_create
            or before.channel.id == self.bot.config["channels_voice"]["afk"]
        ):
            return
        await before.channel.delete()


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnVoiceStateUpdateEvent(bot))
