# Plan Refactoringu Projektu ZGDK Discord Bot

## Podsumowanie Analizy

Projekt znajduje się w fazie przejściowej między starą architekturą opartą na klasach użytkowych a nowoczesną architekturą opartą na wzorcach Service Layer, Repository i Unit of Work. Ta migracja jest niekompletna, co powoduje:

- Duplikację kodu między utils/ i core/services/
- Niespójne wzorce obsługi błędów
- Mieszane podejścia architektoniczne w różnych modułach
- Nadmiarowe pliki testowe
- Problemy z utrzymaniem kodu

## Główne Problemy do Rozwiązania

### 1. Duplikacja Kodu
- **Problem**: Ten sam kod istnieje w utils/ i core/services/ (np. currency.py)
- **Wpływ**: Podwójne utrzymanie, niejasność którą wersję używać

### 2. Mieszane Wzorce Architektoniczne
- **Problem**: Stare wzorce (queries/) współistnieją z nowymi (repositories/)
- **Wpływ**: Niespójność, trudność w zrozumieniu przepływu danych

### 3. Niekompletna Migracja do Serwisów
- **Problem**: Niektóre cogs używają utils, inne services
- **Wpływ**: Brak jednolitego podejścia, różne poziomy abstrakcji

### 4. Chaos w Testach
- **Problem**: 9+ wersji testów dla tej samej funkcjonalności
- **Wpływ**: Niejasność które testy są aktualne, zaśmiecenie projektu

## Plan Refactoringu - Fazy

### Faza 1: Czyszczenie i Konsolidacja (1-2 tygodnie)

#### 1.1 Usunięcie Duplikatów
- [ ] Usunąć zduplikowane implementacje z utils/, pozostawić tylko w services/
- [ ] Zaktualizować wszystkie importy
- [ ] Przeprowadzić testy regresyjne

#### 1.2 Konsolidacja Testów
- [ ] Zidentyfikować najnowsze/działające wersje testów
- [ ] Usunąć wszystkie przestarzałe wersje
- [ ] Uporządkować strukturę katalogów testowych

#### 1.3 Czyszczenie Logów
- [ ] Usunąć stare logi PostgreSQL
- [ ] Wdrożyć strategię rotacji logów

### Faza 2: Unifikacja Architektury (2-3 tygodnie)

#### 2.1 Migracja z Queries do Repositories
- [ ] Przepisać wszystkie klasy z datasources/queries/ na wzorzec Repository
- [ ] Zaktualizować wszystkie miejsca użycia
- [ ] Usunąć stare klasy queries

#### 2.2 Standaryzacja Obsługi Błędów
- [ ] Utworzyć wspólne klasy wyjątków w core/exceptions/
- [ ] Wdrożyć jednolity wzorzec try/except we wszystkich serwisach
- [ ] Dodać centralne logowanie błędów

#### 2.3 Kompletna Migracja Cogs do Serwisów
- [ ] Zmigrować wszystkie cogs do używania serwisów zamiast utils
- [ ] Usunąć bezpośrednie użycie modeli bazy danych w cogs
- [ ] Wdrożyć dependency injection we wszystkich cogs

### Faza 3: Modularyzacja (3-4 tygodnie)

#### 3.1 Reorganizacja Struktury Katalogów
```
zgdk/
├── app/                      # Główna aplikacja
│   ├── bot/                  # Logika bota Discord
│   │   ├── cogs/            # Komendy i eventy
│   │   ├── extensions/      # Rozszerzenia bota
│   │   └── ui/              # Komponenty UI
│   ├── core/                # Rdzeń biznesowy
│   │   ├── domain/          # Modele domenowe
│   │   ├── services/        # Serwisy biznesowe
│   │   ├── interfaces/      # Protokoły i interfejsy
│   │   └── exceptions/      # Wyjątki domenowe
│   └── infrastructure/      # Warstwa infrastruktury
│       ├── database/        # Repozytoria i modele DB
│       ├── external/        # Integracje zewnętrzne
│       └── config/          # Konfiguracja
├── tests/                   # Testy (odzwierciedlające strukturę app/)
├── scripts/                 # Skrypty pomocnicze
└── docs/                    # Dokumentacja
```

#### 3.2 Wydzielenie Modułów Funkcjonalnych
- [ ] Ekonomia (shop, currency, transactions)
- [ ] Moderacja (moderation, permissions, roles)
- [ ] Aktywność (activity tracking, voice, messages)
- [ ] Premium (premium features, subscriptions)
- [ ] Administracja (owner commands, system management)

