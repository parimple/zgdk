# Service Architecture Migration Guide

## Overview

This guide documents the migration from utility-based architecture to service-oriented architecture in the zaGadka Discord Bot.

## Migration Status

### ✅ Completed Migrations

1. **Core Services**
   - `CurrencyManager` → `ICurrencyService` / `CurrencyService`
   - `ActivityManager` → `IActivityTrackingService` / `ActivityTrackingService`
   - Query classes → Repository pattern

2. **Base Classes**
   - Created `ServiceCog` - Base class for commands with service integration
   - Created `ServiceView` - Base class for Discord UI views with service integration

3. **Adapters for Gradual Migration**
   - `MessageSenderAdapter` - Bridges old MessageSender to new IMessageSender
   - `VoiceChannelAdapter` - Integrates voice services with existing code
   - `VoiceCommandAdapter` - Helps voice commands use new services
   - `BumpHandlerAdapter` - Integrates bump handlers with services

4. **Migrated Components**
   - `RankingCommands` - Using ServiceCog and IActivityTrackingService
   - `CategoryCommands` - Using ServiceCog with service methods
   - `OnBumpEvent` - Extended to use ServiceCog
   - `MuteCommands` - Migrated to ServiceCog
   - `RoleShopView` - Now extends ServiceView
   - `TeamManagementCommands` - Updated to use service methods

### 🔄 In Progress

- Voice system migration (partially complete)
- Message sender full migration
- Repository pattern adoption

### ⏳ Pending

- Complete removal of old utilities
- Full test coverage for migrated components
- Performance optimization

## Migration Patterns

### 1. Migrating a Cog to ServiceCog

**Before:**
```python
from discord.ext import commands
from utils.message_sender import MessageSender

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.message_sender = MessageSender(bot)
        
    async def my_command(self, ctx):
        embed = self.message_sender._create_embed(
            title="Title",
            description="Description",
            color="success"
        )
        await self.message_sender._send_embed(ctx, embed)
```

**After:**
```python
from core.base_cog import ServiceCog

class MyCog(ServiceCog):
    def __init__(self, bot):
        super().__init__(bot)
        
    async def my_command(self, ctx):
        await self.send_success(ctx, "Title", "Description")
```

### 2. Migrating a View to ServiceView

**Before:**
```python
import discord
from utils.message_sender import MessageSender

class MyView(discord.ui.View):
    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.message_sender = MessageSender(bot)
```

**After:**
```python
from core.base_view import ServiceView

class MyView(ServiceView):
    def __init__(self, bot):
        super().__init__(bot)
```

### 3. Using Services Directly

```python
async with self.bot.get_db() as session:
    # Get service
    currency_service = await self.bot.get_service(ICurrencyService, session)
    
    # Use service
    balance = await currency_service.get_balance(member_id)
    await currency_service.add_currency(member_id, amount)
```

## Service Architecture Benefits

1. **Separation of Concerns** - Business logic separated from Discord-specific code
2. **Testability** - Services can be easily mocked and tested
3. **Reusability** - Services can be used across different cogs and contexts
4. **Maintainability** - Clear interfaces make code easier to understand
5. **Scalability** - New features can be added without affecting existing code

## Best Practices

1. **Always extend ServiceCog/ServiceView** for new components
2. **Use service methods** (send_success, send_error, etc.) instead of direct MessageSender
3. **Implement gradual migration** - Don't break existing functionality
4. **Create adapters** when needed for smooth transition
5. **Document changes** in commit messages and code comments

## Common Pitfalls

1. **Don't remove old code immediately** - Maintain backward compatibility
2. **Test thoroughly** - Ensure both old and new paths work
3. **Handle service failures** - Always have fallback logic
4. **Avoid circular dependencies** - Use dependency injection properly

## Future Directions

1. **Complete MessageSender migration** - Replace all direct usage
2. **Implement caching layer** in services for performance
3. **Add comprehensive logging** to all services
4. **Create service health checks** for monitoring
5. **Develop service documentation** with examples

## Conclusion

The migration to service architecture is an ongoing process that improves code quality while maintaining stability. By following these patterns and best practices, the codebase becomes more maintainable and scalable for future development.