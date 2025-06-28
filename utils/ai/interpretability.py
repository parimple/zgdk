"""
AI interpretability and explainability tools for ZGDK bot.
Provides decision logging, feature extraction, and explanation generation.
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from pydantic_ai import Agent

if TYPE_CHECKING:
    from discord.ext import commands

logger = logging.getLogger(__name__)


@dataclass
class DecisionTrace:
    """Records a single AI decision with full context."""

    timestamp: datetime
    module: str  # e.g., "duration_parser", "color_parser", "intent_classifier"
    input_data: Dict[str, Any]
    features_extracted: Dict[str, Any]
    model_output: Any
    final_decision: Any
    confidence: float
    reasoning: str
    execution_time_ms: float
    user_id: Optional[int] = None
    guild_id: Optional[int] = None
    command_context: Optional[str] = None


@dataclass
class FeatureImportance:
    """Tracks importance of different features in AI decisions."""

    feature_name: str
    importance_score: float
    usage_count: int
    avg_impact: float
    examples: List[str] = field(default_factory=list)


class DecisionLogger:
    """Logs AI decisions for analysis and debugging."""

    def __init__(self, log_dir: str = "logs/ai_decisions"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: List[DecisionTrace] = []
        self.feature_usage: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    async def log_decision(
        self,
        module: str,
        input_data: Dict[str, Any],
        features: Dict[str, Any],
        output: Any,
        decision: Any,
        confidence: float,
        reasoning: str,
        execution_time_ms: float,
        context: Optional["commands.Context"] = None,
    ):
        """Log an AI decision with full context."""
        trace = DecisionTrace(
            timestamp=datetime.utcnow(),
            module=module,
            input_data=input_data,
            features_extracted=features,
            model_output=output,
            final_decision=decision,
            confidence=confidence,
            reasoning=reasoning,
            execution_time_ms=execution_time_ms,
            user_id=context.author.id if context else None,
            guild_id=context.guild.id if context and context.guild else None,
            command_context=str(context.command) if context else None,
        )

        self.current_session.append(trace)

        # Update feature usage statistics
        for feature_name in features:
            self.feature_usage[module][feature_name] += 1

        # Write to daily log file
        log_file = self.log_dir / f"decisions_{datetime.utcnow().strftime('%Y%m%d')}.jsonl"
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(trace), default=str) + "\n")

        logger.debug(f"Logged AI decision: {module} -> {decision} (confidence: {confidence:.2f})")

    def get_recent_decisions(self, limit: int = 10, module: Optional[str] = None) -> List[DecisionTrace]:
        """Get recent decisions, optionally filtered by module."""
        decisions = self.current_session[-limit:]
        if module:
            decisions = [d for d in decisions if d.module == module]
        return decisions

    def get_feature_importance(self, module: str) -> List[FeatureImportance]:
        """Calculate feature importance for a specific module."""
        if module not in self.feature_usage:
            return []

        total_uses = sum(self.feature_usage[module].values())
        if total_uses == 0:
            return []

        importances = []
        for feature, count in self.feature_usage[module].items():
            importance = FeatureImportance(
                feature_name=feature,
                importance_score=count / total_uses,
                usage_count=count,
                avg_impact=0.8,  # Would need more sophisticated tracking
                examples=self._get_feature_examples(module, feature, limit=3),
            )
            importances.append(importance)

        return sorted(importances, key=lambda x: x.importance_score, reverse=True)

    def _get_feature_examples(self, module: str, feature: str, limit: int = 3) -> List[str]:
        """Get example values for a specific feature."""
        examples = []
        for trace in reversed(self.current_session):
            if trace.module == module and feature in trace.features_extracted:
                value = str(trace.features_extracted[feature])
                if value not in examples:
                    examples.append(value)
                if len(examples) >= limit:
                    break
        return examples


class FeatureExtractor:
    """Extracts interpretable features from inputs for AI models."""

    @staticmethod
    async def extract_duration_features(text: str) -> Dict[str, Any]:
        """Extract features from duration text input."""
        features = {
            "length": len(text),
            "has_numbers": any(c.isdigit() for c in text),
            "number_count": sum(1 for c in text if c.isdigit()),
            "has_unit_keywords": any(
                unit in text.lower()
                for unit in [
                    "dni",
                    "dzień",
                    "godzin",
                    "minut",
                    "sekund",
                    "tyg",
                    "mies",
                    "rok",
                    "day",
                    "hour",
                    "minute",
                    "second",
                    "week",
                    "month",
                    "year",
                ]
            ),
            "has_polish_numerals": any(
                num in text.lower()
                for num in [
                    "jeden",
                    "dwa",
                    "trzy",
                    "cztery",
                    "pięć",
                    "sześć",
                    "siedem",
                    "osiem",
                    "dziewięć",
                    "dziesięć",
                    "dwadzieścia",
                    "trzydzieści",
                ]
            ),
            "has_relative_terms": any(term in text.lower() for term in ["pół", "połowa", "kwadrans", "półtora"]),
            "word_count": len(text.split()),
            "first_word": text.split()[0].lower() if text.split() else "",
            "last_word": text.split()[-1].lower() if text.split() else "",
        }
        return features

    @staticmethod
    async def extract_color_features(text: str) -> Dict[str, Any]:
        """Extract features from color text input."""
        features = {
            "length": len(text),
            "starts_with_hash": text.startswith("#"),
            "has_hex_chars": all(c in "0123456789ABCDEFabcde" for c in text.strip("#")),
            "has_rgb_pattern": "rgb" in text.lower() or "," in text,
            "has_color_name": any(
                color in text.lower()
                for color in [
                    "czerwon",
                    "zielon",
                    "niebiesk",
                    "żółt",
                    "fiolet",
                    "różow",
                    "czarn",
                    "biał",
                    "szar",
                    "brązow",
                    "pomarańcz",
                    "red",
                    "green",
                    "blue",
                    "yellow",
                    "purple",
                    "pink",
                    "black",
                    "white",
                    "gray",
                    "brown",
                    "orange",
                ]
            ),
            "has_modifier": any(
                mod in text.lower()
                for mod in ["jasn", "ciemn", "pastel", "neon", "metalic", "light", "dark", "bright", "pale"]
            ),
            "word_count": len(text.split()),
            "char_pattern": "hex" if text.startswith("#") and len(text) == 7 else "name",
        }
        return features

    @staticmethod
    async def extract_intent_features(text: str, command_name: str) -> Dict[str, Any]:
        """Extract features from command text for intent classification."""
        features = {
            "command": command_name,
            "text_length": len(text),
            "word_count": len(text.split()),
            "has_question": "?" in text or any(q in text.lower() for q in ["co", "jak", "czy", "kiedy"]),
            "has_mention": "@" in text,
            "has_role_mention": "<@&" in text,
            "has_channel_mention": "<#" in text,
            "has_emoji": any(ord(c) > 127 for c in text),
            "has_url": "http" in text or "www" in text,
            "sentiment_keywords": {
                "positive": any(w in text.lower() for w in ["dziękuję", "super", "świetnie", "dobra"]),
                "negative": any(w in text.lower() for w in ["nie", "źle", "problem", "błąd"]),
                "help": any(w in text.lower() for w in ["pomoc", "help", "jak", "instrukcja"]),
            },
            "action_keywords": {
                "add": any(w in text.lower() for w in ["dodaj", "stwórz", "ustaw", "add"]),
                "remove": any(w in text.lower() for w in ["usuń", "zdejmij", "kasuj", "remove"]),
                "check": any(w in text.lower() for w in ["sprawdź", "pokaż", "wyświetl", "check"]),
                "modify": any(w in text.lower() for w in ["zmień", "edytuj", "popraw", "change"]),
            },
        }
        return features


class ModelExplainer:
    """Generates human-readable explanations for AI decisions."""

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.gemini_api_key = gemini_api_key
        self.logger = DecisionLogger()
        self.extractor = FeatureExtractor()

        if gemini_api_key:
            import os

            os.environ["GOOGLE_API_KEY"] = gemini_api_key
            self.explanation_agent = Agent(
                model="gemini-1.5-flash",
                system_prompt="""You are an AI explainability assistant for a Discord bot.
                Your task is to explain AI decisions in simple, understandable terms.
                Focus on what features influenced the decision and why.
                Respond in Polish when explaining Polish language processing.""",
            )

    async def explain_decision(
        self, module: str, input_text: str, decision: Any, features: Dict[str, Any], confidence: float
    ) -> str:
        """Generate a human-readable explanation for an AI decision."""
        if hasattr(self, "explanation_agent"):
            prompt = """
            Explain this AI decision:
            Module: {module}
            Input: "{input_text}"
            Decision: {decision}
            Confidence: {confidence:.2%}

            Key features that influenced the decision:
            {json.dumps(features, indent=2, ensure_ascii=False)}

            Provide a brief, clear explanation of why this decision was made.
            """

            result = await self.explanation_agent.run(prompt)
            return result.data

        # Fallback to rule-based explanation
        return self._generate_rule_based_explanation(module, input_text, decision, features, confidence)

    def _generate_rule_based_explanation(
        self, module: str, input_text: str, decision: Any, features: Dict[str, Any], confidence: float
    ) -> str:
        """Generate explanation using rules when AI is not available."""
        explanations = {
            "duration_parser": self._explain_duration,
            "color_parser": self._explain_color,
            "intent_classifier": self._explain_intent,
        }

        if module in explanations:
            return explanations[module](input_text, decision, features, confidence)

        return f"Moduł {module} przetworzoł '{input_text}' i zdecydował: {decision} (pewność: {confidence:.0%})"

    def _explain_duration(self, input_text: str, decision: Any, features: Dict[str, Any], confidence: float) -> str:
        """Explain duration parsing decision."""
        explanation = f"Analizując tekst '{input_text}':\n"

        if features.get("has_numbers"):
            explanation += f"• Znaleziono liczby ({features['number_count']} cyfr)\n"
        if features.get("has_unit_keywords"):
            explanation += "• Wykryto jednostki czasu\n"
        if features.get("has_polish_numerals"):
            explanation += "• Rozpoznano polskie liczebniki\n"

        explanation += f"\nWynik: {decision} sekund (pewność: {confidence:.0%})"
        return explanation

    def _explain_color(self, input_text: str, decision: Any, features: Dict[str, Any], confidence: float) -> str:
        """Explain color parsing decision."""
        explanation = f"Analizując kolor '{input_text}':\n"

        if features.get("starts_with_hash"):
            explanation += "• Format HEX (zaczyna się od #)\n"
        elif features.get("has_color_name"):
            explanation += "• Rozpoznano nazwę koloru\n"
        if features.get("has_modifier"):
            explanation += "• Wykryto modyfikator (jasny/ciemny)\n"

        explanation += f"\nWynik: {decision} (pewność: {confidence:.0%})"
        return explanation

    def _explain_intent(self, input_text: str, decision: Any, features: Dict[str, Any], confidence: float) -> str:
        """Explain intent classification decision."""
        explanation = "Analizując intencję komendy:\n"

        if features.get("has_question"):
            explanation += "• Wykryto pytanie\n"

        sentiments = features.get("sentiment_keywords", {})
        if sentiments.get("help"):
            explanation += "• Prośba o pomoc\n"
        elif sentiments.get("positive"):
            explanation += "• Pozytywny wydźwięk\n"
        elif sentiments.get("negative"):
            explanation += "• Negatywny wydźwięk lub problem\n"

        actions = features.get("action_keywords", {})
        for action, present in actions.items():
            if present:
                action_pl = {
                    "add": "dodawanie",
                    "remove": "usuwanie",
                    "check": "sprawdzanie",
                    "modify": "modyfikacja",
                }.get(action, action)
                explanation += f"• Akcja: {action_pl}\n"

        explanation += f"\nIntencja: {decision} (pewność: {confidence:.0%})"
        return explanation

    async def get_decision_trace(self, trace_id: int) -> Optional[DecisionTrace]:
        """Get a specific decision trace by ID."""
        decisions = self.logger.current_session
        if 0 <= trace_id < len(decisions):
            return decisions[trace_id]
        return None

    async def generate_feature_report(self, module: str) -> str:
        """Generate a report on feature importance for a module."""
        importances = self.logger.get_feature_importance(module)

        if not importances:
            return f"Brak danych o cechach dla modułu: {module}"

        report = f"📊 **Raport cech dla modułu: {module}**\n\n"

        for imp in importances[:5]:  # Top 5 features
            report += f"**{imp.feature_name}**\n"
            report += f"• Ważność: {imp.importance_score:.1%}\n"
            report += f"• Użycia: {imp.usage_count}\n"
            if imp.examples:
                report += f"• Przykłady: {', '.join(imp.examples[:3])}\n"
            report += "\n"

        return report


# Global explainer instance
_explainer: Optional[ModelExplainer] = None


def get_explainer(gemini_api_key: Optional[str] = None) -> ModelExplainer:
    """Get or create the global explainer instance."""
    global _explainer
    if _explainer is None:
        _explainer = ModelExplainer(gemini_api_key)
    return _explainer


async def log_and_explain(
    module: str,
    input_data: Dict[str, Any],
    features: Dict[str, Any],
    output: Any,
    decision: Any,
    confidence: float,
    reasoning: str,
    execution_time_ms: float,
    context: Optional["commands.Context"] = None,
    auto_explain: bool = False,
) -> Optional[str]:
    """
    Log an AI decision and optionally generate an explanation.

    This is a convenience function that combines logging and explanation.
    """
    explainer = get_explainer()

    # Log the decision
    await explainer.logger.log_decision(
        module=module,
        input_data=input_data,
        features=features,
        output=output,
        decision=decision,
        confidence=confidence,
        reasoning=reasoning,
        execution_time_ms=execution_time_ms,
        context=context,
    )

    # Generate explanation if requested
    if auto_explain:
        input_text = input_data.get("text", str(input_data))
        return await explainer.explain_decision(
            module=module, input_text=input_text, decision=decision, features=features, confidence=confidence
        )

    return None
