# Projekt Modularnej Architektury

## Wizja Architektury

Przekształcenie monolitycznego bota Discord w modularną aplikację opartą na Domain-Driven Design (DDD) z czystą architekturą heksagonalną (Ports & Adapters).

## Struktura Wysokopoziomowa

```
zgdk/
├── app/                           # Główna aplikacja
│   ├── core/                      # Rdzeń aplikacji (Domain + Application)
│   │   ├── shared/               # Współdzielone elementy
│   │   │   ├── domain/           # Współdzielone modele domenowe
│   │   │   ├── interfaces/       # Bazowe protokoły
│   │   │   └── exceptions/       # Wspólne wyjątki
│   │   │
│   │   ├── economy/              # Moduł Ekonomii
│   │   │   ├── domain/           # Logika biznesowa
│   │   │   ├── application/      # Przypadki użycia
│   │   │   └── interfaces/       # Porty (interfejsy)
│   │   │
│   │   ├── moderation/           # Moduł Moderacji
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   └── interfaces/
│   │   │
│   │   ├── activity/             # Moduł Aktywności
│   │   │   ├── domain/
│   │   │   ├── application/
│   │   │   └── interfaces/
│   │   │
│   │   └── premium/              # Moduł Premium
│   │       ├── domain/
│   │       ├── application/
│   │       └── interfaces/
│   │
│   ├── infrastructure/           # Adaptery i implementacje
│   │   ├── discord/             # Adapter Discord
│   │   ├── database/            # Adapter bazy danych
│   │   ├── cache/               # Adapter cache
│   │   ├── messaging/           # System eventów
│   │   └── config/              # Konfiguracja
│   │
│   └── presentation/            # Warstwa prezentacji
│       ├── bot/                 # Discord bot
│       ├── api/                 # REST API (opcjonalne)
│       └── web/                 # Web dashboard (opcjonalne)
│
├── tests/                       # Testy (struktura lustrzana)
├── scripts/                     # Skrypty pomocnicze
├── docs/                        # Dokumentacja
└── deployment/                  # Konfiguracja deploymentu
```

## Architektura Modułu

Każdy moduł (economy, moderation, activity, premium) ma identyczną strukturę:

### 1. Warstwa Domain

```
economy/domain/
├── models/                      # Modele biznesowe
│   ├── money.py                # Value Objects
│   ├── wallet.py               # Entities
│   ├── transaction.py          # Aggregates
│   └── shop_item.py
├── services/                    # Domain Services
│   ├── pricing_service.py
│   └── exchange_service.py
├── events/                      # Domain Events
│   ├── money_transferred.py
│   └── item_purchased.py
├── repositories/                # Interfejsy repozytoriów
│   ├── wallet_repository.py
│   └── transaction_repository.py
└── exceptions/                  # Wyjątki domenowe
    └── economy_exceptions.py
```

#### Przykład Value Object
```python
# app/core/economy/domain/models/money.py
from dataclasses import dataclass
from decimal import Decimal
from typing import NewType

CurrencyCode = NewType('CurrencyCode', str)

@dataclass(frozen=True)
class Money:
    """Value Object reprezentujący pieniądze"""
    amount: Decimal
    currency: CurrencyCode
    
    def __post_init__(self):
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")
        
        # Zaokrąglij do 2 miejsc po przecinku
        object.__setattr__(self, 'amount', self.amount.quantize(Decimal('0.01')))
    
    def add(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError(f"Cannot add {self.currency} to {other.currency}")
        return Money(self.amount + other.amount, self.currency)
    
    def subtract(self, other: 'Money') -> 'Money':
        if self.currency != other.currency:
            raise ValueError(f"Cannot subtract {other.currency} from {self.currency}")
        return Money(self.amount - other.amount, self.currency)
    
    def multiply(self, factor: Decimal) -> 'Money':
        return Money(self.amount * factor, self.currency)
    
    def __str__(self) -> str:
        return f"{self.amount} {self.currency}"
```

