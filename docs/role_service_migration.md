# Role Service Layer Migration Guide

## Overview

The RoleQueries class has been migrated to a proper service layer architecture following the Repository and Service patterns. This improves code organization, testability, and maintainability.

## New Architecture

### Components

1. **IRoleService**: Service interface defining business logic operations
2. **IRoleRepository**: Repository interface defining data access operations  
3. **RoleService**: Implementation of role business logic
4. **RoleRepository**: Implementation of role data access

### Key Improvements

- **Separation of Concerns**: Business logic separated from data access
- **Testability**: Services can be easily mocked for testing
- **Null Safety**: Proper error handling and null checks
- **Logging**: Comprehensive logging of operations and errors
- **Type Safety**: Full type hints and interface contracts

## Migration Guide

### Before (RoleQueries)
```python
from datasources.queries import RoleQueries

# In your code
expired_roles = await RoleQueries.get_expired_roles(session, current_time)
await RoleQueries.delete_member_role(session, member_id, role_id)
```

### After (Service Layer)
```python
from core.interfaces.role_interfaces import IRoleService
from core.repositories.role_repository import RoleRepository
from core.services.role_service import RoleService

# Setup (typically done in dependency injection container)
role_repository = RoleRepository(session)
role_service = RoleService(role_repository)

# In your code
expired_roles = await role_service.process_expired_roles()
await role_service.delete_member_role(member_id, role_id)
```

## Available Methods

### Role Management
- `get_role_by_id(role_id)` - Get role by ID
- `get_role_by_name(name)` - Get role by name
- `create_role(role_id, name, type)` - Create new role

### Member Role Operations
- `add_or_update_role_to_member(member_id, role_id, duration)` - Add/update role
- `delete_member_role(member_id, role_id)` - Remove role from member
- `check_member_has_role(member_id, role_id)` - Check if member has role
- `get_member_role_info(member_id)` - Get all roles for member

### Premium Role Operations
- `get_member_premium_roles(member_id)` - Get premium roles for member
- `get_premium_role(member_id)` - Get active premium role
- `count_unique_premium_users()` - Count premium users

### Role Expiration
- `process_expired_roles(role_type, role_ids)` - Process expired roles
- `get_expiring_roles(reminder_time, role_type)` - Get expiring roles
- `update_role_expiration_date(member_id, role_id, duration)` - Extend role
- `update_role_expiration_date_direct(member_id, role_id, new_expiry)` - Set expiry

### Discord Integration
- `assign_role_to_member(member, role, expiry_time, role_type)` - Assign Discord role
- `remove_role_from_member(member, role)` - Remove Discord role

## Error Handling

The service layer includes comprehensive error handling:

- **Logging**: All operations and errors are logged with context
- **Null Safety**: Proper handling of null references  
- **Exception Handling**: Graceful handling of database and Discord API errors
- **Return Values**: Clear boolean/optional return types

## Integration with Existing Code

The service layer is designed to be backward compatible. Existing RoleQueries usage can be gradually migrated without breaking changes.

### Example: Migrating role_manager.py

```python
# Old approach
class RoleManager:
    async def check_expired_roles(self, session):
        expired_roles = await RoleQueries.get_expired_roles(session, current_time)
        
# New approach  
class RoleManager:
    def __init__(self, bot, role_service: IRoleService):
        self.bot = bot
        self.role_service = role_service
        
    async def check_expired_roles(self):
        expired_roles = await self.role_service.process_expired_roles()
```

## Next Steps

1. **Gradual Migration**: Update one file at a time to use the service layer
2. **Dependency Injection**: Set up proper DI container for services
3. **Testing**: Add unit tests for service layer components
4. **Documentation**: Update code documentation to reflect new patterns

## Files That Need Migration

Key files still using RoleQueries:
- `utils/role_manager.py` - Main role management logic
- `cogs/events/on_task.py` - Scheduled tasks
- `cogs/commands/info.py` - Info commands
- `utils/premium_logic.py` - Premium logic
- `utils/role_sale.py` - Role sales

These files should be updated to use the new service layer for better maintainability.