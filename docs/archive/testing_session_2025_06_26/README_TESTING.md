# Discord Bot Testing Framework

## Przegląd

Ten dokument opisuje kompletny framework testowania dla Discord bota zaGadka, włączając w to:
- Testy jednostkowe (unit tests)
- Testy integracyjne (integration tests) 
- Testy live funkcjonalności
- CI/CD pipeline z GitHub Actions

## Struktura Testów

```
zgdk/
├── tests/
│   ├── __init__.py
│   ├── test_config.py              # Konfiguracja testów
│   ├── test_basic_functionality.py # Testy jednostkowe
│   └── integration/
│       └── test_shop_integration.py # Testy integracyjne
├── test_live_functionality.py      # Testy live funkcjonalności
├── .github/
│   └── workflows/
│       └── discord-bot-tests.yml   # GitHub Actions CI/CD
└── README_TESTING.md               # Ten dokument
```

## Konfiguracja Testowa

### Test User & Environment
- **Test User ID**: `968632323916566579` (dodany jako test_owner_id)
- **Test Channel ID**: `1387864734002446407`
- **Guild ID**: `960665311701528596`

### Tokeny
- **CLAUDE_BOT**: Token dla test bota
- **ZAGADKA_TOKEN**: Token głównego bota (do monitorowania)
- **TIPO_API_TOKEN**: Token API płatności

## Typy Testów

### 1. Testy Jednostkowe (`tests/test_basic_functionality.py`)

Testują pojedyncze komponenty:
- Premium Service functionality
- Invite system fix verification
- Shop functionality logic
- Data structure consistency
- Error logging structure

**Uruchomienie:**
```bash
python -m pytest tests/test_basic_functionality.py -v
```

### 2. Testy Integracyjne (`tests/integration/test_shop_integration.py`)

Testują end-to-end flows:
- Balance management
- Shop display
- Role purchase flow
- Error handling

**Uruchomienie:**
```bash
python tests/integration/test_shop_integration.py
```

### 3. Testy Live Funkcjonalności (`test_live_functionality.py`)

Monitorują rzeczywisty bot przez logi Docker:
- Bot responsiveness
- Invite system health
- Activity tracking
- Premium system health

**Uruchomienie:**
```bash
python test_live_functionality.py
```

### 4. CI/CD Pipeline (`.github/workflows/discord-bot-tests.yml`)

Automatyczne testy przy push/PR:
- Unit tests
- Linting (black, isort, pylint)
- Security scanning
- Integration tests (jeśli tokeny dostępne)

## Kluczowe Naprawki Zweryfikowane Testami

### 1. ✅ Invite System Fix
**Problem**: `UniqueViolationError` dla duplikatów invite
**Naprawka**: Zmiana z `create_invite()` na `add_or_update_invite()`
**Test**: `test_invite_upsert_logic()` w unit tests

### 2. ✅ Role Data Structure Fix  
**Problem**: Tuple unpacking vs Dictionary access
**Naprawka**: Unified dictionary-based role data
**Test**: `test_role_data_structure()` w unit tests

### 3. ✅ Service Architecture Migration
**Problem**: Mixed legacy utilities and new services
**Naprawka**: Consistent service pattern with dependency injection
**Test**: `test_service_architecture_consistency()` w unit tests

### 4. ✅ Owner Permissions Extension
**Problem**: Tylko jeden owner_id w config
**Naprawka**: Added test_owner_id support
**Test**: Manual verification through addbalance command

## Live Testing Workflow

### Faza 1: Przygotowanie
1. **Setup owner permissions**: Dodano test_owner_id do config
2. **Verify bot status**: Sprawdzenie że bot jest online
3. **Check logs**: Brak krytycznych błędów

### Faza 2: Balance Testing
```bash
# W Discord:
/addbalance @user 1000
/profile  # Verify balance shows 1000G
```

### Faza 3: Shop Testing
```bash
# W Discord:
/shop  # View available roles
# Click purchase button for zG50 (49G)
# Verify role assignment and balance deduction
```

### Faza 4: Verification
```bash
python test_live_functionality.py  # Run automated checks
```

## CI/CD Integration

### GitHub Actions Workflow

Automatyczne triggery:
- **Push** do `main`, `develop`, `refactor/*`
- **Pull Request** do `main`
- **Manual trigger** via GitHub UI

### Test Stages

1. **Setup**: Python 3.10, PostgreSQL, dependencies
2. **Unit Tests**: pytest z coverage
3. **Linting**: black, isort, pylint
4. **Integration**: Jeśli tokeny bot dostępne
5. **Security**: GitHub Super Linter
6. **Artifacts**: Upload wyników testów

### Sekrety GitHub

Wymagane dla pełnych testów:
```
CLAUDE_BOT=<discord_bot_token>
ZAGADKA_TOKEN=<main_bot_token>  
TIPO_API_TOKEN=<payment_api_token>
```

## Metryki Sukcesu

### Unit Tests
- ✅ **100%** pass rate wymagane
- ✅ **Coverage** > 80% preferowane

### Live Tests  
- ✅ **Activity Tracking**: Musi działać
- ✅ **Bot Responsiveness**: >75% success rate
- ✅ **Invite System**: Zero critical errors
- ✅ **Premium System**: Core functions operational

### CI/CD Pipeline
- ✅ **Build Time**: < 5 minut
- ✅ **Test Success**: > 90%
- ✅ **Security**: No high-severity issues

## Troubleshooting

### Typowe Problemy

1. **Docker Not Running**
   ```bash
   docker-compose up -d
   ```

2. **Import Errors**
   ```bash
   export PYTHONPATH="/home/ubuntu/Projects/zgdk:$PYTHONPATH"
   ```

3. **Permission Errors**
   - Sprawdź czy test_user_id jest w config.yml
   - Zweryfikuj czy bot ma permissions na test channel

4. **Database Connection**
   ```bash
   # Test database connection
   docker-compose exec app python -c "from datasources.models import Base; print('DB OK')"
   ```

## Monitoring & Alerting

### Log Monitoring
```bash
# Monitor errors in real-time
docker-compose logs app --follow | grep -E "(ERROR|FAIL)"

# Check system health
python test_live_functionality.py
```

### Metrics Collection
- Test results zapisywane do JSON files
- GitHub Actions artifacts zachowywane 30 dni
- Manual test logs w test_results.md

## Przyszłe Rozszerzenia

### Planowane Features
1. **Performance Tests**: Load testing shop functionality
2. **Chaos Engineering**: Simulate database failures
3. **A/B Testing**: Test different role pricing
4. **User Journey Tests**: Complete user flows
5. **Alerting Integration**: Slack/Discord notifications

### Automatyzacja
- Scheduled health checks (cron jobs)
- Automatic rollback on test failures
- Performance regression detection
- Database backup verification

---

## Quick Start

```bash
# 1. Run all unit tests
python -m pytest tests/ -v

# 2. Check live system health  
python test_live_functionality.py

# 3. Trigger CI/CD (push code)
git push origin feature-branch

# 4. Manual integration test
python tests/integration/test_shop_integration.py
```

**Status**: ✅ Framework kompletny i gotowy do użycia