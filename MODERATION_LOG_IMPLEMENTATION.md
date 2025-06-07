# Implementacja systemu logowania akcji moderatorskich

## ✅ Co zostało zaimplementowane

### 1. **Nowy model bazy danych: ModerationLog**
- **Plik:** `datasources/models.py`
- **Tabela:** `moderation_logs`
- **Pola:**
  - `id` - Unikalny identyfikator akcji
  - `target_user_id` - ID użytkownika, na którym wykonano akcję
  - `moderator_id` - ID moderatora wykonującego akcję
  - `action_type` - Typ akcji ('mute', 'unmute', 'kick', 'ban')
  - `mute_type` - Typ mute'a ('nick', 'img', 'txt', 'live', 'rank')
  - `duration_seconds` - Czas trwania w sekundach (NULL = permanentny)
  - `reason` - Powód akcji (opcjonalny)
  - `channel_id` - ID kanału gdzie wykonano komendę
  - `created_at` - Data wykonania akcji
  - `expires_at` - Data wygaśnięcia (obliczana automatycznie)

### 2. **Nowe zapytania bazy danych: ModerationLogQueries**
- **Plik:** `datasources/queries.py`
- **Metody:**
  - `log_mute_action()` - Zapisuje akcję do bazy
  - `get_user_mute_history()` - Historia użytkownika
  - `get_user_mute_count()` - Liczba mute'ów użytkownika
  - `get_moderator_actions()` - Akcje wykonane przez moderatora
  - `get_mute_statistics()` - Statystyki serwera
  - `get_recent_actions()` - Ostatnie akcje

### 3. **Zmodyfikowany MuteManager**
- **Plik:** `utils/moderation/mute_manager.py`
- Metoda `_log_mute_action()` została rozszerzona o:
  - Zapisywanie akcji do bazy danych
  - Obsługa błędów bazy danych
  - Zachowanie oryginalnej funkcjonalności logowania na kanale

### 4. **Nowe komendy moderatorskie**
- **Plik:** `cogs/commands/mod.py`
- **Dostępne komendy:**
  - `,mutehistory @user [limit]` - Historia mute'ów użytkownika
  - `,mutestats [days]` - Statystyki mute'ów z serwera  
  - `,mutecount @user [days]` - Liczba mute'ów użytkownika

### 5. **Automatyczne logowanie**
- **Plik:** `cogs/events/on_task.py`
- Automatyczne unmute'y są teraz logowane do bazy danych
- Bot jest oznaczany jako moderator dla automatycznych akcji

### 6. **Skrypt migracji bazy danych**
- **Plik:** `create_moderation_log_table.py`
- Automatyczne tworzenie tabeli `moderation_logs`
- Tworzenie indeksów dla wydajności

## 🚀 Instrukcje uruchomienia

### Krok 1: Tworzenie tabeli w bazie danych

1. **Edytuj dane połączenia** w pliku `create_moderation_log_table.py`:
   ```python
   conn = await asyncpg.connect(
       host="twój_host",           # np. "localhost"
       port=5432,                  # twój port PostgreSQL
       user="twój_user",           # np. "postgres"
       password="twoje_hasło",     # hasło do bazy
       database="twoja_baza"       # nazwa bazy danych bota
   )
   ```

2. **Uruchom skrypt migracji:**
   ```bash
   python create_moderation_log_table.py
   ```

3. **Sprawdź czy tabela została utworzona:**
   ```sql
   \dt moderation_logs  -- w psql
   ```

### Krok 2: Restart bota

1. **Zatrzymaj bota**
2. **Uruchom ponownie** - nowe komendy będą dostępne automatycznie

## 📋 Przykłady użycia

### Sprawdzanie historii użytkownika
```
,mutehistory @ProblemUser 20
```
Pokaże ostatnie 20 akcji moderatorskich dla użytkownika.

### Statystyki serwera  
```
,mutestats 30
```
Pokaże statystyki mute'ów z ostatnich 30 dni:
- Całkowita liczba mute'ów
- Podział według typu mute'a
- Najczęściej mutowani użytkownicy
- Najaktywniejszi moderatorzy

### Liczba mute'ów użytkownika
```
,mutecount @User 7
```
Pokaże ile razy użytkownik był mutowany w ostatnich 7 dniach.

## 📊 Jakie dane są teraz dostępne

### Dla każdej akcji moderatorskiej zapisywane są:
- **Kto** wykonał akcję (moderator)
- **Na kim** wykonano akcję (użytkownik)
- **Jaki** typ akcji ('mute'/'unmute')
- **Jaki** typ mute'a ('nick', 'img', 'txt', 'live', 'rank')
- **Kiedy** wykonano akcję
- **Jak długo** miał trwać mute (jeśli dotyczy)
- **Gdzie** wykonano komendę (kanał)

### Możliwe analizy:
- Historia wszystkich akcji użytkownika
- Ile razy użytkownik był mutowany
- Który moderator jest najaktywniejszy
- Jakie typy mute'ów są najczęściej używane
- Trendy w moderacji (wzrost/spadek liczby mute'ów)

## 🔧 Funkcje dodatkowe

### Automatyczne logowanie
- **Manualne mute/unmute** - logowane przez MuteManager
- **Automatyczne unmute** - logowane przez zadania cykliczne
- **Wygaśnięcie roli** - logowane z botem jako moderatorem

### Obsługa błędów
- Jeśli baza danych nie działa, logi na kanale Discord nadal działają
- Błędy są logowane w konsoli dla debugowania
- Komendy gracefully obsługują błędy bazy danych

### Wydajność
- Indeksy na często używanych polach
- Limity na ilość wyników
- Optymalne zapytania SQL

## 🎯 Korzyści

### Dla moderatorów:
- ✅ Pełna historia akcji użytkownika
- ✅ Statystyki aktywności moderacyjnej
- ✅ Identyfikacja problematycznych użytkowników
- ✅ Śledzenie własnej aktywności

### Dla administracji:
- ✅ Audyt działań moderatorów
- ✅ Analiza trendów moderacyjnych
- ✅ Identyfikacja potrzeb szkoleniowych
- ✅ Statystyki do raportów

### Dla systemu:
- ✅ Trwałe przechowywanie danych
- ✅ Możliwość analiz historycznych
- ✅ Podstawa do przyszłych funkcji
- ✅ Automatyczne śledzenie wszystkich akcji

## 🔮 Przyszłe rozszerzenia

System jest przygotowany na łatwe dodanie:
- Powodów mute'ów (reason field)
- Logowania ban'ów i kick'ów
- Alertów o częstych mute'ach
- Automatycznych kar za powtarzające się problemy
- Eksportu danych do analiz zewnętrznych
- Dashboardu webowego ze statystykami 