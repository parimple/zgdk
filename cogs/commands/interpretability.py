"""
Interpretability commands for understanding bot decisions.
"""

import discord
from discord.ext import commands
from typing import Optional

from core.interpretability import (
    DecisionLogger, 
    ActionExplainer, 
    ExplanationLevel,
    CommandTracer
)


class InterpretabilityCog(commands.Cog, name="Interpretability"):
    """Commands for understanding bot decisions and behavior."""
    
    def __init__(self, bot):
        self.bot = bot
        self.decision_logger = DecisionLogger()
        self.explainer = ActionExplainer(bot)
        self.tracer = CommandTracer(bot)
        
        # Inject into bot for global access
        bot.decision_logger = self.decision_logger
        bot.explainer = self.explainer
        bot.tracer = self.tracer
    
    @commands.hybrid_group(name="explain", description="Wyjaśnij decyzje bota")
    async def explain(self, ctx: commands.Context):
        """Base command for explanations."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
    
    @explain.command(name="last", description="Wyjaśnij ostatnią decyzję")
    async def explain_last(
        self,
        ctx: commands.Context,
        level: Optional[str] = "simple"
    ):
        """Explain the last decision made for the user."""
        # Get explanation level
        try:
            explanation_level = ExplanationLevel(level.lower())
        except ValueError:
            await ctx.send(
                f"❌ Nieprawidłowy poziom. Dostępne: simple, detailed, technical"
            )
            return
        
        # Get user's last decision
        user_decisions = self.decision_logger.get_user_decisions(
            str(ctx.author.id), 
            limit=1
        )
        
        if not user_decisions:
            await ctx.send("📊 Nie znaleziono żadnych decyzji dla Ciebie.")
            return
        
        decision = user_decisions[0]
        await self.explainer.send_explanation(
            ctx, 
            decision, 
            level=explanation_level,
            ephemeral=False
        )
    
    @explain.command(name="command", description="Wyjaśnij decyzje dla komendy")
    @commands.has_permissions(administrator=True)
    async def explain_command(
        self,
        ctx: commands.Context,
        command_name: str,
        limit: int = 5
    ):
        """Explain recent decisions for a specific command."""
        decisions = self.decision_logger.get_command_decisions(
            command_name,
            limit=limit
        )
        
        if not decisions:
            await ctx.send(f"📊 Nie znaleziono decyzji dla komendy: {command_name}")
            return
        
        # Create summary embed
        embed = discord.Embed(
            title=f"📊 Ostatnie decyzje dla: {command_name}",
            description=f"Pokazuję ostatnie {len(decisions)} decyzji",
            color=discord.Color.blue()
        )
        
        for i, decision in enumerate(decisions, 1):
            embed.add_field(
                name=f"{i}. {decision.action}",
                value=(
                    f"**Użytkownik:** <@{decision.user_id}>\n"
                    f"**Wynik:** {decision.result}\n"
                    f"**Powód:** {decision.reason[:50]}..."
                ),
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_group(name="trace", description="Śledź wykonanie komend")
    @commands.has_permissions(administrator=True)
    async def trace(self, ctx: commands.Context):
        """Base command for tracing."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
    
    @trace.command(name="active", description="Pokaż aktywne śledzenia")
    async def trace_active(self, ctx: commands.Context):
        """Show currently active traces."""
        active_traces = self.tracer.get_active_traces()
        
        if not active_traces:
            await ctx.send("🔍 Brak aktywnych śledzeń.")
            return
        
        embed = discord.Embed(
            title="🔍 Aktywne śledzenia",
            description=f"Obecnie śledzone: {len(active_traces)}",
            color=discord.Color.green()
        )
        
        for trace in active_traces[:5]:  # Show max 5
            embed.add_field(
                name=f"{trace['command']}",
                value=(
                    f"**User:** <@{trace['user_id']}>\n"
                    f"**Duration:** {trace['total_duration_ms']:.1f}ms\n"
                    f"**Steps:** {trace['steps_count']}"
                ),
                inline=True
            )
        
        await ctx.send(embed=embed)
    
    @trace.command(name="recent", description="Pokaż ostatnie śledzenia")
    async def trace_recent(self, ctx: commands.Context, limit: int = 5):
        """Show recent completed traces."""
        recent_traces = self.tracer.get_recent_traces(limit=limit)
        
        if not recent_traces:
            await ctx.send("🔍 Brak zapisanych śledzeń.")
            return
        
        embed = discord.Embed(
            title="🔍 Ostatnie śledzenia",
            description=f"Pokazuję ostatnie {len(recent_traces)} wykonań",
            color=discord.Color.blue()
        )
        
        for trace in recent_traces:
            # Find slowest step
            slowest_step = max(
                trace['steps'], 
                key=lambda s: s['duration_ms'] or 0
            ) if trace['steps'] else None
            
            embed.add_field(
                name=f"{trace['command']} ({trace['total_duration_ms']:.1f}ms)",
                value=(
                    f"**User:** <@{trace['user_id']}>\n"
                    f"**Steps:** {trace['steps_count']}\n"
                    f"**Slowest:** {slowest_step['name'] if slowest_step else 'N/A'}"
                ),
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @trace.command(name="performance", description="Pokaż wydajność komendy")
    async def trace_performance(self, ctx: commands.Context, command_name: str):
        """Show performance statistics for a command."""
        stats = self.tracer.get_command_performance(command_name)
        
        if "message" in stats:
            await ctx.send(f"📊 {stats['message']}")
            return
        
        embed = discord.Embed(
            title=f"📊 Wydajność: {command_name}",
            description=f"Statystyki z {stats['executions']} wykonań",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="Średni czas",
            value=f"{stats['avg_duration_ms']:.1f}ms",
            inline=True
        )
        embed.add_field(
            name="Min/Max",
            value=f"{stats['min_duration_ms']:.1f}ms / {stats['max_duration_ms']:.1f}ms",
            inline=True
        )
        embed.add_field(
            name="Wykonania",
            value=str(stats['executions']),
            inline=True
        )
        
        # Add recent traces
        if stats['recent_traces']:
            recent_times = [t['total_duration_ms'] for t in stats['recent_traces'][-5:]]
            embed.add_field(
                name="Ostatnie czasy (ms)",
                value=", ".join(f"{t:.1f}" for t in recent_times),
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.hybrid_command(name="debug", description="Pokaż informacje debugowania")
    @commands.has_permissions(administrator=True)
    async def debug_info(self, ctx: commands.Context):
        """Show debugging information."""
        summary = self.decision_logger.generate_summary()
        
        embed = discord.Embed(
            title="🐛 Informacje debugowania",
            description="Podsumowanie aktualnej sesji",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="Decyzje ogółem",
            value=str(summary.get('total_decisions', 0)),
            inline=True
        )
        embed.add_field(
            name="Unikalnych użytkowników",
            value=str(summary.get('total_users', 0)),
            inline=True
        )
        embed.add_field(
            name="Średnia pewność",
            value=f"{summary.get('average_confidence', 0) * 100:.0f}%",
            inline=True
        )
        
        # Decision types breakdown
        if summary.get('by_type'):
            type_text = "\n".join(
                f"• {dtype}: {count}"
                for dtype, count in summary['by_type'].items()
            )
            embed.add_field(
                name="Typy decyzji",
                value=type_text or "Brak",
                inline=False
            )
        
        # Results breakdown
        if summary.get('by_result'):
            result_text = "\n".join(
                f"• {result}: {count}"
                for result, count in summary['by_result'].items()
                if count > 0
            )
            embed.add_field(
                name="Wyniki",
                value=result_text or "Brak",
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: Exception):
        """Log command errors for interpretability."""
        if hasattr(ctx, 'trace'):
            # Mark in trace
            ctx.trace.metadata['error'] = str(error)
        
        # Log decision about error handling
        self.decision_logger.log_decision(
            self.decision_logger.Decision(
                decision_type=self.decision_logger.DecisionType.ERROR_HANDLING,
                command=ctx.command.name if ctx.command else None,
                user_id=str(ctx.author.id),
                action="handle_command_error",
                result="error_shown",
                reason=str(error),
                context={
                    "error_type": type(error).__name__,
                    "command": ctx.command.name if ctx.command else None,
                    "args": str(ctx.args),
                    "kwargs": str(ctx.kwargs)
                }
            )
        )


async def setup(bot):
    """Setup function for loading the cog."""
    await bot.add_cog(InterpretabilityCog(bot))