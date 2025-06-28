"""Activity tracking service for managing user points and ranking system."""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Tuple

import discord
from sqlalchemy.ext.asyncio import AsyncSession

from core.interfaces.activity_interfaces import ActivityType, IActivityTrackingService
from core.services.base_service import BaseService
from datasources.queries import (
    add_activity_points,
    ensure_member_exists,
    get_activity_leaderboard_with_names,
    get_member_activity_breakdown,
    get_member_ranking_position,
    get_member_total_points,
    get_ranking_tier,
)


class ActivityTrackingService(BaseService, IActivityTrackingService):
    """Service for managing user activity points and ranking system."""

    # OPTIMAL POINT SYSTEM
    # Designed for maximum fairness and social motivation

    # 🎤 VOICE ACTIVITY (per minute)
    VOICE_WITH_OTHERS = 2  # Higher reward for social interactions
    VOICE_ALONE = 1  # Basic reward for presence

    # 💬 TEXT ACTIVITY
    TEXT_MESSAGE = 1  # Points per word (max 15 per message - less spam)
    MAX_MESSAGE_POINTS = 15  # Reduced from 32 to limit spam

    # 📢 PROMOTION (every 5 minutes instead of 3)
    PROMOTION_STATUS = 2  # Higher reward for server promotion

    # 🎁 NEW BONUSES (optional - can be enabled in the future)
    DAILY_LOGIN_BONUS = 10  # Bonus for first daily login
    WEEKEND_MULTIPLIER = 1.5  # Weekend multiplier (Saturday-Sunday)
    NIGHT_OWL_BONUS = 1  # Extra point for activity 22:00-06:00
    EARLY_BIRD_BONUS = 1  # Extra point for activity 06:00-10:00

    def __init__(self, activity_repository, member_repository, unit_of_work, guild: discord.Guild = None, **kwargs):
        super().__init__(unit_of_work=unit_of_work)
        self.activity_repository = activity_repository
        self.member_repository = member_repository
        self.guild = guild
        self.promotion_keywords = ["zagadka", ".gg/zagadka", "discord.gg/zagadka"]
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate activity tracking operation."""
        return True

    def set_guild(self, guild: discord.Guild) -> None:
        """Set the guild for the activity tracking service."""
        self.guild = guild
        self._log_operation("set_guild", guild_id=guild.id if guild else None)

    async def add_voice_activity(self, session: AsyncSession, member_id: int, is_with_others: bool = True) -> None:
        """Add voice activity points for a member."""
        try:
            base_points = self.VOICE_WITH_OTHERS if is_with_others else self.VOICE_ALONE
            time_bonus = self.get_time_bonus()
            total_points = base_points + time_bonus
            await self._add_points(session, member_id, ActivityType.VOICE, total_points)

            self._log_operation(
                "add_voice_activity",
                member_id=member_id,
                is_with_others=is_with_others,
                base_points=base_points,
                time_bonus=time_bonus,
                total_points=total_points,
            )

        except Exception as e:
            self._log_error(
                "add_voice_activity",
                e,
                member_id=member_id,
                is_with_others=is_with_others,
            )

    async def add_text_activity(self, session: AsyncSession, member_id: int, message_content: str = "") -> None:
        """Add text activity points for a member based on word count."""
        try:
            if not message_content:
                return

            # Count words in message
            word_count = len(message_content.split())

            # Apply maximum points limit
            points = min(word_count * self.TEXT_MESSAGE, self.MAX_MESSAGE_POINTS)

            if points > 0:
                await self._add_points(session, member_id, ActivityType.TEXT, points)

                self._log_operation(
                    "add_text_activity",
                    member_id=member_id,
                    word_count=word_count,
                    points=points,
                    message_length=len(message_content),
                )

        except Exception as e:
            self._log_error(
                "add_text_activity",
                e,
                member_id=member_id,
                message_length=len(message_content) if message_content else 0,
            )

    async def add_promotion_activity(self, session: AsyncSession, member_id: int) -> None:
        """Add promotion activity points for a member."""
        try:
            await self._add_points(session, member_id, ActivityType.PROMOTION, self.PROMOTION_STATUS)

            self._log_operation(
                "add_promotion_activity",
                member_id=member_id,
                points=self.PROMOTION_STATUS,
            )

        except Exception as e:
            self._log_error("add_promotion_activity", e, member_id=member_id)

    async def add_bonus_activity(self, session: AsyncSession, member_id: int, points: int) -> None:
        """Add bonus activity points for a member."""
        try:
            await self._add_points(session, member_id, ActivityType.BONUS, points)

            self._log_operation(
                "add_bonus_activity",
                member_id=member_id,
                points=points,
            )

        except Exception as e:
            self._log_error(
                "add_bonus_activity",
                e,
                member_id=member_id,
                points=points,
            )

    async def _add_points(self, session: AsyncSession, member_id: int, activity_type: str, points: int) -> None:
        """Internal method to add points."""
        try:
            # Ensure member exists in database
            await ensure_member_exists(session, member_id)
            await add_activity_points(session, member_id, activity_type, points)
            await session.commit()

            self.logger.debug(f"Added {points} {activity_type} points to member {member_id}")

        except Exception as e:
            self.logger.error(f"Failed to add {points} {activity_type} points to member {member_id}: {e}")
            await session.rollback()
            raise

    async def get_member_stats(self, session: AsyncSession, member_id: int, days_back: int = 7) -> Dict[str, any]:
        """Get comprehensive stats for a member."""
        try:
            total_points = await get_member_total_points(session, member_id, days_back)
            position = await get_member_ranking_position(session, member_id, days_back)
            tier = await get_ranking_tier(session, member_id, days_back)
            breakdown = await get_member_activity_breakdown(session, member_id, days_back)

            stats = {
                "total_points": total_points,
                "position": position,
                "tier": tier,
                "breakdown": breakdown,
                "days_back": days_back,
            }

            self._log_operation(
                "get_member_stats",
                member_id=member_id,
                days_back=days_back,
                total_points=total_points,
                position=position,
                tier=tier,
            )

            return stats

        except Exception as e:
            self._log_error(
                "get_member_stats",
                e,
                member_id=member_id,
                days_back=days_back,
            )
            return {
                "total_points": 0,
                "position": 0,
                "tier": "No Rank",
                "breakdown": {},
                "days_back": days_back,
            }

    async def get_leaderboard(
        self, session: AsyncSession, limit: int = 10, days_back: int = 7
    ) -> List[Tuple[int, int, int]]:
        """Get leaderboard with member_id, points, and position."""
        try:
            leaderboard = await get_activity_leaderboard_with_names(session, limit, days_back)

            self._log_operation(
                "get_leaderboard",
                limit=limit,
                days_back=days_back,
                result_count=len(leaderboard),
            )

            return leaderboard

        except Exception as e:
            self._log_error(
                "get_leaderboard",
                e,
                limit=limit,
                days_back=days_back,
            )
            return []

    async def check_member_promotion_status(self, member: discord.Member) -> bool:
        """Check if member has server promotion in their status."""
        try:
            if not member.activities:
                return False

            for activity in member.activities:
                # Check custom status
                if isinstance(activity, discord.CustomActivity):
                    if activity.name and any(keyword in activity.name.lower() for keyword in self.promotion_keywords):
                        self._log_operation(
                            "promotion_status_found",
                            member_id=member.id,
                            activity_type="custom",
                            content=activity.name,
                        )
                        return True

                # Check activity name
                if hasattr(activity, "name") and activity.name:
                    if any(keyword in activity.name.lower() for keyword in self.promotion_keywords):
                        self._log_operation(
                            "promotion_status_found",
                            member_id=member.id,
                            activity_type="name",
                            content=activity.name,
                        )
                        return True

                # Check activity details
                if hasattr(activity, "details") and activity.details:
                    if any(keyword in activity.details.lower() for keyword in self.promotion_keywords):
                        self._log_operation(
                            "promotion_status_found",
                            member_id=member.id,
                            activity_type="details",
                            content=activity.details,
                        )
                        return True

                # Check activity state
                if hasattr(activity, "state") and activity.state:
                    if any(keyword in activity.state.lower() for keyword in self.promotion_keywords):
                        self._log_operation(
                            "promotion_status_found",
                            member_id=member.id,
                            activity_type="state",
                            content=activity.state,
                        )
                        return True

            return False

        except Exception as e:
            self._log_error("check_member_promotion_status", e, member_id=member.id)
            return False

    async def check_member_antipromo_status(self, member: discord.Member) -> bool:
        """Check if member is promoting other Discord servers (anti-cheat)."""
        try:
            if not member.activities:
                return False

            for activity in member.activities:
                # Check custom status
                if isinstance(activity, discord.CustomActivity):
                    if activity.name and ".gg/" in activity.name.lower():
                        # Check if it's NOT our server
                        if not any(keyword in activity.name.lower() for keyword in self.promotion_keywords):
                            self._log_operation(
                                "antipromo_status_found",
                                member_id=member.id,
                                activity_type="custom",
                                content=activity.name,
                            )
                            return True

                # Check activity name
                if hasattr(activity, "name") and activity.name:
                    if ".gg/" in activity.name.lower():
                        if not any(keyword in activity.name.lower() for keyword in self.promotion_keywords):
                            self._log_operation(
                                "antipromo_status_found",
                                member_id=member.id,
                                activity_type="name",
                                content=activity.name,
                            )
                            return True

            return False

        except Exception as e:
            self._log_error("check_member_antipromo_status", e, member_id=member.id)
            return False

    async def track_message_activity(self, member_id: int, content: str, channel_id: int) -> None:
        """Track message activity for points."""
        try:
            # Get session from unit of work
            if not self.unit_of_work:
                self._log_error("track_message_activity", ValueError("No unit of work available"), member_id=member_id)
                return

            async with self.unit_of_work as uow:
                # Use the existing add_text_activity method
                await self.add_text_activity(uow.session, member_id, content)
                await uow.commit()

                # Log the operation
                word_count = len(content.split())
                points = min(word_count * self.TEXT_MESSAGE, self.MAX_MESSAGE_POINTS)

                self._log_operation(
                    "track_message_activity",
                    member_id=member_id,
                    points=points,
                    word_count=word_count,
                    channel_id=channel_id,
                )

        except Exception as e:
            self._log_error("track_message_activity", e, member_id=member_id, channel_id=channel_id)

    def format_leaderboard_embed(
        self,
        leaderboard: List[Tuple[int, int, int]],
        guild: discord.Guild,
        days_back: int = 7,
        author_color: discord.Color = None,
    ) -> discord.Embed:
        """Format leaderboard as Discord embed."""
        try:
            # Use author's color if provided, otherwise blue
            color = author_color if author_color and author_color.value != 0 else discord.Color.blue()

            embed = discord.Embed(
                title=f"🏆 Ranking Aktywności zaGadki",
                description=f"📌 **Najaktywniejsi członkowie serwera z ostatnich {days_back} dni**",
                color=color,
            )

            if not leaderboard:
                embed.add_field(
                    name="Brak danych",
                    value="Nie znaleziono aktywności w tym okresie",
                    inline=False,
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

            self._log_operation(
                "format_leaderboard_embed",
                days_back=days_back,
                leaderboard_count=len(leaderboard),
                total_active=total_active,
                total_points=total_points,
            )

            return embed

        except Exception as e:
            self._log_error(
                "format_leaderboard_embed",
                e,
                days_back=days_back,
                leaderboard_count=len(leaderboard) if leaderboard else 0,
            )
            # Return basic embed on error
            return discord.Embed(
                title="🏆 Ranking Aktywności zaGadki",
                description="Wystąpił błąd podczas formatowania rankingu.",
                color=discord.Color.red(),
            )

    def format_member_stats_embed(self, stats: Dict[str, any], member: discord.Member) -> discord.Embed:
        """Format member stats as Discord embed."""
        try:
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
                name="⭐ Łączne punkty",
                value=f"**{stats['total_points']}** pkt",
                inline=True,
            )

            # Activity breakdown
            if stats["breakdown"]:
                breakdown_text = ""
                activity_emojis = {
                    "voice": "🎤",
                    "text": "💬",
                    "promotion": "📢",
                    "bonus": "🎁",
                }

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
                    name="📈 Podział punktów według aktywności",
                    value=breakdown_text,
                    inline=False,
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

            self._log_operation(
                "format_member_stats_embed",
                member_id=member.id,
                total_points=stats["total_points"],
                position=stats["position"],
                days_back=stats["days_back"],
            )

            return embed

        except Exception as e:
            self._log_error(
                "format_member_stats_embed",
                e,
                member_id=member.id if member else None,
                stats=stats,
            )
            # Return basic embed on error
            return discord.Embed(
                title="📊 Statystyki aktywności zaGadki",
                description="Wystąpił błąd podczas formatowania statystyk.",
                color=discord.Color.red(),
            )

    async def has_daily_activity_today(self, session: AsyncSession, member_id: int, activity_type: str) -> bool:
        """Check if member already got points for this activity type today."""
        try:
            today_breakdown = await get_member_activity_breakdown(session, member_id, days_back=1)
            has_activity = activity_type in today_breakdown and today_breakdown[activity_type] > 0

            self._log_operation(
                "has_daily_activity_today",
                member_id=member_id,
                activity_type=activity_type,
                has_activity=has_activity,
            )

            return has_activity

        except Exception as e:
            self._log_error(
                "has_daily_activity_today",
                e,
                member_id=member_id,
                activity_type=activity_type,
            )
            return False

    async def add_voice_activity_daily(
        self, session: AsyncSession, member_id: int, is_with_others: bool = True
    ) -> None:
        """Add voice activity points once per day."""
        try:
            # Check if user already got voice points today
            if await self.has_daily_activity_today(session, member_id, ActivityType.VOICE):
                return

            points = self.VOICE_WITH_OTHERS if is_with_others else self.VOICE_ALONE
            await self._add_points(session, member_id, ActivityType.VOICE, points)

            self._log_operation(
                "add_voice_activity_daily",
                member_id=member_id,
                is_with_others=is_with_others,
                points=points,
            )

        except Exception as e:
            self._log_error(
                "add_voice_activity_daily",
                e,
                member_id=member_id,
                is_with_others=is_with_others,
            )

    async def add_promotion_activity_daily(self, session: AsyncSession, member_id: int) -> None:
        """Add promotion activity points once per day."""
        try:
            # Check if user already got promotion points today
            if await self.has_daily_activity_today(session, member_id, ActivityType.PROMOTION):
                return

            await self._add_points(session, member_id, ActivityType.PROMOTION, self.PROMOTION_STATUS)

            self._log_operation(
                "add_promotion_activity_daily",
                member_id=member_id,
                points=self.PROMOTION_STATUS,
            )

        except Exception as e:
            self._log_error(
                "add_promotion_activity_daily",
                e,
                member_id=member_id,
            )

    def get_time_bonus(self) -> int:
        """Calculate time-based bonus points based on current hour."""
        try:
            current_time = datetime.now(timezone.utc)
            hour = current_time.hour

            bonus = 0

            # Night owl bonus (22:00-06:00 UTC)
            if hour >= 22 or hour < 6:
                bonus += self.NIGHT_OWL_BONUS

            # Early bird bonus (06:00-10:00 UTC)
            elif 6 <= hour < 10:
                bonus += self.EARLY_BIRD_BONUS

            # Weekend multiplier (currently not applied, but calculated)
            # if current_time.weekday() >= 5:  # Saturday = 5, Sunday = 6
            #     bonus = int(bonus * self.WEEKEND_MULTIPLIER)

            self._log_operation(
                "get_time_bonus",
                hour=hour,
                bonus=bonus,
                weekday=current_time.weekday(),
            )

            return bonus

        except Exception as e:
            self._log_error("get_time_bonus", e)
            return 0

    async def track_voice_activity(self, member_id: int, channel_id: int, is_with_others: bool = True) -> None:
        """Track voice activity for a member in a specific channel."""
        try:
            # Get session from unit of work
            if not self.unit_of_work:
                self._log_error(
                    "track_voice_activity",
                    ValueError("No unit of work available"),
                    member_id=member_id,
                    channel_id=channel_id,
                )
                return

            async with self.unit_of_work as uow:
                # Use the existing add_voice_activity method
                await self.add_voice_activity(uow.session, member_id, is_with_others)
                await uow.commit()

                self._log_operation(
                    "track_voice_activity", member_id=member_id, channel_id=channel_id, is_with_others=is_with_others
                )

        except Exception as e:
            self._log_error("track_voice_activity", e, member_id=member_id, channel_id=channel_id)

    async def track_promotion_activity(self, member_id: int) -> None:
        """Track promotion activity for a member."""
        try:
            # Get session from unit of work
            if not self.unit_of_work:
                self._log_error(
                    "track_promotion_activity", ValueError("No unit of work available"), member_id=member_id
                )
                return

            async with self.unit_of_work as uow:
                # Use the existing add_promotion_activity method
                await self.add_promotion_activity(uow.session, member_id)
                await uow.commit()

                self._log_operation("track_promotion_activity", member_id=member_id, points=self.PROMOTION_STATUS)

        except Exception as e:
            self._log_error("track_promotion_activity", e, member_id=member_id)

    async def get_member_activity_summary(self, member_id: int, days_back: int = 7) -> Dict[str, any]:
        """Get a summary of member's activity for profile display."""
        try:
            # Get session from unit of work
            if not self.unit_of_work:
                self._log_error(
                    "get_member_activity_summary", ValueError("No unit of work available"), member_id=member_id
                )
                return None

            async with self.unit_of_work as uow:
                # Use get_member_stats method
                stats = await self.get_member_stats(uow.session, member_id, days_back)

                # Format for profile display
                summary = {
                    "total_points": stats.get("total_points", 0),
                    "ranking_position": stats.get("position", 0),
                    "tier": stats.get("tier", "No Rank"),
                    "days_included": days_back,
                    "breakdown": stats.get("breakdown", {}),
                }

                self._log_operation(
                    "get_member_activity_summary",
                    member_id=member_id,
                    days_back=days_back,
                    total_points=summary["total_points"],
                )

                return summary

        except Exception as e:
            self._log_error("get_member_activity_summary", e, member_id=member_id, days_back=days_back)
            return None
