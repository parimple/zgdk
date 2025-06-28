# System Interpretowalności ZGDK

System interpretowalności dla bota Discord ZGDK, inspirowany badaniami Anthropic nad interpretowalnością modeli AI.

## 🎯 Cel Systemu

- **Transparentność**: Każda decyzja bota jest rejestrowana i może być wyjaśniona
- **Debugowanie**: Łatwe śledzenie problemów i wydajności
- **Zaufanie**: Użytkownicy mogą zrozumieć dlaczego bot podjął daną decyzję
- **Rozwój**: Analiza wzorców pomaga w ulepszaniu bota

## 🧠 Komponenty Systemu

### 1. Decision Logger (`decision_logger.py`)
Rejestruje każdą decyzję podjętą przez bota:

```python
# Przykład logowania decyzji o uprawnieniach
decision = bot.decision_logger.log_permission_check(
    user_id=str(ctx.author.id),
    command="ban",
    required_permissions=["administrator"],
    user_permissions=user_perms,
    result=has_permission
)
```

### 2. Feature Extractor (`feature_extractor.py`)
Wyodrębnia "cechy" z decyzji - wzorce zachowań bota:

```python
# Wyodrębnianie cech z decyzji
features = bot.feature_extractor.extract_features(decision)
# Zwraca: [("perm_admin_required", 1.0), ("mod_severity_high", 0.8)]
```

### 3. Action Explainer (`explainer.py`)
Tworzy czytelne wyjaśnienia dla użytkowników:

```python
# Wysłanie wyjaśnienia użytkownikowi
await bot.explainer.send_explanation(ctx, decision, level="detailed")
```

### 4. Command Tracer (`tracer.py`)
Śledzi wykonanie komend krok po kroku:

```python
@trace_command
async def complex_command(self, ctx):
    async with bot.tracer.trace_step(ctx.trace, "validate_input"):
        # Walidacja
    
    async with bot.tracer.trace_step(ctx.trace, "process_data"):
        # Przetwarzanie
```

## 📊 Typy Decyzji

### DecisionType Enum:
- `PERMISSION_CHECK` - Sprawdzanie uprawnień
- `MODERATION_ACTION` - Akcje moderacyjne
- `COMMAND_EXECUTION` - Wykonanie komendy
- `ROLE_ASSIGNMENT` - Przypisanie roli
- `PURCHASE_VALIDATION` - Walidacja zakupu
- `TEAM_MANAGEMENT` - Zarządzanie drużyną
- `VOICE_CHANNEL` - Kanały głosowe
- `AI_INFERENCE` - Decyzje AI
- `COOLDOWN_CHECK` - Sprawdzanie cooldownów
- `ERROR_HANDLING` - Obsługa błędów

## 🔍 Cechy (Features)

System automatycznie wykrywa i śledzi cechy zachowań:

### Cechy Uprawnień:
- `perm_admin_required` - Wymaga administratora
- `perm_premium_required` - Wymaga premium
- `perm_team_leader` - Wymaga bycia liderem

### Cechy Moderacji:
- `mod_spam_detected` - Wykryto spam
- `mod_repeat_offender` - Recydywista
- `mod_severity_high` - Wysokie zagrożenie

### Cechy Ekonomiczne:
- `econ_insufficient_funds` - Brak środków
- `econ_role_upgrade` - Upgrade rangi
- `econ_refund_calculated` - Obliczono zwrot

## 💻 Komendy Użytkownika

### `/explain last [level]`
Wyjaśnia ostatnią decyzję dotyczącą użytkownika
- `level`: simple, detailed, technical

### `/explain command <nazwa> [limit]`
Pokazuje ostatnie decyzje dla danej komendy (admin)

### `/trace active`
Pokazuje aktywnie śledzone komendy (admin)

### `/trace performance <komenda>`
Statystyki wydajności komendy (admin)

### `/features map`
Mapa cech decyzyjnych bota (admin)

### `/features analyze`
Analizuje ostatnią decyzję użytkownika

### `/features visualize [cecha]`
Wizualizacja powiązań między cechami

## 🔧 Integracja w Kodzie

### 1. Dodaj do nowej komendy:

