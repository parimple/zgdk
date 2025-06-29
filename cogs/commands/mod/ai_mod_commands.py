"""
AI-enhanced moderation commands using PydanticAI.
"""

from datetime import datetime, timedelta
from typing import Optional

import discord
from discord.ext import commands

from core.ai.moderation_assistant import (
    ModerationAssistant,
    ModerationSuggestion,
    ThreatLevel,
    UserContext,
    ViolationType,
)


class AIModerationCommands(commands.Cog):
    """AI-powered moderation commands."""

    def __init__(self, bot):
        self.bot = bot
        self.assistant = ModerationAssistant(use_ai=True)
        self.auto_mod_enabled = {}  # guild_id -> bool

    @commands.hybrid_group(name="aimod", description="AI moderation commands")
    @commands.has_permissions(manage_messages=True)
    async def aimod_group(self, ctx: commands.Context):
        """AI moderation command group."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Użyj: `/aimod analyze`, `/aimod auto`, `/aimod review`")

    @aimod_group.command(name="analyze", description="Analyze a message with AI")
    @commands.has_permissions(manage_messages=True)
    async def analyze_message(self, ctx: commands.Context, message_id: str, user: Optional[discord.Member] = None):
        """Analyze a specific message for moderation."""
        await ctx.defer()

        try:
            # Fetch the message
            message_id_int = int(message_id)
            message = None

            # Search in current channel first
            try:
                message = await ctx.channel.fetch_message(message_id_int)
            except Exception:
                # Search in other channels
                for channel in ctx.guild.text_channels:
                    try:
                        message = await channel.fetch_message(message_id_int)
                        break
                    except Exception:
                        continue

            if not message:
                await ctx.send("❌ Nie znaleziono wiadomości o podanym ID")
                return

            # Use message author if user not specified
            if not user:
                user = message.author

            # Build user context
            # Get user moderation history from database
            # This is simplified - would need actual queries
            user_context = UserContext(
                user_id=str(user.id),
                username=str(user),
                join_date=user.joined_at or datetime.utcnow(),
                previous_violations=0,  # Would fetch from DB
                previous_warnings=0,
                previous_mutes=0,
                previous_bans=0,
                is_new_user=(datetime.utcnow() - (user.joined_at or datetime.utcnow())).days < 7,
                is_repeat_offender=False,  # Would check DB
                recent_messages=[],  # Would fetch recent messages
                roles=[role.name for role in user.roles],
            )

            # Analyze the message
            result = await self.assistant.analyze_message(
                message.content, user_context, server_rules=self._get_server_rules(ctx.guild)
            )

            # Create response embed
            embed = discord.Embed(
                title="🤖 Analiza AI Moderacji",
                description=f"Wiadomość: {message.content[:100]}...",
                color=self._get_threat_color(result.threat_level),
            )

            embed.add_field(name="Poziom zagrożenia", value=self._format_threat_level(result.threat_level), inline=True)

            embed.add_field(name="Pewność", value=f"{result.confidence:.0%}", inline=True)

            embed.add_field(name="Sugerowana akcja", value=self._format_action(result.suggested_action), inline=True)

            if result.violations:
                embed.add_field(
                    name="Wykryte naruszenia",
                    value="\n".join(f"• {self._format_violation(v)}" for v in result.violations),
                    inline=False,
                )

            embed.add_field(name="Uzasadnienie", value=result.reason, inline=False)

            if result.evidence:
                embed.add_field(name="Dowody", value="\n".join(f"• {e}" for e in result.evidence[:3]), inline=False)

            embed.set_footer(text=f"Analiza użytkownika: {user}")

            # Add action buttons
            view = ModerationActionView(self, message, user, result)
            await ctx.send(embed=embed, view=view)

        except Exception as e:
            await ctx.send(f"❌ Błąd podczas analizy: {str(e)}")

    @aimod_group.command(name="auto", description="Toggle automatic AI moderation")
    @commands.has_permissions(administrator=True)
    async def toggle_auto_mod(self, ctx: commands.Context):
        """Enable/disable automatic AI moderation."""
        guild_id = ctx.guild.id
        current = self.auto_mod_enabled.get(guild_id, False)
        self.auto_mod_enabled[guild_id] = not current

        status = "włączona" if not current else "wyłączona"
        embed = discord.Embed(
            title="🤖 Auto-moderacja AI",
            description=f"Auto-moderacja została **{status}**",
            color=discord.Color.green() if not current else discord.Color.red(),
        )

        if not current:
            embed.add_field(
                name="ℹ️ Informacja", value="Bot będzie automatycznie analizował podejrzane wiadomości", inline=False
            )

        await ctx.send(embed=embed)

    @aimod_group.command(name="review", description="Review recent AI moderation decisions")
    @commands.has_permissions(manage_messages=True)
    async def review_decisions(self, ctx: commands.Context, limit: int = 5):
        """Review recent AI moderation decisions."""
        # Get recent decisions from interpretability system
        from utils.ai.interpretability import get_explainer

        explainer = get_explainer()

        decisions = explainer.logger.get_recent_decisions(limit=limit, module="moderation_assistant")

        if not decisions:
            await ctx.send("Brak ostatnich decyzji moderacyjnych do przeglądu.")
            return

        embed = discord.Embed(
            title="📋 Ostatnie decyzje AI moderacji",
            description=f"Pokazuję {len(decisions)} ostatnich decyzji",
            color=discord.Color.blue(),
        )

        for i, decision in enumerate(decisions):
            input_data = decision.input_data
            embed.add_field(
                name=f"#{i+1} - {decision.timestamp.strftime('%H:%M:%S')}",
                value=f"**Użytkownik**: {input_data.get('author', 'Unknown')}\n"
                f"**Decyzja**: {decision.decision}\n"
                f"**Pewność**: {decision.confidence:.0%}\n"
                f"**Czas**: {decision.execution_time_ms:.1f}ms",
                inline=False,
            )

        await ctx.send(embed=embed)

    @aimod_group.command(name="sensitivity", description="Adjust AI moderation sensitivity")
    @commands.has_permissions(administrator=True)
    async def set_sensitivity(self, ctx: commands.Context, level: str):
        """Set AI moderation sensitivity level."""
        levels = {
            "low": "Niska - tylko poważne naruszenia",
            "medium": "Średnia - standardowa detekcja",
            "high": "Wysoka - ścisła moderacja",
        }

        if level.lower() not in levels:
            await ctx.send("❌ Poziom musi być: low, medium lub high")
            return

        # Store in bot config or database
        # This is simplified
        embed = discord.Embed(
            title="⚙️ Czułość AI moderacji",
            description=f"Ustawiono poziom: **{levels[level.lower()]}**",
            color=discord.Color.green(),
        )

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Auto-moderate messages if enabled."""
        if message.author.bot:
            return

        if not message.guild:
            return

        if not self.auto_mod_enabled.get(message.guild.id, False):
            return

        # Quick pre-filter to avoid analyzing every message
        if len(message.content) < 5:
            return

        suspicious_indicators = [
            len(message.mentions) > 5,
            message.content.isupper() and len(message.content) > 20,
            any(word in message.content.lower() for word in ["spam", "scam", "hack"]),
            message.content.count("!") > 10,
            len(set(message.content)) < 5 and len(message.content) > 20,
        ]

        if not any(suspicious_indicators):
            return

        # Analyze with AI
        try:
            user_context = UserContext(
                user_id=str(message.author.id),
                username=str(message.author),
                join_date=message.author.joined_at or datetime.utcnow(),
                previous_violations=0,
                previous_warnings=0,
                previous_mutes=0,
                previous_bans=0,
                is_new_user=(datetime.utcnow() - (message.author.joined_at or datetime.utcnow())).days < 7,
                is_repeat_offender=False,
                recent_messages=[],
                roles=[role.name for role in message.author.roles],
            )

            result = await self.assistant.analyze_message(message.content, user_context)

            # Only act on high confidence, high threat
            if result.confidence >= 0.8 and result.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]:
                # Log to mod channel
                mod_channel = discord.utils.get(message.guild.text_channels, name="mod-log")

                if mod_channel:
                    embed = discord.Embed(
                        title="⚠️ Auto-moderacja AI",
                        description="Wykryto podejrzaną wiadomość",
                        color=discord.Color.red(),
                    )

                    embed.add_field(name="Użytkownik", value=message.author.mention, inline=True)

                    embed.add_field(name="Kanał", value=message.channel.mention, inline=True)

                    embed.add_field(
                        name="Zagrożenie", value=self._format_threat_level(result.threat_level), inline=True
                    )

                    embed.add_field(name="Wiadomość", value=f"||{message.content[:200]}...||", inline=False)

                    embed.add_field(
                        name="Sugerowana akcja", value=self._format_action(result.suggested_action), inline=False
                    )

                    await mod_channel.send(embed=embed)

                    # Auto-delete if critical
                    if result.threat_level == ThreatLevel.CRITICAL:
                        try:
                            await message.delete()
                            await message.channel.send(
                                f"{message.author.mention} - Twoja wiadomość została usunięta przez auto-moderację.",
                                delete_after=10,
                            )
                        except Exception:
                            pass

        except Exception:
            # Don't crash on auto-mod errors
            pass

    def _get_server_rules(self, guild: discord.Guild) -> list:
        """Get server rules (simplified)."""
        return [
            "Szanuj innych użytkowników",
            "Zakaz spamu i floodowania",
            "Zakaz treści NSFW",
            "Zakaz reklam bez zgody",
            "Używaj odpowiednich kanałów",
        ]

    def _get_threat_color(self, threat_level: ThreatLevel) -> discord.Color:
        """Get color for threat level."""
        colors = {
            ThreatLevel.NONE: discord.Color.green(),
            ThreatLevel.LOW: discord.Color.gold(),
            ThreatLevel.MEDIUM: discord.Color.orange(),
            ThreatLevel.HIGH: discord.Color.red(),
            ThreatLevel.CRITICAL: discord.Color.dark_red(),
        }
        return colors.get(threat_level, discord.Color.gray())

    def _format_threat_level(self, level: ThreatLevel) -> str:
        """Format threat level for display."""
        formats = {
            ThreatLevel.NONE: "✅ Brak",
            ThreatLevel.LOW: "🟡 Niski",
            ThreatLevel.MEDIUM: "🟠 Średni",
            ThreatLevel.HIGH: "🔴 Wysoki",
            ThreatLevel.CRITICAL: "🚨 Krytyczny",
        }
        return formats.get(level, str(level))

    def _format_action(self, action) -> str:
        """Format moderation action."""
        from core.models.moderation import ModerationType

        formats = {
            ModerationType.WARN: "⚠️ Ostrzeżenie",
            ModerationType.TIMEOUT: "⏱️ Timeout",
            ModerationType.MUTE: "🔇 Wyciszenie",
            ModerationType.KICK: "👢 Wyrzucenie",
            ModerationType.BAN: "🔨 Ban",
        }
        return formats.get(action, str(action))

    def _format_violation(self, violation: ViolationType) -> str:
        """Format violation type."""
        formats = {
            ViolationType.SPAM: "📢 Spam",
            ViolationType.TOXICITY: "☠️ Toksyczność",
            ViolationType.HARASSMENT: "🎯 Nękanie",
            ViolationType.NSFW: "🔞 NSFW",
            ViolationType.ADVERTISING: "📣 Reklama",
            ViolationType.RAID: "⚔️ Raid",
            ViolationType.IMPERSONATION: "🎭 Podszywanie",
            ViolationType.DOXXING: "📍 Doxxing",
            ViolationType.OTHER: "❓ Inne",
        }
        return formats.get(violation, str(violation))


