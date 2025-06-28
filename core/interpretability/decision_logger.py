"""
Decision logging system for tracking and explaining bot decisions.
"""

import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class DecisionType(str, Enum):
    """Types of decisions the bot can make."""
    PERMISSION_CHECK = "permission_check"
    MODERATION_ACTION = "moderation_action"
    COMMAND_EXECUTION = "command_execution"
    ROLE_ASSIGNMENT = "role_assignment"
    PURCHASE_VALIDATION = "purchase_validation"
    TEAM_MANAGEMENT = "team_management"
    VOICE_CHANNEL = "voice_channel"
    AI_INFERENCE = "ai_inference"
    COOLDOWN_CHECK = "cooldown_check"
    ERROR_HANDLING = "error_handling"


class Decision(BaseModel):
    """Represents a single decision made by the bot."""
    decision_id: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    decision_type: DecisionType
    command: Optional[str] = None
    user_id: str
    guild_id: Optional[str] = None
    
    # Decision details
    action: str
    result: str
    reason: str
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    
    # Context and conditions
    checked_conditions: List[Dict[str, Any]] = Field(default_factory=list)
    context: Dict[str, Any] = Field(default_factory=dict)
    
    # Performance metrics
    execution_time_ms: Optional[float] = None
    
    # Chain of reasoning
    reasoning_steps: List[str] = Field(default_factory=list)
    alternatives_considered: List[Dict[str, Any]] = Field(default_factory=list)
    
    def to_user_friendly(self) -> str:
        """Convert decision to user-friendly explanation."""
        if self.decision_type == DecisionType.PERMISSION_CHECK:
            if self.result == "denied":
                return f"❌ Odmowa dostępu: {self.reason}"
            return f"✅ Dostęp przyznany: {self.reason}"
        
        elif self.decision_type == DecisionType.MODERATION_ACTION:
            return f"🔨 Akcja moderacyjna: {self.action}\n📝 Powód: {self.reason}"
        
        elif self.decision_type == DecisionType.PURCHASE_VALIDATION:
            if self.result == "rejected":
                return f"❌ Zakup odrzucony: {self.reason}"
            return f"✅ Zakup zaakceptowany: {self.reason}"
        
        return f"{self.action}: {self.reason}"