#### Przykład Aggregate
```python
# app/core/economy/domain/models/wallet.py
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime
from ..events import MoneyDeposited, MoneyWithdrawn

@dataclass
class Wallet:
    """Aggregate reprezentujący portfel użytkownika"""
    id: str
    owner_id: str
    balance: Money
    created_at: datetime
    updated_at: datetime
    _domain_events: List = field(default_factory=list, init=False)
    
    def deposit(self, amount: Money) -> None:
        """Wpłata pieniędzy"""
        if amount.amount <= 0:
            raise ValueError("Deposit amount must be positive")
        
        self.balance = self.balance.add(amount)
        self.updated_at = datetime.utcnow()
        
        # Dodaj zdarzenie domenowe
        self._domain_events.append(
            MoneyDeposited(
                wallet_id=self.id,
                amount=amount,
                timestamp=self.updated_at
            )
        )
    
    def withdraw(self, amount: Money) -> None:
        """Wypłata pieniędzy"""
        if amount.amount <= 0:
            raise ValueError("Withdrawal amount must be positive")
        
        if self.balance.amount < amount.amount:
            raise InsufficientFundsError(
                f"Insufficient funds. Available: {self.balance}, Requested: {amount}"
            )
        
        self.balance = self.balance.subtract(amount)
        self.updated_at = datetime.utcnow()
        
        self._domain_events.append(
            MoneyWithdrawn(
                wallet_id=self.id,
                amount=amount,
                timestamp=self.updated_at
            )
        )
    
    def can_afford(self, amount: Money) -> bool:
        """Sprawdź czy stać na wydatek"""
        return self.balance.amount >= amount.amount and self.balance.currency == amount.currency
    
    @property
    def domain_events(self) -> List:
        """Pobierz i wyczyść zdarzenia"""
        events = self._domain_events[:]
        self._domain_events.clear()
        return events
```

### 2. Warstwa Application

```
economy/application/
├── commands/                    # Commands (CQRS)
│   ├── transfer_money.py
│   └── purchase_item.py
├── queries/                     # Queries (CQRS)
│   ├── get_wallet_balance.py
│   └── get_transaction_history.py
├── handlers/                    # Command/Query Handlers
│   ├── transfer_money_handler.py
│   └── get_balance_handler.py
└── services/                    # Application Services
    └── payment_service.py
```

#### Przykład Command i Handler
```python
# app/core/economy/application/commands/transfer_money.py
from dataclasses import dataclass
from ..base import Command

@dataclass
class TransferMoneyCommand(Command):
    """Komenda transferu pieniędzy"""
    from_wallet_id: str
    to_wallet_id: str
    amount: Decimal
    currency: str
    reason: str

# app/core/economy/application/handlers/transfer_money_handler.py
from ..interfaces import ICommandHandler, IUnitOfWork, IEventBus

class TransferMoneyHandler(ICommandHandler[TransferMoneyCommand]):
    def __init__(self, 
                 uow: IUnitOfWork,
                 event_bus: IEventBus):
        self._uow = uow
        self._event_bus = event_bus
    
    async def handle(self, command: TransferMoneyCommand) -> None:
        async with self._uow:
            # Pobierz portfele
            from_wallet = await self._uow.wallets.get(command.from_wallet_id)
            to_wallet = await self._uow.wallets.get(command.to_wallet_id)
            
            if not from_wallet or not to_wallet:
                raise WalletNotFoundError()
            
            # Wykonaj transfer
            money = Money(command.amount, command.currency)
            from_wallet.withdraw(money)
            to_wallet.deposit(money)
            
            # Zapisz zmiany
            await self._uow.wallets.update(from_wallet)
            await self._uow.wallets.update(to_wallet)
            
            # Utwórz transakcję
            transaction = Transaction(
                from_wallet_id=command.from_wallet_id,
                to_wallet_id=command.to_wallet_id,
                amount=money,
                reason=command.reason
            )
            await self._uow.transactions.add(transaction)
            
            # Zatwierdź
            await self._uow.commit()
            
            # Publikuj zdarzenia
            for event in from_wallet.domain_events + to_wallet.domain_events:
                await self._event_bus.publish(event)
```

