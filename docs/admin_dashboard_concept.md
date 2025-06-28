# Koncepcja Admin Dashboard dla zgdk Discord Bot

## 🎯 Cel
Stworzenie panelu administracyjnego do zarządzania subskrypcjami premium, przeglądania statystyk i monitorowania bota w czasie rzeczywistym.

## 🏗️ Architektura

### Backend
- **FastAPI** - lekki, asynchroniczny framework webowy (kompatybilny z asyncio używanym przez bota)
- **SQLAlchemy** - współdzielenie modeli z botem
- **WebSockets** - real-time updates dla dashboardu
- **JWT Authentication** - bezpieczny dostęp tylko dla adminów

### Frontend
- **React** + **TypeScript** - nowoczesny, type-safe frontend
- **Tailwind CSS** - szybkie stylowanie z dark mode
- **Recharts/Chart.js** - wykresy i wizualizacje
- **Tanstack Query** - cache'owanie i synchronizacja danych
- **Socket.io** - real-time updates

## 📊 Główne Funkcjonalności

### 1. Dashboard Główny
- **Widżety KPI**:
  - Liczba aktywnych subskrypcji premium (zG50/100/500/1000)
  - Przychód miesięczny/roczny
  - Liczba aktywnych użytkowników (24h/7d/30d)
  - Status bota (online/offline, ping, użycie RAM/CPU)

- **Wykresy**:
  - Trend subskrypcji premium (liniowy, ostatnie 30 dni)
  - Rozkład typów premium (kołowy)
  - Aktywność użytkowników (słupkowy, godzinowy)
  - Przychody w czasie (obszarowy)

### 2. Zarządzanie Premium

#### Lista Subskrypcji
```
[Wyszukiwarka] [Filtry: Typ | Status | Data wygaśnięcia]

| Użytkownik | Discord ID | Typ Premium | Data Zakupu | Wygasa | Status | Akcje |
|------------|------------|-------------|-------------|---------|---------|--------|
| User#1234  | 123456789  | zG500      | 2024-01-15  | 2024-02-15 | ✅ Aktywna | [Przedłuż][Anuluj] |
| User#5678  | 987654321  | zG100      | 2024-01-10  | 2024-01-25 | ⚠️ Wygasa | [Przedłuż][Przypomnij] |
```

#### Funkcje:
- **Filtry zaawansowane**:
  - Typ premium (zG50/100/500/1000)
  - Status (aktywne/wygasłe/wygasające w 7 dni)
  - Zakres dat
  - Sortowanie po dowolnej kolumnie

- **Akcje masowe**:
  - Eksport do CSV/Excel
  - Wysyłanie przypomnień o wygaśnięciu
  - Przedłużanie grupowe

- **Widok szczegółowy użytkownika**:
  - Historia subskrypcji
  - Historia płatności
  - Statystyki aktywności
  - Notatki administracyjne

### 3. Statystyki i Analityka

#### Sekcje:
1. **Przychody**:
   - Wykres przychodów dziennych/miesięcznych
   - Porównanie YoY/MoM
   - Prognoza przychodów
   - Top 10 użytkowników po wartości

2. **Retencja**:
   - Wskaźnik odnowień
   - Churn rate
   - Średni czas życia subskrypcji
   - Powody rezygnacji

3. **Aktywność**:
   - Użytkownicy online w czasie
   - Najpopularniejsze komendy
   - Wykorzystanie kanałów głosowych
   - Aktywność po dniach tygodnia

### 4. Zarządzanie Użytkownikami

- **Wyszukiwanie globalne** (po ID, nazwie, email)
- **Profile użytkowników**:
  - Dane podstawowe
  - Role i uprawnienia
  - Historia aktywności
  - Ekonomia (saldo zG, transakcje)
  - Team/klan membership

- **Akcje administracyjne**:
  - Nadawanie/odbieranie premium
  - Modyfikacja salda zG
  - Banowanie/odbanowanie
  - Reset hasła voice channela

### 5. Monitoring Bota

- **Status w czasie rzeczywistym**:
  - Uptime
  - Użycie zasobów (CPU, RAM, dysk)
  - Liczba serwerów
  - Ping do Discord API

- **Logi**:
  - Logi błędów (z filtrowaniem)
  - Logi komend
  - Logi płatności
  - Eksport logów

- **Alerty**:
  - Bot offline
  - Wysokie użycie zasobów
  - Błędy krytyczne
  - Masowe wygasanie subskrypcji

### 6. Konfiguracja

- **Ustawienia bota**:
  - Edycja config.yml przez UI
  - Zarządzanie rolami premium
  - Konfiguracja cen
  - Ustawienia auto-moderacji

