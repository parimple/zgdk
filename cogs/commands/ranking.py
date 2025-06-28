"""Ranking commands for the activity/points system."""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.interfaces import IActivityTrackingService, IPermissionService
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class RankingCommands(commands.Cog):
    """Commands for checking rankings and activity stats."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.message_sender = MessageSender(bot)

    @commands.Cog.listener()
    async def on_ready(self):
        """Set guild when bot is ready."""
        # Activity service will be fetched when needed with session
        pass

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
            logger.info(f"Getting leaderboard for {days} days, limit {limit}")
            
            async with self.bot.get_db() as session:
                # Get activity service with session
                activity_service = await self.bot.get_service(IActivityTrackingService, session)
                
                if not activity_service:
                    logger.error("Activity service is None")
                    await ctx.send("❌ Usługa aktywności nie jest dostępna.", ephemeral=True)
                    return
                
                leaderboard = await activity_service.get_leaderboard(
                    session, limit, days
                )
                logger.info(f"Leaderboard result: {len(leaderboard) if leaderboard else 0} entries")

            if not leaderboard:
                embed = self.message_sender._create_embed(
                    title="🏆 Ranking Aktywności",
                    description="Brak danych aktywności w tym okresie.",
                    color="error",
                    ctx=ctx
                )
                await self.message_sender._send_embed(ctx, embed)
                return

            # Format leaderboard into embed using MessageSender
            embed = self._format_leaderboard_embed(leaderboard, ctx, days)
            await self.message_sender._send_embed(ctx, embed)

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
                # Get activity service with session
                activity_service = await self.bot.get_service(IActivityTrackingService, session)
                
                if not activity_service:
                    logger.error("Activity service is None")
                    await ctx.send("❌ Usługa aktywności nie jest dostępna.", ephemeral=True)
                    return
                    
                stats = await activity_service.get_member_stats(
                    session, target_member.id, days
                )

            # Format stats like ,vc command - description only
            if stats["position"] > 0:
                base_text = f"**Profil:** {target_member.display_name}\n"
                base_text += f"**🏆 Pozycja:** #{stats['position']} • **🏅 Ranga:** {stats['tier']} • **⭐ Punkty:** {stats['total_points']} pkt"
                
                # Add activity breakdown if available
                activity_lines = []
                if stats.get("text_points", 0) > 0:
                    activity_lines.append(f"💬 Wiadomości: {stats['text_points']} pkt")
                if stats.get("voice_points", 0) > 0:
                    activity_lines.append(f"🎤 Głosowe: {stats['voice_points']} pkt")
                if stats.get("promotion_points", 0) > 0:
                    activity_lines.append(f"📢 Promocja: {stats['promotion_points']} pkt")
                
                if activity_lines:
                    base_text += "\n**📊 Aktywność:** " + " • ".join(activity_lines)
            else:
                base_text = f"**Profil:** {target_member.display_name}\nBrak punktów w rankingu w tym okresie."
            
            # Create embed with only description
            embed = self.message_sender._create_embed(
                description=base_text,
                ctx=ctx
            )
            
            # Add premium text
            _, premium_text = self.message_sender._get_premium_text(ctx)
            if premium_text:
                embed.description = f"{embed.description}\n{premium_text}"
            
            await self.message_sender._send_embed(ctx, embed)

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
                # Get activity service with session
                activity_service = await self.bot.get_service(IActivityTrackingService, session)
                
                if not activity_service:
                    logger.error("Activity service is None")
                    await ctx.send("❌ Usługa aktywności nie jest dostępna.", ephemeral=True)
                    return
                    
                stats = await activity_service.get_member_stats(
                    session, ctx.author.id, days
                )

            # Use member's color if available, otherwise blue
            color = (
                ctx.author.color
                if ctx.author.color.value != 0
                else discord.Color.blue()
            )

            # Format my rank like ,vc command - description only
            if stats["position"] > 0:
                base_text = f"**🏆 Pozycja:** #{stats['position']} • **🏅 Ranga:** {stats['tier']}\n**⭐ Punkty:** {stats['total_points']} pkt"
            else:
                base_text = "Nie masz jeszcze punktów w rankingu w tym okresie."
            
            # Create embed with only description, no title
            embed = self.message_sender._create_embed(
                description=base_text,
                ctx=ctx
            )
            
            # Add premium text
            _, premium_text = self.message_sender._get_premium_text(ctx)
            if premium_text:
                embed.description = f"{embed.description}\n{premium_text}"
            
            await self.message_sender._send_embed(ctx, embed)

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
                # Get activity service with session
                activity_service = await self.bot.get_service(IActivityTrackingService, session)
                
                if not activity_service:
                    logger.error("Activity service is None")
                    await ctx.send("❌ Usługa aktywności nie jest dostępna.", ephemeral=True)
                    return
                    
                leaderboard = await activity_service.get_leaderboard(
                    session, limit, days
                )

            if not leaderboard:
                embed = self.message_sender._create_embed(
                    title=f"🏆 TOP {category}",
                    description="Brak danych aktywności w tym okresie.",
                    color="error",
                    ctx=ctx
                )
                await self.message_sender._send_embed(ctx, embed)
                return

            # Group by tiers
            tier_100 = [x for x in leaderboard if x[2] <= 100]
            tier_200 = [x for x in leaderboard if 101 <= x[2] <= 200]
            tier_300 = [x for x in leaderboard if 201 <= x[2] <= 300]

            # Build fields for embed
            fields = []
            
            if category == "100" or category == "all":
                if tier_100:
                    top_10 = tier_100[:10]
                    text = "\n".join(
                        [
                            f"**{pos}.** {ctx.guild.get_member(mid).display_name if ctx.guild.get_member(mid) else f'User {mid}'} - {pts} pkt"
                            for mid, pts, pos in top_10
                        ]
                    )
                    fields.append(("🥇 TOP 100", text, False))

            if category == "200" or category == "all":
                if tier_200:
                    sample = tier_200[:5]
                    text = "\n".join(
                        [
                            f"**{pos}.** {ctx.guild.get_member(mid).display_name if ctx.guild.get_member(mid) else f'User {mid}'} - {pts} pkt"
                            for mid, pts, pos in sample
                        ]
                    )
                    fields.append(("🥈 Ranga 200 (101-200)", text, False))

            if category == "300" or category == "all":
                if tier_300:
                    sample = tier_300[:5]
                    text = "\n".join(
                        [
                            f"**{pos}.** {ctx.guild.get_member(mid).display_name if ctx.guild.get_member(mid) else f'User {mid}'} - {pts} pkt"
                            for mid, pts, pos in sample
                        ]
                    )
                    fields.append(("🥉 Ranga 300 (201-300)", text, False))

            # Summary
            fields.append((
                "📊 Podsumowanie",
                f"🥇 Ranga 100: {len(tier_100)} osób\n"
                f"🥈 Ranga 200: {len(tier_200)} osób\n"
                f"🥉 Ranga 300: {len(tier_300)} osób\n"
                f"📊 Łącznie: {len(leaderboard)} osób",
                False
            ))

            # Create embed with MessageSender
            embed = self.message_sender._create_embed(
                title=f"🏆 TOP {category} zaGadki",
                description=f"📌 **Najlepsi użytkownicy z ostatnich {days} dni**",
                fields=fields,
                footer=f"💡 Aktualizacja: co godzinę | Dane z ostatnich {days} dni",
                ctx=ctx
            )
            
            # Add premium text
            _, premium_text = self.message_sender._get_premium_text(ctx)
            if premium_text:
                embed.description = f"{embed.description}\n{premium_text}"
            
            if ctx.guild.icon:
                embed.set_footer(
                    text=f"💡 Aktualizacja: co godzinę | Dane z ostatnich {days} dni",
                    icon_url=ctx.guild.icon.url
                )
                
            await self.message_sender._send_embed(ctx, embed)

        except Exception as e:
            logger.error(f"Error in top command: {e}")
            await ctx.send(
                "❌ Wystąpił błąd podczas pobierania rankingu.", ephemeral=True
            )

    # Admin commands
    @commands.hybrid_command(name="reset_daily_points")
    @commands.check(lambda ctx: ctx.cog.permission_service and ctx.cog.permission_service.is_owner(ctx.author) if hasattr(ctx.cog, 'permission_service') else False)
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
    @commands.check(lambda ctx: ctx.cog.permission_service and ctx.cog.permission_service.is_owner(ctx.author) if hasattr(ctx.cog, 'permission_service') else False)
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


    def _format_leaderboard_embed(self, leaderboard, ctx, days):
        """Format leaderboard data into embed using MessageSender."""
        # Build leaderboard text
        leaderboard_text = []
        for i, (member_id, points, position) in enumerate(leaderboard[:10]):
            member = ctx.guild.get_member(member_id)
            member_name = member.display_name if member else f"User {member_id}"
            
            # Add medal emojis for top 3
            if position == 1:
                leaderboard_text.append(f"🥇 {member_name} - **{points}** pkt")
            elif position == 2:
                leaderboard_text.append(f"🥈 {member_name} - **{points}** pkt")
            elif position == 3:
                leaderboard_text.append(f"🥉 {member_name} - **{points}** pkt")
            else:
                leaderboard_text.append(f"**{position}.** {member_name} - **{points}** pkt")
        
        # Calculate statistics
        total_points = sum(points for _, points, _ in leaderboard)
        avg_points = total_points // len(leaderboard) if leaderboard else 0
        
        # Create fields
        fields = [
            ("🎯 TOP 10", "\\n".join(leaderboard_text) if leaderboard_text else "Brak danych", False),
            ("📊 Statystyki", 
             f"Łącznie aktywnych: **{len(leaderboard)}** osób\\n"
             f"Średnia punktów: **{avg_points}** pkt\\n"
             f"Suma wszystkich punktów: **{total_points}** pkt", True),
            ("🏅 System rang",
             "🥇 **1-100**: Ranga 100\\n"
             "🥈 **101-200**: Ranga 200\\n"
             "🥉 **201-300**: Ranga 300", True)
        ]
        
        # Create embed with MessageSender
        embed = self.message_sender._create_embed(
            title="🏆 Ranking Aktywności zaGadki",
            description=f"📌 **Najaktywniejsi członkowie serwera z ostatnich {days} dni**",
            fields=fields,
            footer=f"💡 Aktualizacja: co godzinę | ID: {ctx.author.id}",
            ctx=ctx
        )
        
        # Add premium text
        _, premium_text = self.message_sender._get_premium_text(ctx)
        if premium_text:
            embed.description = f"{embed.description}\n{premium_text}"
        
        # Add guild icon as thumbnail
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
            
        return embed

    def _format_member_stats_embed(self, stats, member, ctx):
        """Format member stats into embed using MessageSender."""
        # Build activity breakdown
        activity_breakdown = []
        if stats.get("text_points", 0) > 0:
            activity_breakdown.append(f"💬 Wiadomości tekstowe: **{stats['text_points']}** pkt")
        if stats.get("voice_points", 0) > 0:
            activity_breakdown.append(f"🎤 Aktywność głosowa: **{stats['voice_points']}** pkt")
        if stats.get("promotion_points", 0) > 0:
            activity_breakdown.append(f"📢 Promocja serwera: **{stats['promotion_points']}** pkt")
        
        # Create fields
        fields = []
        if stats["position"] > 0:
            fields.extend([
                ("🏆 Pozycja w rankingu", f"**#{stats['position']}**", True),
                ("🏅 Ranga", f"**{stats['tier']}**", True),
                ("⭐ Łączne punkty", f"**{stats['total_points']}** pkt", True)
            ])
        
        if activity_breakdown:
            fields.append(("📈 Podział punktów według aktywności", "\\n".join(activity_breakdown), False))
        
        # Create embed
        embed = self.message_sender._create_embed(
            title="📊 Statystyki aktywności zaGadki",
            description=f"**Profil użytkownika:** {member.display_name}",
            fields=fields,
            ctx=ctx
        )
        
        # Add premium text
        _, premium_text = self.message_sender._get_premium_text(ctx)
        if premium_text:
            embed.description = f"{embed.description}\n{premium_text}"
        
        # Add member avatar as thumbnail
        embed.set_thumbnail(url=member.display_avatar.url)
        
        return embed


async def setup(bot: commands.Bot):
    """Set up the cog."""
    await bot.add_cog(RankingCommands(bot))