### 3. Warstwa Infrastructure

```
infrastructure/
├── discord/                     # Adapter Discord
│   ├── bot.py                  # Główna klasa bota
│   ├── cogs/                   # Discord Cogs
│   │   ├── economy_cog.py
│   │   └── moderation_cog.py
│   └── converters/             # Konwertery typów
├── database/                    # Adapter bazy danych
│   ├── models/                 # SQLAlchemy models
│   ├── repositories/           # Implementacje repozytoriów
│   └── unit_of_work.py        # Implementacja UoW
├── cache/                      # Adapter cache
│   ├── redis_cache.py
│   └── memory_cache.py
└── messaging/                  # System eventów
    ├── event_bus.py
    └── handlers/
```

#### Przykład Implementacji Repozytorium
```python
# app/infrastructure/database/repositories/wallet_repository.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional

from app.core.economy.domain.models import Wallet as DomainWallet
from app.core.economy.domain.repositories import IWalletRepository
from ..models import WalletModel

class SqlAlchemyWalletRepository(IWalletRepository):
    def __init__(self, session: AsyncSession):
        self._session = session
    
    async def get(self, wallet_id: str) -> Optional[DomainWallet]:
        stmt = select(WalletModel).where(WalletModel.id == wallet_id)
        result = await self._session.execute(stmt)
        db_wallet = result.scalar_one_or_none()
        
        if not db_wallet:
            return None
        
        return self._to_domain(db_wallet)
    
    async def get_by_owner(self, owner_id: str) -> Optional[DomainWallet]:
        stmt = select(WalletModel).where(WalletModel.owner_id == owner_id)
        result = await self._session.execute(stmt)
        db_wallet = result.scalar_one_or_none()
        
        if not db_wallet:
            return None
        
        return self._to_domain(db_wallet)
    
    async def add(self, wallet: DomainWallet) -> None:
        db_wallet = self._to_db(wallet)
        self._session.add(db_wallet)
    
    async def update(self, wallet: DomainWallet) -> None:
        stmt = select(WalletModel).where(WalletModel.id == wallet.id)
        result = await self._session.execute(stmt)
        db_wallet = result.scalar_one()
        
        # Aktualizuj pola
        db_wallet.balance = float(wallet.balance.amount)
        db_wallet.currency = wallet.balance.currency
        db_wallet.updated_at = wallet.updated_at
    
    def _to_domain(self, db_wallet: WalletModel) -> DomainWallet:
        """Konwersja z modelu DB do modelu domenowego"""
        return DomainWallet(
            id=db_wallet.id,
            owner_id=db_wallet.owner_id,
            balance=Money(Decimal(str(db_wallet.balance)), db_wallet.currency),
            created_at=db_wallet.created_at,
            updated_at=db_wallet.updated_at
        )
    
    def _to_db(self, wallet: DomainWallet) -> WalletModel:
        """Konwersja z modelu domenowego do modelu DB"""
        return WalletModel(
            id=wallet.id,
            owner_id=wallet.owner_id,
            balance=float(wallet.balance.amount),
            currency=wallet.balance.currency,
            created_at=wallet.created_at,
            updated_at=wallet.updated_at
        )
```

### 4. Warstwa Presentation

```
presentation/bot/
├── cogs/                       # Discord Cogs
│   ├── base_cog.py            # Bazowy cog z DI
│   ├── economy_cog.py         # Komendy ekonomii
│   └── moderation_cog.py      # Komendy moderacji
├── views/                      # Discord UI Views
│   ├── shop_view.py
│   └── confirmation_view.py
├── embeds/                     # Discord Embeds
│   ├── wallet_embed.py
│   └── transaction_embed.py
└── converters/                 # Konwertery argumentów
    ├── member_converter.py
    └── money_converter.py
```

