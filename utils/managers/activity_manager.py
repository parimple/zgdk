"""Activity Manager for tracking user points and ranking system."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from datasources.queries import (
    add_activity_points,
    ensure_member_exists,
    get_activity_leaderboard_with_names,
    get_member_activity_breakdown,
    get_member_ranking_position,
    get_member_total_points,
    get_ranking_tier,
    get_top_members_by_points,
)

logger = logging.getLogger(__name__)


class ActivityType:
    """Activity types for point tracking."""

    VOICE = "voice"
    TEXT = "text"
    PROMOTION = "promotion"  # For promoting server in status
    BONUS = "bonus"


class ActivityManager:
    """Manages user activity points and ranking system."""

    # NOWY OPTYMALNY SYSTEM PUNKTÓW
    # Zaprojektowany dla maksymalnej sprawiedliwości i motywacji społecznej

    # 🎤 VOICE ACTIVITY (co minutę)
    VOICE_WITH_OTHERS = 2  # Wyższa nagroda za społeczne interakcje
    VOICE_ALONE = 1  # Podstawowa nagroda za obecność

    # 💬 TEXT ACTIVITY
    TEXT_MESSAGE = 1  # Punkty za słowo (max 15 za wiadomość - mniej spamu)
    MAX_MESSAGE_POINTS = 15  # Zmniejszone z 32 żeby ograniczyć spam

    # 📢 PROMOTION (co 5 minut zamiast co 3)
    PROMOTION_STATUS = 2  # Wyższa nagroda za promocję serwera

    # 🎁 NOWE BONUSY (opcjonalne - można włączyć w przyszłości)
    DAILY_LOGIN_BONUS = 10  # Bonus za pierwsze logowanie dziennie
    WEEKEND_MULTIPLIER = 1.5  # Mnożnik weekendowy (sobota-niedziela)
    NIGHT_OWL_BONUS = 1  # Dodatkowy punkt za aktywność 22:00-06:00
    EARLY_BIRD_BONUS = 1  # Dodatkowy punkt za aktywność 06:00-10:00

    def __init__(self, guild: discord.Guild = None):
        self.guild = guild
        self.promotion_keywords = ["zagadka", ".gg/zagadka", "discord.gg/zagadka"]

    def set_guild(self, guild: discord.Guild):
        """Set the guild for the activity manager."""
        self.guild = guild

    async def add_voice_activity(
        self, session: AsyncSession, member_id: int, is_with_others: bool = True
    ) -> None:
        """Add voice activity points for a member."""
        base_points = self.VOICE_WITH_OTHERS if is_with_others else self.VOICE_ALONE
        time_bonus = self.get_time_bonus()
        total_points = base_points + time_bonus
        await self._add_points(session, member_id, ActivityType.VOICE, total_points)

    async def add_text_activity(
        self, session: AsyncSession, member_id: int, message_content: str = ""
    ) -> None:
        """Add text activity points for a member based on word count (like original zagadka)."""
        if not message_content:
            return

        # Count words in message
        word_count = len(message_content.split())

        # Apply maximum points limit (like original zagadka)
        points = min(word_count * self.TEXT_MESSAGE, self.MAX_MESSAGE_POINTS)

        if points > 0:
            await self._add_points(session, member_id, ActivityType.TEXT, points)

    async def add_promotion_activity(
        self, session: AsyncSession, member_id: int
    ) -> None:
        """Add promotion activity points for a member."""
        await self._add_points(
            session, member_id, ActivityType.PROMOTION, self.PROMOTION_STATUS
        )

    async def add_bonus_activity(
        self, session: AsyncSession, member_id: int, points: int
    ) -> None:
        """Add bonus activity points for a member."""
        await self._add_points(session, member_id, ActivityType.BONUS, points)

    async def _add_points(
        self, session: AsyncSession, member_id: int, activity_type: str, points: int
    ) -> None:
        """Internal method to add points."""
        try:
            # Ensure member exists in database
            await ensure_member_exists(session, member_id)
            await add_activity_points(session, member_id, activity_type, points)
            await session.commit()

            logger.debug(
                f"Added {points} {activity_type} points for member {member_id}"
            )
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Error adding {activity_type} points for member {member_id}: {e}"
            )
            raise

    def get_time_bonus(self) -> int:
        """Get time-based bonus points."""
        current_hour = datetime.now(timezone.utc).hour

        # Night owl bonus (22:00-06:00)
        if current_hour >= 22 or current_hour < 6:
            return self.NIGHT_OWL_BONUS

        # Early bird bonus (06:00-10:00)
        if 6 <= current_hour < 10:
            return self.EARLY_BIRD_BONUS

        return 0

    async def get_member_stats(
        self, session: AsyncSession, member_id: int
    ) -> Dict[str, any]:
        """Get comprehensive stats for a member."""
        total_points = await get_member_total_points(session, member_id)
        breakdown = await get_member_activity_breakdown(session, member_id)
        position = await get_member_ranking_position(session, member_id)
        tier = await get_ranking_tier(session, member_id)

        return {
            "total_points": total_points,
            "breakdown": breakdown,
            "position": position,
            "tier": tier,
        }

    async def get_leaderboard(
        self, session: AsyncSession, limit: int = 10
    ) -> List[Tuple[str, int]]:
        """Get activity leaderboard with member names."""
        return await get_activity_leaderboard_with_names(session, self.guild, limit)

    def is_promotion_message(self, content: str) -> bool:
        """Check if message contains promotion keywords."""
        content_lower = content.lower()
        return any(keyword in content_lower for keyword in self.promotion_keywords)
