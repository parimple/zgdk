# Test Scripts Guide

## Overview
This directory contains various testing scripts for the zaGadka Discord Bot. These scripts help verify bot functionality, test commands, and ensure proper integration.

## Main Testing Scripts

### 🔧 automated_bot_tester.py
**Purpose**: Comprehensive automated testing of bot commands and features
**Usage**: 
```bash
python automated_bot_tester.py
```
**Features**:
- Runs through predefined test scenarios
- Validates command responses
- Checks for error conditions
- Generates test reports

### 🔧 bot_command_tester.py
**Purpose**: Interactive command testing with real-time feedback
**Usage**:
```bash
python bot_command_tester.py <command> [args]
```
**Example**:
```bash
python bot_command_tester.py ranking
python bot_command_tester.py stats @user
```

### 🔧 quick_bot_test.py
**Purpose**: Quick smoke tests for basic bot functionality
**Usage**:
```bash
python quick_bot_test.py
```
**Tests**:
- Bot connection
- Basic command responses
- Database connectivity
- Service availability

## Specific Feature Tests

### Premium System Tests
- `test_check_balance.py` - Test G currency balance checking
- `test_direct_role_assignment.py` - Test role assignment functionality
- `test_full_premium_workflow.py` - End-to-end premium feature testing

### Integration Tests
- `test_live_integration.py` - Live Discord integration testing
- `test_gemini_integration.py` - Gemini AI integration tests
- `test_user_brilliant_fix.py` - Specific user role fix validation

### Permission Tests
- `test_bot_permissions.py` - Verify bot has correct permissions

### Utility Scripts
- `check_bump_cooldown.py` - Check bump command cooldowns
- `check_docker_errors.py` - Analyze Docker container errors

## Environment Setup

Before running tests:
1. Ensure Docker containers are running:
   ```bash
   docker-compose up -d
   ```

2. Set environment variables in .env:
   ```
   ZAGADKA_TOKEN=your_bot_token
   TEST_WEBHOOK_URL=your_test_webhook
   ```

3. Wait for bot initialization:
   ```bash
   sleep 10  # Wait for bot to fully start
   ```

## Test Data

Test scripts use:
- Test guild ID: 960665311701528596
- Test channel ID: 1387864734002446407
- Test user: bohun (ID: 956602391891947592)

## Common Issues

1. **Connection Refused**: Bot not fully started, wait longer
2. **Token Error**: Check ZAGADKA_TOKEN in .env
3. **Command Not Found**: Cog not loaded, check Docker logs
4. **Database Error**: PostgreSQL container not running

## Adding New Tests

1. Create new test script in this directory
2. Import common utilities:
   ```python
   import asyncio
   import aiohttp
   from datetime import datetime
   ```

3. Use standard test structure:
   ```python
   async def test_feature():
       # Setup
       # Execute
       # Validate
       # Cleanup
   
   if __name__ == "__main__":
       asyncio.run(test_feature())
   ```

4. Document expected results and edge cases