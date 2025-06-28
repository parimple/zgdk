"""
AI-enhanced duration parsing using PydanticAI.
"""

import asyncio
import re
import logging
from datetime import datetime, timedelta
from typing import Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from ..models.moderation import DurationInput

logger = logging.getLogger(__name__)


class EnhancedDurationInput(BaseModel):
    """Enhanced duration with AI interpretation."""
    raw_input: str
    seconds: int = Field(..., gt=0)
    human_readable: str
    confidence: float = Field(..., ge=0, le=1)
    interpretation: str
    expires_at: datetime
    
    @classmethod
    def from_duration_input(cls, duration: DurationInput, interpretation: str = "", confidence: float = 1.0) -> 'EnhancedDurationInput':
        """Create from basic DurationInput."""
        return cls(
            raw_input=duration.raw_input,
            seconds=duration.seconds,
            human_readable=duration.human_readable,
            confidence=confidence,
            interpretation=interpretation,
            expires_at=datetime.utcnow() + timedelta(seconds=duration.seconds)
        )


class DurationParser:
    """AI-powered duration parser for natural language."""
    
    def __init__(self, use_ai: bool = True):
        """Initialize parser with optional AI support."""
        self.use_ai = use_ai
        
        if use_ai:
            import os
            # Pobierz klucz API z zmiennych środowiskowych - Gemini jako priorytet
            gemini_key = os.getenv('GEMINI_API_KEY')
            openai_key = os.getenv('OPENAI_API_KEY')
            
            system_prompt = """Jesteś parserem czasu dla polskiego bota moderacyjnego na Discordzie.
                Konwertuj naturalne określenia czasu na sekundy.
                
                Przykłady:
                - "1 dzień" -> 86400
                - "tydzień" -> 604800
                - "2 godziny i 30 minut" -> 9000
                - "do jutra" -> oblicz sekundy do następnego dnia
                - "na weekend" -> oblicz do poniedziałku
                - "na zawsze" lub "permanentnie" -> -1
                - "pół godziny" -> 1800
                - "kwadrans" -> 900
                
                Zawsze odpowiadaj tylko liczbą sekund, lub -1 dla permanentnego.
                Dla niejednoznacznych wpisów, wybierz najbardziej rozsądną interpretację.
                Kontekst aktualnego czasu może być podany."""
            
            if gemini_key:
                self.agent = Agent(
                    'google-generativeai:gemini-1.5-flash',  # Darmowy do 1M tokenów/miesiąc!
                    api_key=gemini_key,
                    system_prompt=system_prompt
                )
                logger.info("Using Google Gemini for AI parsing (free tier)")
            elif openai_key:
                self.agent = Agent(
                    'openai:gpt-3.5-turbo',
                    api_key=openai_key,
                    system_prompt=system_prompt
                )
                logger.info("Using OpenAI for AI parsing")
            else:
                logger.warning("No API key found (GEMINI_API_KEY or OPENAI_API_KEY), AI features will be disabled")
                self.use_ai = False
    
    async def parse(self, duration_str: str, context: Optional[dict] = None) -> EnhancedDurationInput:
        """Parse duration string with AI enhancement."""
        # First try traditional parsing
        try:
            basic_duration = self._parse_traditional(duration_str)
            if basic_duration:
                return EnhancedDurationInput.from_duration_input(
                    basic_duration,
                    interpretation="Parsed using standard format",
                    confidence=1.0
                )
        except:
            pass
        
        # If traditional parsing fails and AI is enabled, use AI
        if self.use_ai:
            return await self._parse_with_ai(duration_str, context)
        else:
            raise ValueError(f"Cannot parse duration: {duration_str}")
    
    def _parse_traditional(self, duration_str: str) -> Optional[DurationInput]:
        """Traditional regex-based parsing."""
        # Check for permanent keywords (Polish)
        permanent_keywords = ['permanent', 'forever', 'indefinite', 'perma', 
                            'zawsze', 'na zawsze', 'permanentnie', 'dożywotnio']
        if any(keyword in duration_str.lower() for keyword in permanent_keywords):
            return None  # None represents permanent
        
        # Standard parsing
        pattern = r'(\d+)\s*([dwhmsDWHMS]?)'
        matches = re.findall(pattern, duration_str)
        
        if not matches:
            return None
        
        total_seconds = 0
        parts = []
        
        for amount, unit in matches:
            amount = int(amount)
            unit = unit.lower()
            
            if unit == 'd':
                total_seconds += amount * 86400
                parts.append(f"{amount} {'dzień' if amount == 1 else 'dni'}")
            elif unit == 'w':
                total_seconds += amount * 604800
                parts.append(f"{amount} {'tydzień' if amount == 1 else 'tygodni' if amount < 5 else 'tygodni'}")
            elif unit == 'h':
                total_seconds += amount * 3600
                parts.append(f"{amount} {'godzina' if amount == 1 else 'godziny' if amount < 5 else 'godzin'}")
            elif unit == 'm':
                total_seconds += amount * 60
                parts.append(f"{amount} {'minuta' if amount == 1 else 'minuty' if amount < 5 else 'minut'}")
            elif unit == 's' or not unit:
                total_seconds += amount
                parts.append(f"{amount} {'sekunda' if amount == 1 else 'sekundy' if amount < 5 else 'sekund'}")
        
        if total_seconds > 0:
            return DurationInput(
                raw_input=duration_str,
                seconds=total_seconds,
                human_readable=' '.join(parts)
            )
        
        return None
    
    async def _parse_with_ai(self, duration_str: str, context: Optional[dict] = None) -> EnhancedDurationInput:
        """Parse using AI for natural language understanding."""
        # Prepare context
        ai_context = {
            "current_time": datetime.utcnow().isoformat(),
            "input": duration_str
        }
        if context:
            ai_context.update(context)
        
        try:
            # Get AI interpretation
            result = await self.agent.run(
                f"Przetłumacz ten czas na sekundy: '{duration_str}'\nKontekst: {ai_context}"
            )
            
            # Extract seconds from response
            seconds = int(result.data)
            
            # Handle permanent duration
            if seconds == -1:
                raise ValueError("Permanent duration requested")
            
            # Generate human-readable format
            human_readable = self._seconds_to_human(seconds)
            
            return EnhancedDurationInput(
                raw_input=duration_str,
                seconds=seconds,
                human_readable=human_readable,
                confidence=0.9,  # AI parsing has slightly lower confidence
                interpretation=f"AI zinterpretowało jako {human_readable}",
                expires_at=datetime.utcnow() + timedelta(seconds=seconds)
            )
            
        except Exception as e:
            # Fallback to error
            raise ValueError(f"AI parsing failed: {str(e)}")
    
    def _seconds_to_human(self, seconds: int) -> str:
        """Convert seconds to human-readable format."""
        parts = []
        
        days = seconds // 86400
        if days > 0:
            parts.append(f"{days} {'dzień' if days == 1 else 'dni'}")
            seconds %= 86400
        
        hours = seconds // 3600
        if hours > 0:
            parts.append(f"{hours} {'godzina' if hours == 1 else 'godziny' if hours < 5 else 'godzin'}")
            seconds %= 3600
        
        minutes = seconds // 60
        if minutes > 0:
            parts.append(f"{minutes} {'minuta' if minutes == 1 else 'minuty' if minutes < 5 else 'minut'}")
            seconds %= 60
        
        if seconds > 0 or not parts:
            parts.append(f"{seconds} {'sekunda' if seconds == 1 else 'sekundy' if seconds < 5 else 'sekund'}")
        
        return ' '.join(parts)


# Convenience function for quick parsing
async def parse_duration(duration_str: str, use_ai: bool = True) -> EnhancedDurationInput:
    """Quick duration parsing function."""
    parser = DurationParser(use_ai=use_ai)
    return await parser.parse(duration_str)