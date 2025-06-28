"""
Developer commands for AI interpretability and debugging.
Provides insights into AI decision-making processes.
"""

import discord
from discord.ext import commands
from typing import Optional
import json
from datetime import datetime

from utils.ai.interpretability import get_explainer, DecisionTrace
from core.ai.duration_parser import DurationParser
from core.ai.color_parser import ColorParser
from core.ai.command_classifier import CommandIntentClassifier


class DeveloperAI(commands.Cog):
    """AI interpretability and debugging commands for developers."""
    
    def __init__(self, bot):
        self.bot = bot
        self.explainer = get_explainer(bot.config.get('gemini_api_key'))
    
    @commands.hybrid_group(name="ai", description="AI interpretability commands")
    @commands.is_owner()
    async def ai_group(self, ctx: commands.Context):
        """Group for AI interpretability commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send("Użyj: `/ai explain`, `/ai features`, `/ai trace`, `/ai stats`")
    
    @ai_group.command(name="explain", description="Explain an AI decision")
    @commands.is_owner()
    async def explain_decision(
        self,
        ctx: commands.Context,
        trace_id: Optional[int] = None,
        module: Optional[str] = None
    ):
        """
        Explain a recent AI decision.
        
        Args:
            trace_id: Specific decision trace ID (optional)
            module: Filter by module name (optional)
        """
        # Get recent decisions
        decisions = self.explainer.logger.get_recent_decisions(limit=10, module=module)
        
        if not decisions:
            await ctx.send("Brak ostatnich decyzji AI do wyjaśnienia.")
            return
        
        # If trace_id provided, find specific decision
        if trace_id is not None:
            decision = await self.explainer.get_decision_trace(trace_id)
            if not decision:
                await ctx.send(f"Nie znaleziono decyzji o ID: {trace_id}")
                return
        else:
            # Use most recent decision
            decision = decisions[0]
        
        # Generate explanation
        explanation = await self.explainer.explain_decision(
            module=decision.module,
            input_text=decision.input_data.get('text', str(decision.input_data)),
            decision=decision.final_decision,
            features=decision.features_extracted,
            confidence=decision.confidence
        )
        
        # Create embed
        embed = discord.Embed(
            title="🤖 Wyjaśnienie Decyzji AI",
            description=explanation,
            color=discord.Color.blue(),
            timestamp=decision.timestamp
        )
        
        embed.add_field(
            name="Moduł",
            value=decision.module,
            inline=True
        )
        embed.add_field(
            name="Pewność",
            value=f"{decision.confidence:.0%}",
            inline=True
        )
        embed.add_field(
            name="Czas wykonania",
            value=f"{decision.execution_time_ms:.1f}ms",
            inline=True
        )
        
        # Add input/output
        embed.add_field(
            name="Wejście",
            value=f"```{decision.input_data.get('text', 'N/A')[:100]}```",
            inline=False
        )
        embed.add_field(
            name="Decyzja",
            value=f"```{str(decision.final_decision)[:100]}```",
            inline=False
        )
        
        # Add key features
        if decision.features_extracted:
            feature_list = []
            for key, value in list(decision.features_extracted.items())[:5]:
                feature_list.append(f"• **{key}**: {value}")
            embed.add_field(
                name="Kluczowe cechy",
                value="\n".join(feature_list),
                inline=False
            )
        
        await ctx.send(embed=embed)
    
    @ai_group.command(name="features", description="Show feature importance for AI module")
    @commands.is_owner()
    async def show_features(self, ctx: commands.Context, module: str):
        """
        Show feature importance for a specific AI module.
        
        Args:
            module: Module name (duration_parser, color_parser, intent_classifier)
        """
        valid_modules = ["duration_parser", "color_parser", "intent_classifier"]
        if module not in valid_modules:
            await ctx.send(f"Nieprawidłowy moduł. Wybierz z: {', '.join(valid_modules)}")
            return
        
        # Generate feature report
        report = await self.explainer.generate_feature_report(module)
        
        # Send as embed
        embed = discord.Embed(
            title=f"📊 Raport Cech: {module}",
            description=report[:2000],  # Discord limit
            color=discord.Color.green()
        )
        
        await ctx.send(embed=embed)
    
    @ai_group.command(name="trace", description="Show recent AI decision traces")
    @commands.is_owner()
    async def show_traces(
        self,
        ctx: commands.Context,
        limit: Optional[int] = 5,
        module: Optional[str] = None
    ):
        """
        Show recent AI decision traces.
        
        Args:
            limit: Number of traces to show (default: 5)
            module: Filter by module name (optional)
        """
        decisions = self.explainer.logger.get_recent_decisions(limit=limit, module=module)
        
        if not decisions:
            await ctx.send("Brak ostatnich decyzji AI.")
            return
        
        embed = discord.Embed(
            title="🔍 Ostatnie Decyzje AI",
            description=f"Pokazuję {len(decisions)} ostatnich decyzji",
            color=discord.Color.purple()
        )
        
        for i, decision in enumerate(decisions):
            # Format decision info
            info = [
                f"**Moduł**: {decision.module}",
                f"**Wejście**: {decision.input_data.get('text', 'N/A')[:50]}",
                f"**Decyzja**: {str(decision.final_decision)[:50]}",
                f"**Pewność**: {decision.confidence:.0%}",
                f"**Czas**: {decision.execution_time_ms:.1f}ms"
            ]
            
            embed.add_field(
                name=f"#{i} - {decision.timestamp.strftime('%H:%M:%S')}",
                value="\n".join(info),
                inline=False
            )
        
        embed.set_footer(text=f"Użyj /ai explain {index} aby uzyskać szczegóły")
        await ctx.send(embed=embed)
    
    @ai_group.command(name="stats", description="Show AI usage statistics")
    @commands.is_owner()
    async def show_stats(self, ctx: commands.Context):
        """Show overall AI usage statistics."""
        # Calculate statistics
        all_decisions = self.explainer.logger.current_session
        
        if not all_decisions:
            await ctx.send("Brak danych statystycznych.")
            return
        
        # Group by module
        module_stats = {}
        total_time = 0
        
        for decision in all_decisions:
            module = decision.module
            if module not in module_stats:
                module_stats[module] = {
                    'count': 0,
                    'total_time': 0,
                    'avg_confidence': 0,
                    'success_count': 0
                }
            
            stats = module_stats[module]
            stats['count'] += 1
            stats['total_time'] += decision.execution_time_ms
            stats['avg_confidence'] += decision.confidence
            if decision.final_decision is not None:
                stats['success_count'] += 1
            
            total_time += decision.execution_time_ms
        
        # Calculate averages
        for module, stats in module_stats.items():
            if stats['count'] > 0:
                stats['avg_confidence'] /= stats['count']
                stats['avg_time'] = stats['total_time'] / stats['count']
                stats['success_rate'] = stats['success_count'] / stats['count']
        
        # Create embed
        embed = discord.Embed(
            title="📈 Statystyki AI",
            description=f"Łącznie przetworzono: **{len(all_decisions)}** decyzji",
            color=discord.Color.gold()
        )
        
        # Add module statistics
        for module, stats in module_stats.items():
            info = [
                f"Użycia: **{stats['count']}**",
                f"Sukces: **{stats['success_rate']:.0%}**",
                f"Śr. pewność: **{stats['avg_confidence']:.0%}**",
                f"Śr. czas: **{stats['avg_time']:.1f}ms**"
            ]
            embed.add_field(
                name=f"📦 {module}",
                value="\n".join(info),
                inline=True
            )
        
        # Add overall stats
        embed.add_field(
            name="⚡ Wydajność",
            value=f"Całkowity czas: **{total_time:.0f}ms**\n"
                  f"Średni czas: **{total_time/len(all_decisions):.1f}ms**",
            inline=False
        )
        
        await ctx.send(embed=embed)
    
    @ai_group.command(name="test", description="Test AI modules with sample input")
    @commands.is_owner()
    async def test_ai(
        self,
        ctx: commands.Context,
        module: str,
        *,
        test_input: str
    ):
        """
        Test AI modules with sample input.
        
        Args:
            module: Module to test (duration, color, intent)
            test_input: Input text to test
        """
        await ctx.defer()
        
        try:
            result = None
            
            if module == "duration":
                parser = DurationParser(use_ai=True)
                result = await parser.parse(test_input)
                response = f"**Wynik**: {result.seconds} sekund ({result.human_readable})\n"
                response += f"**Pewność**: {result.confidence:.0%}\n"
                response += f"**Interpretacja**: {result.interpretation}"
                
            elif module == "color":
                parser = ColorParser(use_ai=True)
                result = await parser.parse(test_input)
                response = f"**Wynik**: {result.hex_color}\n"
                response += f"**RGB**: {result.rgb}\n"
                response += f"**Pewność**: {result.confidence:.0%}\n"
                response += f"**Interpretacja**: {result.interpretation}"
                if result.closest_named_color:
                    response += f"\n**Najbliższy**: {result.closest_named_color}"
                
            elif module == "intent":
                classifier = CommandIntentClassifier(use_ai=True)
                result = await classifier.classify(test_input)
                response = f"**Kategoria**: {result.category.value}\n"
                response += f"**Pewność**: {result.confidence:.0%}\n"
                response += f"**Interpretacja**: {result.interpretation}"
                if result.suggested_command:
                    response += f"\n**Sugerowana komenda**: {result.suggested_command}"
                if result.alternative_categories:
                    response += f"\n**Alternatywy**: {', '.join(c.value for c in result.alternative_categories)}"
                
            else:
                await ctx.send("Nieprawidłowy moduł. Użyj: duration, color, intent")
                return
            
            # Get the last decision trace for explanation
            decisions = self.explainer.logger.get_recent_decisions(limit=1, module=f"{module}_parser" if module != "intent" else "intent_classifier")
            
            embed = discord.Embed(
                title=f"🧪 Test AI: {module}",
                description=f"**Wejście**: `{test_input}`",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Wynik",
                value=response,
                inline=False
            )
            
            # Add explanation if available
            if decisions:
                decision = decisions[0]
                explanation = await self.explainer.explain_decision(
                    module=decision.module,
                    input_text=test_input,
                    decision=decision.final_decision,
                    features=decision.features_extracted,
                    confidence=decision.confidence
                )
                embed.add_field(
                    name="Wyjaśnienie",
                    value=explanation[:1024],
                    inline=False
                )
            
            await ctx.send(embed=embed)
            
        except Exception as e:
            await ctx.send(f"❌ Błąd podczas testowania: {str(e)}")
    
    @commands.command(name="ai_debug", hidden=True)
    @commands.is_owner()
    async def debug_ai_state(self, ctx: commands.Context):
        """Debug command to check AI system state."""
        info = []
        
        # Check if AI modules are enabled
        import os
        gemini_key = os.getenv('GEMINI_API_KEY')
        openai_key = os.getenv('OPENAI_API_KEY')
        
        info.append(f"**Gemini API**: {'✅ Configured' if gemini_key else '❌ Not configured'}")
        info.append(f"**OpenAI API**: {'✅ Configured' if openai_key else '❌ Not configured'}")
        
        # Check interpretability system
        info.append(f"**Explainer**: {'✅ Active' if self.explainer else '❌ Inactive'}")
        info.append(f"**Decisions logged**: {len(self.explainer.logger.current_session)}")
        
        # Check feature usage
        total_features = sum(
            sum(counts.values())
            for counts in self.explainer.logger.feature_usage.values()
        )
        info.append(f"**Feature extractions**: {total_features}")
        
        embed = discord.Embed(
            title="🔧 AI System Debug",
            description="\n".join(info),
            color=discord.Color.orange()
        )
        
        await ctx.send(embed=embed)


async def setup(bot):
    """Load the cog."""
    await bot.add_cog(DeveloperAI(bot))