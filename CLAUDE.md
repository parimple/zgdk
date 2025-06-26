# Claude AI Assistant Guidelines

## Critical Rules for Docker Testing

� **ALWAYS verify Docker logs after making changes** �

When testing Discord bot changes:
1. Run `docker-compose down && docker-compose up --build` 
2. Check logs with `docker-compose logs app --tail=100 | grep -E "(ERROR|Failed)"`
3. Look for:
   - Command registration errors (duplicate commands/aliases)
   - Import errors 
   - Database constraint violations
   - Any other ERROR or Failed messages
4. **Do not assume success without checking logs**

## Common Issues to Watch For

### Command Conflicts
- Multiple cogs can't have commands with same name/alias
- Check existing commands before adding new ones

### Database Issues  
- Foreign key constraint violations
- Missing repository methods
- Null reference errors in services

### Import/Loading Issues
- Missing dependencies
- Circular imports
- Malformed Python syntax

## Debugging Commands

```bash
# Check for errors in logs
docker-compose logs app --tail=100 | grep -E "(ERROR|Failed)"

# Monitor live logs
docker-compose logs app --follow --tail=50

# Find command conflicts
grep -r "@commands\.hybrid_command" cogs/commands/ | grep "name="

# Search for specific patterns
grep -r "pattern" --include="*.py" cogs/
```

## Architecture Notes

### Service Layer Migration
- Bot is migrating from utility classes to Protocol-based services
- Use dependency injection via `bot.get_service(Interface, session)`
- Always use async context managers for database sessions

### Null Safety Pattern
```python
if self.service_manager:
    await self.service_manager.method()
```

### Repository Pattern
- Repositories handle database operations
- Services handle business logic
- Use get_or_create for members to avoid FK violations

## Test Verification Checklist

Before completing any task:
- [ ] Docker builds successfully
- [ ] All cogs load without errors  
- [ ] No command conflicts
- [ ] Database operations work
- [ ] Bot connects to Discord
- [ ] Real functionality tested (if possible)

## Current System Status

-  Null safety fixes completed
-  Service architecture migration completed  
-  Foreign key constraint issues resolved
-  Command conflict (profile) resolved
-  Member repository get_or_create method added
-  Activity tracking working correctly

## Notification System

� **ALWAYS notify user when task is completed** �

After completing any task, run: `echo -e "\a"`
This will emit a terminal bell sound to notify user via SSH.

## Future Maintenance

When adding new commands:
1. Check for name conflicts first
2. Use unique, descriptive names
3. Test in Docker immediately
4. Verify logs are clean

When modifying database operations:
1. Ensure proper null checks
2. Use get_or_create for referenced entities
3. Handle exceptions gracefully
4. Test foreign key relationships