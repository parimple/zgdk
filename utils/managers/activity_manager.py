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

    # Point values (similar to zagadka)
    VOICE_WITH_OTHERS = 12  # Points per minute in voice with others
    VOICE_ALONE = 2  # Points per minute in voice alone
    TEXT_MESSAGE = 1  # Points per message (can be adjusted)
    PROMOTION_STATUS = 4  # Points per minute for promoting server in status

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
        points = self.VOICE_WITH_OTHERS if is_with_others else self.VOICE_ALONE
        await self._add_points(session, member_id, ActivityType.VOICE, points)

    async def add_text_activity(
        self, session: AsyncSession, member_id: int, message_count: int = 1
    ) -> None:
        """Add text activity points for a member."""
        points = self.TEXT_MESSAGE * message_count
        await self._add_points(session, member_id, ActivityType.TEXT, points)

    async def add_promotion_activity(self, session: AsyncSession, member_id: int) -> None:
        """Add promotion activity points for a member."""
        await self._add_points(session, member_id, ActivityType.PROMOTION, self.PROMOTION_STATUS)

    async def add_bonus_activity(self, session: AsyncSession, member_id: int, points: int) -> None:
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

            logger.debug(f"Added {points} {activity_type} points to member {member_id}")
        except Exception as e:
            logger.error(
                f"Failed to add {points} {activity_type} points to member {member_id}: {e}"
            )
            await session.rollback()

    async def get_member_stats(
        self, session: AsyncSession, member_id: int, days_back: int = 7
    ) -> Dict[str, any]:
        """Get comprehensive stats for a member."""
        total_points = await get_member_total_points(session, member_id, days_back)
        position = await get_member_ranking_position(session, member_id, days_back)
        tier = await get_ranking_tier(session, member_id, days_back)
        breakdown = await get_member_activity_breakdown(session, member_id, days_back)

        return {
            "total_points": total_points,
            "position": position,
            "tier": tier,
            "breakdown": breakdown,
            "days_back": days_back,
        }

    async def get_leaderboard(
        self, session: AsyncSession, limit: int = 10, days_back: int = 7
    ) -> List[Tuple[int, int, int]]:
        """Get leaderboard with member_id, points, and position."""
        return await get_activity_leaderboard_with_names(session, limit, days_back)

    async def check_member_promotion_status(self, member: discord.Member) -> bool:
        """Check if member has server promotion in their status."""
        if not member.activities:
            return False

        for activity in member.activities:
            # Check custom status
            if isinstance(activity, discord.CustomActivity):
                if activity.name and any(
                    keyword in activity.name.lower() for keyword in self.promotion_keywords
                ):
                    return True

            # Check activity name
            if hasattr(activity, "name") and activity.name:
                if any(keyword in activity.name.lower() for keyword in self.promotion_keywords):
                    return True

            # Check activity details
            if hasattr(activity, "details") and activity.details:
                if any(keyword in activity.details.lower() for keyword in self.promotion_keywords):
                    return True

            # Check activity state
            if hasattr(activity, "state") and activity.state:
                if any(keyword in activity.state.lower() for keyword in self.promotion_keywords):
                    return True

        return False

    async def check_member_antipromo_status(self, member: discord.Member) -> bool:
        """Check if member is promoting other Discord servers (anti-cheat)."""
        if not member.activities:
            return False

        for activity in member.activities:
            # Check custom status
            if isinstance(activity, discord.CustomActivity):
                if activity.name and ".gg/" in activity.name.lower():
                    # Check if it's NOT our server
                    if not any(
                        keyword in activity.name.lower() for keyword in self.promotion_keywords
                    ):
                        return True

            # Check activity name
            if hasattr(activity, "name") and activity.name:
                if ".gg/" in activity.name.lower():
                    if not any(
                        keyword in activity.name.lower() for keyword in self.promotion_keywords
                    ):
                        return True

        return False

    def format_leaderboard_embed(
        self,
        leaderboard: List[Tuple[int, int, int]],
        guild: discord.Guild,
        days_back: int = 7,
        author_color: discord.Color = None,
    ) -> discord.Embed:
        """Format leaderboard as Discord embed."""
        # Use author's color if provided, otherwise blue
        color = author_color if author_color and author_color.value != 0 else discord.Color.blue()

        embed = discord.Embed(
            title=f"🏆 Ranking Aktywności zaGadki",
            description=f"📌 **Najaktywniejszi członkowie serwera z ostatnich {days_back} dni**",
            color=color,
        )

        if not leaderboard:
            embed.add_field(
                name="Brak danych", value="Nie znaleziono aktywności w tym okresie", inline=False
            )
            embed.set_footer(
                text=f"💡 Aktualizacja: co godzinę | Dane z ostatnich {days_back} dni",
                icon_url=guild.icon.url if guild.icon else None,
            )
            return embed

        leaderboard_text = ""
        for member_id, points, position in leaderboard[:10]:  # Top 10
            member = guild.get_member(member_id)
            member_name = member.display_name if member else f"User {member_id}"

            # Add medal for top 3
            if position == 1:
                medal = "🥇"
            elif position == 2:
                medal = "🥈"
            elif position == 3:
                medal = "🥉"
            else:
                medal = f"**{position}.**"

            leaderboard_text += f"{medal} {member_name} - **{points}** pkt\n"

        embed.add_field(name="🎯 TOP 10", value=leaderboard_text, inline=False)

        # Statistics
        total_active = len(leaderboard)
        total_points = sum(p[1] for p in leaderboard)
        avg_points = total_points // total_active if total_active > 0 else 0

        embed.add_field(
            name="📊 Statystyki",
            value=f"Łącznie aktywnych: **{total_active}** osób\n"
            f"Średnia punktów: **{avg_points}** pkt\n"
            f"Suma wszystkich punktów: **{total_points}** pkt",
            inline=True,
        )

        # Add tier info
        embed.add_field(
            name="🏅 System rang",
            value="🥇 **1-100**: Ranga 100\n🥈 **101-200**: Ranga 200\n🥉 **201-300**: Ranga 300",
            inline=True,
        )

        embed.set_footer(
            text=f"💡 Aktualizacja: co godzinę | Dane z ostatnich {days_back} dni",
            icon_url=guild.icon.url if guild.icon else None,
        )
        return embed

    def format_member_stats_embed(
        self, stats: Dict[str, any], member: discord.Member
    ) -> discord.Embed:
        """Format member stats as Discord embed."""
        # Use member's color if available, otherwise blue
        color = member.color if member.color.value != 0 else discord.Color.blue()

        embed = discord.Embed(
            title=f"📊 Statystyki aktywności zaGadki",
            description=f"**Profil użytkownika:** {member.display_name}",
            color=color,
        )

        # Main stats
        position_text = f"**#{stats['position']}**" if stats["position"] > 0 else "Brak rankingu"
        embed.add_field(name="🏆 Pozycja w rankingu", value=position_text, inline=True)

        embed.add_field(name="🏅 Ranga", value=f"**{stats['tier']}**", inline=True)

        embed.add_field(
            name="⭐ Łączne punkty", value=f"**{stats['total_points']}** pkt", inline=True
        )

        # Activity breakdown
        if stats["breakdown"]:
            breakdown_text = ""
            activity_emojis = {"voice": "🎤", "text": "💬", "promotion": "📢", "bonus": "🎁"}

            activity_names = {
                "voice": "Rozmowy głosowe",
                "text": "Wiadomości tekstowe",
                "promotion": "Promocja serwera",
                "bonus": "Punkty bonusowe",
            }

            for activity_type, points in stats["breakdown"].items():
                emoji = activity_emojis.get(activity_type, "📊")
                name = activity_names.get(activity_type, activity_type.title())
                breakdown_text += f"{emoji} {name}: **{points}** pkt\n"

            embed.add_field(
                name="📈 Podział punktów według aktywności", value=breakdown_text, inline=False
            )
        else:
            embed.add_field(
                name="📈 Podział punktów według aktywności",
                value="Brak danych o aktywności w tym okresie",
                inline=False,
            )

        # User info
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)

        embed.set_footer(
            text=f"💡 Dane z ostatnich {stats['days_back']} dni | ID: {member.id}",
            icon_url=member.guild.icon.url if member.guild.icon else None,
        )

        return embed