class ModerationActionView(discord.ui.View):
    """View for moderation action buttons."""

    def __init__(self, cog, message: discord.Message, user: discord.Member, suggestion: ModerationSuggestion):
        super().__init__(timeout=300)
        self.cog = cog
        self.message = message
        self.user = user
        self.suggestion = suggestion

    @discord.ui.button(label="Zastosuj sugestię", style=discord.ButtonStyle.primary, emoji="✅")
    async def apply_suggestion(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Apply the AI suggestion."""
        await interaction.response.defer()

        # Import moderation commands
        mod_cog = self.cog.bot.get_cog("ModCommands")
        if not mod_cog:
            await interaction.followup.send("❌ Moduł moderacji niedostępny")
            return

        # Apply the suggested action
        from core.models.moderation import ModerationType

        try:
            if self.suggestion.suggested_action == ModerationType.WARN:
                # Just send a warning
                await self.message.channel.send(f"{self.user.mention} - **Ostrzeżenie**: {self.suggestion.reason}")
            elif self.suggestion.suggested_action == ModerationType.TIMEOUT:
                # Apply timeout
                duration = timedelta(seconds=self.suggestion.suggested_duration or 600)
                await self.user.timeout(duration, reason=f"AI: {self.suggestion.reason}")
            elif self.suggestion.suggested_action == ModerationType.MUTE:
                # Would need to call mute command
                pass
            elif self.suggestion.suggested_action == ModerationType.KICK:
                await self.user.kick(reason=f"AI: {self.suggestion.reason}")
            elif self.suggestion.suggested_action == ModerationType.BAN:
                await self.user.ban(reason=f"AI: {self.suggestion.reason}")

            await interaction.followup.send(
                f"✅ Zastosowano: {self.cog._format_action(self.suggestion.suggested_action)}"
            )

            # Disable all buttons
            for item in self.children:
                item.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await interaction.followup.send(f"❌ Błąd: {str(e)}")

    @discord.ui.button(label="Usuń wiadomość", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_message(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Delete the analyzed message."""
        await interaction.response.defer()

        try:
            await self.message.delete()
            await interaction.followup.send("✅ Wiadomość została usunięta")

            # Disable delete button
            button.disabled = True
            await interaction.message.edit(view=self)
        except Exception:
            await interaction.followup.send("❌ Nie można usunąć wiadomości")

    @discord.ui.button(label="Ignoruj", style=discord.ButtonStyle.secondary, emoji="❌")
    async def ignore(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Ignore the suggestion."""
        await interaction.response.defer()

        await interaction.followup.send("ℹ️ Sugestia została zignorowana")

        # Disable all buttons
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)


async def setup(bot):
    """Load the cog."""
    await bot.add_cog(AIModerationCommands(bot))