- **Zarządzanie adminami**:
  - Lista adminów dashboardu
  - Poziomy dostępu
  - Logi aktywności adminów

## 🔐 Bezpieczeństwo

1. **Autentykacja**:
   - Login przez Discord OAuth2
   - Weryfikacja roli admina na serwerze
   - JWT z krótkim czasem życia
   - Refresh tokens

2. **Autoryzacja**:
   - Role-based access control (RBAC)
   - Różne poziomy dostępu (viewer, moderator, admin, super-admin)
   - Audit log wszystkich akcji

3. **Zabezpieczenia**:
   - HTTPS obowiązkowe
   - Rate limiting
   - CORS tylko dla zaufanych domen
   - Sanityzacja inputów

## 🚀 Funkcje Zaawansowane

### Real-time Updates
- WebSocket dla live updates:
  - Nowe subskrypcje
  - Wygasające subskrypcje
  - Status bota
  - Aktywni użytkownicy

### Powiadomienia
- **Email**:
  - Podsumowanie dzienne/tygodniowe
  - Alerty o problemach
  - Raporty miesięczne

- **Discord**:
  - Webhook z alertami
  - Podsumowania do kanału adminów

### Automatyzacja
- **Zadania cykliczne**:
  - Auto-przypomnienia o wygaśnięciu
  - Czyszczenie wygasłych ról
  - Generowanie raportów
  - Backup bazy danych

### API dla Integracji
- RESTful API z dokumentacją OpenAPI
- Webhooks dla zewnętrznych systemów
- Integracja z systemami płatności

## 📱 Responsywność

- **Desktop First** z pełną funkcjonalnością
- **Tablet** - podstawowe funkcje zarządzania
- **Mobile** - podgląd statystyk i alertów

## 🎨 UI/UX Inspirowane Twenty CRM

1. **Clean Design**:
   - Minimalistyczny interfejs
   - Dark mode domyślnie
   - Spójne kolory z botem Discord

2. **Intuicyjna Nawigacja**:
   - Sidebar z głównym menu
   - Breadcrumbs
   - Szybkie skróty klawiszowe

3. **Interaktywność**:
   - Drag & drop dla reorganizacji
   - Inline editing gdzie możliwe
   - Tooltips z pomocą

## 🛠️ Implementacja - Plan

### Faza 1 - MVP (2-3 tygodnie)
- [ ] Setup FastAPI + podstawowa autentykacja
- [ ] Dashboard z podstawowymi statystykami
- [ ] Lista subskrypcji premium z filtrowaniem
- [ ] Podstawowy monitoring bota

### Faza 2 - Rozszerzenie (3-4 tygodnie)
- [ ] Zaawansowane wykresy i analityka
- [ ] Zarządzanie użytkownikami
- [ ] System alertów
- [ ] Real-time updates przez WebSocket

### Faza 3 - Zaawansowane (4-6 tygodni)
- [ ] Pełna automatyzacja zadań
- [ ] API dla integracji
- [ ] Zaawansowane raportowanie
- [ ] Mobile app (opcjonalnie)

## 🔧 Stack Technologiczny - Podsumowanie

### Backend
```python
# requirements.txt
fastapi==0.104.1
uvicorn==0.24.0
sqlalchemy==2.0.15  # ta sama wersja co bot
asyncpg==0.29.0
python-jose[cryptography]==3.3.0  # JWT
python-multipart==0.0.6  # file uploads
aioredis==2.0.1  # cache
python-socketio==5.10.0  # websockets
```

### Frontend
```json
// package.json
{
  "dependencies": {
    "react": "^18.2.0",
    "typescript": "^5.3.0",
    "tailwindcss": "^3.4.0",
    "@tanstack/react-query": "^5.17.0",
    "recharts": "^2.10.0",
    "socket.io-client": "^4.7.0",
    "react-router-dom": "^6.21.0"
  }
}
```

## 📈 Korzyści

1. **Dla Adminów**:
   - Pełna kontrola nad subskrypcjami
   - Szybki wgląd w finanse
   - Proaktywne zarządzanie problemami

2. **Dla Użytkowników**:
   - Lepsza obsługa (szybsze rozwiązywanie problemów)
   - Transparentność systemu
   - Możliwość self-service (w przyszłości)

3. **Dla Rozwoju**:
   - Łatwiejsze debugowanie
   - Szybsze wykrywanie problemów
   - Dane do podejmowania decyzji biznesowych

## 🎯 Następne Kroki

1. **Walidacja koncepcji** z zespołem
2. **Prototyp UI** w Figma/Excalidraw
3. **Setup projektu** (monorepo vs separate)
4. **Implementacja MVP** z podstawowymi funkcjami
5. **Testy z prawdziwymi danymi**
6. **Iteracyjny rozwój** na podstawie feedbacku