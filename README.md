[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/ambv/black)
[![Code style: Prettier](https://img.shields.io/badge/code_style-Prettier-ff69b4.svg)](https://github.com/prettier/prettier)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![Python version](https://img.shields.io/badge/python-3.10-blue.svg)](https://www.python.org/downloads/release/python-3100/)

# zgdk

This is a Discord bot that does manage discord server channels, gives moderators the tools to manage the server and introduces currency, a ranking system and many other features.
gi

## Prerequisites

- Docker
- Python 3.10 or higher
- Discord account and API token

## Installation

1. Clone the repository:

`git clone https://gitlab.com/patrykpyzel/zgdk.git`

2. Create a `.env` file in the root directory of the project and set the following environment variable:

`DISCORD_TOKEN=<your Discord API token>`

3. Build the Docker image:

`docker build -t zgdk .`

4. Run the Docker container:

`docker run -d --name zgdk zgdk`

## Usage

To use the bot, invite it to a Discord server and use the following commands:

- `!help`: Display a list of available commands.
- `!ping`: Display bot latency.

## Architecture & Refactoring

We are in the process of improving the architecture of the project to make it more maintainable and extensible. The planned architecture follows a layered approach:

```
┌─ Presentation Layer ─┐
│  Commands, Events,   │
│  Views, Embeds       │
├─────────┬────────────┤
          │
┌─────────▼────────────┐
│    Service Layer     │
│  Service classes     │
├─────────┬────────────┤
          │
┌─────────▼────────────┐
│    Domain Layer      │
│  Business logic      │
├─────────┬────────────┤
          │
┌─────────▼────────────┐
│  Data Access Layer   │
│  Database operations │
└──────────────────────┘
```

For more details, see [ARCHITECTURE.md](ARCHITECTURE.md) and [SHOP_REFACTOR_PLAN.md](SHOP_REFACTOR_PLAN.md).

## Contributing

We welcome contributions to this project. If you are interested in contributing, please follow these guidelines:

- Fork the repository and make your changes in a feature branch.
- Run the tests to ensure that they pass.
- Follow the architectural guidelines described in ARCHITECTURE.md.
- Submit a pull request.

## License

This project is licensed under the MIT License.

## Funkcje głosowe

System zarządzania kanałami głosowymi z zaawansowanymi uprawnieniami.

### Komendy głosowe
- **speak/s** - Zarządzanie uprawnieniem mówienia
- **view/v** - Zarządzanie uprawnieniem widzenia kanału
- **connect/c** - Zarządzanie uprawnieniem połączenia
- **text/t** - Zarządzanie uprawnieniem pisania
- **live/lv** - Zarządzanie uprawnieniem streamowania
- **mod/m** - Zarządzanie moderatorami kanału
- **autokick/ak** - Zarządzanie listą autokick
- **reset/r** - Reset uprawnień kanału lub użytkownika
- **limit/l** - Ustawienie limitu użytkowników
- **voicechat/vc** - Informacje o kanale głosowym

### Automatyczne funkcje
- **Tworzenie kanałów** - Automatyczne tworzenie kanałów głosowych
- **Autokick** - Automatyczne wykopywanie niepożądanych użytkowników
- **Zarządzanie uprawnieniami** - Persistentne uprawnienia użytkowników
- **Optymalizacja wydajności** - Cache i asynchroniczne operacje

### Persistentne uprawnienia
System automatycznie przywraca uprawnienia użytkowników po ponownym dołączeniu na serwer:

1. **Gdy użytkownik opuszcza serwer:**
   - Discord automatycznie usuwa uprawnienia z kanałów
   - Dane pozostają zapisane w bazie danych

2. **Gdy użytkownik wraca na serwer:**
   - System sprawdza zapisane uprawnienia w bazie przy dołączaniu do kanału
   - Automatycznie aplikuje ograniczenia gdy właściciel kanału jest obecny
   - Sprawdza czy właściciel nadal ma uprawnienia do kanału (priority_speaker)

3. **Diagnostyka:**
   - `voice_stats` - Statystyki systemu z metrykami przywróconych uprawnień
   - `debug_permissions` - Szczegółowe informacje o uprawnieniach użytkownika

**Przykład:** Jeśli użytkownik miał zabronione połączenie (`c-`) od konkretnego właściciela kanału, a następnie opuścił serwer i wrócił, system automatycznie przywróci to ograniczenie gdy dołączy do kanału tego właściciela (jeśli właściciel nadal jest w kanale).

### Diagnostyczne komendy
- **voice_stats** - Statystyki systemu voice (tylko admini)
- **debug_permissions** - Sprawdzanie uprawnień w bazie danych (tylko admini)
