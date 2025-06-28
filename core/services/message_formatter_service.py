"""Message formatter service for Discord content formatting."""

from datetime import datetime
from typing import Any, Optional

import discord

from core.interfaces.messaging_interfaces import IMessageFormatter


class MessageFormatterService(IMessageFormatter):
    """Service for formatting Discord message content."""

    def format_member_mention(self, member: discord.Member) -> str:
        """Format member mention string."""
        return member.mention

    def format_role_mention(self, role: discord.Role) -> str:
        """Format role mention string."""
        return role.mention

    def format_channel_mention(self, channel: discord.abc.GuildChannel) -> str:
        """Format channel mention string."""
        return channel.mention

    def format_timestamp(self, timestamp: Any, style: str = "f") -> str:
        """Format timestamp for Discord."""
        if isinstance(timestamp, datetime):
            unix_timestamp = int(timestamp.timestamp())
        elif isinstance(timestamp, (int, float)):
            unix_timestamp = int(timestamp)
        else:
            return str(timestamp)

        return f"<t:{unix_timestamp}:{style}>"

    def build_description(self, base_text: str, ctx: Any, channel: Optional[discord.TextChannel] = None) -> str:
        """Build formatted description with context."""
        description = base_text

        # Add context information
        if hasattr(ctx, "author"):
            author = ctx.author
        elif hasattr(ctx, "user"):
            author = ctx.user
        else:
            author = None

        if author:
            description += f"\n\n**Wykonano przez:** {self.format_member_mention(author)}"

        # Add channel information if provided
        if channel:
            description += f"\n**Kanał:** {self.format_channel_mention(channel)}"
        elif hasattr(ctx, "channel") and ctx.channel:
            description += f"\n**Kanał:** {self.format_channel_mention(ctx.channel)}"

        # Add timestamp
        timestamp = datetime.now()
        description += f"\n**Czas:** {self.format_timestamp(timestamp)}"

        return description

    def format_duration(self, seconds: int) -> str:
        """Format duration in seconds to human-readable string."""
        if seconds < 60:
            return f"{seconds} sekund"
        elif seconds < 3600:
            minutes = seconds // 60
            remaining_seconds = seconds % 60
            if remaining_seconds > 0:
                return f"{minutes} minut, {remaining_seconds} sekund"
            return f"{minutes} minut"
        elif seconds < 86400:
            hours = seconds // 3600
            remaining_minutes = (seconds % 3600) // 60
            if remaining_minutes > 0:
                return f"{hours} godzin, {remaining_minutes} minut"
            return f"{hours} godzin"
        else:
            days = seconds // 86400
            remaining_hours = (seconds % 86400) // 3600
            if remaining_hours > 0:
                return f"{days} dni, {remaining_hours} godzin"
            return f"{days} dni"

    def format_file_size(self, size_bytes: int) -> str:
        """Format file size in bytes to human-readable string."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.1f} TB"

    def format_percentage(self, value: float, total: float) -> str:
        """Format percentage with proper handling of edge cases."""
        if total == 0:
            return "0%"
        percentage = (value / total) * 100
        return f"{percentage:.1f}%"

    def format_user_list(self, users: list[discord.Member], max_display: int = 10) -> str:
        """Format a list of users with mention limits."""
        if not users:
            return "Brak użytkowników"

        if len(users) <= max_display:
            return "\n".join([f"• {self.format_member_mention(user)}" for user in users])
        else:
            displayed = users[:max_display]
            remaining = len(users) - max_display
            user_list = "\n".join([f"• {self.format_member_mention(user)}" for user in displayed])
            user_list += f"\n... i {remaining} więcej"
            return user_list

    def format_role_list(self, roles: list[discord.Role], max_display: int = 10) -> str:
        """Format a list of roles with mention limits."""
        if not roles:
            return "Brak ról"

        if len(roles) <= max_display:
            return "\n".join([f"• {self.format_role_mention(role)}" for role in roles])
        else:
            displayed = roles[:max_display]
            remaining = len(roles) - max_display
            role_list = "\n".join([f"• {self.format_role_mention(role)}" for role in displayed])
            role_list += f"\n... i {remaining} więcej"
            return role_list

    def truncate_text(self, text: str, max_length: int = 2000) -> str:
        """Truncate text to fit Discord message limits."""
        if len(text) <= max_length:
            return text

        # Try to truncate at word boundary
        truncated = text[: max_length - 3]
        last_space = truncated.rfind(" ")

        if last_space > max_length * 0.8:  # If we can truncate at a reasonable word boundary
            return truncated[:last_space] + "..."
        else:
            return truncated + "..."