#### Przykład Cog z Dependency Injection
```python
# app/presentation/bot/cogs/economy_cog.py
from discord.ext import commands
from discord import app_commands
import discord

from app.core.economy.application.commands import TransferMoneyCommand
from app.core.economy.application.queries import GetWalletBalanceQuery
from app.core.shared.interfaces import ICommandBus, IQueryBus

class EconomyCog(commands.Cog):
    def __init__(self, bot: commands.Bot, command_bus: ICommandBus, query_bus: IQueryBus):
        self.bot = bot
        self._command_bus = command_bus
        self._query_bus = query_bus
    
    @app_commands.command(name="balance", description="Check your wallet balance")
    async def balance(self, interaction: discord.Interaction):
        """Sprawdź stan portfela"""
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Wykonaj zapytanie
            query = GetWalletBalanceQuery(user_id=str(interaction.user.id))
            balance = await self._query_bus.query(query)
            
            # Utwórz embed
            embed = discord.Embed(
                title="💰 Wallet Balance",
                color=discord.Color.gold()
            )
            embed.add_field(name="Balance", value=str(balance))
            embed.set_footer(text=f"User: {interaction.user.name}")
            
            await interaction.followup.send(embed=embed)
            
        except WalletNotFoundError:
            await interaction.followup.send(
                "❌ You don't have a wallet yet. Use `/wallet create` to create one."
            )
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}")
    
    @app_commands.command(name="transfer", description="Transfer money to another user")
    @app_commands.describe(
        recipient="The user to transfer money to",
        amount="The amount to transfer",
        reason="Reason for the transfer"
    )
    async def transfer(
        self, 
        interaction: discord.Interaction,
        recipient: discord.Member,
        amount: int,
        reason: str = "Transfer"
    ):
        """Transfer pieniędzy do innego użytkownika"""
        await interaction.response.defer()
        
        try:
            # Utwórz i wykonaj komendę
            command = TransferMoneyCommand(
                from_wallet_id=str(interaction.user.id),
                to_wallet_id=str(recipient.id),
                amount=Decimal(amount),
                currency="PLN",
                reason=reason
            )
            
            await self._command_bus.send(command)
            
            # Sukces
            embed = discord.Embed(
                title="✅ Transfer Successful",
                description=f"Transferred {amount} PLN to {recipient.mention}",
                color=discord.Color.green()
            )
            embed.add_field(name="Reason", value=reason)
            
            await interaction.followup.send(embed=embed)
            
        except InsufficientFundsError:
            await interaction.followup.send("❌ Insufficient funds for this transfer.")
        except WalletNotFoundError:
            await interaction.followup.send("❌ Wallet not found. Make sure both users have wallets.")
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {str(e)}")
```

## Komunikacja Między Modułami

### 1. Event-Driven Communication

```python
# app/core/shared/events/base.py
from dataclasses import dataclass
from datetime import datetime
from abc import ABC

@dataclass
class DomainEvent(ABC):
    """Bazowe zdarzenie domenowe"""
    event_id: str
    timestamp: datetime
    aggregate_id: str

# app/core/economy/events/money_transferred.py
@dataclass
class MoneyTransferred(DomainEvent):
    from_wallet_id: str
    to_wallet_id: str
    amount: Money
    reason: str

# app/core/activity/handlers/economy_events_handler.py
class EconomyEventsHandler:
    """Handler zdarzeń z modułu Economy w module Activity"""
    
    async def handle_money_transferred(self, event: MoneyTransferred):
        # Dodaj punkty aktywności za transfer
        await self._activity_service.add_points(
            user_id=event.from_wallet_id,
            points=10,
            reason="Money transfer activity"
        )
```

### 2. Inter-Module Services

```python
# app/core/shared/interfaces/inter_module.py
from typing import Protocol

class IEconomyFacade(Protocol):
    """Fasada modułu Economy dla innych modułów"""
    
    async def get_balance(self, user_id: str) -> Money:
        ...
    
    async def can_afford(self, user_id: str, amount: Money) -> bool:
        ...

# app/core/premium/services/subscription_service.py
class SubscriptionService:
    def __init__(self, economy_facade: IEconomyFacade):
        self._economy = economy_facade
    
    async def purchase_subscription(self, user_id: str, plan: SubscriptionPlan):
        # Sprawdź czy użytkownik może sobie pozwolić
        if not await self._economy.can_afford(user_id, plan.price):
            raise InsufficientFundsError()
        
        # Kontynuuj zakup...
```

