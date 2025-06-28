# Analiza Kosztów Orkiestracji AI dla ZGDK

## Porównanie Kosztów

### 1. **CrewAI**
- **Licencja**: MIT (open source) ✅
- **Koszt**: DARMOWE
- **Ale uwaga**: CrewAI domyślnie używa modeli OpenAI/Anthropic
- **Rzeczywisty koszt**: Zależy od używanych modeli AI

```python
# Przykład kosztów z CrewAI
# 1 zadanie = ~3-5 wywołań AI (agenci się komunikują)
# Koszt: 3-5x więcej niż pojedyncze wywołanie

# Z Gemini (darmowe do 1M tokenów):
- Darmowe: ~200k zadań CrewAI miesięcznie
- Po przekroczeniu: ~$0.0005 per zadanie

# Z OpenAI GPT-3.5:
- ~$0.006 per zadanie (3x wywołania)
- 1000 zadań = $6
```

### 2. **LangGraph**
- **Licencja**: MIT (open source) ✅
- **Koszt**: DARMOWE
- **Model**: Nie wymaga AI - to orkiestrator workflow
- **Rzeczywisty koszt**: 0 (jeśli nie używasz AI w nodach)

```python
# LangGraph sam nie generuje kosztów AI
# Koszty tylko jeśli dodasz AI do konkretnych nodów
# Możesz użyć zwykłej logiki Python = $0
```

### 3. **Alternatywy Open Source (Tańsze/Darmowe)**

#### **Temporal (workflow orchestration)**
- **Licencja**: MIT
- **Koszt**: DARMOWE
- **Use case**: Złożone workflow bez AI
```python
# Przykład dla moderacji
@workflow.defn
class ModerationWorkflow:
    @workflow.run
    async def run(self, message_data):
        # Czysta logika Python, bez AI
        threat = await workflow.execute_activity(
            analyze_patterns,  # Regex, nie AI
            message_data
        )
```

#### **Prefect**
- **Licencja**: Apache 2.0
- **Koszt**: DARMOWE (self-hosted)
- **Use case**: Task orchestration
```python
from prefect import flow, task

@task
def check_user_history(user_id):
    # Sprawdzanie w bazie, nie AI
    return db.get_violations(user_id)

@flow
def moderation_flow(message):
    history = check_user_history(message.user_id)
    action = decide_action(history)  # Prosta logika
    return execute_action(action)
```

#### **Apache Airflow**
- **Licencja**: Apache 2.0
- **Koszt**: DARMOWE
- **Use case**: Scheduled tasks (np. bump notifications)
```python
# DAG dla przypominania o bumpach
bump_dag = DAG(
    'bump_reminders',
    schedule_interval='*/5 * * * *',  # Co 5 minut
    default_args={'retries': 1}
)
```

## Rekomendowane Rozwiązanie (Najtańsze)

### **Hybrid Approach - Minimal AI**

```python
# core/workflows/moderation_workflow.py
from enum import Enum
from dataclasses import dataclass
from typing import Optional
import re

class ThreatLevel(Enum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3

@dataclass
class ModerationDecision:
    threat_level: ThreatLevel
    action: str
    duration: Optional[int]
    reason: str

class SimpleModerationWorkflow:
    """Workflow moderacji bez AI - czyste reguły."""
    
    def __init__(self):
        # Słownik złych słów (polski)
        self.bad_words = {
            'spam', 'scam', # ... więcej słów
        }
        
        # Wzorce spam
        self.spam_patterns = [
            re.compile(r'(.)\1{10,}'),  # Powtórzenia znaków
            re.compile(r'https?://\S+', re.IGNORECASE),  # Linki
        ]
    
    async def analyze_message(self, message: str, user_history: dict) -> ModerationDecision:
        """Analiza bez AI - czyste reguły."""
        threat_level = ThreatLevel.NONE
        reasons = []
        
        # 1. Sprawdź złe słowa
        message_lower = message.lower()
        for bad_word in self.bad_words:
            if bad_word in message_lower:
                threat_level = ThreatLevel.MEDIUM
                reasons.append(f"Niedozwolone słowo: {bad_word}")
        
        # 2. Sprawdź spam
        for pattern in self.spam_patterns:
            if pattern.search(message):
                threat_level = max(threat_level, ThreatLevel.LOW)
                reasons.append("Wykryto spam")
        
        # 3. Sprawdź historię użytkownika
        if user_history.get('violations', 0) > 3:
            threat_level = ThreatLevel.HIGH
            reasons.append("Recydywista")
        
        # 4. Decyzja o akcji
        if threat_level == ThreatLevel.HIGH:
            return ModerationDecision(
                threat_level=threat_level,
                action="ban",
                duration=None,
                reason="; ".join(reasons)
            )
        elif threat_level == ThreatLevel.MEDIUM:
            return ModerationDecision(
                threat_level=threat_level,
                action="mute",
                duration=3600,  # 1 godzina
                reason="; ".join(reasons)
            )
        elif threat_level == ThreatLevel.LOW:
            return ModerationDecision(
                threat_level=threat_level,
                action="warn",
                duration=None,
                reason="; ".join(reasons)
            )
        
        return ModerationDecision(
            threat_level=ThreatLevel.NONE,
            action="none",
            duration=None,
            reason="OK"
        )
```

