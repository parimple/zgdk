"""Interfaces for messaging and notification system."""

from abc import ABC, abstractmethod
from typing import Any, Optional

import discord


class IEmbedBuilder(ABC):
    """Interface for building Discord embeds."""

    @abstractmethod
    def create_embed(
        self,
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[str] = None,
        fields: Optional[list[dict[str, Any]]] = None,
        footer: Optional[str] = None,
        author: Optional[dict[str, str]] = None,
    ) -> discord.Embed:
        """Create a Discord embed with given parameters."""
        pass

    @abstractmethod
    def create_success_embed(
        self, title: str, description: str, **kwargs: Any
    ) -> discord.Embed:
        """Create a success-styled embed."""
        pass

    @abstractmethod
    def create_error_embed(
        self, title: str, description: str, **kwargs: Any
    ) -> discord.Embed:
        """Create an error-styled embed."""
        pass

    @abstractmethod
    def create_info_embed(
        self, title: str, description: str, **kwargs: Any
    ) -> discord.Embed:
        """Create an info-styled embed."""
        pass

    @abstractmethod
    def create_warning_embed(
        self, title: str, description: str, **kwargs: Any
    ) -> discord.Embed:
        """Create a warning-styled embed."""
        pass


class IMessageSender(ABC):
    """Interface for sending messages to Discord channels."""

    @abstractmethod
    async def send_embed(
        self,
        target: discord.abc.Messageable,
        embed: discord.Embed,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        """Send an embed to a Discord channel or user."""
        pass

    @abstractmethod
    async def send_text(
        self,
        target: discord.abc.Messageable,
        content: str,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        """Send a text message to a Discord channel or user."""
        pass

    @abstractmethod
    async def reply_to_interaction(
        self,
        interaction: discord.Interaction,
        embed: Optional[discord.Embed] = None,
        content: Optional[str] = None,
        ephemeral: bool = False,
    ) -> None:
        """Reply to a Discord interaction."""
        pass

    @abstractmethod
    async def send_to_context(
        self,
        ctx: Any,
        embed: Optional[discord.Embed] = None,
        content: Optional[str] = None,
        allowed_mentions: Optional[discord.AllowedMentions] = None,
    ) -> Optional[discord.Message]:
        """Send message using command context."""
        pass


class INotificationService(ABC):
    """Interface for sending specific types of notifications."""

    @abstractmethod
    async def send_permission_update(
        self, ctx: Any, target: discord.Member, permission: str, new_value: bool
    ) -> None:
        """Send permission update notification."""
        pass

    @abstractmethod
    async def send_user_not_found(self, ctx: Any) -> None:
        """Send user not found notification."""
        pass

    @abstractmethod
    async def send_no_permission(self, ctx: Any, required_permission: str) -> None:
        """Send no permission notification."""
        pass

    @abstractmethod
    async def send_voice_channel_info(
        self, ctx: Any, channel: discord.VoiceChannel, **info: Any
    ) -> None:
        """Send voice channel information."""
        pass

    @abstractmethod
    async def send_role_update(
        self, ctx: Any, target: discord.Member, role: discord.Role, added: bool
    ) -> None:
        """Send role update notification."""
        pass


class IMessageFormatter(ABC):
    """Interface for formatting message content."""

    @abstractmethod
    def format_member_mention(self, member: discord.Member) -> str:
        """Format member mention string."""
        pass

    @abstractmethod
    def format_role_mention(self, role: discord.Role) -> str:
        """Format role mention string."""
        pass

    @abstractmethod
    def format_channel_mention(self, channel: discord.abc.GuildChannel) -> str:
        """Format channel mention string."""
        pass

    @abstractmethod
    def format_timestamp(self, timestamp: Any, style: str = "f") -> str:
        """Format timestamp for Discord."""
        pass

    @abstractmethod
    def build_description(
        self, base_text: str, ctx: Any, channel: Optional[discord.TextChannel] = None
    ) -> str:
        """Build formatted description with context."""
        pass
