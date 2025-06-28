# Strategia Migracji z Legacy do Nowoczesnej Architektury

## Przegląd Strategii

Migracja będzie przeprowadzana metodą "Strangler Fig Pattern" - stopniowe zastępowanie starego kodu nowym, bez przerywania działania systemu. Kluczem jest utrzymanie kompatybilności wstecznej podczas całego procesu.

## Fazy Migracji

### Faza 0: Przygotowanie (Tydzień 0)

#### Zadania
1. **Backup i wersjonowanie**
   ```bash
   # Utworzenie brancha dla refactoringu
   git checkout -b refactor/architecture-migration
   
   # Tag przed rozpoczęciem
   git tag -a pre-refactor-v1.0 -m "Stan przed refactoringiem"
   ```

2. **Infrastruktura testowa**
   ```python
   # tests/helpers/migration_test_base.py
   class MigrationTestBase:
       """Bazowa klasa dla testów migracji"""
       
       async def assert_backwards_compatible(self, old_impl, new_impl, *args):
           """Weryfikuje że nowa implementacja daje te same wyniki"""
           old_result = await old_impl(*args)
           new_result = await new_impl(*args)
           assert old_result == new_result
   ```

3. **Metryki i monitoring**
   - Ustaw baseline dla wydajności
   - Skonfiguruj alerty dla błędów
   - Przygotuj dashboard do śledzenia postępu

### Faza 1: Warstwa Abstrakcji (Tydzień 1-2)

#### Cel
Wprowadzić warstwę abstrakcji między starym a nowym kodem, umożliwiając stopniową migrację.

#### Implementacja

1. **Adapter Pattern dla Queries**
   ```python
   # app/infrastructure/adapters/query_adapter.py
   class QueryToRepositoryAdapter:
       """Adapter pozwalający używać starych Queries przez interfejs Repository"""
       
       def __init__(self, query_class: Type):
           self._query_class = query_class
       
       async def get_by_id(self, id: int, session: AsyncSession):
           # Stara metoda
           return await self._query_class.get_member(session, id)
       
       async def get_or_create(self, discord_id: int, session: AsyncSession):
           # Mapowanie na nowy interfejs
           return await self._query_class.get_or_add_member(
               session, discord_id, "Unknown"
           )
   ```

2. **Facade dla Utils**
   ```python
   # app/core/facades/utils_facade.py
   class UtilsFacade:
       """Fasada dla funkcji z utils, przekierowująca do serwisów"""
       
       def __init__(self, service_container: ServiceContainer):
           self._container = service_container
       
       def g_to_pln(self, amount: int) -> int:
           # Przekierowanie do nowego serwisu
           currency_service = self._container.resolve(ICurrencyService)
           return currency_service.g_to_pln(amount)
   ```

3. **Feature Toggle System**
   ```python
   # app/infrastructure/config/feature_flags.py
   class FeatureFlags:
       USE_NEW_REPOSITORIES = False
       USE_NEW_SERVICES = False
       USE_NEW_ERROR_HANDLING = False
       
       @classmethod
       def toggle(cls, feature: str, enabled: bool):
           setattr(cls, feature, enabled)
   ```

### Faza 2: Migracja Bottom-Up (Tydzień 3-5)

#### Strategia
Zaczynamy od najniższych warstw (repositories) i idziemy w górę do cogs.

#### Krok 1: Migracja Repositories
```python
# app/bot/main.py - Modified get_repository method
async def get_repository(self, interface: Type[T], session: AsyncSession) -> T:
    if FeatureFlags.USE_NEW_REPOSITORIES:
        # Nowa implementacja
        return self._container.resolve(interface)(session)
    else:
        # Adapter dla starej implementacji
        query_class = self._legacy_mapping.get(interface)
        return QueryToRepositoryAdapter(query_class)
```

#### Krok 2: Migracja Services
```python
# Stopniowa migracja serwis po serwisie
class MigrationPlan:
    services = [
        ("CurrencyService", "2024-01-15"),
        ("MemberService", "2024-01-17"),
        ("TransactionService", "2024-01-20"),
        # ... kolejne serwisy
    ]
    
    @staticmethod
    async def migrate_service(service_name: str):
        # 1. Włącz feature flag
        FeatureFlags.toggle(f"USE_NEW_{service_name.upper()}", True)
        
        # 2. Monitoruj przez 24h
        await monitor_service_health(service_name, hours=24)
        
        # 3. Jeśli OK, usuń stary kod
        if await is_service_healthy(service_name):
            remove_legacy_code(service_name)
```

#### Krok 3: Migracja Cogs
```python
# Przykład migracji pojedynczego cog
class ShopCogMigration:
    @staticmethod
    async def migrate():
        # 1. Utworz nową wersję cog używającą serwisów
        new_cog = "cogs/commands/shop_v2.py"
        
        # 2. Uruchom równolegle ze starą wersją
        # (używając różnych nazw komend tymczasowo)
        
        # 3. A/B testing - część użytkowników używa nowej wersji
        
        # 4. Po weryfikacji - zamień kompletnie
```

### Faza 3: Czyszczenie i Konsolidacja (Tydzień 6-7)

#### Zadania

1. **Usunięcie starego kodu**
   ```python
   # scripts/cleanup_legacy.py
   def cleanup_phase_1():
       """Usuń utils zduplikowane w services"""
       deprecated_utils = [
           "utils/currency.py",
           "utils/member_manager.py",
           # ...
       ]
       for util in deprecated_utils:
           if verify_no_usage(util):
               remove_file(util)
   ```

