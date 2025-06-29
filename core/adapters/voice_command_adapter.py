"""Adapter for voice commands to use new services."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from core.interfaces.voice_interfaces import IVoiceChannelService, IAutoKickService
from core.adapters.voice_channel_adapter import VoiceChannelAdapter


class VoiceCommandAdapter:
    """Adapter to help voice commands transition to new services."""
    
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)
        self.channel_adapter = VoiceChannelAdapter(bot)
        
    async def autokick(self, ctx: commands.Context, target: discord.Member, action: str) -> bool:
        """Handle autokick command using new services."""
        if not ctx.author.voice or not ctx.author.voice.channel:
            return False
            
        channel = ctx.author.voice.channel
        
        if action == "+":
            return await self.channel_adapter.add_autokick(
                channel.id,
                target.id,
                ctx.author.id
            )
        elif action == "-":
            return await self.channel_adapter.remove_autokick(
                channel.id,
                target.id
            )
        
        return False
        
    async def get_autokick_list(self, channel_id: int) -> list[int]:
        """Get autokick list for a channel."""
        service = await self.channel_adapter.get_autokick_service()
        
        if service:
            try:
                return await service.get_autokick_list(channel_id)
            except Exception as e:
                self.logger.error(f"Failed to get autokick list: {e}")
        
        return []
        
    async def modify_permissions(
        self,
        channel: discord.VoiceChannel,
        target: discord.Member,
        permission_type: str,
        action: str
    ) -> bool:
        """Modify channel permissions using new services."""
        service = await self.channel_adapter.get_voice_service()
        
        if service:
            try:
                return await service.modify_channel_permissions(
                    channel,
                    target,
                    permission_type,
                    action
                )
            except Exception as e:
                self.logger.error(f"Failed to modify permissions: {e}")
        
        return False
        
    async def get_member_channels(self, member_id: int) -> list[discord.VoiceChannel]:
        """Get all voice channels owned by a member."""
        service = await self.channel_adapter.get_voice_service()
        
        if service:
            try:
                return await service.get_member_channels(member_id)
            except Exception as e:
                self.logger.error(f"Failed to get member channels: {e}")
        
        return []