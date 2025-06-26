# Live Bot Testing

Katalog zawiera testy które sprawdzają prawdziwe komendy Discord bot poprzez wysyłanie ich jako użytkownik i oczekiwanie odpowiedzi.

## Struktura

```
test_live_bot/
├── live_commands_test.py    # Główny skrypt testujacy
├── run_test.sh             # Skrypt uruchamiający 
├── results/                # Wyniki testów (JSON)
└── README.md              # Ta dokumentacja
```

## Użycie

### Metoda 1: Z .env
```bash
source .env && ./test_live_bot/run_test.sh
```

### Metoda 2: Bezpośrednio z tokenem
```bash
CLAUDE_BOT_TOKEN="your_token" ./test_live_bot/run_test.sh
```

### Metoda 3: Bezpośrednio python
```bash
export CLAUDE_BOT_TOKEN="your_token"
python test_live_bot/live_commands_test.py
```

## Co testuje

1. **,addbalance <@user> 1000** - Dodanie balance do użytkownika
2. **,profile** - Sprawdzenie profilu
3. **,shop** - Wyświetlenie sklepu

## Wyniki

- Wyniki zapisywane są do `test_live_bot/results/live_test_YYYYMMDD_HHMMSS.json`
- Konsola pokazuje live output z każdej komendy
- Success rate i podsumowanie na końcu

## Wymagania techniczne

- `discord.py-self` (do logowania jako użytkownik)
- Token użytkownika Discord w `CLAUDE_BOT_TOKEN`
- Dostęp do serwera zaGadka i kanału #cicd
- Bot musi być online i działający

## Rozwiązywanie problemów

### "module 'discord' has no attribute 'Intents'"
- To normalne - discord.py-self ma inne API niż discord.py
- Skrypt jest napisany specjalnie dla discord.py-self

### "Could not find guild or channel"
- Sprawdź czy token ma dostęp do serwera zaGadka
- Sprawdź czy kanał cicd istnieje

### "No bot responses detected"
- Sprawdź czy bot jest online: `docker-compose logs app --tail=20`
- Sprawdź czy bot odpowiada na komendy ręcznie w Discord

## Bezpieczeństwo

⚠️ **Uwaga**: Ten test używa prawdziwego tokenu użytkownika Discord. Zachowaj ostrożność:
- Nie commituj tokenów do repo
- Używaj tylko w kontrolowanym środowisku
- Testy wysyłają prawdziwe komendy do Discord