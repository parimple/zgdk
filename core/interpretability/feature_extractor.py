"""
Feature extraction system inspired by Anthropic's interpretability research.
Extracts and maps bot decision patterns.
"""

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from .decision_logger import Decision, DecisionType


class Feature:
    """Represents a behavioral feature/pattern in bot decisions."""

    def __init__(self, feature_id: str, name: str, description: str):
        self.id = feature_id
        self.name = name
        self.description = description
        self.activations: List[Tuple[Decision, float]] = []
        self.related_features: Set[str] = set()
        self.metadata: Dict = {}

    def add_activation(self, decision: Decision, strength: float = 1.0):
        """Record when this feature activated."""
        self.activations.append((decision, strength))

    def get_activation_strength(self) -> float:
        """Get average activation strength."""
        if not self.activations:
            return 0.0
        return sum(strength for _, strength in self.activations) / len(self.activations)

    def get_common_contexts(self, limit: int = 5) -> List[Dict]:
        """Get most common contexts where this feature activates."""
        context_counts = defaultdict(int)

        for decision, _ in self.activations:
            for key, value in decision.context.items():
                if isinstance(value, (str, int, bool)):
                    context_counts[f"{key}={value}"] += 1

        return [
            {"context": ctx, "count": count}
            for ctx, count in sorted(context_counts.items(), key=lambda x: x[1], reverse=True)[:limit]
        ]


