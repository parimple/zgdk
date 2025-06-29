# Service Architecture Quick Reference

## Available Services

### Core Services

| Interface | Implementation | Purpose |
|-----------|----------------|---------|
| `ICurrencyService` | `CurrencyService` | Manage user currency/points |
| `IActivityTrackingService` | `ActivityTrackingService` | Track user activity |
| `IPremiumService` | `PremiumService` | Handle premium features |
| `IMessageSender` | `MessageSenderService` | Send Discord messages |
| `IEmbedBuilder` | `EmbedBuilderService` | Create Discord embeds |
| `IRoleService` | `RoleService` | Manage Discord roles |
| `IMemberService` | `MemberService` | Handle member data |
| `IVoiceChannelService` | `VoiceChannelService` | Manage voice channels |
| `IAutoKickService` | `AutoKickService` | Handle auto-kick functionality |

### Getting Services

```python
# In a command
async with self.bot.get_db() as session:
    service = await self.bot.get_service(IServiceInterface, session)
```

## Base Classes

### ServiceCog

```python
from core.base_cog import ServiceCog

class MyCog(ServiceCog):
    async def my_command(self, ctx):
        # Built-in methods
        await self.send_success(ctx, "Title", "Success message")
        await self.send_error(ctx, "Error", "Error message")
        await self.send_info(ctx, "Info", "Information message")
        
        # Get services
        embed_builder = await self.get_embed_builder()
        message_service = await self.get_message_service()
```

### ServiceView

```python
from core.base_view import ServiceView

class MyView(ServiceView):
    async def button_callback(self, interaction: discord.Interaction):
        # Built-in methods
        await self.send_success(interaction, "Success", "Action completed")
        await self.send_error(interaction, "Error", "Action failed")
        await self.send_info(interaction, "Info", "Information")
```

## Repositories

| Repository | Purpose |
|------------|---------|
| `MemberRepository` | Member data access |
| `RoleRepository` | Role data access |
| `ActivityRepository` | Activity tracking data |
| `ChannelRepository` | Channel permissions |
| `PaymentRepository` | Payment records |
| `PremiumRepository` | Premium status |

### Using Repositories

```python
from core.repositories import MemberRepository

async with self.bot.get_db() as session:
    member_repo = MemberRepository(session)
    member = await member_repo.get_or_create(member_id)
```

## Adapters

| Adapter | Purpose |
|---------|---------|
| `MessageSenderAdapter` | Bridge old MessageSender to services |
| `VoiceChannelAdapter` | Integrate voice services |
| `VoiceCommandAdapter` | Help voice commands use services |
| `BumpHandlerAdapter` | Integrate bump handlers |

## Common Patterns

### Error Handling

```python
try:
    service = await self.bot.get_service(IService, session)
    result = await service.method()
except Exception as e:
    logger.error(f"Service error: {e}")
    await self.send_error(ctx, "Error", "Service unavailable")
```

### Service with Fallback

```python
service = await self.get_message_service()
if service:
    await service.send_embed(ctx, embed)
else:
    # Fallback to old method
    await self.message_sender._send_embed(ctx, embed)
```

### Transaction Pattern

```python
async with self.bot.get_db() as session:
    try:
        service = await self.bot.get_service(IService, session)
        await service.operation()
        await session.commit()
    except Exception as e:
        await session.rollback()
        raise
```

## Migration Checklist

- [ ] Extend ServiceCog/ServiceView instead of commands.Cog/discord.ui.View
- [ ] Replace MessageSender with built-in methods
- [ ] Use services through interfaces
- [ ] Add error handling with fallbacks
- [ ] Test both new and legacy paths
- [ ] Update imports and dependencies
- [ ] Document any special behavior

## Tips

1. **Start small** - Migrate one command at a time
2. **Test thoroughly** - Ensure backward compatibility
3. **Use type hints** - Makes service usage clearer
4. **Log service calls** - Helps with debugging
5. **Cache services** - ServiceCog/View do this automatically

## Need Help?

- Check `/docs/architecture/MIGRATION_GUIDE.md` for detailed examples
- Look at migrated cogs in `/cogs/commands/` for patterns
- Review service implementations in `/core/services/`