```python
from core.interpretability import DecisionType
from core.interpretability.tracer import trace_command

class MyCog(commands.Cog):
    @commands.hybrid_command()
    @trace_command  # Automatyczne śledzenie
    async def my_command(self, ctx, arg):
        # Loguj decyzje
        decision = self.bot.decision_logger.log_decision(
            self.bot.decision_logger.Decision(
                decision_type=DecisionType.COMMAND_EXECUTION,
                command="my_command",
                user_id=str(ctx.author.id),
                action="execute_my_command",
                result="success",
                reason="Komenda wykonana pomyślnie",
                context={"arg": arg}
            )
        )
        
        # Wyślij wyjaśnienie jeśli coś poszło nie tak
        if error:
            await self.bot.explainer.send_explanation(ctx, decision)
```

### 2. Logowanie walidacji:

```python
validation_steps = [
    {
        "check": "Sprawdzenie salda",
        "passed": balance >= price,
        "reason": f"Brak środków" if balance < price else None
    },
    {
        "check": "Limit dzienny",
        "passed": daily_purchases < 10,
        "reason": "Przekroczono limit dzienny" if daily_purchases >= 10 else None
    }
]

decision = self.bot.decision_logger.log_purchase_validation(
    user_id=str(ctx.author.id),
    item="premium_role",
    price=100,
    user_balance=balance,
    validation_steps=validation_steps,
    result=all(step["passed"] for step in validation_steps)
)
```

### 3. Śledzenie kroków:

```python
async with self.bot.tracer.trace_step(ctx.trace, "database_query"):
    # Długa operacja bazodanowa
    result = await long_database_operation()

async with self.bot.tracer.trace_step(ctx.trace, "api_call", service="discord"):
    # Wywołanie API
    await member.add_roles(role)
```

## 📈 Analiza Wzorców

System automatycznie znajduje wzorce w decyzjach:

1. **Powiązane cechy** - które cechy często występują razem
2. **Dominujące wzorce** - najczęstsze typy decyzji
3. **Anomalie** - nietypowe decyzje wymagające uwagi

## 🎨 Wizualizacja

Komenda `/features visualize` tworzy grafy pokazujące:
- Powiązania między cechami
- Siłę korelacji
- Częstotliwość aktywacji

## 🔐 Bezpieczeństwo

- Tylko administratorzy mają dostęp do pełnych logów
- Użytkownicy widzą tylko swoje decyzje
- Wrażliwe dane są maskowane w logach

## 🚀 Przykłady Użycia

### Debugowanie problemu:
```
User: Dlaczego nie mogę kupić rangi?
Admin: /explain last detailed
Bot: Pokazuje szczegółową analizę z krokami walidacji
```

### Analiza wydajności:
```
Admin: /trace performance shop
Bot: Średni czas: 45.2ms, Min: 12ms, Max: 203ms
```

### Zrozumienie zachowania:
```
Admin: /features map
Bot: Pokazuje mapę wszystkich cech i ich powiązań
```

## 📚 Inspiracja

System inspirowany jest badaniami Anthropic nad interpretowalnością:
- Wyodrębnianie cech (features) z zachowań
- Mapowanie powiązań między cechami
- Manipulacja cechami (symulacja)
- Transparentność decyzji

Podobnie jak w badaniach nad Claude, nasz system pozwala:
1. Zrozumieć "co bot myśli" przed podjęciem decyzji
2. Zobaczyć które "cechy" się aktywują
3. Śledzić powiązania między różnymi aspektami zachowania
4. Debugować i ulepszać zachowanie bota

## 🔮 Przyszłe Rozszerzenia

1. **Dashboard webowy** - wizualizacja w czasie rzeczywistym
2. **Eksport raportów** - miesięczne analizy zachowań
3. **Alerty anomalii** - powiadomienia o nietypowych decyzjach
4. **A/B testing** - porównywanie różnych strategii decyzyjnych
5. **Uczenie się** - bot uczy się z własnych decyzji

---

System interpretowalności sprawia, że ZGDK jest nie tylko potężnym botem, ale także transparentnym i godnym zaufania narzędziem, którego decyzje można zrozumieć i zweryfikować.