2. **Refactor importów**
   ```python
   # scripts/fix_imports.py
   import ast
   import os
   
   class ImportRefactorer(ast.NodeTransformer):
       """Automatyczne poprawianie importów"""
       
       def visit_ImportFrom(self, node):
           if node.module and node.module.startswith('utils.'):
               # Zamień na import z services
               new_module = node.module.replace('utils.', 'core.services.')
               node.module = new_module
           return node
   ```

3. **Konsolidacja testów**
   ```bash
   # Skrypt do identyfikacji duplikatów testów
   #!/bin/bash
   
   # Znajdź wszystkie pliki testowe z podobnymi nazwami
   find tests -name "test_*.py" | sort | uniq -d
   
   # Analiza pokrycia kodu
   pytest --cov=app --cov-report=html
   ```

### Faza 4: Optymalizacja (Tydzień 8-9)

#### Performance Tuning

1. **Profilowanie**
   ```python
   # app/infrastructure/profiling/profiler.py
   import cProfile
   import pstats
   from functools import wraps
   
   def profile_async(func):
       @wraps(func)
       async def wrapper(*args, **kwargs):
           profiler = cProfile.Profile()
           profiler.enable()
           try:
               result = await func(*args, **kwargs)
               return result
           finally:
               profiler.disable()
               stats = pstats.Stats(profiler)
               stats.sort_stats('cumulative')
               stats.print_stats(10)  # Top 10 funkcji
       return wrapper
   ```

2. **Cache Implementation**
   ```python
   # app/infrastructure/caching/redis_cache.py
   class RedisCache:
       def __init__(self, redis_url: str):
           self.redis = aioredis.from_url(redis_url)
       
       async def get_or_set(self, key: str, factory, ttl: int = 300):
           # Sprawdź cache
           cached = await self.redis.get(key)
           if cached:
               return json.loads(cached)
           
           # Oblicz wartość
           value = await factory()
           
           # Zapisz w cache
           await self.redis.setex(key, ttl, json.dumps(value))
           return value
   ```

## Harmonogram Szczegółowy

### Tydzień 1
- [ ] Dzień 1-2: Setup infrastruktury testowej i metryk
- [ ] Dzień 3-4: Implementacja adapterów i fasad
- [ ] Dzień 5: Testy integracyjne warstwy abstrakcji

### Tydzień 2
- [ ] Dzień 1-2: Feature flags i system toggles
- [ ] Dzień 3-5: Początek migracji repositories (Member, Role)

### Tydzień 3-4
- [ ] Migracja wszystkich repositories
- [ ] Testy A/B dla każdego repository
- [ ] Monitoring i rollback w razie problemów

### Tydzień 5
- [ ] Migracja services (Currency, Member, Transaction)
- [ ] Aktualizacja cogs do używania services

### Tydzień 6-7
- [ ] Usunięcie legacy code
- [ ] Konsolidacja testów
- [ ] Refactoring importów

### Tydzień 8-9
- [ ] Profilowanie wydajności
- [ ] Implementacja cache
- [ ] Optymalizacja zapytań

## Checklisty Migracji

### Przed migracją modułu
- [ ] Napisz testy dla starej implementacji
- [ ] Napisz testy dla nowej implementacji
- [ ] Utwórz adapter/fasadę
- [ ] Skonfiguruj feature flag
- [ ] Przygotuj plan rollback

### Podczas migracji
- [ ] Włącz feature flag dla 10% użytkowników
- [ ] Monitoruj metryki (błędy, wydajność)
- [ ] Stopniowo zwiększaj % użytkowników
- [ ] Dokumentuj problemy

### Po migracji
- [ ] Usuń stary kod
- [ ] Zaktualizuj dokumentację
- [ ] Usuń feature flag
- [ ] Przeprowadź retrospektywę

## Zarządzanie Ryzykiem

### Ryzyko 1: Regression Bugs
**Mitygacja:**
- Comprehensive test suite przed rozpoczęciem
- A/B testing dla każdej zmiany
- Automated regression tests

### Ryzyko 2: Performance Degradation
**Mitygacja:**
- Baseline metrics przed migracją
- Continuous performance monitoring
- Rollback plan dla każdej zmiany

### Ryzyko 3: Data Corruption
**Mitygacja:**
- Database backups przed każdą fazą
- Transactional migrations
- Dry-run w środowisku testowym

## Narzędzia Wspomagające

### Skrypt Monitoringu
```python
# scripts/migration_monitor.py
import asyncio
from datetime import datetime

class MigrationMonitor:
    def __init__(self):
        self.metrics = {
            'errors': 0,
            'response_times': [],
            'success_rate': 100.0
        }
    
    async def monitor_service(self, service_name: str):
        """Monitor service health during migration"""
        while True:
            health = await self.check_health(service_name)
            self.update_metrics(health)
            
            if self.metrics['success_rate'] < 95.0:
                await self.trigger_rollback(service_name)
                break
            
            await asyncio.sleep(60)  # Check every minute
```

### Dashboard Migracji
```yaml
# docker-compose.monitoring.yml
services:
  grafana:
    image: grafana/grafana
    ports:
      - "3000:3000"
    volumes:
      - ./dashboards:/etc/grafana/provisioning/dashboards
  
  prometheus:
    image: prometheus/prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
```

## Podsumowanie

Ta strategia migracji zapewnia:
1. **Bezpieczeństwo** - poprzez stopniowe zmiany i możliwość rollback
2. **Ciągłość** - system działa podczas migracji
3. **Weryfikowalność** - każdy krok jest testowany i monitorowany
4. **Elastyczność** - możliwość dostosowania tempa do sytuacji

Kluczem do sukcesu jest cierpliwość i metodyczne podejście. Każda faza powinna być dokładnie przetestowana przed przejściem do następnej.