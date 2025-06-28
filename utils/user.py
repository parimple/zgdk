from typing import Literal, Optional, Tuple, Union

import discord
from discord.ext import commands


async def get_target_user(
    ctx: commands.Context, target: Optional[Union[discord.Member, str]] = None
) -> Optional[discord.Member]:
    """
    Attempts to find a user based on various input formats.

    :param ctx: The command context
    :param target: The target user input (can be None, Member object, ID, mention, or username)
    :return: discord.Member object if found, None otherwise
    """
    if isinstance(target, discord.Member):
        return target

    if target is None:
        if ctx.message.reference:
            # Check if the message is a reply
            return ctx.message.reference.resolved.author

        # Extract potential target from the second word in message content
        message_parts = ctx.message.content.split()
        if len(message_parts) > 1:
            potential_target = message_parts[1]  # Check the second word
            if potential_target in ["+", "-"]:
                return None

            if potential_target.isdigit():
                user = ctx.guild.get_member(int(potential_target))
                if user:
                    return user

            if potential_target.startswith("<@") and potential_target.endswith(">"):
                user_id = potential_target.strip("<@!>")
                if user_id.isdigit():
                    user = ctx.guild.get_member(int(user_id))
                    if user:
                        return user

            # Check if the potential target is a username
            user = discord.utils.get(ctx.guild.members, name=potential_target)
            if user:
                return user

        return None

    # Check if the target is a user ID
    if target.isdigit():
        user = ctx.guild.get_member(int(target))
        if user:
            return user

    # Check if the target is a mention
    if target.startswith("<@") and target.endswith(">"):
        user_id = target.strip("<@!>")
        if user_id.isdigit():
            user = ctx.guild.get_member(int(user_id))
            if user:
                return user

    # Check if the target is a username
    return discord.utils.get(ctx.guild.members, name=target)


async def get_target_and_permission(
    ctx: commands.Context,
    target: Optional[Union[discord.Member, str]] = None,
    permission: Optional[Literal["+", "-"]] = None,
) -> Tuple[Union[discord.Member, discord.Role], Optional[Literal["+", "-"]]]:
    """
    Get the target member or @everyone role and parse the permission.

    :param ctx: The command context
    :param target: The target user input or permission
    :param permission: The permission value
    :return: Tuple of (target_member_or_role, permission)
    """
    # Sprawdź, czy target to Member z display_name "+" lub "-"
    if isinstance(target, discord.Member) and target.display_name in ["+", "-"]:
        permission = target.display_name
        target = None

    # Jeśli target to string "+" lub "-", a permission jest None, zamień je miejscami
    if isinstance(target, str) and target in ["+", "-"] and permission is None:
        permission = target
        target = None

    # Jeśli target jest None lub jest stringiem "+" lub "-", użyj @everyone
    if target is None or (isinstance(target, str) and target in ["+", "-"]):
        return ctx.guild.default_role, permission or target

    # W przeciwnym razie, użyj get_target_user do znalezienia użytkownika
    if isinstance(target, str):
        target_member = await get_target_user(ctx, target)
    else:
        target_member = target

    # Jeśli nie znaleziono użytkownika, użyj @everyone
    if target_member is None:
        return ctx.guild.default_role, permission

    return target_member, permission


class TargetHelper:
    """Helper class for handling user targets and permissions."""

    def __init__(self, bot):
        self.bot = bot

    async def get_target(self, ctx, target_arg):
        """Get target member from command argument."""
        if isinstance(target_arg, discord.Member):
            return target_arg

        try:
            # Try to get member by ID
            member_id = int("".join(filter(str.isdigit, target_arg)))
            return ctx.guild.get_member(member_id)
        except (ValueError, TypeError):
            # If not ID, try to find member by name
            return discord.utils.get(ctx.guild.members, name=target_arg)

    async def get_voice_channel_info(self, member):
        """Get voice channel information for a member."""
        if not member.voice or not member.voice.channel:
            return None

        channel = member.voice.channel
        return {
            "name": channel.name,
            "id": channel.id,
            "mention": channel.mention,
            "member_count": len(channel.members),
        }
