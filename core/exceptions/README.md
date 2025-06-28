# Exception Handling Guide

## Overview

This module provides a structured approach to error handling throughout the bot. All exceptions inherit from `BotError` and provide consistent error information.

## Exception Hierarchy

```
BotError
├── ValidationError         # Input validation failures
├── NotFoundError          # Resource not found
├── PermissionError        # Permission denied
├── ConfigurationError     # Configuration issues
├── ExternalServiceError   # External service failures
├── DatabaseError          # Database-related errors
│   ├── EntityNotFoundError
│   ├── IntegrityError
│   └── ConnectionError
├── DiscordError           # Discord API errors
│   ├── CommandError
│   ├── InteractionError
│   └── RateLimitError
└── DomainError            # Business logic errors
    ├── BusinessRuleViolation
    ├── InsufficientBalanceError
    ├── CooldownError
    └── LimitExceededError
```

## Usage Examples

### In Services

```python
from core.exceptions import (
    ValidationError,
    EntityNotFoundError,
    InsufficientBalanceError,
    CooldownError
)

class ShopService:
    async def purchase_role(self, member_id: int, role_id: int) -> Transaction:
        # Validation
        if role_id not in self.config["shop_roles"]:
            raise ValidationError(
                "Invalid role ID",
                field="role_id",
                value=role_id,
                user_message="Ta rola nie jest dostępna w sklepie."
            )
        
        # Get member
        member = await self.member_repo.get_by_id(member_id)
        if not member:
            raise EntityNotFoundError("Member", member_id)
        
        # Check balance
        role_price = self.config["shop_roles"][role_id]["price"]
        if member.balance < role_price:
            raise InsufficientBalanceError(
                required=role_price,
                available=member.balance
            )
        
        # Process purchase...
```

### In Commands

```python
from core.exceptions import BotError, CooldownError
from datetime import datetime, timedelta

@commands.hybrid_command(name="bump")
async def bump(self, ctx: commands.Context):
    try:
        # Check cooldown
        last_bump = await self.bump_service.get_last_bump()
        if last_bump:
            time_since = datetime.utcnow() - last_bump.timestamp
            if time_since < timedelta(hours=2):
                raise CooldownError(
                    action="bump",
                    retry_after=timedelta(hours=2) - time_since,
                    next_available=last_bump.timestamp + timedelta(hours=2)
                )
        
        # Process bump
        await self.bump_service.bump(ctx.author.id)
        await ctx.send("✅ Bump wykonany pomyślnie!")
        
    except CooldownError as e:
        await ctx.send(f"⏰ {e.user_message}")
    except BotError as e:
        await ctx.send(f"❌ {e.user_message}")
        logger.error(f"Bump error: {e}", exc_info=True)
    except Exception as e:
        await ctx.send("❌ Wystąpił nieoczekiwany błąd.")
        logger.error(f"Unexpected error in bump: {e}", exc_info=True)
```

### Global Error Handler

```python
@commands.Cog.listener()
async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
    # Handle command-specific errors
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"❌ Brakuje wymaganego argumentu: {error.param.name}")
        return
    
    # Handle our custom errors
    if isinstance(error.original, BotError):
        await ctx.send(f"❌ {error.original.user_message}")
        logger.warning(
            f"Command error in {ctx.command}: {error.original}",
            extra={"error_code": error.original.code, "details": error.original.details}
        )
        return
    
    # Log unexpected errors
    logger.error(f"Unexpected error in {ctx.command}: {error}", exc_info=True)
    await ctx.send("❌ Wystąpił nieoczekiwany błąd.")
```

## Best Practices

1. **Always provide user_message in Polish** - Users should see friendly error messages
2. **Include relevant details** - Add context that helps with debugging
3. **Use specific exceptions** - Don't use generic BotError, use specific subclasses
4. **Log appropriately** - Log errors with proper levels and context
5. **Handle at appropriate level** - Catch errors where you can handle them meaningfully

## Migration Guide

To migrate existing code:

1. Replace generic exceptions with specific ones:
   ```python
   # Before
   raise Exception("User not found")
   
   # After
   raise EntityNotFoundError("User", user_id)
   ```

2. Add user-friendly messages:
   ```python
   # Before
   await ctx.send("Error: Insufficient balance")
   
   # After
   raise InsufficientBalanceError(
       required=price,
       available=balance,
       user_message=f"Potrzebujesz {price} G, aby kupić tę rolę."
   )
   ```

3. Use error details for logging:
   ```python
   try:
       await service.process()
   except BotError as e:
       logger.error(
           f"Service error: {e}",
           extra={
               "error_code": e.code,
               "details": e.details,
               "user_id": ctx.author.id
           }
       )
   ```