"""
Moderation-related Pydantic models.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Literal

from pydantic import Field, validator

from .base import BaseModel, DiscordID, Timestamp


class ModerationType(str, Enum):
    """Types of moderation actions."""

    MUTE = "mute"
    TIMEOUT = "timeout"
    BAN = "ban"
    KICK = "kick"
    WARN = "warn"
    UNMUTE = "unmute"
    UNBAN = "unban"


class MuteType(str, Enum):
    """Types of mutes available."""

    VOICE = "voice"  # Can't speak in voice
    TEXT = "text"  # Can't send messages
    MEDIA = "media"  # Can't send attachments
    REACT = "react"  # Can't add reactions
    FULL = "full"  # All restrictions


class ModerationAction(BaseModel):
    """Base moderation action model."""

    action: ModerationType
    target_id: DiscordID
    moderator_id: DiscordID
    reason: str = Field(..., min_length=3, max_length=500)
    duration_seconds: int | None = Field(None, gt=0)
    timestamp: Timestamp = Field(default_factory=datetime.utcnow)
    guild_id: DiscordID
    channel_id: DiscordID | None = None

    @validator("reason")
    def clean_reason(cls, v: str) -> str:
        """Clean and validate reason."""
        v = v.strip()
        if len(v) < 3:
            raise ValueError("Reason must be at least 3 characters")
        # Remove multiple spaces
        v = " ".join(v.split())
        return v

    @property
    def duration_text(self) -> str:
        """Get human-readable duration."""
        if not self.duration_seconds:
            return "permanent"

        seconds = self.duration_seconds
        if seconds < 60:
            return f"{seconds} seconds"
        elif seconds < 3600:
            return f"{seconds // 60} minutes"
        elif seconds < 86400:
            return f"{seconds // 3600} hours"
        else:
            return f"{seconds // 86400} days"

    @property
    def expires_at(self) -> datetime | None:
        """Calculate expiration time."""
        if not self.duration_seconds:
            return None
        return self.timestamp + timedelta(seconds=self.duration_seconds)


class MuteRequest(ModerationAction):
    """Mute request with specific mute type."""

    action: Literal[ModerationType.MUTE] = ModerationType.MUTE
    mute_type: MuteType = MuteType.FULL
    remove_nickname: bool = False

    @validator("mute_type")
    def validate_mute_type(cls, v: MuteType) -> MuteType:
        """Validate mute type."""
        # Add any specific mute type validation here
        return v


class TimeoutRequest(ModerationAction):
    """Discord timeout request."""

    action: Literal[ModerationType.TIMEOUT] = ModerationType.TIMEOUT
    duration_seconds: int = Field(..., gt=0, le=2419200)  # Max 28 days

    @validator("duration_seconds")
    def validate_timeout_duration(cls, v: int) -> int:
        """Validate timeout duration (Discord limit is 28 days)."""
        max_seconds = 28 * 24 * 60 * 60  # 28 days
        if v > max_seconds:
            raise ValueError(f"Timeout duration cannot exceed 28 days ({max_seconds} seconds)")
        return v


class BanRequest(ModerationAction):
    """Ban request with delete options."""

    action: Literal[ModerationType.BAN] = ModerationType.BAN
    delete_message_days: int = Field(default=0, ge=0, le=7)

    @validator("delete_message_days")
    def validate_delete_days(cls, v: int) -> int:
        """Validate message deletion days (Discord limit is 7)."""
        if v > 7:
            raise ValueError("Cannot delete more than 7 days of messages")
        return v


class WarnRequest(ModerationAction):
    """Warning request."""

    action: Literal[ModerationType.WARN] = ModerationType.WARN
    severity: Literal["low", "medium", "high"] = "medium"
    points: int = Field(default=1, ge=1, le=10)

    @validator("points")
    def validate_points_by_severity(cls, v: int, values: dict) -> int:
        """Validate points match severity."""
        severity = values.get("severity")
        if severity == "low" and v > 3:
            raise ValueError("Low severity warnings should have 1-3 points")
        elif severity == "high" and v < 5:
            raise ValueError("High severity warnings should have 5-10 points")
        return v


class ModerationHistory(BaseModel):
    """User's moderation history."""

    user_id: DiscordID
    guild_id: DiscordID
    total_warnings: int = Field(default=0, ge=0)
    total_mutes: int = Field(default=0, ge=0)
    total_bans: int = Field(default=0, ge=0)
    warning_points: int = Field(default=0, ge=0)
    last_action: datetime | None = None
    active_mutes: list[MuteRequest] = Field(default_factory=list)
    recent_actions: list[ModerationAction] = Field(default_factory=list)

    @property
    def risk_level(self) -> Literal["low", "medium", "high", "critical"]:
        """Calculate user risk level based on history."""
        if self.total_bans > 0 or self.warning_points >= 10:
            return "critical"
        elif self.total_mutes >= 3 or self.warning_points >= 7:
            return "high"
        elif self.total_mutes >= 1 or self.warning_points >= 4:
            return "medium"
        return "low"

    def add_action(self, action: ModerationAction) -> None:
        """Add action to history."""
        self.recent_actions.insert(0, action)
        # Keep only last 10 actions
        self.recent_actions = self.recent_actions[:10]

        if isinstance(action, WarnRequest):
            self.total_warnings += 1
            self.warning_points += action.points
        elif isinstance(action, MuteRequest):
            self.total_mutes += 1
            self.active_mutes.append(action)
        elif action.action == ModerationType.BAN:
            self.total_bans += 1

        self.last_action = action.timestamp


class DurationInput(BaseModel):
    """Parsed duration from user input."""

    raw_input: str
    seconds: int
    human_readable: str

    @classmethod
    def parse(cls, duration_str: str) -> "DurationInput":
        """Parse duration string to seconds."""
        import re

        # Pattern for duration parsing
        pattern = r"(\d+)\s*([dhms]?)"
        matches = re.findall(pattern, duration_str.lower())

        if not matches:
            raise ValueError(f"Invalid duration format: {duration_str}")

        total_seconds = 0
        parts = []

        for amount, unit in matches:
            amount = int(amount)

            if unit == "d":
                total_seconds += amount * 86400
                parts.append(f"{amount} day{'s' if amount != 1 else ''}")
            elif unit == "h":
                total_seconds += amount * 3600
                parts.append(f"{amount} hour{'s' if amount != 1 else ''}")
            elif unit == "m":
                total_seconds += amount * 60
                parts.append(f"{amount} minute{'s' if amount != 1 else ''}")
            elif unit == "s" or not unit:
                total_seconds += amount
                parts.append(f"{amount} second{'s' if amount != 1 else ''}")

        if total_seconds <= 0:
            raise ValueError("Duration must be positive")

        return cls(raw_input=duration_str, seconds=total_seconds, human_readable=" ".join(parts))
