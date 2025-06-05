"""Voice commands cog for managing voice channel permissions and operations."""

import logging
from typing import Literal, Optional

import discord
from discord import Member
from discord.ext import commands

from utils.message_sender import MessageSender
from utils.premium_checker import PremiumChecker
from utils.services.voice_service import VoiceService

logger = logging.getLogger(__name__)


class VoiceCogRefactored(commands.Cog):
    """Voice commands cog for managing voice channel permissions and operations."""

    def __init__(self, bot):
        """Initialize the voice cog."""
        self.bot = bot
        self.voice_service = VoiceService(bot)
        self.message_sender = MessageSender()
        self.premium_checker = PremiumChecker(bot)
        self.logger = logging.getLogger(__name__)

    def voice_command(requires_owner: bool = False):
        """
        Decorator for voice commands that enforces channel permission requirements.

        Args:
            requires_owner (bool): If True, only channel owner (priority_speaker) can use the command.
                                If False, both owner and mod can use the command.
        """
        async def predicate(ctx):
            # Skip checks for help command and help context
            if ctx.command.name in ["help", "pomoc"] or ctx.invoked_with in ["help", "pomoc"]:
                return True

            # Check if user is in voice channel
            if not ctx.author.voice:
                await ctx.cog.message_sender.send_not_in_voice_channel(ctx)
                return False

            # Check permission level
            success, _, permission_level = await ctx.cog.voice_service.get_permission_level(ctx)
            if not success:
                await ctx.cog.message_sender.send_not_in_voice_channel(ctx)
                return False

            if requires_owner and permission_level != "owner":
                await ctx.cog.message_sender.send_no_permission(
                    ctx, "tej komendy (wymagany właściciel kanału)!"
                )
                return False
            elif permission_level == "none":
                await ctx.cog.message_sender.send_no_permission(ctx, "zarządzania tym kanałem!")
                return False

            return True

        return commands.check(predicate)

    async def _parse_target_and_value(self, ctx, target, permission_value):
        """Parse target and permission value from command arguments."""
        # For text commands, parse from message content
        if not ctx.interaction:  # Text command
            message_parts = ctx.message.content.split()

            if len(message_parts) > 1:
                second_arg = message_parts[1]

                # Handle +/- with or without target
                if second_arg in ["+", "-"]:
                    if len(message_parts) == 2:
                        return ctx.guild.default_role, second_arg
                    else:
                        mention = message_parts[2]
                        if mention.startswith("<@") and not mention.startswith("<@&"):
                            user_id = "".join(filter(str.isdigit, mention))
                            target = ctx.guild.get_member(int(user_id)) if user_id else None
                        elif mention.isdigit():  # Handle raw user ID
                            target = ctx.guild.get_member(int(mention))
                        else:
                            target = ctx.guild.default_role
                        return target, second_arg

                # Handle target with optional +/-
                elif second_arg.startswith("<@") and not second_arg.startswith("<@&"):
                    user_id = "".join(filter(str.isdigit, second_arg))
                    target = ctx.guild.get_member(int(user_id)) if user_id else None
                    permission_value = (
                        message_parts[2]
                        if len(message_parts) > 2 and message_parts[2] in ["+", "-"]
                        else None
                    )
                    return target, permission_value
                elif second_arg.isdigit():  # Handle raw user ID
                    target = ctx.guild.get_member(int(second_arg))
                    permission_value = (
                        message_parts[2]
                        if len(message_parts) > 2 and message_parts[2] in ["+", "-"]
                        else None
                    )
                    return target, permission_value

            # Default to @everyone toggle
            return ctx.guild.default_role, None

        # Slash command - arguments already properly parsed
        return target, permission_value

    @commands.command(name="speak", aliases=["s"])
    @voice_command(requires_owner=False)
    async def speak(self, ctx, target: Optional[Member] = None, value: Optional[Literal["+", "-"]] = None):
        """
        Manage speak permission for users in your voice channel.

        Examples:
        - speak @user + (give permission)
        - speak @user - (deny permission)
        - speak @user (toggle permission)
        - speak + (give permission to @everyone)
        - speak - (deny permission to @everyone)
        """
        target, value = await self._parse_target_and_value(ctx, target, value)
        
        if not target:
            await self.message_sender.send_invalid_target(ctx)
            return
        
        success, message = await self.voice_service.modify_permission(
            ctx, target, "speak", value, toggle=True
        )
        
        if success:
            await self.message_sender.send_success(ctx, description=message)
        else:
            await self.message_sender.send_error(ctx, description=message)

    @commands.command(name="view", aliases=["v"])
    @voice_command(requires_owner=False)
    async def view(self, ctx, target: Optional[Member] = None, value: Optional[Literal["+", "-"]] = None):
        """
        Manage view permission for users in your voice channel.

        Examples:
        - view @user + (give permission)
        - view @user - (deny permission)
        - view @user (toggle permission)
        - view + (give permission to @everyone)
        - view - (deny permission to @everyone)
        """
        target, value = await self._parse_target_and_value(ctx, target, value)
        
        if not target:
            await self.message_sender.send_invalid_target(ctx)
            return
        
        success, message = await self.voice_service.modify_permission(
            ctx, target, "view_channel", value, toggle=True
        )
        
        if success:
            await self.message_sender.send_success(ctx, description=message)
        else:
            await self.message_sender.send_error(ctx, description=message)

    @commands.command(name="connect", aliases=["c"])
    @voice_command(requires_owner=False)
    async def connect(self, ctx, target: Optional[Member] = None, value: Optional[Literal["+", "-"]] = None):
        """
        Manage connect permission for users in your voice channel.

        Examples:
        - connect @user + (give permission)
        - connect @user - (deny permission)
        - connect @user (toggle permission)
        - connect + (give permission to @everyone)
        - connect - (deny permission to @everyone)
        """
        target, value = await self._parse_target_and_value(ctx, target, value)
        
        if not target:
            await self.message_sender.send_invalid_target(ctx)
            return
        
        success, message = await self.voice_service.modify_permission(
            ctx, target, "connect", value, toggle=True
        )
        
        if success:
            await self.message_sender.send_success(ctx, description=message)
        else:
            await self.message_sender.send_error(ctx, description=message)

    @commands.command(name="text", aliases=["t"])
    @voice_command(requires_owner=False)
    async def text(self, ctx, target: Optional[Member] = None, value: Optional[Literal["+", "-"]] = None):
        """
        Manage text permission for users in your voice channel.

        Examples:
        - text @user + (give permission)
        - text @user - (deny permission)
        - text @user (toggle permission)
        - text + (give permission to @everyone)
        - text - (deny permission to @everyone)
        """
        target, value = await self._parse_target_and_value(ctx, target, value)
        
        if not target:
            await self.message_sender.send_invalid_target(ctx)
            return
        
        success, message = await self.voice_service.modify_permission(
            ctx, target, "send_messages", value, toggle=True
        )
        
        if success:
            await self.message_sender.send_success(ctx, description=message)
        else:
            await self.message_sender.send_error(ctx, description=message)

    @commands.command(name="live", aliases=["lv"])
    @voice_command(requires_owner=False)
    async def live(self, ctx, target: Optional[Member] = None, value: Optional[Literal["+", "-"]] = None):
        """
        Manage stream permission for users in your voice channel.

        Examples:
        - live @user + (give permission)
        - live @user - (deny permission)
        - live @user (toggle permission)
        - live + (give permission to @everyone)
        - live - (deny permission to @everyone)
        """
        target, value = await self._parse_target_and_value(ctx, target, value)
        
        if not target:
            await self.message_sender.send_invalid_target(ctx)
            return
        
        success, message = await self.voice_service.modify_permission(
            ctx, target, "stream", value, toggle=True
        )
        
        if success:
            await self.message_sender.send_success(ctx, description=message)
        else:
            await self.message_sender.send_error(ctx, description=message)

    @commands.command(name="mod", aliases=["m"])
    @voice_command(requires_owner=True)
    async def mod(self, ctx, target: Optional[Member] = None, value: Optional[Literal["+", "-"]] = None):
        """
        Manage moderator permission for users in your voice channel.
        Only the channel owner can use this command.

        Examples:
        - mod @user + (give permission)
        - mod @user - (deny permission)
        - mod @user (toggle permission)
        """
        target, value = await self._parse_target_and_value(ctx, target, value)
        
        if not target:
            await self.message_sender.send_invalid_target(ctx)
            return
        
        # Check if target is a Member (not a Role)
        if not isinstance(target, Member):
            await self.message_sender.send_error(ctx, description="You can only make members moderators, not roles.")
            return
        
        success, message = await self.voice_service.modify_permission(
            ctx, target, "manage_messages", value, toggle=True, default_to_true=True
        )
        
        if success:
            await self.message_sender.send_success(ctx, description=message)
        else:
            await self.message_sender.send_error(ctx, description=message)

    @commands.command(name="limit", aliases=["l"])
    @voice_command(requires_owner=False)
    async def limit(self, ctx, max_members: int = 0):
        """
        Set the member limit for your voice channel.
        
        Args:
            max_members: The maximum number of members (0 for unlimited)
        """
        success, message = await self.voice_service.set_channel_limit(ctx, max_members)
        
        if success:
            limit_text = "unlimited" if max_members == 0 else str(max_members)
            await self.message_sender.send_member_limit_set(ctx, ctx.author.voice.channel, limit_text)
        else:
            await self.message_sender.send_error(ctx, description=message)

    @commands.command(name="reset", aliases=["r"])
    @voice_command(requires_owner=True)
    async def reset(self, ctx, target: Optional[Member] = None):
        """
        Reset permissions for your voice channel or a specific user.
        Only the channel owner can use this command.
        
        Args:
            target: The target member to reset permissions for
        """
        if target:
            success, message = await self.voice_service.reset_user_permissions(ctx, target)
            
            if success:
                await self.message_sender.send_success(
                    ctx, description=f"Reset permissions for {target.display_name}"
                )
            else:
                await self.message_sender.send_error(ctx, description=message)
        else:
            success, message = await self.voice_service.reset_channel_permissions(ctx)
            
            if success:
                await self.message_sender.send_success(
                    ctx, description="Reset all permissions for this channel"
                )
            else:
                await self.message_sender.send_error(ctx, description=message)

    @commands.command(name="autokick", aliases=["ak"])
    @voice_command(requires_owner=False)
    async def autokick(self, ctx, target: Optional[Member] = None, value: Optional[Literal["+", "-"]] = None):
        """
        Manage autokick list for your voice channel.
        
        Args:
            target: The target member to add/remove from autokick list
            value: "+" to add, "-" to remove
        """
        # List autokicks if no target is specified
        if not target:
            success, message, target_ids = await self.voice_service.get_autokicks(ctx)
            
            if success and target_ids:
                members = []
                for target_id in target_ids:
                    member = ctx.guild.get_member(target_id)
                    if member:
                        members.append(member.mention)
                
                if members:
                    await self.message_sender.send_info(
                        ctx,
                        title="Autokick List",
                        description=f"You have {len(members)} users in your autokick list:\n" + "\n".join(members),
                    )
                else:
                    await self.message_sender.send_info(
                        ctx,
                        title="Autokick List",
                        description="Your autokick list is empty",
                    )
            else:
                await self.message_sender.send_info(
                    ctx,
                    title="Autokick List",
                    description="Your autokick list is empty",
                )
            
            return
        
        # Default to adding if no value is specified
        value = value or "+"
        
        if value == "+":
            success, message = await self.voice_service.add_autokick(ctx, target)
            
            if success:
                await self.message_sender.send_success(
                    ctx, description=f"Added {target.display_name} to your autokick list"
                )
            else:
                await self.message_sender.send_error(ctx, description=message)
        else:
            success, message = await self.voice_service.remove_autokick(ctx, target)
            
            if success:
                await self.message_sender.send_success(
                    ctx, description=f"Removed {target.display_name} from your autokick list"
                )
            else:
                await self.message_sender.send_error(ctx, description=message)


async def setup(bot: commands.Bot):
    """Setup function for VoiceCogRefactored."""
    await bot.add_cog(VoiceCogRefactored(bot))