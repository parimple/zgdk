# MCP (Model Context Protocol) Integration dla ZGDK

MCP pozwala na łatwą komunikację z botem Discord do testowania, debugowania i monitorowania.

## 🚀 Szybki Start

### 1. Włącz MCP w bocie

Dodaj do `.env`:
```bash
ENABLE_MCP=true
```

### 2. Uruchom bota z Docker

```bash
docker-compose up -d
```

### 3. Połącz się przez MCP Client

```bash
cd mcp
python mcp_client_example.py
```

## 📡 Dostępne Narzędzia MCP

### 1. **bot_status**
Sprawdza status bota i statystyki.

```python
result = await client.call_tool("bot_status", {})
# Zwraca: online, guild_count, member_count, uptime, latency
```

### 2. **execute_command**
Wykonuje komendę bota jako określony użytkownik.

```python
result = await client.call_tool("execute_command", {
    "command": "profile",
    "user_id": "123456789",
    "args": "",
    "guild_id": "960665311701528596"  # opcjonalne
})
```

### 3. **get_user_info**
Pobiera informacje o użytkowniku z bazy danych.

```python
result = await client.call_tool("get_user_info", {
    "user_id": "123456789"
})
# Zwraca: balance, premium_roles, team_name, activity_points
```

### 4. **modify_user_balance**
Modyfikuje saldo użytkownika (do testów).

```python
result = await client.call_tool("modify_user_balance", {
    "user_id": "123456789",
    "amount": 1000,  # dodatnie = dodaj, ujemne = odejmij
    "reason": "Test payment"
})
```

### 5. **analyze_decisions**
Analizuje decyzje bota (wymaga systemu interpretowalności).

```python
result = await client.call_tool("analyze_decisions", {
    "user_id": "123456789",  # opcjonalne
    "command": "buy",        # opcjonalne
    "limit": 10
})
```

### 6. **simulate_message**
Symuluje wiadomość Discord.

```python
result = await client.call_tool("simulate_message", {
    "content": "!help",
    "user_id": "123456789",
    "channel_id": "987654321",
    "guild_id": "960665311701528596"
})
```

### 7. **get_performance_stats**
Pobiera statystyki wydajności.

```python
result = await client.call_tool("get_performance_stats", {
    "command": "shop"  # opcjonalne, dla konkretnej komendy
})
```

## 💻 Tryb Interaktywny

Uruchom klienta w trybie interaktywnym:

```bash
python mcp_client_example.py
```

Dostępne komendy:
- `status` - Sprawdź status bota
- `user <id>` - Pobierz info o użytkowniku
- `cmd <command> <user_id> [args]` - Wykonaj komendę
- `balance <user_id> <amount>` - Zmień saldo
- `decisions [user_id]` - Analizuj decyzje
- `perf [command]` - Statystyki wydajności
- `quit` - Wyjdź

## 🧪 Przykłady Testów

### Test zakupu premium:

```bash
> balance 123456789 1000      # Dodaj 1000 zł
> cmd shop 123456789          # Pokaż sklep
> cmd buy 123456789 zG100     # Kup rangę
> user 123456789              # Sprawdź czy ma rangę
```

### Test moderacji:

```bash
> cmd mute 987654321 123456789 1h spam  # Admin wycisza użytkownika
> decisions 987654321                    # Zobacz decyzję
```

### Test wydajności:

```bash
> cmd profile 123456789       # Wykonaj komendę
> cmd profile 123456789       # Powtórz
> cmd profile 123456789       # Jeszcze raz
> perf profile               # Zobacz statystyki
```

## 🔧 Tworzenie Własnych Testów

```python
#!/usr/bin/env python3
import asyncio
from mcp.client import Client
from mcp.client.stdio import stdio_transport

async def test_premium_flow():
    """Test pełnego flow zakupu premium."""
    async with stdio_transport(
        Client("test-client"),
        "python", "mcp/zgdk_mcp_server.py"
    ) as transport:
        await transport.start()
        client = transport.client
        
        # 1. Sprawdź początkowy stan
        user = await client.call_tool("get_user_info", {
            "user_id": "123456789"
        })
        print(f"Początkowe saldo: {user['balance']}")
        
        # 2. Dodaj środki
        await client.call_tool("modify_user_balance", {
            "user_id": "123456789",
            "amount": 100,
            "reason": "Test funds"
        })
        
        # 3. Kup rangę
        result = await client.call_tool("execute_command", {
            "command": "buy",
            "user_id": "123456789",
            "args": "zG100"
        })
        
        # 4. Sprawdź rezultat
        if result['success']:
            user = await client.call_tool("get_user_info", {
                "user_id": "123456789"
            })
            print(f"Nowe role: {user['premium_roles']}")
            print(f"Pozostałe saldo: {user['balance']}")

asyncio.run(test_premium_flow())
```

## 🐛 Debugging z MCP

### 1. Śledź decyzje w czasie rzeczywistym:

```python
async def monitor_decisions():
    """Monitor decisions in real-time."""
    while True:
        decisions = await client.call_tool("analyze_decisions", {
            "limit": 5
        })
        
        for decision in decisions['decisions']:
            print(f"{decision['timestamp']}: {decision['type']} - {decision['reason']}")
        
        await asyncio.sleep(5)  # Check every 5 seconds
```

### 2. Testuj różne scenariusze:

```python
# Test cooldownów
await client.call_tool("execute_command", {
    "command": "daily",
    "user_id": "123456789"
})

# Sprawdź decyzję
decisions = await client.call_tool("analyze_decisions", {
    "user_id": "123456789",
    "limit": 1
})

if decisions['decisions'][0]['type'] == 'cooldown_check':
    print("Cooldown aktywny!")
```

## 🔒 Bezpieczeństwo

- MCP działa tylko gdy `ENABLE_MCP=true`
- Domyślnie nasłuchuje tylko lokalnie
- Wszystkie akcje są logowane
- Modyfikacje oznaczone jako "MCP adjustment"

## 📊 Monitorowanie

Użyj MCP do monitorowania bota:

```python
async def health_check():
    """Regular health check."""
    status = await client.call_tool("bot_status", {})
    
    if status['latency_ms'] > 200:
        print(f"⚠️ High latency: {status['latency_ms']}ms")
    
    if status['uptime_seconds'] < 60:
        print("⚠️ Bot recently restarted")
    
    return status['online']
```

## 🚀 Zaawansowane Użycie

### Integracja z CI/CD:

```yaml
# .github/workflows/test.yml
- name: Test Bot Commands
  run: |
    docker-compose up -d
    sleep 10  # Wait for bot to start
    python mcp/mcp_client_example.py --test $TEST_USER_ID
```

### Automatyczne testy wydajności:

```python
async def performance_regression_test():
    """Check if commands got slower."""
    baseline = {
        "profile": 50,  # ms
        "shop": 100,
        "team": 75
    }
    
    for cmd, expected_ms in baseline.items():
        stats = await client.call_tool("get_performance_stats", {
            "command": cmd
        })
        
        if stats['avg_duration_ms'] > expected_ms * 1.5:
            print(f"❌ {cmd} is too slow: {stats['avg_duration_ms']}ms")
```

---

MCP sprawia, że testowanie i debugowanie ZGDK jest proste i efektywne! 🎯