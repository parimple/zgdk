# Szczegółowe Rekomendacje Refactoringu Modułów

## 1. Moduł Ekonomii (Economy)

### Stan Obecny
- **Duplikacja**: `utils/currency.py` vs `core/services/currency_service.py`
- **Rozproszona logika**: Transakcje w queries, waluty w utils, shop w cogs
- **Brak enkapsulacji**: Bezpośredni dostęp do modeli DB

### Rekomendacje Refactoringu

#### Struktura Docelowa
```
app/core/domain/economy/
├── models/
│   ├── money.py          # Value object dla pieniędzy
│   ├── transaction.py    # Entity transakcji
│   └── wallet.py         # Aggregate dla portfela
├── services/
│   ├── transaction_service.py
│   ├── currency_service.py
│   └── shop_service.py
├── events/
│   ├── transaction_events.py
│   └── shop_events.py
└── exceptions/
    └── economy_exceptions.py
```

#### Przykład Implementacji
```python
# app/core/domain/economy/models/money.py
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

class Currency(Enum):
    PLN = "PLN"
    GOLD = "G"

@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: Currency
    
    def __add__(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)
    
    def convert_to(self, target: Currency, rate: Decimal) -> 'Money':
        return Money(self.amount * rate, target)

# app/core/domain/economy/services/transaction_service.py
class TransactionService:
    async def transfer_money(
        self,
        from_member_id: int,
        to_member_id: int,
        amount: Money
    ) -> Transaction:
        async with self._uow:
            sender = await self._uow.members.get_by_id(from_member_id)
            receiver = await self._uow.members.get_by_id(to_member_id)
            
            if not sender.can_afford(amount):
                raise InsufficientFundsError()
            
            transaction = sender.transfer_to(receiver, amount)
            await self._uow.transactions.add(transaction)
            await self._uow.commit()
            
            await self._event_bus.publish(
                MoneyTransferred(from_member_id, to_member_id, amount)
            )
            
            return transaction
```

## 2. Moduł Moderacji (Moderation)

### Stan Obecny
- **Rozproszone uprawnienia**: Utils, cogs, queries
- **Brak audytu**: Akcje moderacyjne nie są logowane systematycznie
- **Niespójne sprawdzanie uprawnień**: Różne podejścia w różnych miejscach

### Rekomendacje Refactoringu

#### Struktura Docelowa
```
app/core/domain/moderation/
├── models/
│   ├── action.py         # Akcje moderacyjne
│   ├── permission.py     # Model uprawnień
│   └── audit_log.py      # Log audytowy
├── services/
│   ├── moderation_service.py
│   ├── permission_service.py
│   └── audit_service.py
├── policies/
│   ├── ban_policy.py
│   ├── mute_policy.py
│   └── role_policy.py
└── events/
    └── moderation_events.py
```

#### Przykład Implementacji
```python
# app/core/domain/moderation/models/action.py
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class ActionType(Enum):
    BAN = "ban"
    KICK = "kick"
    MUTE = "mute"
    WARN = "warn"

@dataclass
class ModerationAction:
    action_type: ActionType
    target_member_id: int
    moderator_id: int
    reason: str
    duration: Optional[timedelta] = None
    created_at: datetime = field(default_factory=datetime.utcnow)

# app/core/domain/moderation/services/moderation_service.py
class ModerationService:
    def __init__(self, 
                 permission_service: IPermissionService,
                 audit_service: IAuditService,
                 policy_registry: IPolicyRegistry):
        self._permission_service = permission_service
        self._audit_service = audit_service
        self._policy_registry = policy_registry
    
    async def execute_action(
        self,
        action: ModerationAction,
        context: ModerationContext
    ) -> ActionResult:
        # Sprawdź uprawnienia
        if not await self._permission_service.can_execute(
            context.moderator, action.action_type
        ):
            raise InsufficientPermissionsError()
        
        # Zastosuj politykę
        policy = self._policy_registry.get_policy(action.action_type)
        result = await policy.apply(action, context)
        
        # Zaloguj akcję
        await self._audit_service.log_action(action, result)
        
        return result
```

## 3. Moduł Aktywności (Activity)

