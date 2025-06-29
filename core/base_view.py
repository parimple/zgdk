"""Base view class with service integration."""

import logging
from typing import Optional

import discord

from core.adapters.message_sender_adapter import MessageSenderAdapter
from core.interfaces.messaging_interfaces import IEmbedBuilder, IMessageSender


logger = logging.getLogger(__name__)


class ServiceView(discord.ui.View):
    """Base view class that provides easy access to services."""
    
    def __init__(self, bot, **kwargs):
        """Initialize the view with service support."""
        super().__init__(**kwargs)
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
        interaction: discord.Interaction,
        title: str,
        description: str,
        ephemeral: bool = True,
        **kwargs
    ) -> None:
        """Send a success message."""
        embed_builder = await self.get_embed_builder()
        message_service = await self.get_message_service()
        
        if embed_builder and message_service:
            embed = embed_builder.create_success_embed(title, description, **kwargs)
            await message_service.send_embed(interaction, embed, ephemeral=ephemeral)
        else:
            # Fallback to basic embed
            embed = discord.Embed(
                title=f"✅ {title}",
                description=description,
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
            
    async def send_error(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        ephemeral: bool = True,
        **kwargs
    ) -> None:
        """Send an error message."""
        embed_builder = await self.get_embed_builder()
        message_service = await self.get_message_service()
        
        if embed_builder and message_service:
            embed = embed_builder.create_error_embed(title, description, **kwargs)
            await message_service.send_embed(interaction, embed, ephemeral=ephemeral)
        else:
            # Fallback to basic embed
            embed = discord.Embed(
                title=f"❌ {title}",
                description=description,
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)
            
    async def send_info(
        self,
        interaction: discord.Interaction,
        title: str,
        description: str,
        ephemeral: bool = True,
        **kwargs
    ) -> None:
        """Send an info message."""
        embed_builder = await self.get_embed_builder()
        message_service = await self.get_message_service()
        
        if embed_builder and message_service:
            embed = embed_builder.create_info_embed(title, description, **kwargs)
            await message_service.send_embed(interaction, embed, ephemeral=ephemeral)
        else:
            # Fallback to basic embed
            embed = discord.Embed(
                title=f"ℹ️ {title}",
                description=description,
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=ephemeral)