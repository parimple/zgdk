# Live Bot Testing

Katalog zawiera testy które sprawdzają prawdziwe komendy Discord bot poprzez wysyłanie ich jako użytkownik i oczekiwanie odpowiedzi.

## Struktura

```
test_live_bot/
├── live_commands_test.py           # Podstawowy test komend
├── comprehensive_shop_test.py      # Komprehensywny test sklepu (nieaktualny)
├── simple_shop_test.py            # Prosty test sklepu z detekcją buttonów
├── run_test.sh                    # Podstawowy skrypt uruchamiający 
├── run_test_with_logs.sh          # Test z analizą logów
├── run_shop_tests.sh              # Komprehensywny test sklepu (nieaktualny)
├── run_simple_shop_test.sh        # Prosty test sklepu
├── results/                       # Wyniki testów (JSON)
└── README.md                      # Ta dokumentacja
```

## Użycie

### Podstawowe testy komend
```bash
# Z .env
source .env && ./test_live_bot/run_test_with_logs.sh

# Bezpośrednio z tokenem
CLAUDE_BOT_TOKEN="your_token" ./test_live_bot/run_test_with_logs.sh
```

### Testy sklepu (ZALECANE)
```bash
# Test sklepu z detekcją buttonów
source .env && ./test_live_bot/run_simple_shop_test.sh

# Bezpośrednio z tokenem
CLAUDE_BOT_TOKEN="your_token" ./test_live_bot/run_simple_shop_test.sh
```

## Co testuje

### Podstawowe testy (`live_commands_test.py`)
1. **,addbalance <@user> 1000** - Dodanie balance do użytkownika
2. **,profile** - Sprawdzenie profilu
3. **,shop** - Wyświetlenie sklepu

### Testy sklepu (`simple_shop_test.py`)
1. **💰 Balance management** - Dodawanie środków na konto
2. **👤 Profile verification** - Sprawdzanie profilu przed/po operacjach
3. **🏪 Shop display** - Wyświetlenie sklepu z buttonami
4. **🔘 Button detection** - Wykrywanie interaktywnych buttonów
5. **🔍 Error monitoring** - Monitorowanie błędów Docker i logów

## Wyniki

- Wyniki zapisywane są do `test_live_bot/results/live_test_YYYYMMDD_HHMMSS.json`
- Konsola pokazuje live output z każdej komendy
- Success rate i podsumowanie na końcu

## Wymagania techniczne

- `discord.py-self` (do logowania jako użytkownik)
- Token użytkownika Discord w `CLAUDE_BOT_TOKEN`
- Dostęp do serwera zaGadka i kanału #cicd
- Bot musi być online i działający

## Manual Testing Sklepu (WAŻNE!)

Ponieważ shop używa interaktywnych buttonów, automatyczne testowanie pełnego flow kupna nie jest możliwe. Po uruchomieniu testów:

### Kroki manual testingu:
1. **Idź do Discord serwera zaGadka**
2. **Przejdź do kanału #cicd**
3. **Użyj komendy `,shop`**
4. **Kliknij na buttony ról (zG50, zG100, etc.)**
5. **Przetestuj flow:**
   - 🛒 Kupno nowej rangi
   - ⏰ Przedłużenie istniejącej rangi  
   - ⬆️ Upgrade z niższej do wyższej rangi
   - 💸 Sprzedaż rangi (jeśli dostępne)

### Sprawdzanie rezultatów:
- Sprawdź `,profile` po każdej operacji
- Sprawdź saldo portfela
- Sprawdź daty wygaśnięcia rang

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

### "Shop buttons not detected"
- Shop może używać innego formatu buttonów
- Sprawdź manual w Discord czy shop się wyświetla poprawnie

## Bezpieczeństwo

⚠️ **Uwaga**: Ten test używa prawdziwego tokenu użytkownika Discord. Zachowaj ostrożność:
- Nie commituj tokenów do repo
- Używaj tylko w kontrolowanym środowisku
- Testy wysyłają prawdziwe komendy do Discord