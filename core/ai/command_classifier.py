"""
AI-powered command intent classification using PydanticAI.
"""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent


class CommandCategory(str, Enum):
    """Command categories for classification."""
    SHOP = "shop"
    MODERATION = "moderation"
    INFO = "info"
    VOICE = "voice"
    PREMIUM = "premium"
    TEAM = "team"
    FUN = "fun"
    HELP = "help"
    UNKNOWN = "unknown"


class CommandIntent(BaseModel):
    """Classified command intent with metadata."""
    raw_message: str
    category: CommandCategory
    confidence: float = Field(..., ge=0, le=1)
    suggested_command: Optional[str] = None
    parameters: Dict[str, str] = Field(default_factory=dict)
    interpretation: str
    alternative_categories: List[CommandCategory] = Field(default_factory=list)


class CommandIntentClassifier:
    """AI-powered command intent detection and classification."""
    
    # Command keywords for fallback classification (Polish + English)
    CATEGORY_KEYWORDS = {
        CommandCategory.SHOP: [
            'buy', 'purchase', 'shop', 'balance', 'money', 'credits', 'wallet',
            'price', 'cost', 'premium', 'subscription', 'role',
            'kupić', 'zakup', 'sklep', 'saldo', 'pieniądze', 'kredyty', 'portfel',
            'cena', 'koszt', 'subskrypcja', 'rola'
        ],
        CommandCategory.MODERATION: [
            'mute', 'ban', 'kick', 'warn', 'timeout', 'unmute', 'unban',
            'punish', 'moderate', 'silence', 'report',
            'wycisz', 'zbanuj', 'wyrzuć', 'ostrzeż', 'ukaraj', 'moderuj',
            'ucisz', 'zgłoś', 'wyciszenie', 'wyciszać'
        ],
        CommandCategory.INFO: [
            'info', 'profile', 'stats', 'status', 'help', 'about', 'user',
            'server', 'member', 'whois', 'avatar',
            'informacje', 'profil', 'statystyki', 'pomoc', 'użytkownik',
            'serwer', 'członek', 'awatar'
        ],
        CommandCategory.VOICE: [
            'voice', 'channel', 'vc', 'speak', 'connect', 'view', 'live',
            'stream', 'mic', 'deafen', 'move',
            'głos', 'kanał', 'mówić', 'połącz', 'widok', 'transmisja',
            'mikrofon', 'przenieś', 'głosowy'
        ],
        CommandCategory.PREMIUM: [
            'premium', 'vip', 'upgrade', 'benefits', 'perks', 'subscribe',
            'tier', 'plan', 'features',
            'ulepszenie', 'korzyści', 'subskrybuj', 'poziom', 'funkcje'
        ],
        CommandCategory.TEAM: [
            'team', 'group', 'clan', 'guild', 'member', 'invite', 'join',
            'leave', 'roster', 'squad',
            'drużyna', 'grupa', 'klan', 'gildia', 'członek', 'zaproś', 'dołącz',
            'opuść', 'skład'
        ],
        CommandCategory.FUN: [
            'game', 'play', 'fun', 'meme', 'joke', 'random', 'dice',
            'coin', 'flip', '8ball',
            'gra', 'zagraj', 'zabawa', 'mem', 'żart', 'losowy', 'kości',
            'moneta', 'rzut'
        ],
        CommandCategory.HELP: [
            'help', 'command', 'how', 'tutorial', 'guide', 'explain',
            'what', 'usage', 'example',
            'pomoc', 'komenda', 'jak', 'poradnik', 'przewodnik', 'wyjaśnij',
            'co', 'użycie', 'przykład'
        ]
    }
    
    # Common command mappings (Polish + English)
    COMMAND_MAPPINGS = {
        # Shop commands - English
        "how to buy": ("shop", CommandCategory.SHOP),
        "check balance": ("balance", CommandCategory.SHOP),
        "show shop": ("shop", CommandCategory.SHOP),
        
        # Shop commands - Polish
        "jak kupić": ("shop", CommandCategory.SHOP),
        "sprawdź saldo": ("balance", CommandCategory.SHOP),
        "pokaż sklep": ("shop", CommandCategory.SHOP),
        
        # Moderation commands - English
        "silence user": ("mute", CommandCategory.MODERATION),
        "remove user": ("kick", CommandCategory.MODERATION),
        "punish member": ("warn", CommandCategory.MODERATION),
        
        # Moderation commands - Polish
        "wycisz użytkownika": ("mute", CommandCategory.MODERATION),
        "wyrzuć użytkownika": ("kick", CommandCategory.MODERATION),
        "ukaraj członka": ("warn", CommandCategory.MODERATION),
        
        # Info commands - English
        "user info": ("profile", CommandCategory.INFO),
        "server stats": ("serverinfo", CommandCategory.INFO),
        "my profile": ("profile", CommandCategory.INFO),
        
        # Info commands - Polish
        "informacje użytkownika": ("profile", CommandCategory.INFO),
        "statystyki serwera": ("serverinfo", CommandCategory.INFO),
        "mój profil": ("profile", CommandCategory.INFO),
        
        # Voice commands
        "create channel": ("voice create", CommandCategory.VOICE),
        "lock channel": ("voice lock", CommandCategory.VOICE),
        "stwórz kanał": ("voice create", CommandCategory.VOICE),
        "zablokuj kanał": ("voice lock", CommandCategory.VOICE),
        
        # Premium commands
        "upgrade account": ("premium", CommandCategory.PREMIUM),
        "show benefits": ("premium info", CommandCategory.PREMIUM),
        "ulepsz konto": ("premium", CommandCategory.PREMIUM),
        "pokaż korzyści": ("premium info", CommandCategory.PREMIUM),
    }
    
    def __init__(self, use_ai: bool = True):
        """Initialize classifier with optional AI support."""
        self.use_ai = use_ai
        
        if use_ai:
            import os
            # Pobierz klucz API z zmiennych środowiskowych - Gemini jako priorytet
            gemini_key = os.getenv('GEMINI_API_KEY')
            openai_key = os.getenv('OPENAI_API_KEY')
            
            system_prompt = """Jesteś klasyfikatorem intencji komend dla polskiego bota Discord.
                Klasyfikuj wiadomości użytkowników w kategorie komend i wydobądź intencję.
                
                Kategorie:
                - shop: zakupy, saldo, transakcje, role premium
                - moderation: wyciszanie, ban, kick, ostrzeżenia, timeout
                - info: pomoc, statystyki, profile, informacje o serwerze
                - voice: zarządzanie kanałami, uprawnienia
                - premium: subskrypcje, benefity, ulepszenia
                - team: zarządzanie drużyną/klanem
                - fun: gry, rozrywka
                - help: pomoc, tutoriale
                - unknown: niejasna intencja
                
                Format odpowiedzi:
                {
                    "category": "nazwa_kategorii",
                    "confidence": 0.0-1.0,
                    "suggested_command": "nazwa_komendy",
                    "parameters": {"param": "wartość"},
                    "interpretation": "krótkie wyjaśnienie"
                }"""
            
            if gemini_key:
                self.agent = Agent(
                    'google-generativeai:gemini-1.5-flash',  # Darmowy do 1M tokenów/miesiąc!
                    api_key=gemini_key,
                    system_prompt=system_prompt
                )
            elif openai_key:
                self.agent = Agent(
                    'openai:gpt-3.5-turbo',
                    api_key=openai_key,
                    system_prompt=system_prompt
                )
            else:
                self.use_ai = False
    
    async def classify(self, message: str, context: Optional[Dict] = None) -> CommandIntent:
        """Classify user message intent."""
        message = message.strip().lower()
        
        # First try keyword-based classification
        keyword_result = self._classify_by_keywords(message)
        if keyword_result.confidence >= 0.8:
            return keyword_result
        
        # If AI is enabled and keyword confidence is low, use AI
        if self.use_ai:
            ai_result = await self._classify_with_ai(message, context)
            # Combine results if keyword had some confidence
            if keyword_result.confidence > 0.3:
                return self._combine_results(keyword_result, ai_result)
            return ai_result
        
        return keyword_result
    
    def _classify_by_keywords(self, message: str) -> CommandIntent:
        """Classify using keyword matching."""
        # Check direct command mappings
        for phrase, (command, category) in self.COMMAND_MAPPINGS.items():
            if phrase in message:
                return CommandIntent(
                    raw_message=message,
                    category=category,
                    confidence=0.9,
                    suggested_command=command,
                    interpretation=f"Matched phrase '{phrase}'",
                    parameters={}
                )
        
        # Score each category by keyword matches
        category_scores = {}
        words = message.split()
        
        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for word in words if word in keywords)
            if score > 0:
                category_scores[category] = score
        
        if not category_scores:
            return CommandIntent(
                raw_message=message,
                category=CommandCategory.UNKNOWN,
                confidence=0.0,
                interpretation="No matching keywords found",
                parameters={}
            )
        
        # Sort by score
        sorted_categories = sorted(
            category_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        best_category = sorted_categories[0][0]
        best_score = sorted_categories[0][1]
        
        # Calculate confidence based on score
        confidence = min(best_score * 0.3, 0.9)
        
        # Get alternatives
        alternatives = [cat for cat, _ in sorted_categories[1:3]]
        
        return CommandIntent(
            raw_message=message,
            category=best_category,
            confidence=confidence,
            interpretation=f"Keyword matches: {best_score}",
            alternative_categories=alternatives,
            parameters={}
        )
    
    async def _classify_with_ai(self, message: str, context: Optional[Dict] = None) -> CommandIntent:
        """Classify using AI."""
        try:
            # Prepare context
            ai_context = {"message": message}
            if context:
                ai_context.update(context)
            
            # Get AI classification
            result = await self.agent.run(
                f"Classify this Discord bot command intent: '{message}'\nContext: {ai_context}",
                result_type=Dict
            )
            
            # Parse AI response
            ai_data = result.data
            
            return CommandIntent(
                raw_message=message,
                category=CommandCategory(ai_data.get("category", "unknown")),
                confidence=float(ai_data.get("confidence", 0.7)),
                suggested_command=ai_data.get("suggested_command"),
                parameters=ai_data.get("parameters", {}),
                interpretation=ai_data.get("interpretation", "AI classified")
            )
            
        except Exception as e:
            # Fallback on AI error
            return CommandIntent(
                raw_message=message,
                category=CommandCategory.UNKNOWN,
                confidence=0.0,
                interpretation=f"AI classification failed: {str(e)}",
                parameters={}
            )
    
    def _combine_results(self, keyword_result: CommandIntent, ai_result: CommandIntent) -> CommandIntent:
        """Combine keyword and AI results."""
        # If they agree, boost confidence
        if keyword_result.category == ai_result.category:
            combined_confidence = min(
                (keyword_result.confidence + ai_result.confidence) / 1.5,
                0.95
            )
            return CommandIntent(
                raw_message=keyword_result.raw_message,
                category=keyword_result.category,
                confidence=combined_confidence,
                suggested_command=ai_result.suggested_command or keyword_result.suggested_command,
                parameters=ai_result.parameters,
                interpretation=f"Keyword and AI agree: {keyword_result.category.value}",
                alternative_categories=[]
            )
        
        # If they disagree, use the one with higher confidence
        if ai_result.confidence > keyword_result.confidence:
            ai_result.alternative_categories = [keyword_result.category]
            return ai_result
        else:
            keyword_result.alternative_categories = [ai_result.category]
            return keyword_result


# Convenience function
async def classify_intent(message: str, use_ai: bool = True) -> CommandIntent:
    """Quick intent classification function."""
    classifier = CommandIntentClassifier(use_ai=use_ai)
    return await classifier.classify(message)