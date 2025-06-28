# Konfiguracja Modeli AI dla ZGDK

## Używane Modele AI

Implementacja PydanticAI w projekcie używa **zewnętrznych API** - nie działa lokalnie. Potrzebujesz kluczy API do:

### 1. Google Gemini (REKOMENDOWANE - Najtańsze!)
- **Model**: `gemini-1.5-flash` 
- **Używane do**: Parsowanie czasu, kolorów, klasyfikacja intencji
- **Koszt**: **DARMOWE** do 1 miliona tokenów/miesiąc!
- **Po przekroczeniu**: ~$0.00015 za 1000 tokenów (10x taniej niż OpenAI)

### 2. OpenAI (Alternatywa)
- **Model**: `gpt-3.5-turbo`
- **Koszt**: ~$0.002 za 1000 tokenów

### 3. Anthropic (Opcjonalnie)
- **Model**: Claude (jeśli chcesz zmienić)
- **Koszt**: Podobny do OpenAI

## Konfiguracja Kluczy API

### Opcja 1: Zmienne środowiskowe (.env)
```bash
# Dodaj do pliku .env (wybierz jeden)

# Google Gemini (REKOMENDOWANE - najtańsze!)
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Lub OpenAI
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Lub Anthropic
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### Opcja 2: Bezpośrednio w kodzie
```python
# W pliku core/ai/duration_parser.py
self.agent = Agent(
    'openai:gpt-3.5-turbo',
    api_key='sk-xxxxxxxx'  # NIE POLECAM - lepiej użyć .env
)
```

## Jak Zdobyć Klucze API

### Google Gemini (REKOMENDOWANE! 🎉)
1. Idź na https://makersuite.google.com/app/apikey
2. Zaloguj się kontem Google
3. Kliknij "Create API Key"
4. Wybierz projekt lub stwórz nowy
5. Skopiuj klucz
6. **DARMOWY LIMIT**: 1 milion tokenów/miesiąc!

### OpenAI
1. Idź na https://platform.openai.com
2. Zarejestruj się / Zaloguj
3. Przejdź do "API Keys"
4. Kliknij "Create new secret key"
5. Skopiuj klucz (pokaże się tylko raz!)
6. Darmowe $5 kredytów przy rejestracji

### Anthropic
1. Idź na https://console.anthropic.com
2. Zarejestruj się / Zaloguj
3. Przejdź do "API Keys"
4. Utwórz nowy klucz

## Szacowane Koszty

### Z Google Gemini (REKOMENDOWANE):
- **Mało aktywny serwer** (100 komend AI/dzień): **DARMOWE** ✅
- **Średnio aktywny** (500 komend AI/dzień): **DARMOWE** ✅
- **Bardzo aktywny** (2000+ komend AI/dzień): **DARMOWE** lub ~$1-5/miesiąc

### Z OpenAI:
- **Mało aktywny serwer** (100 komend AI/dzień): ~$1-2/miesiąc
- **Średnio aktywny** (500 komend AI/dzień): ~$5-10/miesiąc
- **Bardzo aktywny** (2000+ komend AI/dzień): ~$20-50/miesiąc

## Tryb Bez AI (Fallback)

Wszystkie moduły mają tryb fallback - działają bez AI, ale z ograniczoną funkcjonalnością:

```python
# Wyłączenie AI w module
duration_parser = DurationParser(use_ai=False)  # Tylko podstawowe parsowanie
color_parser = ColorParser(use_ai=False)        # Tylko hex/rgb/podstawowe nazwy
```

## Zmiana Modelu

### Na Google Gemini (REKOMENDOWANE!)
```python
# W duration_parser.py, color_parser.py, etc.
self.agent = Agent(
    'google:gemini-1.5-flash',  # Szybki i darmowy!
    # 'google:gemini-1.5-pro',  # Lepszy ale droższy
    api_key=os.getenv('GEMINI_API_KEY')
)
```

### Na tańszy model OpenAI
```python
self.agent = Agent(
    'openai:gpt-3.5-turbo',  # Obecny (tani i dobry)
    # 'openai:gpt-4o-mini',  # Alternatywa (jeszcze tańszy)
)
```

### Na model Anthropic
```python
self.agent = Agent(
    'anthropic:claude-3-haiku',  # Najtańszy Claude
    # 'anthropic:claude-3-sonnet', # Średni
    # 'anthropic:claude-3-opus',   # Najlepszy (drogi)
)
```

### Na model lokalny (eksperymentalne)
PydanticAI wspiera lokalne modele przez Ollama:
```python
# Wymaga zainstalowania Ollama i pobrania modelu
self.agent = Agent(
    'ollama:llama2',  # Darmowy, lokalny
    # 'ollama:mistral', # Też darmowy
)
```

## Optymalizacja Kosztów

### 1. Cache odpowiedzi
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
async def cached_parse_color(color_str: str):
    return await color_parser.parse(color_str)
```

### 2. Ograniczenie użycia
```python
# W komendach
@commands.cooldown(1, 60, commands.BucketType.user)  # 1 użycie na minutę
async def kolor_ai(self, ctx, *, color: str):
    # ...
```

### 3. Użycie tylko dla premium
```python
if not has_premium:
    # Użyj podstawowego parsera bez AI
    color = ColorInput.parse(color_str)  # Bez AI
else:
    # Użyj AI dla premium
    color = await self.color_parser.parse(color_str)  # Z AI
```

## Monitorowanie Użycia

### Sprawdzanie zużycia OpenAI
1. Zaloguj się na https://platform.openai.com
2. Przejdź do "Usage"
3. Sprawdź dzienne/miesięczne zużycie

### Logi w bocie
```python
# Dodaj logowanie użycia
logger.info(f"AI parse request: {user_id} - {command} - {tokens_used}")
```

## Rekomendacje

1. **NA START**: Użyj Google Gemini - **DARMOWY** do 1M tokenów! 🎉
2. **Ustaw limity**: W Google Cloud Console (opcjonalnie)
3. **Monitoruj**: Sprawdzaj zużycie w konsoli Google
4. **Cache agresywnie**: Te same pytania = te same odpowiedzi
5. **Fallback zawsze**: AI może nie działać, bot musi działać dalej

## Dlaczego Gemini?

✅ **1 milion darmowych tokenów miesięcznie** (wystarczy na ~500k komend!)
✅ **10x tańszy po przekroczeniu** limitu niż OpenAI
✅ **Szybkie odpowiedzi** (gemini-1.5-flash)
✅ **Wsparcie dla polskiego** języka
✅ **Łatwa konfiguracja** (jedno konto Google)

## Przykład Pełnej Konfiguracji

```bash
# .env
DISCORD_TOKEN=your_discord_token

# AI - wybierz JEDEN (Gemini rekomendowane!)
GEMINI_API_KEY=AIzaSyxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
# OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

POSTGRES_USER=zagadka
POSTGRES_PASSWORD=your_password
POSTGRES_DB=zagadka_db
POSTGRES_PORT=5432

# Opcjonalne
AI_MODEL=gemini-1.5-flash  # lub gpt-3.5-turbo
AI_MAX_TOKENS=150
AI_TEMPERATURE=0.3
AI_CACHE_TTL=3600
```

## Testowanie Bez Płacenia

Możesz przetestować podstawową funkcjonalność bez AI:
```python
# Ustaw use_ai=False we wszystkich parserach
# Bot będzie działał, ale bez naturalnego języka
```

Lub użyj darmowych kredytów:
- OpenAI: $5 kredytów przy rejestracji
- Anthropic: $5 kredytów przy rejestracji