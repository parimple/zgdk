# Plan Reorganizacji Testów Commands

## 🎯 Cel
Stworzenie kompletnego, profesjonalnego frameworka testów jednostkowych dla wszystkich komend Discord bota, z osobnym plikiem testów dla każdej komendy.

## 📁 Nowa Struktura Testów

```
tests/
├── commands/                          # 🆕 Testy komend
│   ├── __init__.py
│   ├── conftest.py                    # Wspólne fixtures i mocks
│   ├── test_giveaway.py              # Testy komend giveaway
│   ├── test_info.py                  # Testy komend info (profile, ping, etc.)
│   ├── test_mod.py                   # Testy komend moderacji
│   ├── test_owner.py                 # Testy komend owner
│   ├── test_premium.py               # Testy komend premium (color, team)
│   ├── test_ranking.py               # Testy komend ranking
│   ├── test_shop.py                  # 🎯 Testy komend shop
│   └── test_voice.py                 # Testy komend voice
├── services/                         # Testy serwisów
├── utils/                           # Testy utilities
├── integration/                     # Testy integracyjne
├── fixtures/                        # Dane testowe
└── mocks/                           # Mock objects
    ├── discord_mocks.py             # Mock Discord objects
    ├── service_mocks.py             # Mock services
    └── database_mocks.py            # Mock database
```

## 🏪 Priorytet: Kompletne Testy Shop

### test_shop.py - Szczegółowe Scenariusze

#### 1. **Komenda: shop**
```python
# Scenariusze testowe:
- Wyświetlenie sklepu z rolami premium
- Różne stany użytkownika (bez roli, z rolą, multiple role)
- Różne salda portfela (0, małe, duże)
- Testy view generation (RoleShopView)
- Testy embed creation
- Testy permission checks
```

#### 2. **Komenda: addbalance**
```python
# Scenariusze testowe:
- Dodawanie balance do istniejącego użytkownika
- Dodawanie balance do nowego użytkownika  
- Validation amount (negative, zero, huge numbers)
- Permission checks (admin only)
- Database transaction handling
- Error scenarios (DB connection fail)
```

#### 3. **Komenda: assign_payment**
```python
# Scenariusze testowe:
- Przypisanie płatności do użytkownika
- Validation payment data
- Multiple payments per user
- Payment history tracking
- Error handling (invalid payment ID)
```

#### 4. **Komenda: payments**
```python
# Scenariusze testowe:
- Wyświetlenie wszystkich płatności
- Pagination handling
- Empty payment list
- Sorting by date/amount
- Permission checks
```

#### 5. **Komenda: set_role_expiry**
```python
# Scenariusze testowe:
- Ustawienie daty wygaśnięcia roli
- Validation date format
- Role existence check
- User permission validation
- Database update verification
```

#### 6. **Komenda: shop_force_check_roles**
```python
# Scenariusze testowe:
- Force check expired roles
- Role removal process
- Notification system
- Batch processing
- Error recovery
```

## 🛠️ Mock Strategy

### Discord Objects
```python
@pytest.fixture
def mock_member():
    member = MagicMock()
    member.id = 123456789
    member.display_name = "TestUser"
    member.roles = []
    return member

@pytest.fixture
def mock_guild():
    guild = MagicMock()
    guild.id = 987654321
    guild.name = "Test Guild"
    return guild
```

### Services
```python
@pytest.fixture
def mock_member_service():
    service = MagicMock()
    service.get_or_create_member = AsyncMock()
    return service

@pytest.fixture
def mock_premium_service():
    service = MagicMock()
    service.get_member_premium_roles = AsyncMock()
    return service
```

### Database Session
```python
@pytest.fixture
def mock_db_session():
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    return session
```

## 📋 Przykładowe Testy Shop

