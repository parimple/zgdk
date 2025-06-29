"""Voice channel management interfaces."""

from typing import List, Optional, Protocol

import discord


class IVoiceChannelService(Protocol):
    """Interface for voice channel management."""

    async def create_voice_channel(
        self,
        member: discord.Member,
        category: discord.CategoryChannel,
        name: Optional[str] = None,
    ) -> discord.VoiceChannel:
        """Create a new voice channel for a member."""
        ...

    async def delete_voice_channel(
        self, channel: discord.VoiceChannel, reason: str = "Channel cleanup"
    ) -> bool:
        """Delete a voice channel."""
        ...

    async def modify_channel_permissions(
        self,
        channel: discord.VoiceChannel,
        target: discord.Member,
        permission_type: str,
        action: str,
    ) -> bool:
        """Modify channel permissions for a user."""
        ...

    async def get_member_channels(
        self, member_id: int
    ) -> List[discord.VoiceChannel]:
        """Get all voice channels owned by a member."""
        ...


class IAutoKickService(Protocol):
    """Interface for auto-kick functionality."""

    async def add_autokick(
        self,
        channel_id: int,
        target_id: int,
        member_id: int,
    ) -> bool:
        """Add a user to auto-kick list."""
        ...

    async def remove_autokick(
        self,
        channel_id: int,
        target_id: int,
    ) -> bool:
        """Remove a user from auto-kick list."""
        ...

    async def check_autokick(
        self,
        channel: discord.VoiceChannel,
        member: discord.Member,
    ) -> bool:
        """Check if a member should be auto-kicked from channel."""
        ...

    async def get_autokick_list(
        self, channel_id: int
    ) -> List[int]:
        """Get list of auto-kicked users for a channel."""
        ...