# Plan podziału dużych plików

Ten dokument zbiera pliki Pythona przekraczające 500 linii kodu i proponuje ich podział na mniejsze moduły. Zachowanie publicznego API jest priorytetem, a zmiany powinny jedynie organizować kod.

## Wykryte pliki > 500 linii

```bash
find . -name '*.py' -print0 | xargs -0 wc -l | sort -nr | awk '$1 > 500 {printf("%s %d\n", $2, $1)}'
```

Wynik z repozytorium (skrócony):

- `datasources/queries.py` – 1721 linii
- `cogs/views/shop_views.py` – 1330 linii
- `cogs/commands/info.py` – 1271 linii
- `cogs/events/on_bump.py` – 1263 linii
- `cogs/commands/premium.py` – 1252 linii
- `utils/message_sender.py` – 1003 linii
- `utils/voice/permissions.py` – 938 linii
- `cogs/events/on_member_join.py` – 868 linii
- `cogs/events/on_task.py` – 831 linii
- `cogs/commands/mod.py` – 763 linii
- `utils/moderation/mute_manager.py` – 701 linii
- `utils/managers/role_manager.py` – 697 linii
- `utils/moderation/message_cleaner.py` – 656 linii
- `utils/role_manager.py` – 623 linii
- `utils/managers/voice_manager.py` – 594 linii
- `cogs/commands/voice.py` – 528 linii
- `utils/premium_logic.py` – 525 linii
- `cogs/events/on_voice_state_update.py` – 525 linii
- `utils/premium_checker.py` – 512 linii
- `cogs/events/on_payment.py` – 512 linii
```

## Szczegółowe propozycje

### `cogs/events/on_voice_state_update.py`

Aktualny plik łączy logikę obsługi zdarzenia, tworzenia kanałów oraz autokicków. Proponowany podział:

1. **`events/voice/event_listener.py`** – główny `Cog` z metodą `on_voice_state_update` wywołującą kolejne moduły.
2. **`events/voice/channel_manager.py`** – funkcje tworzące i usuwające kanały, cache kategorii.
3. **`events/voice/autokick_worker.py`** – obsługa kolejek autokick i zadanie pracownika.
4. **`events/voice/permission_utils.py`** – obecne metody pomocnicze związane z uprawnieniami.

Interfejs publiczny (`setup(bot)` i nazwy metod `Cog`‑a) pozostaje bez zmian – plik główny importuje potrzebne klasy i deleguje do nich zadania.

### `cogs/commands/voice.py`

Ten plik zawiera wiele komend oraz logikę zarządzania kanałami i uprawnieniami. Podział na mniejsze moduły:

1. **`commands/voice/core.py`** – klasa `VoiceCog` z definicją komend. Każda komenda deleguje do serwisów.
2. **`commands/voice/services/channel_service.py`** – metody dołączania do kanału, ustawiania limitów, autokick itp.
3. **`commands/voice/services/permission_service.py`** – operacje `speak`, `text`, `mod`, `reset`, `debug_permissions`.
4. **`commands/voice/utils.py`** – funkcje pomocnicze np. `parse_target_and_value`.

Tak jak w przypadku wydarzenia, `VoiceCog` importuje te elementy, dzięki czemu API komend nie zmieni się dla użytkowników bota.

### `cogs/events/on_bump.py`

Plik obsługuje wiele serwisów (Disboard, Discadia, Discadia Vote, DiscordServers). Każda obsługa ma własną logikę analizy wiadomości i przyznawania nagród. Proponowane moduły:

1. **`events/bump/bump_cog.py`** – główny `Cog` z metodą `on_message` oraz `on_message_edit` delegującą do serwisów.
2. **`events/bump/services/<service>_service.py`** – osobny moduł dla `disboard`, `dzik`, `discadia`, `discordservers`. Każdy udostępnia funkcję `handle_message` i `handle_confirmation`.
3. **`events/bump/utils.py`** – wspólne funkcje: parsowanie ID użytkownika, obliczanie cooldownów i czasu trwania.

Dzięki temu każda logika bumpa staje się niezależnym komponentem, który łatwiej utrzymać i testować. `BumpCog` importuje te moduły i zachowuje istniejące API (`setup(bot)` i eventy).

## Dalsze kroki

1. Utworzyć nowe katalogi i przenieść odpowiedni kod, dodając importy w plikach głównych.
2. Upewnić się, że istniejące testy nadal przechodzą oraz że komendy bota działają bez zmian.
3. Stopniowo refaktoryzować pozostałe duże pliki wymienione w pierwszej sekcji.