### Test Structure Example:
```python
class TestShopCommand:
    """Testy komendy shop - wyświetlanie sklepu"""
    
    async def test_shop_display_success(self, mock_ctx, mock_member_service):
        """Test poprawnego wyświetlenia sklepu"""
        
    async def test_shop_no_balance(self, mock_ctx, mock_member_service):
        """Test sklepu gdy użytkownik ma 0 balance"""
        
    async def test_shop_with_existing_role(self, mock_ctx, mock_premium_service):
        """Test sklepu gdy użytkownik ma już rolę premium"""

class TestAddBalanceCommand:
    """Testy komendy addbalance"""
    
    async def test_addbalance_success(self, mock_ctx, mock_member_service):
        """Test dodania balance do użytkownika"""
        
    async def test_addbalance_negative_amount(self, mock_ctx):
        """Test validation - ujemna kwota"""
        
    async def test_addbalance_permission_denied(self, mock_ctx):
        """Test permission check - nie admin"""

class TestShopIntegration:
    """Testy integracyjne shop workflow"""
    
    async def test_complete_purchase_flow(self, mock_db):
        """Test całego procesu kupna roli"""
        
    async def test_role_expiration_check(self, mock_db):
        """Test sprawdzania wygasłych ról"""
```

## 🧪 Typy Testów

### 1. Unit Tests
- **Scope**: Pojedyncze komendy w izolacji
- **Mocking**: Wszystkie dependencies
- **Focus**: Logika biznesowa, validation, edge cases

### 2. Integration Tests  
- **Scope**: Interakcja między komendami i serwisami
- **Mocking**: Tylko Discord API i external services
- **Focus**: Workflow, data flow, service integration

### 3. Error Handling Tests
- **Scope**: Error scenarios i edge cases
- **Mocking**: Failure scenarios 
- **Focus**: Graceful error handling, rollbacks

## 🎭 Mock Scenarios

### Shop-Specific Mocks
```python
# Premium role configurations
MOCK_PREMIUM_ROLES = [
    {"name": "zG50", "price": 500, "duration": 30},
    {"name": "zG100", "price": 999, "duration": 30},
    {"name": "zG500", "price": 4999, "duration": 30}
]

# User states
MOCK_USER_NO_ROLE = {"roles": [], "balance": 1000}
MOCK_USER_WITH_ZG50 = {"roles": ["zG50"], "balance": 500}
MOCK_USER_RICH = {"balance": 10000}
```

## ⚡ Execution Plan

### Phase 1: Foundation (1-2h)
1. ✅ Stworzenie struktury katalogów
2. ✅ Stworzenie conftest.py z podstawowymi fixtures
3. ✅ Stworzenie mock objects (discord, services, database)

### Phase 2: Shop Tests (2-3h)
1. ✅ test_shop.py - wszystkie komendy shop
2. ✅ Kompletne scenariusze testowe
3. ✅ Error handling i edge cases
4. ✅ Integration tests

### Phase 3: Other Commands (opjonalne)
1. test_info.py - profile, ping, etc.
2. test_mod.py - moderation commands
3. test_premium.py - color, team commands
4. Pozostałe pliki

## 🎯 Success Metrics

### Code Coverage
- **Target**: 90%+ coverage dla shop commands
- **Focus**: Krytyczne ścieżki logiki biznesowej
- **Tools**: pytest-cov

### Test Quality
- **Isolation**: Każdy test niezależny
- **Performance**: <100ms per test
- **Reliability**: 100% pass rate
- **Maintainability**: Clear test names, good structure

### Documentation
- **Test descriptions**: Jasne, w języku polskim
- **Mock strategy**: Udokumentowane dla każdego typu
- **Usage examples**: Jak uruchamiać i interpretować

## 🚀 Implementation

**Start**: Bezpośrednio z test_shop.py - najpriorytetniejsze
**Focus**: Praktyczne, kompletne testy covering real scenarios
**Quality**: Professional-grade test suite ready for production

---

**Status**: READY TO IMPLEMENT ✅
**Estimated Time**: 3-4 hours total  
**Priority**: HIGH - Shop jest core functionality