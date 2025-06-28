# Kompleksowy Plan Refaktoringu ZGDK Discord Bot

## Podsumowanie Stanu Obecnego

Projekt ZGDK Discord Bot znajduje się w stanie przejściowym między starą architekturą (utils + queries) a nową (services + repositories). Ta niekompletna migracja powoduje:

- **Potrójna duplikacja kodu** (np. logika premium w 3 miejscach)
- **Mieszane wzorce architektoniczne** (49 plików używa queries, 18 repositories)
- **Chaos w testach** (10+ wersji tego samego testu)
- **Niespójną strukturę** (niektóre cogs używają services, inne queries)
- **Hardkodowane wartości** rozproszone w 14+ plikach

## Plan Refaktoringu - 4 Fazy

### Faza 1: Czyszczenie i Stabilizacja (Tydzień 1-2) 🧹

#### Priorytet 1: Usunięcie Duplikatów
```
Zadania:
□ Skonsolidować 3 implementacje premium do jednego serwisu
□ Usunąć duplikaty: message_sender, role_manager, team_manager
□ Wyczyścić 10+ duplikatów testów addbalance
□ Usunąć katalog cogs/trash/
□ Usunąć nieużywane pliki z roota (test_*.py)
```

#### Priorytet 2: Konsolidacja Testów
```
tests/
├── unit/               # Testy jednostkowe
├── integration/        # Testy integracyjne  
├── fixtures/           # Wspólne fixtures
└── e2e/               # Testy end-to-end
```

#### Skrypt Automatyzacji:
```python
# scripts/cleanup_duplicates.py
def find_duplicates():
    duplicates = {
        'premium': ['utils/premium.py', 'utils/premium_logic.py', 
                   'utils/premium_checker.py', 'core/services/premium_service.py'],
        'tests': glob.glob('test_*.py') + glob.glob('tests/**/test_addbalance*.py')
    }
    return duplicates
```

### Faza 2: Unifikacja Architektury (Tydzień 3-5) 🏗️

#### Migracja Query → Repository

**Plan migracji dla 49 plików używających queries:**

1. **Tydzień 3**: Migracja core queries
   - MemberQueries → MemberRepository ✓
   - RoleQueries → RoleRepository
   - TransactionQueries → TransactionRepository

2. **Tydzień 4**: Migracja feature queries  
   - ShopQueries → ShopRepository
   - VoiceQueries → VoiceRepository
   - BypassQueries → BypassRepository

3. **Tydzień 5**: Migracja pomocniczych queries
   - StatisticsQueries → StatisticsRepository
   - ConfigQueries → ConfigRepository

#### Wzorzec Migracji:
```python
# Stary kod (queries)
class MemberQueries:
    @staticmethod
    async def get_member(session, member_id):
        query = "SELECT * FROM members WHERE id = ?"
        return await session.execute(query, [member_id])

# Nowy kod (repository)  
class MemberRepository(IMemberRepository):
    async def get_by_id(self, member_id: int) -> Optional[Member]:
        stmt = select(MemberModel).where(MemberModel.id == member_id)
        result = await self._session.execute(stmt)
        return self._to_domain(result.scalar_one_or_none())
```

### Faza 3: Modularyzacja (Tydzień 6-8) 📦

#### Nowa Struktura Katalogów:
```
zgdk/
├── app/
│   ├── core/                    # Logika biznesowa
│   │   ├── economy/            # Moduł ekonomii
│   │   │   ├── domain/         # Modele i logika
│   │   │   ├── services/       # Serwisy biznesowe
│   │   │   └── interfaces/     # Kontrakty
│   │   ├── moderation/         # Moduł moderacji
│   │   ├── activity/           # Moduł aktywności
│   │   └── premium/            # Moduł premium
│   ├── infrastructure/         # Implementacje
│   │   ├── discord/           # Bot Discord
│   │   ├── database/          # Repozytoria
│   │   └── config/            # Konfiguracja
│   └── presentation/          # UI/Commands
│       └── bot/
│           ├── cogs/          # Komendy Discord
│           └── ui/            # Komponenty UI
```

#### Podział Dużych Cogs:
- `info.py` (54KB) → economy_info.py, server_info.py, user_info.py
- `premium.py` (54KB) → premium_commands.py, premium_admin.py, premium_ui.py

