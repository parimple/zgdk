"""Adapter for bump handlers to use new services."""

import logging
from typing import Optional

import discord

from core.adapters.message_sender_adapter import MessageSenderAdapter


class BumpHandlerAdapter:
    """Base adapter for bump handlers with service integration."""
    
    def __init__(self, bot, message_sender=None):
        """Initialize with bot and optional message sender."""
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Use MessageSenderAdapter for gradual migration
        if message_sender is None:
            self.message_sender = MessageSenderAdapter(bot)
        else:
            self.message_sender = message_sender
            
    async def send_bump_notification(
        self,
        channel: discord.TextChannel,
        user: discord.Member,
        service_name: str,
        bypass_hours: int,
        cooldown_info: Optional[str] = None
    ) -> None:
        """Send bump notification with service integration."""
        # Build message content
        content = f"🎉 **{user.mention}** właśnie zbumpował serwer na **{service_name}**!"
        
        if bypass_hours > 0:
            content += f"\n⏰ Otrzymujesz **{bypass_hours}h** czasu bypass!"
            
        if cooldown_info:
            content += f"\n{cooldown_info}"
            
        try:
            # Try to use embed with new services
            embed_builder = None
            message_service = None
            
            try:
                async with self.bot.get_db() as session:
                    from core.interfaces.messaging_interfaces import IEmbedBuilder, IMessageSender
                    embed_builder = await self.bot.get_service(IEmbedBuilder, session)
                    message_service = await self.bot.get_service(IMessageSender, session)
            except Exception as e:
                self.logger.debug(f"Could not get services: {e}")
                
            if embed_builder and message_service:
                embed = embed_builder.create_success_embed(
                    title="Bump wykonany!",
                    description=content
                )
                await message_service.send_embed(channel, embed)
            else:
                # Fallback to simple message
                await channel.send(content)
                
        except Exception as e:
            self.logger.error(f"Error sending bump notification: {e}")
            # Last resort fallback
            try:
                await channel.send(content)
            except:
                pass