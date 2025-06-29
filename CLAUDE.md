# Claude AI Assistant Guidelines

## 📁 Project Structure Overview

The zaGadka Discord Bot project has been reorganized for better maintainability:

```
zgdk/
├── docs/           # All documentation
│   ├── architecture/   # System design docs
│   ├── refactoring/    # Migration plans
│   ├── ai/            # AI integration docs
│   └── planning/      # PRDs and task lists
│
├── scripts/        # Utility scripts
│   ├── debug/         # Debug tools
│   ├── testing/       # Test scripts
│   ├── migration/     # Migration utilities
│   └── fixes/         # Quick fixes
│
├── tests/          # Test suites
│   ├── unit/          # Unit tests
│   ├── integration/   # Integration tests
│   └── mcp/           # MCP testing tools
│
├── cogs/           # Discord bot modules
│   ├── commands/      # Command handlers
│   ├── events/        # Event listeners
│   ├── ui/            # UI components
│   └── views/         # Discord views
│
├── core/           # Business logic
│   ├── interfaces/    # Protocol definitions
│   ├── services/      # Service implementations
│   ├── repositories/  # Data access layer
│   └── adapters/      # External integrations
│
├── datasources/    # Database layer
│   ├── models/        # SQLAlchemy models
│   └── queries/       # Legacy (migrating to repositories)
│
└── utils/          # Utilities (migrating to services)
```

## 📚 Key Documentation Locations

- **Project Structure**: `/PROJECT_STRUCTURE.md`
- **Architecture**: `/docs/architecture/MODULAR_ARCHITECTURE_DESIGN.md`
- **Refactoring Plan**: `/docs/refactoring/REFACTORING_PLAN.md`
- **Test Guide**: `/tests/mcp/README.md`
- **Scripts Guide**: `/scripts/README.md`

## 🔧 Testing Discord Commands

### Using MCP (Model Context Protocol)
```bash
# Test single command
python tests/mcp/utils/test_commands_mcp.py ranking

# Interactive testing
python tests/mcp/utils/mcp_client.py
```

### Quick Testing
```bash
# Test bot functionality
python scripts/testing/bot_command_tester.py <command>

# Automated tests
python scripts/testing/automated_bot_tester.py
```

## Critical Rules for Docker Testing

⚠️ **ALWAYS verify Docker logs after making changes** ⚠️

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

# Rebuild Docker containers (when changes aren't reflected)
docker-compose down && docker-compose up --build

# Use debug interface
python scripts/debug/debug_interface.py
```

## Architecture Notes

### Service Layer Migration
- Bot is migrating from utility classes to Protocol-based services
- Use dependency injection via `bot.get_service(Interface, session)`
- Always use async context managers for database sessions

### Current Migration Status
- ✅ `utils/currency.py` → `core/services/currency_service.py`
- ✅ `utils/managers/activity_manager.py` → `core/services/activity_tracking_service.py`
- 🔄 `utils/team_manager.py` → `core/services/team_management_service.py` (partial)
- 🔄 `datasources/queries/` → `core/repositories/` (ongoing)

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

- ✅ Null safety fixes completed
- ✅ Service architecture migration in progress
- ✅ Foreign key constraint issues resolved
- ✅ Command conflict (profile) resolved
- ✅ Member repository get_or_create method added
- ✅ Activity tracking working correctly
- ✅ Project structure reorganized
- ✅ All test scripts organized in `/tests/mcp/`
- ✅ All utility scripts organized in `/scripts/`
- ✅ Documentation consolidated in `/docs/`

## Integration Testing

### Running Tests
```bash
# Run all integration tests
cd /home/ubuntu/Projects/zgdk
python -m pytest tests/integration/ -v

# Run specific test
python -m pytest tests/integration/test_bump_commands.py -v

# Run with output
python -m pytest tests/integration/test_bump_commands.py -v -s
```

### Creating New Tests
1. Create test file in `tests/integration/`
2. Use existing test structure as template
3. Mock Discord objects properly
4. Test both success and failure cases

### Example Test Structure
```python
import pytest
from unittest.mock import MagicMock, AsyncMock
import discord

@pytest.mark.asyncio
async def test_command():
    # Setup mocks
    bot = MagicMock()
    ctx = MagicMock()
    
    # Test command
    # Assert results
```

## Testing Commands with Pytest

🧪 **ALWAYS test commands using pytest with MCP** 🧪

When testing or modifying commands:
1. Run tests for specific command module:
   ```bash
   python -m pytest tests/commands/test_mute_commands.py -v
   ```
2. Run single test with output for debugging:
   ```bash
   python -m pytest tests/commands/test_mute_commands.py::TestMuteCommands::test_mute_txt_default_duration -v -s
   ```
3. If tests fail, iterate:
   - Check the actual error
   - Fix the code
   - Run tests again
   - Repeat until all tests pass

Example workflow (from mute/unmute fix):
```bash
# 1. Run tests
python -m pytest tests/commands/test_mute_commands.py -v

# 2. If failing, check specific test
python -m pytest tests/commands/test_mute_commands.py::TestMuteCommands::test_mute_txt_default_duration -v -s

# 3. Fix the code (e.g., static method calls → instance method calls)

# 4. Restart bot
docker-compose down && docker-compose up -d --build

# 5. Run tests again to verify fix
python -m pytest tests/commands/test_mute_commands.py -v
```

**Important**: Tests use MCP (Model Context Protocol) to execute real commands through API, ensuring real functionality is tested.


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

## Finding Files

### Quick File Location Guide
- **Commands**: `/cogs/commands/`
- **Services**: `/core/services/`
- **Tests**: `/tests/` and `/scripts/testing/`
- **Configs**: `/config.yml` and `/.env`
- **Docs**: `/docs/`
- **Debug Tools**: `/scripts/debug/`
- **Migration Scripts**: `/scripts/migration/`

### Common File Searches
```bash
# Find command implementation
grep -r "command_name" cogs/commands/

# Find service usage
grep -r "IServiceName" core/

# Find test for feature
find tests/ -name "*feature*"
```

## Critical Error Checking Guidelines

- Always check logs for errors after making changes
- Verify error logs in Docker containers
- Modify and test scripts thoroughly before deployment
- Carefully examine logs to ensure all components load correctly
```

## Memory Notes

- **Push/Deployment Workflow Notes**:
  - After pushing changes, always verify that everything has been deployed correctly
  - If any issues are detected, continue working and addressing them immediately
  - Reminder: zapamietaj by po pushu sprawdzic jeszcze czy wszystko przeszlo i jak nie to pracuj dalej