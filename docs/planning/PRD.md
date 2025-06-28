# Product Requirements Document - zaGadka Discord Bot Refactoring

## Overview
Complete refactoring of zaGadka Discord bot to improve code quality, maintainability, and reliability.

## Current State
- Bot is functional but has technical debt
- Mixed architecture patterns (utility classes vs services)
- Some commands have errors (ranking, stats)
- Bump notification system needs fixes
- Code organization could be improved

## Goals
1. **Complete Service Architecture Migration**
   - Migrate all utility classes to Protocol-based services
   - Implement proper dependency injection
   - Use Unit of Work pattern for database transactions

2. **Fix All Command Errors**
   - Fix ranking/stats commands (activity service issues)
   - Fix team commands (no response)
   - Ensure all commands work properly

3. **Improve Bump System**
   - Fix notification messages after bumps
   - Handle cooldowns properly
   - Show proper emojis from config

4. **Code Organization**
   - Split large files into smaller modules
   - Group related functionality
   - Improve naming conventions

5. **Testing & Documentation**
   - Test all commands thoroughly
   - Document complex systems
   - Add integration tests

## Technical Requirements

### Architecture
- Use Protocol interfaces for all services
- Implement dependency injection
- Use async context managers for database sessions
- Follow SOLID principles

### Database
- Use repository pattern for all database operations
- Implement proper error handling
- Use transactions for data consistency

### Commands
- All commands must handle errors gracefully
- Provide user-friendly error messages
- Support both slash and text commands

### Performance
- Optimize database queries
- Use caching where appropriate
- Handle rate limits properly

## Success Criteria
- [ ] All commands work without errors
- [ ] Bump notifications appear after successful bumps
- [ ] Service architecture is consistent throughout
- [ ] Code is well-organized and maintainable
- [ ] All tests pass

## Current Issues to Fix
1. Activity service not working in ranking/stats commands
2. Bump handlers don't send congratulation messages
3. Team commands don't respond
4. Some Polish aliases are missing
5. Error handling needs improvement

## Priority Order
1. Fix critical command errors (High)
2. Complete service architecture migration (Medium)
3. Improve code organization (Medium)
4. Add missing features (Low)
5. Documentation and tests (Low)