class DecisionLogger:
    """Logs and tracks all bot decisions for interpretability."""
    
    def __init__(self, log_dir: str = "logs/decisions"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_session: List[Decision] = []
        self.session_file = self.log_dir / f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    
    def log_decision(self, decision: Decision) -> None:
        """Log a decision to memory and file."""
        self.current_session.append(decision)
        
        # Log to file
        self._append_to_file(decision)
        
        # Log to standard logger with structured format
        logger.info(
            f"DECISION: {decision.decision_type.value} | "
            f"User: {decision.user_id} | "
            f"Action: {decision.action} | "
            f"Result: {decision.result} | "
            f"Reason: {decision.reason}"
        )
    
    def log_permission_check(
        self,
        user_id: str,
        command: str,
        required_permissions: List[str],
        user_permissions: List[str],
        result: bool,
        **kwargs
    ) -> Decision:
        """Log a permission check decision."""
        missing_perms = set(required_permissions) - set(user_permissions)
        
        decision = Decision(
            decision_type=DecisionType.PERMISSION_CHECK,
            command=command,
            user_id=user_id,
            action=f"check_permissions_for_{command}",
            result="granted" if result else "denied",
            reason=f"Brak uprawnień: {', '.join(missing_perms)}" if not result else "Wszystkie uprawnienia spełnione",
            checked_conditions=[
                {"permission": perm, "has": perm in user_permissions}
                for perm in required_permissions
            ],
            context={
                "required_permissions": required_permissions,
                "user_permissions": user_permissions,
                **kwargs
            }
        )
        
        self.log_decision(decision)
        return decision
    
    def log_moderation_action(
        self,
        moderator_id: str,
        target_id: str,
        action: str,
        reason: str,
        duration: Optional[int] = None,
        **kwargs
    ) -> Decision:
        """Log a moderation action."""
        decision = Decision(
            decision_type=DecisionType.MODERATION_ACTION,
            user_id=moderator_id,
            action=action,
            result="executed",
            reason=reason,
            context={
                "target_user": target_id,
                "duration_seconds": duration,
                **kwargs
            },
            reasoning_steps=[
                f"Moderator {moderator_id} zainicjował akcję",
                f"Sprawdzono uprawnienia moderatora",
                f"Zweryfikowano cel akcji: {target_id}",
                f"Wykonano akcję: {action}"
            ]
        )
        
        self.log_decision(decision)
        return decision
    
    def log_purchase_validation(
        self,
        user_id: str,
        item: str,
        price: int,
        user_balance: int,
        validation_steps: List[Dict[str, Any]],
        result: bool,
        **kwargs
    ) -> Decision:
        """Log a purchase validation decision."""
        decision = Decision(
            decision_type=DecisionType.PURCHASE_VALIDATION,
            user_id=user_id,
            action=f"validate_purchase_{item}",
            result="approved" if result else "rejected",
            reason=self._generate_purchase_reason(validation_steps, result),
            checked_conditions=validation_steps,
            context={
                "item": item,
                "price": price,
                "user_balance": user_balance,
                **kwargs
            },
            confidence=1.0 if all(step.get("passed", False) for step in validation_steps) else 0.0
        )
        
        self.log_decision(decision)
        return decision
    
    def log_ai_decision(
        self,
        user_id: str,
        ai_model: str,
        input_text: str,
        output: Any,
        confidence: float,
        reasoning: str,
        **kwargs
    ) -> Decision:
        """Log an AI-based decision."""
        decision = Decision(
            decision_type=DecisionType.AI_INFERENCE,
            user_id=user_id,
            action=f"ai_inference_{ai_model}",
            result=str(output),
            reason=reasoning,
            confidence=confidence,
            context={
                "model": ai_model,
                "input": input_text,
                "output": output,
                **kwargs
            }
        )
        
        self.log_decision(decision)
        return decision
    
    def get_user_decisions(self, user_id: str, limit: int = 10) -> List[Decision]:
        """Get recent decisions for a specific user."""
        user_decisions = [d for d in self.current_session if d.user_id == user_id]
        return user_decisions[-limit:]
    
    def get_command_decisions(self, command: str, limit: int = 10) -> List[Decision]:
        """Get recent decisions for a specific command."""
        cmd_decisions = [d for d in self.current_session if d.command == command]
        return cmd_decisions[-limit:]
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate a summary of all decisions in the current session."""
        if not self.current_session:
            return {"message": "No decisions logged yet"}
        
        summary = {
            "total_decisions": len(self.current_session),
            "by_type": {},
            "by_result": {"approved": 0, "denied": 0, "executed": 0, "rejected": 0},
            "average_confidence": 0.0,
            "total_users": len(set(d.user_id for d in self.current_session))
        }
        
        for decision in self.current_session:
            # Count by type
            dtype = decision.decision_type.value
            summary["by_type"][dtype] = summary["by_type"].get(dtype, 0) + 1
            
            # Count by result
            if decision.result in summary["by_result"]:
                summary["by_result"][decision.result] += 1
            
            # Sum confidence
            summary["average_confidence"] += decision.confidence
        
        summary["average_confidence"] /= len(self.current_session)
        
        return summary
    
    def _append_to_file(self, decision: Decision) -> None:
        """Append decision to session file."""
        try:
            with open(self.session_file, 'a') as f:
                f.write(decision.model_dump_json() + '\n')
        except Exception as e:
            logger.error(f"Failed to write decision to file: {e}")
    
    def _generate_purchase_reason(self, validation_steps: List[Dict[str, Any]], result: bool) -> str:
        """Generate a reason string from validation steps."""
        if result:
            return "Wszystkie warunki zakupu spełnione"
        
        failed_steps = [step for step in validation_steps if not step.get("passed", False)]
        if failed_steps:
            return f"Niespełnione warunki: {', '.join(step.get('reason', 'Unknown') for step in failed_steps)}"
        
        return "Zakup odrzucony z nieznanego powodu"