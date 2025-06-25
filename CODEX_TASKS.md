# Zadania dla CodeX - Refaktoryzacja ZGDK

Po analizie PRs #6-13 wybrałem najlepsze pomysły do zaimplementowania. **Każde zadanie = osobny PR**.

## ✅ Zasady
- **Jeden PR = jedno zadanie**
- **Bazuj na aktualnym main branch** (nie na starych PRs)
- **Wszystkie testy muszą przechodzić** (43/43)
- **Kod musi być sformatowany** (black + isort)
- **Każdy PR musi mieć jasny opis co robi**

---

## 🎯 Zadanie 1: Cleanup imports i konfiguracja isort
**Priorytet: WYSOKI**

### Cel:
Posprzątać nieużywane importy i skonfigurować isort dla spójnego formatowania.

### Zakres:
1. **Usuń nieużywane importy** we wszystkich plikach Python
2. **Dodaj konfigurację isort** w `pyproject.toml`:
   ```toml
   [tool.isort]
   profile = "black"
   line_length = 88
   skip = [".venv", "__pycache__"]
   skip_gitignore = true
   known_first_party = ["cogs", "datasources", "utils"]
   ```
3. **Uruchom isort** na całym projekcie
4. **Dodaj brakujące `__init__.py`** gdzie potrzebne

### Kryteria akceptacji:
- ✅ `isort --check-only .` przechodzi bez błędów
- ✅ `black --check .` przechodzi bez błędów  
- ✅ Wszystkie testy przechodzą (43/43)
- ✅ Bot startuje bez błędów

---

## 🎯 Zadanie 2: Przeniesienie ID do config.yml
**Priorytet: ŚREDNI**

### Cel:
Przenieść hardcoded ID z kodu do pliku konfiguracyjnego.

### Zakres:
1. **Znajdź wszystkie hardcoded ID** w kodzie (role, kanały, kategorie)
2. **Dodaj je do config.yml** w odpowiednich sekcjach:
   ```yaml
   roles:
     booster: 1052692705718829117
     invite: 960665311760248879
     avatar_bot: 489377322042916885
   
   channels:
     premium_info: 960665316109713421
   
   categories:
     excluded: [1127590722015604766, 960665312200626199]
   ```
3. **Zaktualizuj kod** żeby używał `bot.config.roles.booster` zamiast hardcoded ID
4. **Dodaj fallbacki** dla missing config (defaulty 0 lub None)

### Kryteria akceptacji:
- ✅ Żadnych hardcoded ID w kodzie Python
- ✅ Wszystkie ID w config.yml
- ✅ Bot działa z nowym config
- ✅ Testy przechodzą

---

## 🎯 Zadanie 3: Dodanie type hints
**Priorytet: ŚREDNI**

### Cel:
Dodać type hints do funkcji i metod dla lepszej czytelności kodu.

### Zakres:
1. **Dodaj type hints** do wszystkich funkcji w `utils/`:
   - Return types: `-> None`, `-> bool`, `-> str`, etc.
   - Parameter types: `member: discord.Member`, `amount: int`, etc.
2. **Dodaj imports** dla typing: `from typing import Optional, List, Dict, Tuple`
3. **Skup się na publicznych metodach** (nie wszystkie prywatne)
4. **Dodaj type hints do nowych klas** jeśli jakieś powstają

### Przykład:
```python
async def add_balance(self, admin: discord.Member, user: discord.User, amount: int) -> Tuple[bool, str]:
    """Add balance to user wallet."""
    # implementation
```

### Kryteria akceptacji:
- ✅ Wszystkie publiczne metody w `utils/` mają type hints
- ✅ Kod się kompiluje bez błędów
- ✅ Testy przechodzą

---

## 🎯 Zadanie 4: Poprawa obsługi błędów i walidacji
**Priorytet: ŚREDNI**

### Cel:
Dodać lepszą obsługę błędów i walidację danych wejściowych.

### Zakres:
1. **Dodaj sprawdzanie config** w miejscach gdzie może być None:
   ```python
   # Zamiast:
   self.base_role_id = bot.config["color"]["base_role_id"]
   
   # Zrób:
   color_config = bot.config.get("color", {})
   self.base_role_id = color_config.get("base_role_id")
   if not self.base_role_id:
       logger.warning("base_role_id not configured")
   ```

2. **Dodaj walidację limitów** w voice commands:
   ```python
   if max_members < 1 or max_members > 99:
       await ctx.reply("Limit musi być między 1 a 99")
       return
   ```

3. **Popraw message_sender** żeby działał z różnymi typami context

### Kryteria akceptacji:
- ✅ Bot nie crashuje przy missing config
- ✅ Lepsze error messages dla userów
- ✅ Testy przechodzą

---

## 🎯 Zadanie 5: Usprawnienie CI/CD pipeline
**Priorytet: NISKI**

### Cel:
Poprawić GitHub Actions dla lepszego testowania.

### Zakres:
1. **Dodaj cache dla pip** w CI
2. **Dodaj Docker integration tests** (bez uruchamiania bota)
3. **Popraw .dockerignore** żeby wykluczać niepotrzebne pliki
4. **Dodaj step sprawdzający isort** w CI

### Kryteria akceptacji:
- ✅ CI działa szybciej (cache)
- ✅ Docker build testuje się automatycznie
- ✅ isort sprawdzany w CI

---

## 📋 Kolejność wykonania:

1. **Zadanie 1** (cleanup imports) - NAJPIERW
2. **Zadanie 2** (config IDs) - po zadaniu 1
3. **Zadanie 4** (error handling) - można równolegle z 2
4. **Zadanie 3** (type hints) - po zadaniu 2
5. **Zadanie 5** (CI/CD) - na końcu

---

## 🚫 Co NIE robić:

- ❌ **Nie dodawaj utils/services/** - zostało usunięte w PR #5
- ❌ **Nie rób masowych refaktorów** - małe zmiany
- ❌ **Nie zmieniaj architektury** - tylko cleanup i poprawki
- ❌ **Nie łącz zadań** - jeden PR = jedno zadanie

---

## 🔍 Sprawdzanie przed PR:

Przed każdym PR uruchom:
```bash
# Formatowanie
black --check .
isort --check-only .

# Testy
pytest -v

# Bot startup
python main.py --test-mode
```

Wszystko musi przechodzić! ✅ 