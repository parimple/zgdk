from typing import Optional, Union
import discord
from discord.ext import commands

async def get_target_user(ctx: commands.Context, target: Optional[Union[discord.Member, str]] = None) -> Optional[discord.Member]:
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
        return None

    # Check if the target is a user ID
    if target.isdigit():
        user = ctx.guild.get_member(int(target))
        if user:
            return user

    # Check if the target is a mention
    if target.startswith('<@') and target.endswith('>'):
        user_id = target.strip('<@!>')
        if user_id.isdigit():
            user = ctx.guild.get_member(int(user_id))
            if user:
                return user

    # Check if the target is a username
    return discord.utils.get(ctx.guild.members, name=target)