## Konfiguracja i Bootstrap

### Dependency Injection Container

```python
# app/infrastructure/config/container.py
from dependency_injector import containers, providers

class Container(containers.DeclarativeContainer):
    # Konfiguracja
    config = providers.Configuration()
    
    # Infrastruktura
    database = providers.Singleton(
        Database,
        url=config.database.url
    )
    
    # Unit of Work
    uow = providers.Factory(
        SqlAlchemyUnitOfWork,
        session_factory=database.provided.session_factory
    )
    
    # Event Bus
    event_bus = providers.Singleton(
        InMemoryEventBus
    )
    
    # Command Bus
    command_bus = providers.Singleton(
        CommandBus
    )
    
    # Economy Module
    economy_facade = providers.Singleton(
        EconomyFacade,
        uow=uow,
        event_bus=event_bus
    )
    
    # Moderation Module
    moderation_facade = providers.Singleton(
        ModerationFacade,
        uow=uow,
        event_bus=event_bus
    )
    
    # Discord Bot
    bot = providers.Singleton(
        Bot,
        command_bus=command_bus,
        query_bus=providers.Singleton(QueryBus)
    )
```

### Bootstrap Application

```python
# app/main.py
import asyncio
from app.infrastructure.config.container import Container
from app.presentation.bot import create_bot

async def main():
    # Inicjalizuj kontener
    container = Container()
    container.config.from_yaml('config.yml')
    
    # Utwórz bota
    bot = await create_bot(container)
    
    # Zarejestruj handlery komend
    register_command_handlers(container.command_bus(), container)
    
    # Zarejestruj handlery zdarzeń
    register_event_handlers(container.event_bus(), container)
    
    # Uruchom bota
    await bot.start(container.config.bot.token())

def register_command_handlers(command_bus, container):
    # Economy
    command_bus.register(
        TransferMoneyCommand,
        TransferMoneyHandler(
            container.uow(),
            container.event_bus()
        )
    )
    # ... więcej handlerów

def register_event_handlers(event_bus, container):
    # Cross-module event handling
    event_bus.subscribe(
        MoneyTransferred,
        container.activity_facade().handle_money_transferred
    )
    # ... więcej subskrypcji

if __name__ == "__main__":
    asyncio.run(main())
```

## Zalety Tej Architektury

1. **Modularność** - Każdy moduł jest niezależny i może być rozwijany osobno
2. **Testowalność** - Łatwe mockowanie dzięki dependency injection
3. **Skalowalność** - Moduły mogą być wydzielone do osobnych serwisów
4. **Czytelność** - Jasna separacja odpowiedzialności
5. **Elastyczność** - Łatwe dodawanie nowych modułów i funkcjonalności
6. **Maintainability** - Zmiany w jednym module nie wpływają na inne

## Przykład Przepływu

### Transfer Pieniędzy - Pełny Przepływ

1. **Discord** → Użytkownik wpisuje: `/transfer @user 100 "za kawę"`

2. **Presentation Layer** → `EconomyCog.transfer()` parsuje komendę

3. **Application Layer** → Tworzy `TransferMoneyCommand`

4. **Command Bus** → Routuje do `TransferMoneyHandler`

5. **Domain Layer** → 
   - Ładuje `Wallet` aggregates
   - Wykonuje logikę biznesową
   - Generuje `MoneyTransferred` event

6. **Infrastructure Layer** →
   - Zapisuje zmiany przez `Repository`
   - Commituje transakcję przez `UnitOfWork`

7. **Event Bus** → Publikuje `MoneyTransferred`

8. **Other Modules** →
   - Activity module dodaje punkty
   - Notification module wysyła powiadomienie

9. **Response** → Embed z potwierdzeniem wraca do użytkownika

Ten przepływ pokazuje jak wszystkie warstwy współpracują zachowując separację i niezależność.