### Faza 4: Optymalizacja i Dokumentacja (Tydzień 9-10) 🚀

#### Konfiguracja Scentralizowana:
```python
# app/infrastructure/config/settings.py
from pydantic import BaseSettings

class Settings(BaseSettings):
    # Zamiast hardkodowanych wartości
    MAIN_GUILD_ID: int = 601370314554998795
    PREMIUM_ROLE_ID: int = 1221834026236563526
    DEFAULT_SOCIAL_PROOF: int = 200
    
    class Config:
        env_file = ".env"
```

#### System Cache:
```python
# app/infrastructure/cache/cache_service.py
class CacheService:
    async def get_or_compute(self, key: str, compute_fn, ttl: int = 300):
        cached = await self.get(key)
        if cached:
            return cached
        value = await compute_fn()
        await self.set(key, value, ttl)
        return value
```

## Harmonogram Szczegółowy

### Tydzień 1-2: Czyszczenie
- [ ] Dzień 1-3: Usunięcie duplikatów kodu
- [ ] Dzień 4-5: Konsolidacja testów
- [ ] Dzień 6-7: Usunięcie nieużywanych plików
- [ ] Dzień 8-10: Testy regresyjne

### Tydzień 3-5: Unifikacja
- [ ] Migracja 49 plików z queries na repositories
- [ ] Standaryzacja obsługi błędów
- [ ] Implementacja Unit of Work

### Tydzień 6-8: Modularyzacja  
- [ ] Reorganizacja struktury katalogów
- [ ] Podział dużych modułów
- [ ] Implementacja fasad modułów

### Tydzień 9-10: Optymalizacja
- [ ] Scentralizowana konfiguracja
- [ ] Implementacja cache
- [ ] Dokumentacja architektury

## Metryki Sukcesu

1. **Redukcja duplikacji**: z 30% do <5%
2. **Spójność architektury**: 100% cogs używa services
3. **Pokrycie testami**: >80%
4. **Czas odpowiedzi**: <100ms dla 95% komend
5. **Złożoność cyklomatyczna**: <10 dla każdej metody

## Kluczowe Decyzje Architektoniczne

### 1. Repository Pattern Everywhere
```python
# Wszystkie operacje DB przez repozytoria
async with uow:
    member = await uow.members.get_by_discord_id(user_id)
    await uow.members.update(member)
    await uow.commit()
```

### 2. Domain Events dla Komunikacji
```python
# Moduły komunikują przez eventy
@dataclass
class PremiumPurchased(DomainEvent):
    user_id: int
    duration_days: int
    
# Activity module nasłuchuje
async def handle_premium_purchased(event: PremiumPurchased):
    await add_activity_points(event.user_id, 1000)
```

### 3. Dependency Injection
```python
# Cogs otrzymują serwisy przez DI
class EconomyCog(commands.Cog):
    def __init__(self, economy_service: IEconomyService):
        self._service = economy_service
```

## Ryzyka i Mitygacje

| Ryzyko | Prawdopodobieństwo | Wpływ | Mitygacja |
|--------|-------------------|--------|-----------|
| Regresje podczas refactoringu | Wysokie | Wysoki | Comprehensive tests, feature flags |
| Opór zespołu | Średnie | Średni | Stopniowa migracja, dokumentacja |
| Przestoje bota | Niskie | Wysoki | Blue-green deployment, rollback plan |

## Narzędzia Wspomagające

1. **Migration Dashboard**: Grafana + Prometheus do monitoringu
2. **Feature Flags**: Stopniowe wdrażanie zmian
3. **Automated Tests**: CI/CD z testami regresyjnymi
4. **Code Analysis**: SonarQube do śledzenia jakości

## Następne Kroki

1. **Natychmiast**: Backup bazy danych i kodu
2. **Dzień 1**: Rozpocząć od usunięcia duplikatów premium
3. **Tydzień 1**: Raport z postępu czyszczenia
4. **Continuous**: Daily standup i tracking w Jira/GitHub Projects

---

Ten plan przekształci chaotyczny kod w czystą, modularną architekturę. Kluczem jest metodyczne podejście i ciągłe testowanie. Każda faza buduje na poprzedniej, zapewniając stabilność systemu podczas transformacji.