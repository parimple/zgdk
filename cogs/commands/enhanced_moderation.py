"""
Enhanced moderation commands with PydanticAI integration.
"""

import logging
from typing import Optional

import discord
from discord.ext import commands

from core.ai.duration_parser import DurationParser
from core.ai.moderation_assistant import ModerationAssistant, UserContext
from core.interfaces.member_interfaces import IModerationService
from core.models.moderation import ModerationAction, ModerationType, TimeoutRequest
from utils.permissions import is_mod_or_admin

logger = logging.getLogger(__name__)


class EnhancedModerationCommands(commands.Cog):
    """Enhanced moderation with AI assistance."""

    def __init__(self, bot):
        """Initialize enhanced moderation."""
        self.bot = bot
        self.duration_parser = DurationParser(use_ai=True)
        self.mod_assistant = ModerationAssistant(use_ai=True)

    @commands.hybrid_command(name="timeout_ai", description="Wycisz członka używając naturalnego języka")
    @commands.guild_only()
    @is_mod_or_admin()
    async def timeout_ai(
        self, ctx: commands.Context, member: discord.Member, duration: str, *, reason: str = "Brak podanego powodu"
    ):
        """
        Wycisz członka z czasem parsowanym przez AI.

        Przykłady:
        - /timeout_ai @user do jutra spam
        - /timeout_ai @user na 2 godziny zakłócanie
        - /timeout_ai @user 1 dzień naruszenie regulaminu
        """
        await ctx.defer()

        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            await ctx.send("❌ Nie możesz wyciszyć kogoś z równą lub wyższą rolą.")
            return

        try:
            # Parse duration with AI
            enhanced_duration = await self.duration_parser.parse(duration)

            # Create timeout request
            timeout_req = TimeoutRequest(
                target_id=str(member.id),
                moderator_id=str(ctx.author.id),
                guild_id=str(ctx.guild.id),
                reason=reason,
                duration_seconds=enhanced_duration.seconds,
            )

            # Show what AI understood
            embed = discord.Embed(title="⏰ Potwierdzenie Wyciszenia", color=discord.Color.orange())
            embed.add_field(name="Członek", value=member.mention, inline=True)
            embed.add_field(name="Czas trwania", value=enhanced_duration.human_readable, inline=True)
            embed.add_field(name="Wygasa", value=f"<t:{int(enhanced_duration.expires_at.timestamp())}:R>", inline=True)
            embed.add_field(name="Powód", value=reason, inline=False)

            if enhanced_duration.confidence < 1.0:
                embed.add_field(
                    name="Interpretacja AI",
                    value=f"{enhanced_duration.interpretation} (Pewność: {enhanced_duration.confidence:.0%})",
                    inline=False,
                )

            # Apply timeout
            try:
                await member.timeout(
                    discord.utils.utcnow() + discord.timedelta(seconds=enhanced_duration.seconds),
                    reason=f"{reason} | By {ctx.author}",
                )

                embed.set_footer(text="✅ Wyciszenie zastosowane pomyślnie")
                await ctx.send(embed=embed)

                # Log to moderation service
                async with self.bot.get_db() as session:
                    mod_service = await self.bot.get_service(IModerationService, session)
                    await mod_service.log_moderation_action(
                        ModerationType.TIMEOUT, str(member.id), str(ctx.author.id), reason, enhanced_duration.seconds
                    )

            except discord.HTTPException as e:
                embed.set_footer(text=f"❌ Błąd: {str(e)}")
                embed.color = discord.Color.red()
                await ctx.send(embed=embed)

        except ValueError as e:
            await ctx.send(f"❌ Nie mogę przetworzyć czasu '{duration}': {str(e)}")
        except Exception as e:
            logger.error(f"Error in timeout_ai: {e}")
            await ctx.send(f"❌ Wystąpił błąd: {str(e)}")

    @commands.hybrid_command(name="analizuj_wiadomosc", description="Analizuj wiadomość pod kątem naruszeń (tylko Mod)")
    @commands.guild_only()
    @is_mod_or_admin()
    async def analyze_message(self, ctx: commands.Context, message_id: str):
        """Analizuj wiadomość z AI do moderacji."""
        await ctx.defer(ephemeral=True)

        try:
            # Try to fetch the message
            message = None
            for channel in ctx.guild.text_channels:
                try:
                    message = await channel.fetch_message(int(message_id))
                    break
                except:
                    continue

            if not message:
                await ctx.send("❌ Nie mogę znaleźć wiadomości o tym ID.", ephemeral=True)
                return

            # Build user context
            user_context = UserContext(
                user_id=str(message.author.id),
                username=str(message.author),
                join_date=message.author.joined_at or message.author.created_at,
                is_new_user=(message.author.joined_at and (discord.utils.utcnow() - message.author.joined_at).days < 7),
                roles=[role.name for role in message.author.roles],
            )

            # Get recent messages for context
            recent = []
            async for msg in message.channel.history(limit=10, before=message):
                if msg.author == message.author:
                    recent.append(msg.content)
            user_context.recent_messages = recent[:5]

            # Analyze with AI
            analysis = await self.mod_assistant.analyze_message(message.content, user_context)

            # Create result embed
            embed = discord.Embed(
                title="🔍 Analiza Wiadomości",
                description=f"Wiadomość od {message.author.mention} w {message.channel.mention}",
                color=self._get_threat_color(analysis.threat_level),
            )

            # Message content (truncated if needed)
            content = message.content[:1000] + "..." if len(message.content) > 1000 else message.content
            embed.add_field(name="Treść Wiadomości", value=f"```{content}```", inline=False)

            # Analysis results
            embed.add_field(
                name="Poziom Zagrożenia",
                value=f"{self._get_threat_emoji(analysis.threat_level)} {analysis.threat_level.value.upper()}",
                inline=True,
            )

            embed.add_field(name="Pewność", value=f"{analysis.confidence:.0%}", inline=True)

            if analysis.violations:
                embed.add_field(
                    name="Wykryte Naruszenia", value=", ".join(v.value for v in analysis.violations), inline=False
                )

            embed.add_field(
                name="Sugerowana Akcja",
                value=f"{analysis.suggested_action.value} {analysis.duration_text if analysis.suggested_duration else ''}",
                inline=True,
            )

            embed.add_field(name="Powód", value=analysis.reason, inline=False)

            if analysis.evidence:
                embed.add_field(name="Dowody", value="\n".join(f"• {e}" for e in analysis.evidence[:3]), inline=False)

            # Add action buttons if high threat
            if analysis.is_immediate_action_needed:
                embed.set_footer(text="⚠️ Zalecana natychmiastowa akcja!")

            await ctx.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error analyzing message: {e}")
            await ctx.send(f"❌ Błąd: {str(e)}", ephemeral=True)

    def _get_threat_color(self, threat_level) -> discord.Color:
        """Get color based on threat level."""
        colors = {
            "none": discord.Color.green(),
            "low": discord.Color.gold(),
            "medium": discord.Color.orange(),
            "high": discord.Color.red(),
            "critical": discord.Color.dark_red(),
        }
        return colors.get(threat_level.value, discord.Color.greyple())

    def _get_threat_emoji(self, threat_level) -> str:
        """Get emoji for threat level."""
        emojis = {"none": "✅", "low": "⚠️", "medium": "🔶", "high": "🔴", "critical": "🚨"}
        return emojis.get(threat_level.value, "❓")

    @commands.hybrid_command(name="parsuj_czas", description="Testuj parsowanie czasu AI")
    async def parse_duration_test(self, ctx: commands.Context, *, duration: str):
        """Testuj parsowanie czasu."""
        await ctx.defer()

        try:
            result = await self.duration_parser.parse(duration)

            embed = discord.Embed(title="⏱️ Wynik Parsowania Czasu", color=discord.Color.blue())
            embed.add_field(name="Wejście", value=f"`{duration}`", inline=False)
            embed.add_field(name="Sekundy", value=f"{result.seconds:,}", inline=True)
            embed.add_field(name="Czytelny Format", value=result.human_readable, inline=True)
            embed.add_field(name="Wygasa", value=f"<t:{int(result.expires_at.timestamp())}:F>", inline=False)

            if result.confidence < 1.0:
                embed.add_field(
                    name="Szczegóły AI",
                    value=f"Interpretacja: {result.interpretation}\nPewność: {result.confidence:.0%}",
                    inline=False,
                )

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Parsowanie nieudane: {str(e)}")


async def setup(bot):
    """Setup enhanced moderation commands."""
    await bot.add_cog(EnhancedModerationCommands(bot))
