"""
AI-powered moderation assistance using PydanticAI.
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ..models.moderation import ModerationType, MuteType


class ThreatLevel(str, Enum):
    """Threat level assessment."""
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ViolationType(str, Enum):
    """Types of violations detected."""
    SPAM = "spam"
    TOXICITY = "toxicity"
    HARASSMENT = "harassment"
    NSFW = "nsfw"
    ADVERTISING = "advertising"
    RAID = "raid"
    IMPERSONATION = "impersonation"
    DOXXING = "doxxing"
    OTHER = "other"


class ModerationSuggestion(BaseModel):
    """AI-generated moderation suggestion."""
    threat_level: ThreatLevel
    violations: List[ViolationType]
    suggested_action: ModerationType
    suggested_duration: Optional[int] = None  # seconds
    reason: str
    confidence: float = Field(..., ge=0, le=1)
    context_considered: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)
    
    @property
    def is_immediate_action_needed(self) -> bool:
        """Check if immediate action is recommended."""
        return self.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]
    
    @property
    def duration_text(self) -> str:
        """Get human-readable duration."""
        if not self.suggested_duration:
            return "permanent"
        
        seconds = self.suggested_duration
        if seconds < 3600:
            return f"{seconds // 60} minutes"
        elif seconds < 86400:
            return f"{seconds // 3600} hours"
        else:
            return f"{seconds // 86400} days"


class UserContext(BaseModel):
    """User context for moderation decisions."""
    user_id: str
    username: str
    join_date: datetime
    previous_violations: int = 0
    previous_warnings: int = 0
    previous_mutes: int = 0
    previous_bans: int = 0
    is_new_user: bool = False
    is_repeat_offender: bool = False
    recent_messages: List[str] = Field(default_factory=list)
    roles: List[str] = Field(default_factory=list)


class ModerationAssistant:
    """AI-powered moderation assistant."""
    
    def __init__(self, use_ai: bool = True):
        """Initialize moderation assistant."""
        self.use_ai = use_ai
        
        if use_ai:
            import os
            # Pobierz klucz API z zmiennych środowiskowych - Gemini jako priorytet
            gemini_key = os.getenv('GEMINI_API_KEY')
            openai_key = os.getenv('OPENAI_API_KEY')
            
            system_prompt = """Jesteś asystentem moderacji Discord. Analizuj wiadomości w języku polskim i angielskim.
                
                Odpowiadaj TYLKO w formacie czystego JSON:
                {
                    "threat_level": "none|low|medium|high|critical",
                    "violations": ["spam", "toxicity", "harassment", "nsfw", "advertising"],
                    "action": "warn|timeout|mute|kick|ban",
                    "duration": null lub liczba sekund,
                    "reason": "Krótkie wyjaśnienie po polsku",
                    "confidence": 0.0 do 1.0,
                    "context": ["Lista czynników które wzięto pod uwagę"],
                    "evidence": ["Konkretne cytaty lub dowody"]
                }
                
                Typy naruszeń:
                - spam: powtarzające się wiadomości, flood, spam znaków
                - toxicity: obraźliwe słowa, wulgaryzmy, hate speech
                - harassment: nękanie, groźby, ataki personalne
                - nsfw: treści nieodpowiednie
                - advertising: niechciane reklamy, linki do serwerów
                
                Poziomy zagrożenia:
                - none: brak naruszenia
                - low: drobne naruszenie
                - medium: wyraźne naruszenie zasad
                - high: poważne naruszenie
                - critical: natychmiastowe zagrożenie
                
                Sugerowane akcje:
                - warn: pierwsze naruszenie lub drobne
                - timeout: powtarzające się lub średnie naruszenia (300-3600 sekund)
                - mute: poważne naruszenia (3600-86400 sekund)
                - kick: bardzo poważne naruszenia
                - ban: krytyczne zagrożenia lub wielokrotni recydywiści"""
            
            if gemini_key:
                # Set API key in environment for pydantic-ai
                import os
                os.environ['GOOGLE_API_KEY'] = gemini_key
                self.agent = Agent(
                    'gemini-1.5-flash',  # Darmowy do 1M tokenów/miesiąc!
                    system_prompt=system_prompt,
                    result_type=str  # Force string output
                )
            elif openai_key:
                # Set API key in environment for pydantic-ai
                import os
                os.environ['OPENAI_API_KEY'] = openai_key
                self.agent = Agent(
                    'openai:gpt-4',  # Use GPT-4 for better moderation
                    system_prompt=system_prompt
                )
            else:
                self.use_ai = False
        
        # Pattern matching for common violations
        self.spam_patterns = [
            r'(.)\1{10,}',  # Character spam
            r'(\b\w+\b)(\s+\1){5,}',  # Word spam
            r'https?://\S+',  # URL spam (check frequency)
        ]
        
        self.toxicity_keywords = [
            # This would contain actual moderation keywords
            # Keeping it simple for example
            'spam', 'scam', 'hack'
        ]
    
    async def analyze_message(
        self,
        message: str,
        user_context: UserContext,
        server_rules: Optional[List[str]] = None
    ) -> ModerationSuggestion:
        """Analyze a message for potential violations."""
        # First do pattern-based analysis
        pattern_result = self._analyze_patterns(message, user_context)
        
        # If high confidence violation found, return immediately
        if pattern_result and pattern_result.confidence >= 0.9:
            return pattern_result
        
        # Use AI for more complex analysis
        if self.use_ai:
            ai_result = await self._analyze_with_ai(
                message, user_context, server_rules
            )
            
            # Combine results if both exist
            if pattern_result:
                return self._combine_analyses(pattern_result, ai_result)
            return ai_result
        
        # Return pattern result or no violation
        return pattern_result or ModerationSuggestion(
            threat_level=ThreatLevel.NONE,
            violations=[],
            suggested_action=ModerationType.WARN,
            reason="No violations detected",
            confidence=0.9
        )
    
    def _analyze_patterns(
        self,
        message: str,
        user_context: UserContext
    ) -> Optional[ModerationSuggestion]:
        """Pattern-based violation detection."""
        import re
        
        violations = []
        evidence = []
        
        # Check for character/word spam
        for pattern in self.spam_patterns[:2]:
            if re.search(pattern, message):
                violations.append(ViolationType.SPAM)
                evidence.append("Repetitive content detected")
                break
        
        # Check for excessive URLs
        urls = re.findall(r'https?://\S+', message)
        if len(urls) > 3:
            violations.append(ViolationType.SPAM)
            violations.append(ViolationType.ADVERTISING)
            evidence.append(f"Multiple URLs ({len(urls)}) in message")
        
        # Check for toxicity keywords
        lower_message = message.lower()
        for keyword in self.toxicity_keywords:
            if keyword in lower_message:
                violations.append(ViolationType.TOXICITY)
                evidence.append(f"Problematic keyword detected")
                break
        
        # Check message flood from user
        if len(user_context.recent_messages) >= 5:
            # Check if sending too fast
            violations.append(ViolationType.SPAM)
            evidence.append("Rapid message sending")
        
        if not violations:
            return None
        
        # Determine threat level and action
        if ViolationType.TOXICITY in violations:
            threat_level = ThreatLevel.HIGH
            action = ModerationType.MUTE
            duration = 3600  # 1 hour
        elif len(violations) > 1:
            threat_level = ThreatLevel.MEDIUM
            action = ModerationType.TIMEOUT
            duration = 600  # 10 minutes
        else:
            threat_level = ThreatLevel.LOW
            action = ModerationType.WARN
            duration = None
        
        # Adjust for repeat offenders
        if user_context.is_repeat_offender:
            if threat_level == ThreatLevel.LOW:
                threat_level = ThreatLevel.MEDIUM
                action = ModerationType.TIMEOUT
                duration = 1800  # 30 minutes
            elif threat_level == ThreatLevel.MEDIUM:
                threat_level = ThreatLevel.HIGH
                duration = (duration or 600) * 2
        
        return ModerationSuggestion(
            threat_level=threat_level,
            violations=list(set(violations)),
            suggested_action=action,
            suggested_duration=duration,
            reason=f"Detected: {', '.join(v.value for v in violations)}",
            confidence=0.8,
            evidence=evidence
        )
    
    async def _analyze_with_ai(
        self,
        message: str,
        user_context: UserContext,
        server_rules: Optional[List[str]] = None
    ) -> ModerationSuggestion:
        """AI-based message analysis."""
        try:
            # Prepare context for AI
            context = {
                "message": message,
                "user": {
                    "username": user_context.username,
                    "is_new": user_context.is_new_user,
                    "previous_violations": user_context.previous_violations,
                    "is_repeat_offender": user_context.is_repeat_offender
                },
                "recent_messages": user_context.recent_messages[-5:],
                "server_rules": server_rules or ["Be respectful", "No spam", "No NSFW"]
            }
            
            # Get AI analysis
            result = await self.agent.run(
                f"Analyze this Discord message for violations:\n{context}"
            )
            
            # Parse JSON response
            import json
            try:
                ai_data = json.loads(result.data)
            except:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{.*\}', result.data, re.DOTALL)
                if json_match:
                    ai_data = json.loads(json_match.group(0))
                else:
                    raise ValueError("Could not parse AI response")
            
            # Parse AI response
            violations = []
            for v in ai_data.get("violations", []):
                try:
                    violations.append(ViolationType(v))
                except:
                    pass
            
            # Map actions to our enums
            action_map = {
                "warn": ModerationType.WARN,
                "timeout": ModerationType.TIMEOUT,
                "mute": ModerationType.MUTE,
                "kick": ModerationType.KICK,
                "ban": ModerationType.BAN
            }
            
            return ModerationSuggestion(
                threat_level=ThreatLevel(ai_data.get("threat_level", "none")),
                violations=violations,
                suggested_action=action_map.get(ai_data.get("action", "warn"), ModerationType.WARN),
                suggested_duration=ai_data.get("duration"),
                reason=ai_data.get("reason", "AI analysis"),
                confidence=float(ai_data.get("confidence", 0.7)),
                context_considered=ai_data.get("context", []),
                evidence=ai_data.get("evidence", [])
            )
            
        except Exception as e:
            # Fallback on AI error
            return ModerationSuggestion(
                threat_level=ThreatLevel.NONE,
                violations=[],
                suggested_action=ModerationType.WARN,
                reason=f"AI analysis failed: {str(e)}",
                confidence=0.0
            )
    
    def _combine_analyses(
        self,
        pattern_result: ModerationSuggestion,
        ai_result: ModerationSuggestion
    ) -> ModerationSuggestion:
        """Combine pattern and AI analyses."""
        # Use the higher threat level
        threat_level = max(
            pattern_result.threat_level,
            ai_result.threat_level,
            key=lambda x: list(ThreatLevel).index(x)
        )
        
        # Combine violations
        all_violations = list(set(
            pattern_result.violations + ai_result.violations
        ))
        
        # Use more severe action
        action_severity = {
            ModerationType.WARN: 1,
            ModerationType.TIMEOUT: 2,
            ModerationType.MUTE: 3,
            ModerationType.KICK: 4,
            ModerationType.BAN: 5
        }
        
        if action_severity.get(pattern_result.suggested_action, 0) > \
           action_severity.get(ai_result.suggested_action, 0):
            action = pattern_result.suggested_action
            duration = pattern_result.suggested_duration
        else:
            action = ai_result.suggested_action
            duration = ai_result.suggested_duration
        
        # Average confidence
        confidence = (pattern_result.confidence + ai_result.confidence) / 2
        
        # Combine evidence
        all_evidence = pattern_result.evidence + ai_result.evidence
        
        return ModerationSuggestion(
            threat_level=threat_level,
            violations=all_violations,
            suggested_action=action,
            suggested_duration=duration,
            reason=f"Pattern and AI analysis: {', '.join(v.value for v in all_violations)}",
            confidence=confidence,
            context_considered=ai_result.context_considered,
            evidence=all_evidence
        )
    
    async def analyze_user_behavior(
        self,
        user_context: UserContext,
        time_window_hours: int = 24
    ) -> ModerationSuggestion:
        """Analyze overall user behavior patterns."""
        # This would analyze patterns over time
        # For now, simplified implementation
        
        if user_context.previous_violations > 5:
            return ModerationSuggestion(
                threat_level=ThreatLevel.HIGH,
                violations=[ViolationType.OTHER],
                suggested_action=ModerationType.BAN,
                reason="Excessive violations history",
                confidence=0.9,
                evidence=[f"{user_context.previous_violations} previous violations"]
            )
        
        if user_context.is_repeat_offender:
            return ModerationSuggestion(
                threat_level=ThreatLevel.MEDIUM,
                violations=[ViolationType.OTHER],
                suggested_action=ModerationType.TIMEOUT,
                suggested_duration=86400,  # 24 hours
                reason="Repeat offender pattern detected",
                confidence=0.8,
                evidence=["Multiple recent infractions"]
            )
        
        return ModerationSuggestion(
            threat_level=ThreatLevel.NONE,
            violations=[],
            suggested_action=ModerationType.WARN,
            reason="No concerning behavior patterns",
            confidence=0.9
        )