#### 3.3 Implementacja Fasad dla Modułów
- [ ] Utworzyć fasady serwisów dla każdego modułu
- [ ] Ukryć wewnętrzną złożoność modułów
- [ ] Zapewnić czyste API między modułami

### Faza 4: Optymalizacja i Dokumentacja (1-2 tygodnie)

#### 4.1 Optymalizacja Wydajności
- [ ] Profilowanie zapytań do bazy danych
- [ ] Implementacja cache'owania gdzie potrzebne
- [ ] Optymalizacja operacji asynchronicznych

#### 4.2 Dokumentacja
- [ ] Dokumentacja architektury (ADR - Architecture Decision Records)
- [ ] Diagramy przepływu danych
- [ ] Przewodnik dla deweloperów
- [ ] API documentation dla serwisów

## Szczegółowe Rekomendacje

### 1. Wzorzec Obsługi Błędów
```python
# core/exceptions/base.py
class DomainError(Exception):
    """Bazowy wyjątek domenowy"""
    pass

class ValidationError(DomainError):
    """Błąd walidacji danych"""
    pass

class NotFoundError(DomainError):
    """Zasób nie został znaleziony"""
    pass

# Użycie w serwisach
async def process_transaction(self, amount: int) -> Transaction:
    try:
        validated_amount = self._validate_amount(amount)
        transaction = await self._repository.create_transaction(validated_amount)
        await self._event_bus.publish(TransactionCreated(transaction))
        return transaction
    except ValidationError:
        raise  # Przepuść błędy domenowe
    except Exception as e:
        self._logger.error(f"Unexpected error in process_transaction: {e}")
        raise DomainError("Transaction processing failed") from e
```

### 2. Struktura Modułu
```python
# app/core/domain/economy/models.py
@dataclass
class Money:
    amount: Decimal
    currency: Currency
    
    def convert_to(self, target_currency: Currency) -> 'Money':
        """Konwersja waluty z zachowaniem niemutowalności"""
        pass

# app/core/services/economy/transaction_service.py
class TransactionService:
    def __init__(self, 
                 repository: ITransactionRepository,
                 currency_service: ICurrencyService,
                 event_bus: IEventBus):
        self._repository = repository
        self._currency_service = currency_service
        self._event_bus = event_bus
```

### 3. Dependency Injection
```python
# app/infrastructure/config/container.py
class ServiceContainer:
    def __init__(self):
        self._services: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}
    
    def register_singleton(self, interface: Type[T], implementation: T) -> None:
        """Rejestruj singleton"""
        self._services[interface] = implementation
    
    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Rejestruj fabrykę"""
        self._factories[interface] = factory
    
    def resolve(self, interface: Type[T]) -> T:
        """Rozwiąż zależność"""
        if interface in self._services:
            return self._services[interface]
        if interface in self._factories:
            return self._factories[interface]()
        raise DependencyNotRegistered(f"No registration for {interface}")
```

## Metryki Sukcesu

1. **Redukcja duplikacji kodu** - cel: 0% duplikacji między utils/ i services/
2. **Pokrycie testami** - cel: >80% dla kodu biznesowego
3. **Jednolitość architektury** - cel: 100% cogs używających serwisów
4. **Czas odpowiedzi** - cel: <100ms dla 95% komend
5. **Łatwość rozszerzania** - cel: nowe funkcje dodawane bez modyfikacji istniejącego kodu

## Harmonogram

- **Tydzień 1-2**: Faza 1 (Czyszczenie)
- **Tydzień 3-5**: Faza 2 (Unifikacja)
- **Tydzień 6-9**: Faza 3 (Modularyzacja)
- **Tydzień 10-11**: Faza 4 (Optymalizacja)

## Ryzyka i Mitygacje

1. **Ryzyko**: Regresje podczas refactoringu
   - **Mitygacja**: Comprehensive test suite przed rozpoczęciem, testy regresyjne po każdej zmianie

2. **Ryzyko**: Przestoje bota
   - **Mitygacja**: Feature flags, stopniowe wdrażanie, rollback strategy

3. **Ryzyko**: Opór zespołu przed zmianami
   - **Mitygacja**: Dokumentacja, szkolenia, pair programming

## Podsumowanie

Ten plan refactoringu przekształci projekt z hybrydowej, niespójnej architektury w czysty, modularny system oparty na solidnych wzorcach projektowych. Kluczem do sukcesu jest stopniowe, metodyczne podejście z ciągłym testowaniem i walidacją na każdym etapie.