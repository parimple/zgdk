# Plan Podziału Dużych Cogs

## info.py (54KB) → Podział na 3 moduły

### 1. info_server.py - Komendy serwerowe
- `ping` - sprawdzenie pingu
- `guild_info` - informacje o serwerze  
- `all_roles` - lista wszystkich ról
- `games` - lista gier użytkowników

### 2. info_user.py - Komendy użytkownika
- `profile` - profil użytkownika
- `list_invites` - lista zaproszeń użytkownika
- `help` - pomoc

### 3. info_admin.py - Komendy administracyjne
- `sync` - synchronizacja komend
- `bypass` - dodawanie bypassu
- `add_t` - dodawanie czasu T
- `check_roles` - sprawdzanie ról użytkownika
- `check_status` - sprawdzanie statusu użytkownika
- `force_check_user_premium_roles` - wymuszenie sprawdzenia ról premium

## premium.py (53KB) → Podział na 3 moduły

### 1. premium_user.py - Komendy dla użytkowników
- Zakup premium
- Sprawdzanie statusu premium
- Lista benefitów

### 2. premium_admin.py - Zarządzanie premium
- Przyznawanie premium
- Usuwanie premium
- Przedłużanie premium
- Statystyki premium

### 3. premium_team.py - Zarządzanie zespołami
- Tworzenie zespołów
- Zarządzanie członkami
- Uprawnienia zespołowe

## mod.py (39KB) → Podział na 2 moduły

### 1. mod_basic.py - Podstawowe komendy moderacyjne
- ban/unban
- kick
- mute/unmute
- warn

### 2. mod_advanced.py - Zaawansowane funkcje
- clear (czyszczenie wiadomości)
- slowmode
- lockdown
- role management

## Korzyści z podziału:
1. **Lepsza organizacja** - łatwiej znaleźć konkretną komendę
2. **Szybsze ładowanie** - mniejsze pliki ładują się szybciej
3. **Łatwiejsze testowanie** - można testować moduły osobno
4. **Mniejsze ryzyko konfliktów** - przy pracy zespołowej
5. **Zgodność z SRP** - każdy moduł ma jedną odpowiedzialność