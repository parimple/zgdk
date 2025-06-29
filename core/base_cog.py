"""Base cog class with service integration."""

import logging
from typing import Optional

from discord.ext import commands

from core.adapters.message_sender_adapter import MessageSenderAdapter
from core.interfaces.messaging_interfaces import IEmbedBuilder, IMessageSender


logger = logging.getLogger(__name__)


class ServiceCog(commands.Cog):
    """Base cog class that provides easy access to services."""
    
    def __init__(self, bot: commands.Bot):
        """Initialize the cog with service support."""
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Use adapter for gradual migration
        self.message_sender = MessageSenderAdapter(bot)
        
        # Cache for services
        self._embed_builder: Optional[IEmbedBuilder] = None
        self._message_service: Optional[IMessageSender] = None
        
    async def get_embed_builder(self) -> Optional[IEmbedBuilder]:
        """Get embed builder service with caching."""
        if self._embed_builder is None:
            try:
                async with self.bot.get_db() as session:
                    self._embed_builder = await self.bot.get_service(IEmbedBuilder, session)
            except Exception as e:
                self.logger.error(f"Failed to get embed builder: {e}")
        return self._embed_builder
        
    async def get_message_service(self) -> Optional[IMessageSender]:
        """Get message sender service with caching."""
        if self._message_service is None:
            try:
                async with self.bot.get_db() as session:
                    self._message_service = await self.bot.get_service(IMessageSender, session)
            except Exception as e:
                self.logger.error(f"Failed to get message service: {e}")
        return self._message_service
        
    async def send_success(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
        **kwargs
    ) -> None:
        """Send a success message."""
        embed_builder = await self.get_embed_builder()
        message_service = await self.get_message_service()
        
        if embed_builder and message_service:
            embed = embed_builder.create_success_embed(title, description, **kwargs)
            await message_service.send_embed(ctx, embed)
        else:
            # Fallback to adapter
            await self.message_sender.send_success(ctx, title, description, **kwargs)
            
    async def send_error(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
        **kwargs
    ) -> None:
        """Send an error message."""
        embed_builder = await self.get_embed_builder()
        message_service = await self.get_message_service()
        
        if embed_builder and message_service:
            embed = embed_builder.create_error_embed(title, description, **kwargs)
            await message_service.send_embed(ctx, embed)
        else:
            # Fallback to adapter
            await self.message_sender.send_error(ctx, title, description, **kwargs)
            
    async def send_info(
        self,
        ctx: commands.Context,
        title: str,
        description: str,
        **kwargs
    ) -> None:
        """Send an info message."""
        embed_builder = await self.get_embed_builder()
        message_service = await self.get_message_service()
        
        if embed_builder and message_service:
            embed = embed_builder.create_info_embed(title, description, **kwargs)
            await message_service.send_embed(ctx, embed)
        else:
            # Fallback to adapter
            await self.message_sender.send_info(ctx, title, description, **kwargs)