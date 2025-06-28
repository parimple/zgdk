"""
Base Pydantic models and validators used across the application.
"""

from datetime import datetime
from typing import Annotated, TypeVar

from pydantic import BaseModel as PydanticBaseModel
from pydantic import Field, validator


class BaseModel(PydanticBaseModel):
    """Base model with common configuration."""

    class Config:
        # Use Enum values instead of names
        use_enum_values = True
        # Validate on assignment
        validate_assignment = True
        # Allow population by field name
        populate_by_name = True
        # Add schema extra
        json_schema_extra = {"example": "See specific model documentation"}


# Type definitions
DiscordID = Annotated[str, Field(..., pattern=r"^\d{17,19}$", description="Discord snowflake ID")]

Timestamp = Annotated[datetime, Field(default_factory=datetime.utcnow, description="UTC timestamp")]


class DiscordUser(BaseModel):
    """Represents a Discord user."""

    id: DiscordID
    username: str = Field(..., min_length=1, max_length=32)
    discriminator: str = Field(default="0", pattern=r"^\d{4}$")
    avatar: str | None = None
    bot: bool = False

    @validator("username")
    def validate_username(cls, v: str) -> str:
        """Validate Discord username."""
        # Discord usernames can't have certain characters
        invalid_chars = ["@", "#", ":", "```"]
        for char in invalid_chars:
            if char in v:
                raise ValueError(f"Username cannot contain '{char}'")
        return v.strip()


class DiscordGuild(BaseModel):
    """Represents a Discord guild (server)."""

    id: DiscordID
    name: str = Field(..., min_length=2, max_length=100)
    owner_id: DiscordID
    member_count: int = Field(..., ge=0)


class DiscordRole(BaseModel):
    """Represents a Discord role."""

    id: DiscordID
    name: str = Field(..., min_length=1, max_length=100)
    color: int = Field(..., ge=0, le=16777215)  # 0xFFFFFF max
    position: int = Field(..., ge=0)
    permissions: int = Field(..., ge=0)

    @validator("color")
    def validate_color(cls, v: int) -> int:
        """Ensure color is valid RGB integer."""
        if v < 0 or v > 0xFFFFFF:
            raise ValueError("Color must be between 0 and 16777215 (0xFFFFFF)")
        return v


class DiscordChannel(BaseModel):
    """Represents a Discord channel."""

    id: DiscordID
    name: str = Field(..., min_length=1, max_length=100)
    type: int = Field(..., ge=0)  # Channel type enum value
    guild_id: DiscordID | None = None
    position: int = Field(default=0, ge=0)

    @validator("name")
    def validate_channel_name(cls, v: str) -> str:
        """Validate channel name."""
        # Discord channel names must be lowercase with limited chars
        import re

        if not re.match(r"^[a-z0-9-_]+$", v):
            # For voice channels, more characters are allowed
            # This is a simplified validation
            pass
        return v


# Generic type for models
T = TypeVar("T", bound=BaseModel)
