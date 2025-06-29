"""Adapter to bridge old MessageSender utils to new MessageSenderService."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from core.interfaces.messaging_interfaces import IMessageSender
from utils.message_sender import MessageSender as OldMessageSender


class MessageSenderAdapter:
    """Adapter to help transition from old MessageSender to new service."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Keep old message sender for compatibility
        self._old_sender = OldMessageSender(bot)
        
    async def get_message_service(self) -> Optional[IMessageSender]:
        """Get the message sender service."""
        try:
            async with self.bot.get_db() as session:
                return await self.bot.get_service(IMessageSender, session)
        except Exception as e:
            self.logger.error(f"Failed to get message service: {e}")
            return None
    
    def __getattr__(self, name):
        """Delegate all method calls to the old sender for now."""
        # This allows gradual migration while maintaining compatibility
        return getattr(self._old_sender, name)
    
    async def send_embed(
        self,
        ctx: commands.Context,
        embed: discord.Embed,
        ephemeral: bool = False
    ) -> Optional[discord.Message]:
        """Send embed using new service when possible."""
        service = await self.get_message_service()
        
        if service:
            try:
                return await service.send_embed(ctx, embed, ephemeral=ephemeral)
            except Exception as e:
                self.logger.error(f"Failed to send with new service: {e}")
        
        # Fallback to old method
        return await ctx.send(embed=embed)
        
    async def send_message(
        self,
        ctx: commands.Context,
        content: str,
        ephemeral: bool = False
    ) -> Optional[discord.Message]:
        """Send message using new service when possible."""
        service = await self.get_message_service()
        
        if service:
            try:
                return await service.send_message(ctx, content, ephemeral=ephemeral)
            except Exception as e:
                self.logger.error(f"Failed to send with new service: {e}")
        
        # Fallback to old method
        return await ctx.send(content)