### Stan Obecny
- **Mieszane odpowiedzialności**: Voice tracking, message tracking, points w różnych miejscach
- **Brak abstrakcji**: Bezpośrednie operacje na DB
- **Słabe raportowanie**: Brak agregatów i statystyk

### Rekomendacje Refactoringu

#### Struktura Docelowa
```
app/core/domain/activity/
├── models/
│   ├── activity.py       # Bazowy model aktywności
│   ├── voice_session.py  # Sesje głosowe
│   └── statistics.py     # Statystyki i agregaty
├── services/
│   ├── tracking_service.py
│   ├── points_service.py
│   └── statistics_service.py
├── calculators/
│   ├── voice_points_calculator.py
│   └── message_points_calculator.py
└── repositories/
    └── activity_repository.py
```

#### Przykład Implementacji
```python
# app/core/domain/activity/models/activity.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

@dataclass
class Activity(ABC):
    member_id: int
    timestamp: datetime
    
    @abstractmethod
    def calculate_points(self) -> int:
        pass

@dataclass
class VoiceActivity(Activity):
    channel_id: int
    duration_seconds: int
    
    def calculate_points(self) -> int:
        base_points = self.duration_seconds // 60  # 1 punkt za minutę
        bonus = self._calculate_bonus()
        return base_points + bonus
    
    def _calculate_bonus(self) -> int:
        # Logika bonusów za długie sesje
        if self.duration_seconds > 3600:  # Ponad godzina
            return 50
        return 0

# app/core/domain/activity/services/tracking_service.py
class ActivityTrackingService:
    def __init__(self,
                 repository: IActivityRepository,
                 points_service: IPointsService,
                 event_bus: IEventBus):
        self._repository = repository
        self._points_service = points_service
        self._event_bus = event_bus
    
    async def track_activity(self, activity: Activity) -> None:
        # Zapisz aktywność
        await self._repository.save(activity)
        
        # Oblicz i przyznaj punkty
        points = activity.calculate_points()
        await self._points_service.award_points(
            activity.member_id, points, f"Activity: {type(activity).__name__}"
        )
        
        # Publikuj zdarzenie
        await self._event_bus.publish(
            ActivityTracked(activity.member_id, type(activity).__name__, points)
        )
```

## 4. System Komend (Commands)

### Stan Obecny
- **Niespójna struktura**: Różne style implementacji komend
- **Brak walidacji**: Walidacja rozproszona lub brakująca
- **Słaba obsługa błędów**: Różne podejścia do błędów

### Rekomendacje Refactoringu

#### Wzorzec Command Handler
```python
# app/bot/commands/base.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TCommand = TypeVar('TCommand')
TResult = TypeVar('TResult')

class Command(ABC):
    """Bazowa klasa komendy"""
    pass

class CommandHandler(Generic[TCommand, TResult], ABC):
    """Bazowy handler komendy"""
    
    @abstractmethod
    async def handle(self, command: TCommand) -> TResult:
        pass

# app/bot/commands/economy/add_balance_command.py
@dataclass
class AddBalanceCommand(Command):
    member_id: int
    amount: int
    currency: Currency
    reason: str

class AddBalanceCommandHandler(CommandHandler[AddBalanceCommand, Money]):
    def __init__(self, transaction_service: ITransactionService):
        self._transaction_service = transaction_service
    
    async def handle(self, command: AddBalanceCommand) -> Money:
        # Walidacja
        if command.amount <= 0:
            raise ValidationError("Amount must be positive")
        
        # Wykonanie
        money = Money(Decimal(command.amount), command.currency)
        await self._transaction_service.add_balance(
            command.member_id, money, command.reason
        )
        
        return money
```

#### Dekorator dla Cog
```python
# app/bot/decorators/command_decorator.py
def discord_command(
    name: str,
    handler_class: Type[CommandHandler],
    description: str = ""
):
    def decorator(func):
        @commands.hybrid_command(name=name, description=description)
        @wraps(func)
        async def wrapper(self, ctx: Context, *args, **kwargs):
            try:
                # Utwórz komendę z argumentów
                command = await self._parse_command(args, kwargs)
                
                # Pobierz handler z kontenera
                handler = self.bot.container.resolve(handler_class)
                
                # Wykonaj
                result = await handler.handle(command)
                
                # Formatuj odpowiedź
                await self._send_response(ctx, result)
                
            except ValidationError as e:
                await ctx.send(f"❌ Błąd walidacji: {e}")
            except DomainError as e:
                await ctx.send(f"❌ Błąd: {e}")
            except Exception as e:
                logger.error(f"Unexpected error in {name}: {e}")
                await ctx.send("❌ Wystąpił nieoczekiwany błąd")
        
        return wrapper
    return decorator
```

