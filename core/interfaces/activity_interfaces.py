"""Interfaces for activity tracking and ranking system."""

from abc import ABC, abstractmethod
from typing import Dict, List, Tuple

import discord
from sqlalchemy.ext.asyncio import AsyncSession


class ActivityType:
    """Activity types for point tracking."""

    VOICE = "voice"
    TEXT = "text"
    PROMOTION = "promotion"  # For promoting server in status
    BONUS = "bonus"


class IActivityTrackingService(ABC):
    """Interface for activity tracking and ranking system."""

    @abstractmethod
    async def add_voice_activity(self, session: AsyncSession, member_id: int, is_with_others: bool = True) -> None:
        """Add voice activity points for a member."""

    @abstractmethod
    async def add_text_activity(self, session: AsyncSession, member_id: int, message_content: str = "") -> None:
        """Add text activity points for a member based on word count."""

    @abstractmethod
    async def add_promotion_activity(self, session: AsyncSession, member_id: int) -> None:
        """Add promotion activity points for a member."""

    @abstractmethod
    async def add_bonus_activity(self, session: AsyncSession, member_id: int, points: int) -> None:
        """Add bonus activity points for a member."""

    @abstractmethod
    async def get_member_stats(self, session: AsyncSession, member_id: int, days_back: int = 7) -> Dict[str, any]:
        """Get comprehensive stats for a member."""

    @abstractmethod
    async def get_leaderboard(
        self, session: AsyncSession, limit: int = 10, days_back: int = 7
    ) -> List[Tuple[int, int, int]]:
        """Get leaderboard with member_id, points, and position."""

    @abstractmethod
    async def check_member_promotion_status(self, member: discord.Member) -> bool:
        """Check if member has server promotion in their status."""

    @abstractmethod
    async def check_member_antipromo_status(self, member: discord.Member) -> bool:
        """Check if member is promoting other Discord servers (anti-cheat)."""

    @abstractmethod
    async def track_message_activity(self, member_id: int, content: str, channel_id: int) -> None:
        """Track message activity for points."""

    @abstractmethod
    def format_leaderboard_embed(
        self,
        leaderboard: List[Tuple[int, int, int]],
        guild: discord.Guild,
        days_back: int = 7,
        author_color: discord.Color = None,
    ) -> discord.Embed:
        """Format leaderboard as Discord embed."""

    @abstractmethod
    def format_member_stats_embed(self, stats: Dict[str, any], member: discord.Member) -> discord.Embed:
        """Format member stats as Discord embed."""

    @abstractmethod
    async def has_daily_activity_today(self, session: AsyncSession, member_id: int, activity_type: str) -> bool:
        """Check if member already got points for this activity type today."""

    @abstractmethod
    async def add_voice_activity_daily(
        self, session: AsyncSession, member_id: int, is_with_others: bool = True
    ) -> None:
        """Add voice activity points once per day."""

    @abstractmethod
    async def add_promotion_activity_daily(self, session: AsyncSession, member_id: int) -> None:
        """Add promotion activity points once per day."""

    @abstractmethod
    def get_time_bonus(self) -> int:
        """Calculate time-based bonus points based on current hour."""

    @abstractmethod
    def set_guild(self, guild: discord.Guild) -> None:
        """Set the guild for the activity tracking service."""

    @abstractmethod
    async def track_voice_activity(self, member_id: int, channel_id: int, is_with_others: bool = True) -> None:
        """Track voice activity for a member in a specific channel."""

    @abstractmethod
    async def track_promotion_activity(self, member_id: int) -> None:
        """Track promotion activity for a member."""

    @abstractmethod
    async def get_member_activity_summary(self, member_id: int, days_back: int = 7) -> Dict[str, any]:
        """Get a summary of member's activity for profile display."""
