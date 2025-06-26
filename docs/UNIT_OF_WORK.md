# Unit of Work Pattern

## Overview

The Unit of Work pattern is implemented to provide better transaction management and maintain data consistency across multiple repository operations.

## Key Benefits

1. **Transaction Management**: Automatic commit/rollback handling
2. **Data Consistency**: All operations within a UoW succeed or fail together
3. **Repository Access**: Direct access to all repositories within a single transaction
4. **Error Handling**: Automatic rollback on exceptions
5. **Performance**: Single database session shared across operations

## Usage Patterns

### 1. Simple Usage with `get_unit_of_work()`

```python
async with self.bot.get_unit_of_work() as uow:
    # All operations share the same transaction
    member = await uow.members.get_by_discord_id(user_id)
    await uow.activities.add_activity(member.id, 10, "bonus")
    await uow.members.update_wallet_balance(member.id, new_balance)
    
    # Automatic commit occurs here
    # If any error occurs, automatic rollback happens
```

### 2. Manual Control with Session

```python
async with self.bot.get_db() as session:
    uow = self.bot.service_container.create_unit_of_work(session)
    
    async with uow:
        # Your operations here
        await uow.members.create_member(discord_id=user_id)
        
        # Manual commit for fine control
        await uow.commit()
```

### 3. Service Layer Integration

```python
# Services can use UoW for complex operations
async with self.bot.get_unit_of_work() as uow:
    member_service = await self.bot.get_service(IMemberService, uow.session)
    activity_service = await self.bot.get_service(IActivityService, uow.session)
    
    member = await member_service.get_or_create_member(discord_user)
    await activity_service.track_activity(member, "text", 5)
```

## Available Repositories

The Unit of Work provides direct access to these repositories:

- `uow.members` - Member data operations
- `uow.activities` - Activity tracking operations  
- `uow.invites` - Invite management operations
- `uow.moderation` - Moderation log operations
- `uow.roles` - Role management operations

## Transaction Behavior

### Automatic Commit
```python
async with self.bot.get_unit_of_work() as uow:
    # Do operations
    pass  # Automatic commit happens here
```

### Manual Commit
```python
async with uow:
    # Do operations
    await uow.commit()  # Manual commit
```

### Rollback on Error
```python
async with uow:
    # Do operations
    raise Exception("Something went wrong")
    # Automatic rollback occurs in __aexit__
```

## Best Practices

1. **Use for Complex Operations**: Use UoW when you need multiple repository operations to be atomic
2. **Keep Transactions Short**: Minimize the time between starting and committing transactions
3. **Handle Exceptions**: Always wrap UoW operations in try/catch blocks
4. **Prefer get_unit_of_work()**: Use the bot's convenience method for most cases
5. **Manual Commit for Complex Logic**: Use manual commit when you need fine-grained control

## Migration from Legacy Patterns

### Before (Legacy)
```python
async with self.bot.get_db() as session:
    member = await MemberQueries.get_by_discord_id(session, user_id)
    await ActivityQueries.add_activity(session, member_id, points, type)
    await session.commit()
```

### After (Unit of Work)
```python
async with self.bot.get_unit_of_work() as uow:
    member = await uow.members.get_by_discord_id(user_id)
    await uow.activities.add_activity(member.id, points, activity_type)
```

## Error Handling

The Unit of Work automatically handles common error scenarios:

- **Database Errors**: Automatic rollback on SQL exceptions
- **Business Logic Errors**: Rollback on any unhandled exception
- **Connection Issues**: Proper cleanup of database resources
- **Timeout Issues**: Session management with proper cleanup

## Performance Considerations

1. **Single Session**: All repositories share one database session
2. **Reduced Overhead**: Fewer database connections
3. **Batch Operations**: Multiple operations in single transaction
4. **Connection Pooling**: Efficient use of connection pool

## Examples

See `/examples/unit_of_work_example.py` for complete examples of:
- Basic Unit of Work usage
- Complex transaction scenarios
- Integration with service layer
- Error handling patterns