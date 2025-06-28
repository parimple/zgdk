"""Embed builder service for creating Discord embeds."""

from typing import Any, Optional

import discord

from core.interfaces.messaging_interfaces import IEmbedBuilder


class EmbedBuilderService(IEmbedBuilder):
    """Service for building Discord embeds with consistent styling."""

    # Standard colors for different message types
    COLORS = {
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "info": discord.Color.blue(),
        "warning": discord.Color.orange(),
        "default": discord.Color.blurple(),
    }

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
        # Determine color
        embed_color = self.COLORS.get(color, self.COLORS["default"])
        if isinstance(color, discord.Color):
            embed_color = color

        # Create embed
        embed = discord.Embed(title=title, description=description, color=embed_color)

        # Add fields if provided
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get("name", ""),
                    value=field.get("value", ""),
                    inline=field.get("inline", True),
                )

        # Add footer if provided
        if footer:
            embed.set_footer(text=footer)

        # Add author if provided
        if author:
            embed.set_author(
                name=author.get("name", ""),
                icon_url=author.get("icon_url"),
                url=author.get("url"),
            )

        return embed

    def create_success_embed(self, title: str, description: str, **kwargs: Any) -> discord.Embed:
        """Create a success-styled embed."""
        return self.create_embed(title=f"✅ {title}", description=description, color="success", **kwargs)

    def create_error_embed(self, title: str, description: str, **kwargs: Any) -> discord.Embed:
        """Create an error-styled embed."""
        return self.create_embed(title=f"❌ {title}", description=description, color="error", **kwargs)

    def create_info_embed(self, title: str, description: str, **kwargs: Any) -> discord.Embed:
        """Create an info-styled embed."""
        return self.create_embed(title=f"ℹ️ {title}", description=description, color="info", **kwargs)

    def create_warning_embed(self, title: str, description: str, **kwargs: Any) -> discord.Embed:
        """Create a warning-styled embed."""
        return self.create_embed(title=f"⚠️ {title}", description=description, color="warning", **kwargs)

    def create_voice_info_embed(self, channel: discord.VoiceChannel, **info: Any) -> discord.Embed:
        """Create an embed with voice channel information."""
        embed = self.create_info_embed(
            title="Informacje o kanale głosowym",
            description=f"Kanał: {channel.mention}",
        )

        # Add channel info fields
        if "member_count" in info:
            embed.add_field(
                name="Liczba użytkowników",
                value=str(info["member_count"]),
                inline=True,
            )

        if "user_limit" in info:
            limit_text = str(info["user_limit"]) if info["user_limit"] > 0 else "Brak"
            embed.add_field(name="Limit użytkowników", value=limit_text, inline=True)

        if "bitrate" in info:
            embed.add_field(name="Bitrate", value=f"{info['bitrate']} kbps", inline=True)

        if "moderators" in info:
            mods = info["moderators"]
            if mods:
                mod_list = "\n".join([f"• {mod.mention}" for mod in mods])
                embed.add_field(name="Moderatorzy", value=mod_list, inline=False)

        return embed

    def create_user_context_embed(self, member: discord.Member, action: str, **context: Any) -> discord.Embed:
        """Create an embed with user context information."""
        embed = self.create_embed(
            title=f"Akcja: {action}",
            description=f"Użytkownik: {member.mention}",
            color=member.color if member.color.value != 0 else "default",
        )

        # Add user avatar
        if member.avatar:
            embed.set_thumbnail(url=member.avatar.url)

        # Add additional context fields
        for key, value in context.items():
            if key not in ["title", "description", "color"]:
                embed.add_field(name=key.replace("_", " ").title(), value=str(value))

        return embed
