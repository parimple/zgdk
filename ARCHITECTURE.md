# ZGDK Architecture

## Overview
This document describes the architecture of the ZGDK Discord bot, outlining both the current architecture and a proposed refactoring plan to improve maintainability, testability, and extensibility.

## Current Architecture

The current architecture of the ZGDK bot is organized as follows:

```
/home/ubuntu/Projects/zgdk/
├── main.py                 # Entry point and bot initialization
├── config.yml              # Configuration
├── requirements.txt        # Dependencies
├── cogs/                   # Discord command & event handlers
│   ├── commands/           # Bot commands
│   ├── events/             # Event handlers
│   ├── ui/                 # UI components (embeds)
│   └── views/              # UI components (views)
├── datasources/            # Data access layer
│   ├── models.py           # SQLAlchemy models
│   └── queries.py          # Database queries
└── utils/                  # Utility functions and classes
    ├── permissions.py      # Permission decorators
    ├── premium.py          # Premium features
    ├── role_manager.py     # Role management
    ├── team_manager.py     # Team management
    └── moderation/         # Moderation utilities
```

### Current Strengths
1. **Clean Data Access**: Well-structured SQLAlchemy models and query classes
2. **Modular Commands**: Separation of commands into different cogs
3. **Event Handling**: Clear separation of event handlers
4. **Utility Classes**: Reusable functionality in utility classes

### Current Pain Points
1. **Mixed Responsibilities**: Some components handle both presentation and business logic
2. **Direct DB Access**: Commands directly access database queries
3. **Missing Service Layer**: No intermediate layer between commands and data access
4. **Duplicate Logic**: Some business logic is duplicated across different components
5. **Limited Testability**: Difficult to test business logic in isolation

## Proposed Architecture

The proposed architecture follows a layered approach to achieve better separation of concerns:

```
┌─ Presentation Layer ─┐
│  Commands, Events,   │
│  Views, Embeds       │
├─────────┬────────────┤
          │
┌─────────▼────────────┐
│    Service Layer     │
│  Service classes     │
├─────────┬────────────┤
          │
┌─────────▼────────────┐
│    Domain Layer      │
│  Business logic      │
├─────────┬────────────┤
          │
┌─────────▼────────────┐
│  Data Access Layer   │
│  Database operations │
└──────────────────────┘
```

### Target Directory Structure (Long-term Goal)

```
/home/ubuntu/Projects/zgdk/
├── main.py
├── config.yml
├── requirements.txt
├── presentation/           # Presentation layer
│   ├── commands/           # Discord commands
│   ├── events/             # Event handlers
│   ├── views/              # UI views
│   ├── embeds/             # Embeds
│   └── formatters/         # Message formatters
├── services/               # Service layer
│   ├── shop_service.py
│   ├── role_service.py
│   ├── voice_service.py
│   └── ...
├── domain/                 # Domain layer
│   ├── errors.py           # Domain exceptions
│   ├── validators/         # Input validation
│   ├── models/             # Domain models
│   └── managers/           # Business logic
├── data/                   # Data access layer
│   └── repositories/       # Repository pattern
└── utils/                  # Shared utilities
```

## Refactoring Plan

### Phase 1: Documentation and Analysis
1. Create architecture documentation
2. Analyze existing code patterns
3. Identify key components for refactoring
4. Document refactoring priorities

### Phase 2: Create Core Infrastructure
1. Define domain exceptions
2. Create base service classes
3. Implement message formatters
4. Define interfaces for domain components

### Phase 3: Refactor One Component at a Time
1. Start with ShopCog (as per SHOP_REFACTOR_ANALYSIS.md)
2. Create ShopService and ShopManager
3. Refactor ShopCog to use ShopService
4. Verify functionality with tests

### Phase 4: Gradually Extend the Pattern
1. Apply the pattern to RoleManager
2. Apply the pattern to VoiceSystem
3. Refactor other components following the same pattern
4. Ensure backward compatibility throughout

### Phase 5: Cleanup and Optimization
1. Remove deprecated components
2. Optimize database access patterns
3. Implement caching where appropriate
4. Complete test coverage

## Implementation Guidelines

### 1. Service Layer (services/*.py)
- Serves as interface between presentation and domain
- Handles error management and transactions
- Returns standardized results (success/failure, messages)
- Example:

```python
class ShopService:
    def __init__(self, bot):
        self.bot = bot
        self.shop_manager = ShopManager(bot)

    async def add_balance(self, admin, user, amount):
        try:
            result = await self.shop_manager.add_balance(
                admin.display_name, user.id, amount
            )
            return True, f"Added {amount} to user's wallet"
        except Exception as e:
            return False, str(e)
```

### 2. Domain Layer (domain/*.py)
- Contains business logic independent of presentation
- Implements domain rules and validations
- Throws domain-specific exceptions
- Example:

```python
class ShopManager:
    def __init__(self, bot):
        self.bot = bot
        
    async def add_balance(self, admin_name, user_id, amount):
        # Validation
        if amount <= 0:
            raise InvalidInputError("Amount must be positive")
            
        # Implementation
        payment_data = PaymentData(...)
        async with self.bot.get_db() as session:
            # Database operations
```

### 3. Presentation Layer (presentation/*.py)
- Handles user interaction
- Delegates business logic to services
- Formats responses for users
- Example:

```python
class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.shop_service = ShopService(bot)
        
    @commands.command(name="add")
    async def add_balance(self, ctx, user, amount):
        success, message = await self.shop_service.add_balance(
            ctx.author, user, amount
        )
        
        if success:
            await ctx.reply(f"Added {amount} to {user.mention}'s wallet!")
        else:
            await ctx.reply(f"Error: {message}")
```

## Benefits of New Architecture

1. **Separation of Concerns**: Each layer has a specific responsibility
2. **Testability**: Business logic can be tested independently
3. **Maintainability**: Easier to understand and modify components
4. **Extensibility**: New features can be added without modifying existing code
5. **Consistency**: Standard patterns across the codebase

## Migration Strategy

To minimize disruption, the refactoring will be performed incrementally:

1. Create new components without removing existing ones
2. Update one component at a time to use the new architecture
3. Ensure tests pass after each change
4. Only remove deprecated components after thorough testing

This approach ensures that the bot remains functional throughout the refactoring process.