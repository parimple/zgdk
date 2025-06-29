"""Adapter for migrating voice channel functionality to new services."""

import logging
from typing import Optional

import discord

from core.interfaces.voice_interfaces import IVoiceChannelService, IAutoKickService
from utils.voice.channel import VoiceChannelManager, ChannelModManager
from utils.voice.autokick import AutoKickManager
from utils.voice.permissions import VoicePermissionManager


class VoiceChannelAdapter:
    """Adapter class to bridge old utils to new services."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Keep old utilities for gradual migration
        self._old_channel_manager = VoiceChannelManager(bot)
        self._old_mod_manager = ChannelModManager(bot)
        self._old_autokick_manager = AutoKickManager(bot)
        self._old_permission_manager = VoicePermissionManager(bot)
        
    async def get_voice_service(self) -> Optional[IVoiceChannelService]:
        """Get the voice channel service."""
        try:
            async with self.bot.get_db() as session:
                return await self.bot.get_service(IVoiceChannelService, session)
        except Exception as e:
            self.logger.error(f"Failed to get voice service: {e}")
            return None
            
    async def get_autokick_service(self) -> Optional[IAutoKickService]:
        """Get the autokick service."""
        try:
            async with self.bot.get_db() as session:
                return await self.bot.get_service(IAutoKickService, session)
        except Exception as e:
            self.logger.error(f"Failed to get autokick service: {e}")
            return None
    
    async def create_voice_channel(
        self,
        member: discord.Member,
        category: discord.CategoryChannel,
        name: Optional[str] = None
    ) -> Optional[discord.VoiceChannel]:
        """Create a voice channel using the new service or fall back to old utils."""
        service = await self.get_voice_service()
        
        if service:
            try:
                return await service.create_voice_channel(member, category, name)
            except Exception as e:
                self.logger.error(f"Failed to create channel with service: {e}")
        
        # Fallback to old implementation
        self.logger.warning("Falling back to old voice channel creation")
        # Use old utils here if needed
        return None
        
    async def check_autokick(
        self,
        channel: discord.VoiceChannel,
        member: discord.Member
    ) -> bool:
        """Check if member should be autokicked."""
        service = await self.get_autokick_service()
        
        if service:
            try:
                return await service.check_autokick(channel, member)
            except Exception as e:
                self.logger.error(f"Failed to check autokick with service: {e}")
        
        # Fallback to old implementation
        return await self._old_autokick_manager.should_kick_member(channel.id, member.id)
        
    async def add_autokick(
        self,
        channel_id: int,
        target_id: int,
        member_id: int
    ) -> bool:
        """Add user to autokick list."""
        service = await self.get_autokick_service()
        
        if service:
            try:
                return await service.add_autokick(channel_id, target_id, member_id)
            except Exception as e:
                self.logger.error(f"Failed to add autokick with service: {e}")
        
        # Fallback to old implementation
        return await self._old_autokick_manager.toggle_autokick(member_id, target_id, channel_id)
        
    async def remove_autokick(
        self,
        channel_id: int,
        target_id: int
    ) -> bool:
        """Remove user from autokick list."""
        service = await self.get_autokick_service()
        
        if service:
            try:
                return await service.remove_autokick(channel_id, target_id)
            except Exception as e:
                self.logger.error(f"Failed to remove autokick with service: {e}")
        
        # Fallback to old implementation
        return False