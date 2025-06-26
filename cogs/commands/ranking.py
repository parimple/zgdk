"""Ranking commands for the activity/points system."""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.interfaces.member_interfaces import (
    IActivityService,
    IMemberService,
)
from utils.managers import ActivityManager
from utils.message_sender import MessageSender
from utils.permissions import is_zagadka_owner, is_mod_or_admin, is_mod_or_admin
from core.interfaces.member_interfaces import (
    IActivityService,
    IMemberService,
)
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class RankingCommands(commands.Cog):
    """Commands for checking rankings and activity stats."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.activity_manager = ActivityManager()

    @commands.Cog.listener()
    async def on_ready(self):
        """Set guild when bot is ready."""
        if self.bot.guild:
            self.activity_manager.set_guild(self.bot.guild)

    @commands.hybrid_command(
        name="ranking", description="Pokaż ranking aktywności serwera"
    )
    @app_commands.describe(
        days="Liczba dni wstecz (domyślnie 7)",
        limit="Liczba użytkowników do pokazania (domyślnie 10)",
    )
    async def ranking(self, ctx: commands.Context, days: int = 7, limit: int = 10):
        """Show activity ranking leaderboard."""
        await ctx.defer()

        # Validate input
        if days < 1 or days > 30:
            await ctx.send("❌ Liczba dni musi być między 1 a 30.", ephemeral=True)
            return

        if limit < 1 or limit > 50:
            await ctx.send("❌ Limit musi być między 1 a 50.", ephemeral=True)
            return

        try:
            async with self.bot.get_db() as session:
                leaderboard = await self.activity_manager.get_leaderboard(
                    session, limit, days
                )

            if not leaderboard:
                embed = discord.Embed(
                    title="🏆 Ranking Aktywności",
                    description="Brak danych aktywności w tym okresie.",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed)
                return

            embed = self.activity_manager.format_leaderboard_embed(
                leaderboard, ctx.guild, days, ctx.author.color
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in ranking command: {e}")
            await ctx.send(
                "❌ Wystąpił błąd podczas pobierania rankingu.", ephemeral=True
            )

    @commands.hybrid_command(
        name="stats", description="Pokaż swoje statystyki aktywności"
    )
    @app_commands.describe(
        member="Użytkownik do sprawdzenia (domyślnie Ty)",
        days="Liczba dni wstecz (domyślnie 7)",
    )
    async def stats(
        self, ctx: commands.Context, member: discord.Member = None, days: int = 7
    ):
        """Show activity stats for a member."""
        await ctx.defer()

        target_member = member or ctx.author

        # Validate input
        if days < 1 or days > 30:
            await ctx.send("❌ Liczba dni musi być między 1 a 30.", ephemeral=True)
            return

        try:
            async with self.bot.get_db() as session:
                stats = await self.activity_manager.get_member_stats(
                    session, target_member.id, days
                )

            embed = self.activity_manager.format_member_stats_embed(
                stats, target_member
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await ctx.send(
                "❌ Wystąpił błąd podczas pobierania statystyk.", ephemeral=True
            )

    @commands.hybrid_command(
        name="my_rank", description="Pokaż swoją pozycję w rankingu"
    )
    @app_commands.describe(days="Liczba dni wstecz (domyślnie 7)")
    async def my_rank(self, ctx: commands.Context, days: int = 7):
        """Show your current ranking position."""
        await ctx.defer()

        # Validate input
        if days < 1 or days > 30:
            await ctx.send("❌ Liczba dni musi być między 1 a 30.", ephemeral=True)
            return

        try:
            async with self.bot.get_db() as session:
                stats = await self.activity_manager.get_member_stats(
                    session, ctx.author.id, days
                )

            # Use member's color if available, otherwise blue
            color = (
                ctx.author.color
                if ctx.author.color.value != 0
                else discord.Color.blue()
            )

            embed = discord.Embed(
                title=f"📊 Twoja pozycja w rankingu zaGadki", color=color
            )

            if stats["position"] > 0:
                embed.add_field(
                    name="🏆 Pozycja", value=f"**#{stats['position']}**", inline=True
                )
                embed.add_field(
                    name="🏅 Ranga", value=f"**{stats['tier']}**", inline=True
                )
                embed.add_field(
                    name="⭐ Punkty",
                    value=f"**{stats['total_points']}** pkt",
                    inline=True,
                )
            else:
                embed.description = "Nie masz jeszcze punktów w rankingu w tym okresie."

            embed.set_thumbnail(url=ctx.author.display_avatar.url)
            embed.set_footer(
                text=f"💡 Dane z ostatnich {days} dni | ID: {ctx.author.id}",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in my_rank command: {e}")
            await ctx.send(
                "❌ Wystąpił błąd podczas pobierania pozycji.", ephemeral=True
            )

    @commands.hybrid_command(
        name="top", description="Pokaż TOP użytkowników w różnych kategoriach"
    )
    @app_commands.describe(
        category="Kategoria rankingu", days="Liczba dni wstecz (domyślnie 7)"
    )
    @app_commands.choices(
        category=[
            app_commands.Choice(name="TOP 100", value="100"),
            app_commands.Choice(name="TOP 200", value="200"),
            app_commands.Choice(name="TOP 300", value="300"),
            app_commands.Choice(name="Wszyscy", value="all"),
        ]
    )
    async def top(self, ctx: commands.Context, category: str = "100", days: int = 7):
        """Show TOP users in different categories."""
        await ctx.defer()

        # Validate input
        if days < 1 or days > 30:
            await ctx.send("❌ Liczba dni musi być między 1 a 30.", ephemeral=True)
            return

        # Determine limit based on category
        limits = {"100": 100, "200": 200, "300": 300, "all": 1000}
        limit = limits.get(category, 100)

        try:
            async with self.bot.get_db() as session:
                leaderboard = await self.activity_manager.get_leaderboard(
                    session, limit, days
                )

            if not leaderboard:
                embed = discord.Embed(
                    title=f"🏆 TOP {category}",
                    description="Brak danych aktywności w tym okresie.",
                    color=discord.Color.red(),
                )
                await ctx.send(embed=embed)
                return

            # Group by tiers
            tier_100 = [x for x in leaderboard if x[2] <= 100]
            tier_200 = [x for x in leaderboard if 101 <= x[2] <= 200]
            tier_300 = [x for x in leaderboard if 201 <= x[2] <= 300]

            # Use author's color if available, otherwise blue
            color = (
                ctx.author.color
                if ctx.author.color.value != 0
                else discord.Color.blue()
            )

            embed = discord.Embed(
                title=f"🏆 TOP {category} zaGadki",
                description=f"📌 **Najlepsi użytkownicy z ostatnich {days} dni**",
                color=color,
            )

            if category == "100" or category == "all":
                if tier_100:
                    top_10 = tier_100[:10]
                    text = "\n".join(
                        [
                            f"**{pos}.** {ctx.guild.get_member(mid).display_name if ctx.guild.get_member(mid) else f'User {mid}'} - {pts} pkt"
                            for mid, pts, pos in top_10
                        ]
                    )
                    embed.add_field(name="🥇 TOP 100", value=text, inline=False)

            if category == "200" or category == "all":
                if tier_200:
                    sample = tier_200[:5]
                    text = "\n".join(
                        [
                            f"**{pos}.** {ctx.guild.get_member(mid).display_name if ctx.guild.get_member(mid) else f'User {mid}'} - {pts} pkt"
                            for mid, pts, pos in sample
                        ]
                    )
                    embed.add_field(
                        name="🥈 Ranga 200 (101-200)", value=text, inline=False
                    )

            if category == "300" or category == "all":
                if tier_300:
                    sample = tier_300[:5]
                    text = "\n".join(
                        [
                            f"**{pos}.** {ctx.guild.get_member(mid).display_name if ctx.guild.get_member(mid) else f'User {mid}'} - {pts} pkt"
                            for mid, pts, pos in sample
                        ]
                    )
                    embed.add_field(
                        name="🥉 Ranga 300 (201-300)", value=text, inline=False
                    )

            # Summary
            embed.add_field(
                name="📊 Podsumowanie",
                value=f"🥇 Ranga 100: {len(tier_100)} osób\n"
                f"🥈 Ranga 200: {len(tier_200)} osób\n"
                f"🥉 Ranga 300: {len(tier_300)} osób\n"
                f"📊 Łącznie: {len(leaderboard)} osób",
                inline=False,
            )

            embed.set_footer(
                text=f"💡 Aktualizacja: co godzinę | Dane z ostatnich {days} dni",
                icon_url=ctx.guild.icon.url if ctx.guild.icon else None,
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Error in top command: {e}")
            await ctx.send(
                "❌ Wystąpił błąd podczas pobierania rankingu.", ephemeral=True
            )

    # Admin commands
    @commands.hybrid_command(name="reset_daily_points")
    @is_zagadka_owner()
    async def reset_daily_points(
        self, ctx: commands.Context, activity_type: str = None
    ):
        """Reset daily points for specific activity type or all."""
        await ctx.defer(ephemeral=True)

        try:
            from datasources.queries import reset_daily_activity_points

            async with self.bot.get_db() as session:
                await reset_daily_activity_points(session, activity_type)
                await session.commit()

            type_text = f" for {activity_type}" if activity_type else ""
            await ctx.send(f"✅ Reset daily points{type_text}.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error resetting daily points: {e}")
            await ctx.send(f"❌ Error resetting points: {e}", ephemeral=True)

    @commands.hybrid_command(name="cleanup_old_activity")
    @is_zagadka_owner()
    async def cleanup_old_activity(self, ctx: commands.Context, days_to_keep: int = 30):
        """Clean up old activity data."""
        await ctx.defer(ephemeral=True)

        if days_to_keep < 7:
            await ctx.send("❌ Minimum 7 days to keep.", ephemeral=True)
            return

        try:
            from datasources.queries import cleanup_old_activity_data

            async with self.bot.get_db() as session:
                deleted_count = await cleanup_old_activity_data(session, days_to_keep)
                await session.commit()

            await ctx.send(
                f"✅ Deleted {deleted_count} old activity records.", ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error cleaning up activity data: {e}")
            await ctx.send(f"❌ Error cleaning up data: {e}", ephemeral=True)


async def setup(bot: commands.Bot):
    """Set up the cog."""
    await bot.add_cog(RankingCommands(bot))
