# Fix Scripts Guide

## Overview
These scripts provide quick fixes for common issues in the zaGadka Discord Bot. They should be used carefully and only when necessary.

## Fix Scripts

### 🔧 fix_premium_mapping.py
**Purpose**: Fix incorrect premium role mappings in the database
**When to use**:
- Users have premium roles but no database records
- Role IDs mismatch between Discord and database
- After manual role assignments

**Usage**:
```bash
python fix_premium_mapping.py [--dry-run]
```

**What it does**:
1. Scans all Discord members with premium roles
2. Checks database for corresponding records
3. Creates missing mappings
4. Updates incorrect mappings

### 🔧 fix_premium_roles.py
**Purpose**: Synchronize Discord roles with database premium status
**When to use**:
- Users lost premium roles after bot restart
- Database shows premium but Discord role missing
- After payment processing issues

**Usage**:
```bash
python fix_premium_roles.py [--user USER_ID]
```

**Options**:
- `--user USER_ID` - Fix specific user only
- `--dry-run` - Preview changes without applying

### 🔧 premium_role_mapping.py
**Purpose**: Utility for managing premium role configurations
**Features**:
- List all premium role mappings
- Validate role configurations
- Export/import role mappings

**Usage**:
```bash
# List mappings
python premium_role_mapping.py list

# Validate configuration
python premium_role_mapping.py validate

# Export mappings
python premium_role_mapping.py export > mappings.json
```

## Safety Guidelines

### Before Running Any Fix Script

1. **Backup Database**
   ```bash
   docker exec zgdk-db-1 pg_dump -U postgres postgres > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Test in Dry Run Mode**
   ```bash
   python fix_script.py --dry-run
   ```

3. **Check Logs**
   ```bash
   tail -f logs/fixes.log
   ```

### During Execution

- Monitor Discord audit logs
- Watch for error messages
- Keep original role configuration noted

### After Running

1. Verify fixes applied correctly
2. Test affected functionality
3. Document what was fixed and why

## Common Issues and Solutions

### Issue: Premium roles not syncing
```bash
# Fix all premium mappings
python fix_premium_mapping.py

# Then sync roles
python fix_premium_roles.py
```

### Issue: Specific user lost premium
```bash
# Fix single user
python fix_premium_roles.py --user 123456789
```

### Issue: Role configuration corrupted
```bash
# Validate and fix configuration
python premium_role_mapping.py validate
python premium_role_mapping.py repair
```

## Script Output

All fix scripts generate logs in:
- `logs/fixes/` - Detailed fix logs
- `logs/fixes/changes.log` - Summary of changes
- `logs/fixes/errors.log` - Any errors encountered

## Emergency Rollback

If a fix causes issues:

1. **Restore Database**
   ```bash
   docker exec -i zgdk-db-1 psql -U postgres postgres < backup_TIMESTAMP.sql
   ```

2. **Revert Discord Roles**
   - Use Discord audit log to manually revert
   - Or run fix script with `--revert` flag

## Best Practices

1. Always run during low-activity periods
2. Notify admins before running fixes
3. Document reason for running fix
4. Keep fix logs for audit trail
5. Remove fix scripts after successful migration to prevent accidental reuse