### **Użyj AI tylko gdzie naprawdę potrzeba**

```python
# core/ai/smart_usage.py
class SmartAIUsage:
    """Używaj AI tylko dla skomplikowanych przypadków."""
    
    def __init__(self):
        self.simple_workflow = SimpleModerationWorkflow()
        self.ai_parser = DurationParser(use_ai=True)
    
    async def process_message(self, message: str, user_history: dict):
        # 1. Najpierw prosta analiza (DARMOWA)
        simple_result = await self.simple_workflow.analyze_message(
            message, user_history
        )
        
        # 2. Użyj AI tylko jeśli nie pewny
        if simple_result.threat_level == ThreatLevel.NONE and len(message) > 100:
            # Długa wiadomość, może coś przeoczyliśmy
            # TUTAJ dopiero użyj AI (płatne/limit)
            ai_result = await self.ai_analyze(message)
            return ai_result
        
        return simple_result
```

## Struktura Kosztów - Podsumowanie

### Najtańsze (Rekomendowane):
1. **LangGraph** + prosta logika Python = **$0**
2. **Temporal/Prefect** dla workflow = **$0**
3. **AI tylko dla 5% najtrudniejszych przypadków** = **$0-5/miesiąc**

### Średnie:
1. **CrewAI z Gemini** = **$0-20/miesiąc** (zależy od użycia)
2. **LangGraph z AI w niektórych nodach** = **$5-30/miesiąc**

### Drogie:
1. **CrewAI z GPT-4** = **$50-500/miesiąc**
2. **Pełna automatyzacja AI** = **$100-1000/miesiąc**

## Implementacja Dla ZGDK (Optymalna)

```python
# Użyj LangGraph dla flow (darmowe)
# + Gemini AI tylko gdzie konieczne (prawie darmowe)
# + Cache agresywnie (Redis)

# config.py
AI_USAGE_CONFIG = {
    "duration_parsing": {
        "use_ai": True,  # Gemini - trudne do reguł
        "cache_ttl": 86400  # 24h cache
    },
    "color_parsing": {
        "use_ai": False,  # Masz słownik kolorów
        "fallback_to_ai": True  # Tylko jeśli nie znaleziono
    },
    "moderation": {
        "use_ai": False,  # Reguły wystarczą
        "ai_threshold": 0.3  # Użyj AI jeśli confidence < 30%
    },
    "command_intent": {
        "use_ai": False,  # Masz mapowania komend
        "cache_ttl": 3600
    }
}
```

## Kalkulator Kosztów

```python
# Dla 1000 aktywnych użytkowników dziennie:

# Scenariusz 1: Wszystko z AI
# - 10k wiadomości/dzień do moderacji
# - 1k parsowań czasu
# - 500 parsowań kolorów
# Koszt: ~$30-50/dzień ❌

# Scenariusz 2: Hybrid (rekomendowany)
# - 10k wiadomości -> 100 do AI (1%)
# - 1k parsowań -> 50 do AI (5%)
# - 500 kolorów -> 10 do AI (2%)
# Koszt: ~$0.50/dzień z Gemini ✅

# Scenariusz 3: Bez AI
# - Wszystko przez reguły
# - Gorsza jakość, ale działa
# Koszt: $0 ✅
```

## Wnioski

1. **Zacznij od prostych reguł** - często wystarczają
2. **LangGraph jest darmowy** - używaj do orkiestracji
3. **AI tylko gdzie dodaje wartość** - np. naturalne parsowanie czasu
4. **Cache wszystko** - Redis zmniejszy koszty 10x
5. **Gemini first** - 1M tokenów free miesięcznie!

Dla ZGDK polecam:
- LangGraph dla workflow (darmowy)
- Gemini dla parsowania (prawie darmowy)  
- Reguły dla moderacji (darmowe)
- Cache z Redis (tani)

Total: **$0-10/miesiąc** dla średniego serwera Discord!