"""Helper functions for using services in cogs."""

import logging
from typing import Optional, Tuple

from discord.ext import commands

from core.interfaces.messaging_interfaces import IEmbedBuilder, IMessageSender


logger = logging.getLogger(__name__)


async def get_messaging_services(
    bot: commands.Bot
) -> Tuple[Optional[IEmbedBuilder], Optional[IMessageSender]]:
    """Get embed builder and message sender services.
    
    Args:
        bot: The bot instance
        
    Returns:
        Tuple of (embed_builder, message_sender) or (None, None) if failed
    """
    try:
        async with bot.get_db() as session:
            embed_builder = await bot.get_service(IEmbedBuilder, session)
            message_sender = await bot.get_service(IMessageSender, session)
            return embed_builder, message_sender
    except Exception as e:
        logger.error(f"Failed to get messaging services: {e}")
        return None, None


async def send_success_message(
    bot: commands.Bot,
    ctx: commands.Context,
    title: str,
    description: str,
    fallback_sender=None
) -> None:
    """Send a success message using new services with fallback.
    
    Args:
        bot: The bot instance
        ctx: The command context
        title: The embed title
        description: The embed description
        fallback_sender: Fallback MessageSender instance
    """
    embed_builder, message_sender = await get_messaging_services(bot)
    
    if embed_builder and message_sender:
        embed = embed_builder.create_success_embed(title, description)
        await message_sender.send_embed(ctx, embed)
    elif fallback_sender:
        embed = fallback_sender._create_embed(
            title=title,
            description=description,
            color="success",
            ctx=ctx
        )
        await fallback_sender._send_embed(ctx, embed)
    else:
        # Last resort - plain message
        await ctx.send(f"✅ **{title}**\n{description}")


async def send_error_message(
    bot: commands.Bot,
    ctx: commands.Context,
    title: str,
    description: str,
    fallback_sender=None
) -> None:
    """Send an error message using new services with fallback.
    
    Args:
        bot: The bot instance
        ctx: The command context
        title: The embed title
        description: The embed description
        fallback_sender: Fallback MessageSender instance
    """
    embed_builder, message_sender = await get_messaging_services(bot)
    
    if embed_builder and message_sender:
        embed = embed_builder.create_error_embed(title, description)
        await message_sender.send_embed(ctx, embed)
    elif fallback_sender:
        embed = fallback_sender._create_embed(
            title=title,
            description=description,
            color="error",
            ctx=ctx
        )
        await fallback_sender._send_embed(ctx, embed)
    else:
        # Last resort - plain message
        await ctx.send(f"❌ **{title}**\n{description}")