class FeatureExtractor:
    """Extracts interpretable features from bot decisions."""

    def __init__(self, decision_logger):
        self.decision_logger = decision_logger
        self.features: Dict[str, Feature] = {}
        self._initialize_features()

    def _initialize_features(self):
        """Initialize known features based on bot behavior patterns."""
        # Permission features
        self.add_feature(
            "perm_admin_required", "Wymaga Administratora", "Aktywuje się gdy komenda wymaga uprawnień administratora"
        )
        self.add_feature("perm_premium_required", "Wymaga Premium", "Aktywuje się gdy funkcja wymaga rangi premium")
        self.add_feature(
            "perm_team_leader", "Wymaga Lidera Drużyny", "Aktywuje się gdy akcja wymaga bycia liderem drużyny"
        )

        # Moderation features
        self.add_feature("mod_spam_detected", "Wykryto Spam", "Aktywuje się przy wykryciu spamu lub flood")
        self.add_feature("mod_repeat_offender", "Recydywista", "Aktywuje się gdy użytkownik ma historię naruszeń")
        self.add_feature("mod_severity_high", "Wysokie Zagrożenie", "Aktywuje się przy poważnych naruszeniach")

        # Economic features
        self.add_feature(
            "econ_insufficient_funds", "Brak Środków", "Aktywuje się gdy użytkownik nie ma wystarczających środków"
        )
        self.add_feature("econ_role_upgrade", "Upgrade Rangi", "Aktywuje się przy próbie ulepszenia rangi")
        self.add_feature("econ_refund_calculated", "Obliczono Zwrot", "Aktywuje się gdy system oblicza zwrot za rangę")

        # Team features
        self.add_feature("team_full", "Drużyna Pełna", "Aktywuje się gdy drużyna osiągnęła limit członków")
        self.add_feature("team_hierarchy", "Hierarchia Drużyny", "Aktywuje się przy sprawdzaniu hierarchii w drużynie")

        # Cooldown features
        self.add_feature("cooldown_active", "Aktywny Cooldown", "Aktywuje się gdy użytkownik jest na cooldownie")
        self.add_feature("cooldown_bump_service", "Cooldown Bump", "Aktywuje się dla cooldownów serwisów bump")

        # AI features
        self.add_feature("ai_natural_language", "Język Naturalny", "Aktywuje się przy przetwarzaniu naturalnego języka")
        self.add_feature("ai_low_confidence", "Niska Pewność AI", "Aktywuje się gdy AI ma niską pewność decyzji")

    def add_feature(self, feature_id: str, name: str, description: str) -> Feature:
        """Add a new feature to track."""
        feature = Feature(feature_id, name, description)
        self.features[feature_id] = feature
        return feature

    def extract_features(self, decision: Decision) -> List[Tuple[Feature, float]]:
        """Extract active features from a decision."""
        active_features = []

        # Permission features
        if decision.decision_type == DecisionType.PERMISSION_CHECK:
            if "administrator" in str(decision.context.get("required_permissions", [])):
                active_features.append((self.features["perm_admin_required"], 1.0))

            if "premium" in decision.reason.lower() or "premium" in str(decision.context):
                active_features.append((self.features["perm_premium_required"], 1.0))

            if "team_leader" in str(decision.context) or "lider" in decision.reason:
                active_features.append((self.features["perm_team_leader"], 1.0))

        # Moderation features
        if decision.decision_type == DecisionType.MODERATION_ACTION:
            if "spam" in decision.reason.lower():
                active_features.append((self.features["mod_spam_detected"], 1.0))

            if decision.context.get("is_repeat_offender"):
                active_features.append((self.features["mod_repeat_offender"], 1.0))

            if decision.context.get("threat_level") in ["high", "critical"]:
                active_features.append((self.features["mod_severity_high"], 1.0))

        # Economic features
        if decision.decision_type == DecisionType.PURCHASE_VALIDATION:
            if "insufficient" in decision.reason or "brak środków" in decision.reason.lower():
                active_features.append((self.features["econ_insufficient_funds"], 1.0))

            if "upgrade" in str(decision.context) or "ulepsz" in decision.reason:
                active_features.append((self.features["econ_role_upgrade"], 1.0))

            if "refund" in str(decision.context) or "zwrot" in decision.reason:
                active_features.append((self.features["econ_refund_calculated"], 1.0))

        # Team features
        if decision.decision_type == DecisionType.TEAM_MANAGEMENT:
            if "full" in decision.reason or "pełna" in decision.reason:
                active_features.append((self.features["team_full"], 1.0))

            if "hierarchy" in str(decision.context) or "lider" in decision.reason:
                active_features.append((self.features["team_hierarchy"], 1.0))

        # Cooldown features
        if decision.decision_type == DecisionType.COOLDOWN_CHECK:
            active_features.append((self.features["cooldown_active"], decision.confidence))

            if any(service in str(decision.context) for service in ["disboard", "dzik", "discadia"]):
                active_features.append((self.features["cooldown_bump_service"], 1.0))

        # AI features
        if decision.decision_type == DecisionType.AI_INFERENCE:
            active_features.append((self.features["ai_natural_language"], 1.0))

            if decision.confidence < 0.7:
                active_features.append((self.features["ai_low_confidence"], 1.0 - decision.confidence))

        # Record activations
        for feature, strength in active_features:
            feature.add_activation(decision, strength)

        return active_features

    def find_related_features(self, feature_id: str, threshold: float = 0.5) -> List[Tuple[str, float]]:
        """Find features that often activate together."""
        if feature_id not in self.features:
            return []

        target_feature = self.features[feature_id]
        target_decisions = {d.decision_id for d, _ in target_feature.activations}

        correlations = []

        for other_id, other_feature in self.features.items():
            if other_id == feature_id:
                continue

            other_decisions = {d.decision_id for d, _ in other_feature.activations}

            if not target_decisions or not other_decisions:
                continue

            # Calculate Jaccard similarity
            intersection = len(target_decisions & other_decisions)
            union = len(target_decisions | other_decisions)

            if union > 0:
                similarity = intersection / union
                if similarity >= threshold:
                    correlations.append((other_id, similarity))

        return sorted(correlations, key=lambda x: x[1], reverse=True)

    def get_feature_map(self) -> Dict[str, Dict]:
        """Get a map of all features and their relationships."""
        feature_map = {}

        for feature_id, feature in self.features.items():
            related = self.find_related_features(feature_id, threshold=0.3)

            feature_map[feature_id] = {
                "name": feature.name,
                "description": feature.description,
                "activation_count": len(feature.activations),
                "avg_strength": feature.get_activation_strength(),
                "related_features": [{"id": rel_id, "correlation": corr} for rel_id, corr in related[:5]],
                "common_contexts": feature.get_common_contexts(),
            }

        return feature_map

    def analyze_decision_path(self, decision: Decision) -> Dict:
        """Analyze the feature activation path for a decision."""
        features = self.extract_features(decision)

        path_analysis = {
            "decision_id": decision.decision_id,
            "type": decision.decision_type.value,
            "result": decision.result,
            "active_features": [
                {"id": feature.id, "name": feature.name, "strength": strength, "description": feature.description}
                for feature, strength in features
            ],
            "feature_interaction": self._analyze_feature_interaction(features),
            "dominant_pattern": self._identify_dominant_pattern(features),
        }

        return path_analysis

    def _analyze_feature_interaction(self, features: List[Tuple[Feature, float]]) -> str:
        """Analyze how features interact in this decision."""
        if not features:
            return "Brak aktywnych cech"

        feature_names = [f.name for f, _ in features]

        # Check for known interaction patterns
        if "Wymaga Premium" in feature_names and "Brak Środków" in feature_names:
            return "Próba zakupu premium bez wystarczających środków"

        if "Recydywista" in feature_names and "Wysokie Zagrożenie" in feature_names:
            return "Poważne naruszenie przez znanego sprawcę"

        if "Wymaga Lidera Drużyny" in feature_names and "Drużyna Pełna" in feature_names:
            return "Lider próbuje zarządzać pełną drużyną"

        if len(features) > 3:
            return "Złożona decyzja z wieloma czynnikami"

        return "Standardowa interakcja cech"

    def _identify_dominant_pattern(self, features: List[Tuple[Feature, float]]) -> str:
        """Identify the dominant behavioral pattern."""
        if not features:
            return "Brak dominującego wzorca"

        # Sort by strength
        sorted_features = sorted(features, key=lambda x: x[1], reverse=True)
        strongest = sorted_features[0][0]

        # Map features to patterns
        pattern_map = {
            "perm_": "Wzorzec uprawnień",
            "mod_": "Wzorzec moderacji",
            "econ_": "Wzorzec ekonomiczny",
            "team_": "Wzorzec drużynowy",
            "cooldown_": "Wzorzec czasowy",
            "ai_": "Wzorzec AI",
        }

        for prefix, pattern in pattern_map.items():
            if strongest.id.startswith(prefix):
                return pattern

        return "Wzorzec mieszany"

    def export_feature_analysis(self, output_path: str = "feature_analysis.json"):
        """Export feature analysis to file."""
        analysis = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_decisions": len(self.decision_logger.current_session),
            "feature_map": self.get_feature_map(),
            "feature_correlations": {
                feature_id: self.find_related_features(feature_id) for feature_id in self.features
            },
        }

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        with open(path, "w", encoding="utf-8") as f:
            json.dump(analysis, f, ensure_ascii=False, indent=2)
