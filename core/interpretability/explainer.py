"""
Action explainer for providing human-readable explanations of bot actions.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
import discord
from discord.ext import commands

from .decision_logger import Decision, DecisionType


class ExplanationLevel(str, Enum):
    """Level of detail for explanations."""
    SIMPLE = "simple"      # Krótkie, proste wyjaśnienie
    DETAILED = "detailed"  # Szczegółowe wyjaśnienie z kontekstem
    TECHNICAL = "technical"  # Techniczne szczegóły dla developerów


class ActionExplainer:
    """Provides human-readable explanations for bot actions."""
    
    def __init__(self, bot):
        self.bot = bot
        self.explanations = {
            # Permission explanations
            "missing_role": "Nie posiadasz wymaganej roli: {role}",
            "missing_permission": "Brak uprawnienia: {permission}",
            "cooldown_active": "Musisz poczekać {time} przed ponownym użyciem",
            
            # Purchase explanations
            "insufficient_balance": "Niewystarczające środki. Potrzebujesz {required} zł, masz {current} zł",
            "already_owned": "Już posiadasz tę rangę",
            "upgrade_available": "Możesz ulepszyć swoją rangę z {current} do {new}",
            
            # Moderation explanations
            "spam_detected": "Wykryto spam: {pattern}",
            "user_muted": "Użytkownik został wyciszony na {duration}",
            "ban_reason": "Użytkownik został zbanowany. Powód: {reason}",
            
            # Team explanations
            "team_full": "Drużyna jest pełna ({current}/{max} członków)",
            "not_team_leader": "Tylko lider drużyny może wykonać tę akcję",
            "member_added": "Dodano {member} do drużyny {team}",
            
            # Voice channel explanations
            "channel_created": "Utworzono kanał głosowy: {channel}",
            "user_limit_reached": "Osiągnięto limit użytkowników ({limit})",
            "autokick_triggered": "Użytkownik został automatycznie wyrzucony - limit przekroczony"
        }
    
    def explain_decision(
        self,
        decision: Decision,
        level: ExplanationLevel = ExplanationLevel.SIMPLE
    ) -> str:
        """Generate explanation for a decision based on level."""
        if level == ExplanationLevel.SIMPLE:
            return self._simple_explanation(decision)
        elif level == ExplanationLevel.DETAILED:
            return self._detailed_explanation(decision)
        else:
            return self._technical_explanation(decision)
    
    def _simple_explanation(self, decision: Decision) -> str:
        """Generate simple explanation."""
        return decision.to_user_friendly()
    
    def _detailed_explanation(self, decision: Decision) -> str:
        """Generate detailed explanation with context."""
        base = self._simple_explanation(decision)
        
        # Add context based on decision type
        if decision.decision_type == DecisionType.PERMISSION_CHECK:
            conditions = "\n".join(
                f"• {cond['permission']}: {'✅' if cond['has'] else '❌'}"
                for cond in decision.checked_conditions
            )
            return f"{base}\n\n**Sprawdzone uprawnienia:**\n{conditions}"
        
        elif decision.decision_type == DecisionType.PURCHASE_VALIDATION:
            steps = "\n".join(
                f"• {step['check']}: {'✅' if step.get('passed') else '❌'} {step.get('reason', '')}"
                for step in decision.checked_conditions
            )
            return f"{base}\n\n**Kroki walidacji:**\n{steps}"
        
        elif decision.decision_type == DecisionType.MODERATION_ACTION:
            steps = "\n".join(f"• {step}" for step in decision.reasoning_steps)
            return f"{base}\n\n**Proces decyzyjny:**\n{steps}"
        
        return base
    
    def _technical_explanation(self, decision: Decision) -> str:
        """Generate technical explanation for developers."""
        return (
            f"**Decision ID:** {decision.decision_id}\n"
            f"**Type:** {decision.decision_type.value}\n"
            f"**Command:** {decision.command or 'N/A'}\n"
            f"**User:** {decision.user_id}\n"
            f"**Result:** {decision.result}\n"
            f"**Confidence:** {decision.confidence:.2f}\n"
            f"**Execution Time:** {decision.execution_time_ms or 'N/A'}ms\n\n"
            f"**Context:**\n```json\n{decision.context}\n```\n"
            f"**Conditions Checked:**\n```json\n{decision.checked_conditions}\n```"
        )
    
    def create_explanation_embed(
        self,
        decision: Decision,
        level: ExplanationLevel = ExplanationLevel.SIMPLE,
        color: Optional[discord.Color] = None
    ) -> discord.Embed:
        """Create Discord embed with explanation."""
        explanation = self.explain_decision(decision, level)
        
        # Choose color based on result
        if not color:
            if decision.result in ["denied", "rejected", "failed"]:
                color = discord.Color.red()
            elif decision.result in ["granted", "approved", "executed"]:
                color = discord.Color.green()
            else:
                color = discord.Color.blue()
        
        embed = discord.Embed(
            title=self._get_title_for_decision(decision),
            description=explanation,
            color=color,
            timestamp=decision.timestamp
        )
        
        # Add fields based on level
        if level in [ExplanationLevel.DETAILED, ExplanationLevel.TECHNICAL]:
            embed.add_field(
                name="Typ decyzji",
                value=decision.decision_type.value,
                inline=True
            )
            embed.add_field(
                name="Pewność",
                value=f"{decision.confidence * 100:.0f}%",
                inline=True
            )
            if decision.execution_time_ms:
                embed.add_field(
                    name="Czas wykonania",
                    value=f"{decision.execution_time_ms:.1f}ms",
                    inline=True
                )
        
        if level == ExplanationLevel.TECHNICAL:
            embed.set_footer(text=f"Decision ID: {decision.decision_id}")
        
        return embed
    
    def _get_title_for_decision(self, decision: Decision) -> str:
        """Get appropriate title for decision type."""
        titles = {
            DecisionType.PERMISSION_CHECK: "🔐 Sprawdzenie Uprawnień",
            DecisionType.MODERATION_ACTION: "🔨 Akcja Moderacyjna",
            DecisionType.COMMAND_EXECUTION: "⚡ Wykonanie Komendy",
            DecisionType.ROLE_ASSIGNMENT: "🎭 Przypisanie Roli",
            DecisionType.PURCHASE_VALIDATION: "💰 Walidacja Zakupu",
            DecisionType.TEAM_MANAGEMENT: "👥 Zarządzanie Drużyną",
            DecisionType.VOICE_CHANNEL: "🔊 Kanał Głosowy",
            DecisionType.AI_INFERENCE: "🤖 Decyzja AI",
            DecisionType.COOLDOWN_CHECK: "⏱️ Sprawdzenie Cooldownu",
            DecisionType.ERROR_HANDLING: "❌ Obsługa Błędu"
        }
        return titles.get(decision.decision_type, "📊 Decyzja Bota")
    
    async def send_explanation(
        self,
        ctx: commands.Context,
        decision: Decision,
        level: ExplanationLevel = ExplanationLevel.SIMPLE,
        ephemeral: bool = True
    ):
        """Send explanation to user."""
        embed = self.create_explanation_embed(decision, level)
        
        if hasattr(ctx, 'interaction') and ctx.interaction:
            await ctx.interaction.response.send_message(
                embed=embed,
                ephemeral=ephemeral
            )
        else:
            await ctx.send(embed=embed)
    
    def format_validation_steps(self, steps: List[Dict[str, Any]]) -> str:
        """Format validation steps for display."""
        formatted = []
        for i, step in enumerate(steps, 1):
            status = "✅" if step.get("passed", False) else "❌"
            check = step.get("check", "Unknown check")
            reason = step.get("reason", "")
            formatted.append(f"{i}. {status} {check}" + (f" - {reason}" if reason else ""))
        
        return "\n".join(formatted)