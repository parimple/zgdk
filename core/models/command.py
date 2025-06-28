"""
Command-related Pydantic models for Discord bot commands.
"""

import re
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import Field, validator

from .base import BaseModel, DiscordID


class CommandCategory(str, Enum):
    """Command categories."""

    SHOP = "shop"
    MODERATION = "moderation"
    INFO = "info"
    VOICE = "voice"
    PREMIUM = "premium"
    TEAM = "team"
    OWNER = "owner"
    FUN = "fun"


class CommandParameter(BaseModel):
    """Base command parameter validation."""

    name: str = Field(..., min_length=1, max_length=32)
    value: Any
    required: bool = True

    @validator("name")
    def validate_name(cls, v: str) -> str:
        """Validate parameter name."""
        if not re.match(r"^[a-z_][a-z0-9_]*$", v.lower()):
            raise ValueError("Parameter name must be valid Python identifier")
        return v.lower()


class ColorInput(BaseModel):
    """Color input validation and parsing."""

    raw_input: str
    hex_color: str = Field(..., pattern=r"^#[0-9A-Fa-f]{6}$")
    rgb: tuple[int, int, int]
    discord_color: int

    @classmethod
    def parse(cls, color_input: str) -> "ColorInput":
        """Parse color from various formats."""
        color_input = color_input.strip()

        # Try hex format
        hex_match = re.match(r"^#?([0-9A-Fa-f]{6})$", color_input)
        if hex_match:
            hex_color = f"#{hex_match.group(1).upper()}"
            int_color = int(hex_match.group(1), 16)
            rgb = ((int_color >> 16) & 0xFF, (int_color >> 8) & 0xFF, int_color & 0xFF)
            return cls(raw_input=color_input, hex_color=hex_color, rgb=rgb, discord_color=int_color)

        # Try RGB format
        rgb_match = re.match(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", color_input.lower())
        if rgb_match:
            r, g, b = map(int, rgb_match.groups())
            if not all(0 <= val <= 255 for val in (r, g, b)):
                raise ValueError("RGB values must be between 0 and 255")

            int_color = (r << 16) | (g << 8) | b
            hex_color = f"#{int_color:06X}"

            return cls(raw_input=color_input, hex_color=hex_color, rgb=(r, g, b), discord_color=int_color)

        # Try color names (basic set)
        color_names = {
            "red": "#FF0000",
            "green": "#00FF00",
            "blue": "#0000FF",
            "yellow": "#FFFF00",
            "purple": "#800080",
            "orange": "#FFA500",
            "pink": "#FFC0CB",
            "black": "#000000",
            "white": "#FFFFFF",
            "gray": "#808080",
            "grey": "#808080",
        }

        lower_input = color_input.lower()
        if lower_input in color_names:
            return cls.parse(color_names[lower_input])

        raise ValueError(f"Invalid color format: '{color_input}'. " f"Use hex (#RRGGBB), rgb(r,g,b), or color name")

    @validator("discord_color")
    def validate_discord_color(cls, v: int) -> int:
        """Ensure color is valid for Discord."""
        if v < 0 or v > 0xFFFFFF:
            raise ValueError("Color value must be between 0 and 16777215")
        return v


class UserTarget(BaseModel):
    """User targeting for commands."""

    user_id: DiscordID
    is_self: bool = False
    is_bot: bool = False
    is_admin: bool = False

    @validator("user_id")
    def validate_not_bot_for_certain_actions(cls, v: str, values: dict) -> str:
        """Some actions can't target bots."""
        # This would be expanded based on command context
        return v


class MemberSearch(BaseModel):
    """Search parameters for finding members."""

    query: str = Field(..., min_length=1)
    search_type: Literal["id", "username", "nickname", "mention"] = "username"
    exact_match: bool = False

    @validator("query")
    def clean_query(cls, v: str, values: dict) -> str:
        """Clean search query based on type."""
        search_type = values.get("search_type", "username")

        if search_type == "mention":
            # Extract ID from mention
            match = re.match(r"<@!?(\d{17,19})>", v)
            if match:
                return match.group(1)
        elif search_type == "id":
            # Validate ID format
            if not re.match(r"^\d{17,19}$", v):
                raise ValueError("Invalid Discord ID format")

        return v.strip()


class ChannelTarget(BaseModel):
    """Channel targeting for commands."""

    channel_id: DiscordID
    channel_type: Literal["text", "voice", "category", "thread"] = "text"

    @validator("channel_id")
    def validate_channel_type_compatibility(cls, v: str, values: dict) -> str:
        """Validate channel is appropriate for action."""
        # This would be expanded based on command context
        return v


class CommandContext(BaseModel):
    """Full command context for validation."""

    command_name: str
    category: CommandCategory
    guild_id: DiscordID
    channel_id: DiscordID
    author_id: DiscordID
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_slash_command: bool = True
    has_permissions: bool = False

    @validator("command_name")
    def validate_command_name(cls, v: str) -> str:
        """Validate command name format."""
        if not re.match(r"^[a-z][a-z0-9_]*$", v):
            raise ValueError("Invalid command name format")
        return v

    def has_parameter(self, param_name: str) -> bool:
        """Check if parameter exists."""
        return param_name in self.parameters

    def get_parameter(self, param_name: str, default: Any = None) -> Any:
        """Get parameter value with default."""
        return self.parameters.get(param_name, default)


class VoiceChannelConfig(BaseModel):
    """Voice channel configuration."""

    name: str = Field(..., min_length=1, max_length=100)
    user_limit: int = Field(default=0, ge=0, le=99)
    bitrate: int = Field(default=64000, ge=8000, le=384000)
    permissions: dict[str, bool] = Field(default_factory=dict)
    auto_delete: bool = False
    auto_delete_empty_after: int = Field(default=300, ge=60)  # seconds

    @validator("name")
    def validate_voice_channel_name(cls, v: str) -> str:
        """Validate voice channel name."""
        # Voice channels have more relaxed naming rules than text
        if len(v) > 100:
            raise ValueError("Channel name too long")
        return v

    @validator("bitrate")
    def validate_bitrate_for_boost_level(cls, v: int) -> int:
        """Validate bitrate based on server boost level."""
        # This would check actual boost level in practice
        # Default limits: 96kbps (no boost), 128kbps (level 1), 256kbps (level 2), 384kbps (level 3)
        return v