## 5. System Konfiguracji

### Stan Obecny
- **Hardcoded wartości**: Stałe rozproszone w kodzie
- **Brak walidacji**: Konfiguracja nie jest walidowana
- **Słabe typowanie**: Dict zamiast typowanych obiektów

### Rekomendacje Refactoringu

#### Typowana Konfiguracja
```python
# app/infrastructure/config/models.py
from pydantic import BaseModel, Field

class DatabaseConfig(BaseModel):
    url: str
    pool_size: int = Field(default=5, ge=1, le=20)
    echo: bool = False

class BotConfig(BaseModel):
    token: str
    prefix: str = "!"
    intents: List[str] = ["guilds", "messages", "voice_states"]

class EconomyConfig(BaseModel):
    starting_balance: int = Field(default=100, ge=0)
    daily_reward: int = Field(default=50, ge=0)
    currency_rate: Decimal = Field(default=Decimal("0.01"))

class AppConfig(BaseModel):
    bot: BotConfig
    database: DatabaseConfig
    economy: EconomyConfig
    
    @classmethod
    def from_file(cls, path: Path) -> 'AppConfig':
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**data)
```

## 6. System Testów

### Stan Obecny
- **Duplikacja**: Wiele wersji tego samego testu
- **Brak struktury**: Płaska organizacja testów
- **Słabe fixtures**: Powtarzający się setup

### Rekomendacje Refactoringu

#### Struktura Testów
```
tests/
├── unit/
│   ├── domain/
│   │   ├── economy/
│   │   │   ├── test_money.py
│   │   │   └── test_transaction_service.py
│   │   └── moderation/
│   └── infrastructure/
├── integration/
│   ├── test_database.py
│   └── test_services.py
├── e2e/
│   ├── test_economy_flow.py
│   └── test_moderation_flow.py
└── fixtures/
    ├── domain_fixtures.py
    ├── database_fixtures.py
    └── discord_fixtures.py
```

#### Przykład Testu
```python
# tests/unit/domain/economy/test_transaction_service.py
import pytest
from decimal import Decimal
from app.core.domain.economy import TransactionService, Money, Currency

class TestTransactionService:
    @pytest.fixture
    def service(self, mock_uow, mock_event_bus):
        return TransactionService(mock_uow, mock_event_bus)
    
    @pytest.mark.asyncio
    async def test_transfer_money_success(self, service, mock_members):
        # Arrange
        sender_id, receiver_id = 1, 2
        amount = Money(Decimal("100"), Currency.PLN)
        
        # Act
        transaction = await service.transfer_money(
            sender_id, receiver_id, amount
        )
        
        # Assert
        assert transaction.amount == amount
        assert transaction.from_member_id == sender_id
        assert transaction.to_member_id == receiver_id
    
    @pytest.mark.asyncio
    async def test_transfer_money_insufficient_funds(self, service):
        # Arrange
        sender_id, receiver_id = 1, 2
        amount = Money(Decimal("1000000"), Currency.PLN)
        
        # Act & Assert
        with pytest.raises(InsufficientFundsError):
            await service.transfer_money(sender_id, receiver_id, amount)
```

## Podsumowanie

Te szczegółowe rekomendacje pokazują jak przekształcić każdy moduł z obecnego, rozproszonego stanu do czystej, modularnej architektury. Kluczowe elementy to:

1. **Wyraźne granice modułów** - każdy moduł ma swoją domenę
2. **Separacja warstw** - domain, application, infrastructure
3. **Typowanie i walidacja** - użycie dataclass, Pydantic, Protocol
4. **Testowalnośc** - dependency injection, mockowanie
5. **Obserwowalnośc** - eventy, logi, metryki

Implementacja tych zmian powinna być stopniowa, zaczynając od najbardziej krytycznych modułów (ekonomia, moderacja).