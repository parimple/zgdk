# Info Cog Split Plan

## Current Structure Analysis

The `info.py` file contains 1326 lines with the following commands:

### Admin Commands
- `invites` - Display invites list with sorting
- `sync` - Sync commands
- `check_roles` - Check user roles (admin only)
- `check_status` - Check user status (admin only)
- `force_check_user_premium_roles` - Force check premium roles (admin only)
- `addt` - Add bypass time to user (admin only)

### General Info Commands
- `ping` - Simple ping command
- `guild_info` - Display guild information
- `all_roles` - Display all server roles

### User Profile Commands
- `profile` - Display user profile with stats
- `bypass` - Check voice bypass status

### Help/Documentation Commands
- `help` - Custom help command
- `games` - Display games information

## Proposed Split Structure

### 1. `admin_info.py` (Admin-only commands)
- `invites` command
- `sync` command
- `check_roles` command
- `check_status` command
- `force_check_user_premium_roles` command
- `addt` command
- Helper function: `remove_premium_role_mod_permissions`

### 2. `user_info.py` (User profile and stats)
- `profile` command
- `bypass` command
- Helper methods:
  - `_get_profile_data`
  - `_get_active_mutes`
  - `_create_profile_embed`
- Profile-related UI components

### 3. `server_info.py` (Server information)
- `ping` command
- `guild_info` command
- `all_roles` command

### 4. `help_info.py` (Help and documentation)
- `help` command
- `games` command
- Games pagination view

## Benefits of Split
1. **Better organization** - Commands grouped by functionality
2. **Easier maintenance** - Smaller files are easier to navigate
3. **Reduced complexity** - Each file has a single responsibility
4. **Better testability** - Smaller modules are easier to test

## Implementation Steps
1. Create new files in `cogs/commands/info/` directory
2. Move commands and their helpers to appropriate files
3. Update imports in each file
4. Create `__init__.py` to export all cogs
5. Update bot loading to handle multiple cogs from the info module
6. Test each command after migration