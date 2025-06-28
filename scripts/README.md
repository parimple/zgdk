# Scripts Directory

This directory contains utility scripts for various purposes in the zaGadka Discord Bot project.

## Directory Organization

### 📁 debug/
Debugging and diagnostic scripts
- `debug_interface.py` - Interactive debugging interface
- `debug_step_by_step.py` - Step-by-step debugging tool
- `debug_stub.py` - Stub for testing debug features
- `debug_test.py` - Debug testing utilities

### 📁 testing/
Testing and bot command testing scripts
- `automated_bot_tester.py` - Automated bot testing framework
- `bot_command_tester.py` - Manual command testing tool
- `quick_bot_test.py` - Quick bot functionality tests
- Various integration test scripts

### 📁 migration/
Data and code migration scripts
- `migrate_currency_imports.py` - Migrate from utils.currency to CurrencyService
- Database migration scripts

### 📁 fixes/
Quick fix scripts for specific issues
- `fix_premium_mapping.py` - Fix premium role mappings
- `fix_premium_roles.py` - Fix premium role assignments
- `premium_role_mapping.py` - Premium role mapping utilities

## Usage Examples

### Running Debug Interface
```bash
python scripts/debug/debug_interface.py
```

### Testing Bot Commands
```bash
python scripts/testing/bot_command_tester.py
```

### Running Migrations
```bash
python scripts/migration/migrate_currency_imports.py
```

### Applying Fixes
```bash
python scripts/fixes/fix_premium_roles.py
```

## Important Notes

- Always backup database before running migration or fix scripts
- Test scripts use the test webhook URL from .env
- Debug scripts may require elevated permissions
- Migration scripts are one-time use and should be removed after successful migration