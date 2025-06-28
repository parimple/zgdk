# Lista Zadań Refaktoryzacji - zaGadka Bot

## 🔴 PILNE - Do naprawienia TERAZ

### 1. Naprawić komendę ranking/stats
- [ ] Sprawdzić dlaczego activity_service nie działa
- [ ] Dodać właściwe wstrzykiwanie serwisu
- [ ] Przetestować z różnymi parametrami
- **Pliki**: `cogs/commands/ranking.py`

### 2. Naprawić powiadomienia po bumpie
- [x] Naprawić metodę `get_last_notification` → `get_service_notification_log`
- [x] Naprawić pole `timestamp` → `sent_at`
- [x] Dodać obsługę interaction.user dla DISBOARD
- [ ] Sprawdzić uprawnienia bota na kanale bump
- [ ] Przetestować po zakończeniu cooldownu
- **Pliki**: `cogs/events/bump/handlers.py`, `cogs/events/bump/bump_event.py`

### 3. Naprawić komendy team
- [ ] Sprawdzić dlaczego nie ma odpowiedzi
- [ ] Zweryfikować czy cog jest ładowany
- [ ] Dodać logi debugowania
- **Pliki**: `cogs/commands/team/`

## 🟡 WAŻNE - Ten tydzień

### 4. Dokończyć migrację serwisów
- [ ] Sprawdzić które utility classes jeszcze istnieją
- [ ] Stworzyć interfejsy Protocol dla każdego
- [ ] Zaimplementować wstrzykiwanie zależności
- **Foldery**: `utils/`, `core/services/`

### 5. Podzielić duże pliki
- [ ] `cogs/commands/mod.py` → osobne pliki dla każdej funkcji
- [ ] `cogs/events/on_message.py` → podzielić na handlery
- [ ] `main.py` → wydzielić setup do osobnych modułów

### 6. Dodać polskie aliasy
- [ ] `/profil` dla `/profile`
- [ ] `/sklep` dla `/shop`
- [ ] `/pomoc` już działa
- [ ] Sprawdzić inne komendy

## 🟢 DODATKOWE - Później

### 7. Testy integracyjne
- [ ] Dokończyć testy dla bump commands
- [ ] Dodać testy dla voice commands
- [ ] Testy dla systemu premium

### 8. Dokumentacja
- [ ] Opisać system bumpów
- [ ] Dokumentacja architektury serwisowej
- [ ] Instrukcja dodawania nowych komend

### 9. Optymalizacja
- [ ] Cache dla często używanych zapytań
- [ ] Indeksy w bazie danych
- [ ] Lazy loading dla dużych danych

## 📊 Postęp

- **Ukończone**: 3/20 zadań (15%)
- **W trakcie**: 2 zadania
- **Oczekujące**: 15 zadań

## 🔧 Obecnie pracuję nad:
1. ✅ Testowanie komend przez MCP
2. 🔄 Naprawa powiadomień po bumpie (czekamy na cooldown)
3. 🔄 Debugowanie activity service dla ranking

## 📝 Notatki
- Token musi być eksportowany: `export ZAGADKA_TOKEN=...`
- Docker rebuild: `docker-compose down && docker-compose up -d --build`
- Testy MCP: `python test_commands.py`
- Bump cooldowny: Disboard 2h, Dzik 3h, Discadia 24h