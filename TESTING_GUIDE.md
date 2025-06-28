# Discord Bot Testing Guide

This guide explains how to test Discord bot commands using the new testing framework.

## Quick Start

### Test a Single Command

```bash
# Basic command
python test_command.py bump

# Command with arguments
python test_command.py userinfo 123456789

# Command with multiple arguments
python test_command.py mute "@user" "10m" "spam"
```

### Test All Commands

```bash
# Run comprehensive test suite
python test_all_commands.py

# This will:
# - Test all available commands
# - Check for errors
# - Generate a detailed report
# - Save results to command_test_report.txt
```

### Generate Command Documentation

```bash
# Scan all cogs and generate command list
python generate_command_docs.py

# This creates:
# - COMMANDS.md: Full command documentation
# - command_test_list.txt: List of test commands to run
```

## Testing Framework Structure

### 1. `test_command.py` - Single Command Tester
- Tests individual commands via MCP
- Shows detailed response output
- Useful for debugging specific commands

**Features:**
- Real-time command execution
- Detailed response display
- Error reporting
- Optional Docker log checking

**Usage:**
```bash
python test_command.py <command> [args...]

# Examples:
python test_command.py help
python test_command.py shop
python test_command.py profile
python test_command.py bump

# With arguments:
python test_command.py buy 1
python test_command.py userinfo 123456789

# Check logs after command:
python test_command.py bump --check-logs
```

### 2. `test_all_commands.py` - Batch Command Tester
- Tests all commands systematically
- Generates comprehensive report
- Tracks success/failure rates
- Identifies permission-based failures

**Features:**
- Batch testing of all commands
- Performance metrics
- Error log extraction
- Report generation

**Output includes:**
- Summary statistics
- Failed command details
- Performance metrics
- Recent Docker errors

### 3. `generate_command_docs.py` - Documentation Generator
- Scans all cog files
- Extracts command definitions
- Generates markdown documentation
- Creates test command list

**Output files:**
- `COMMANDS.md`: Full command documentation
- `command_test_list.txt`: Ready-to-run test commands

### 4. Test Framework (`tests/framework/`)

#### `command_test_framework.py`
Advanced testing framework with:
- Command execution via MCP
- Response validation
- Mock data support
- Performance tracking
- Error handling tests
- Permission tests
- Cooldown tests

#### `mcp_test_runner.py`
MCP-integrated test runner with:
- Direct MCP server integration
- Real command execution
- Database state verification
- Docker log monitoring

## Writing New Tests

### Basic Test Structure

```python
from tests.framework.command_test_framework import CommandTestCase, CommandTestFramework

class MyCommandTest(CommandTestCase):
    """Test case for my commands."""
    
    async def test_my_command(self):
        """Test my command."""
        result = await self.assert_command_success(
            "mycommand",
            expected_response="Success"
        )
        print("✅ My command works!")
```

### Testing Command Failures

```python
async def test_command_permissions(self):
    """Test command permission requirements."""
    await self.assert_command_fails(
        "admin_command",
        expected_error="permissions"
    )
```

### Testing Cooldowns

```python
async def test_command_cooldown(self):
    """Test command cooldown."""
    # First execution
    await self.assert_command_success("cooldown_command")
    
    # Second should be on cooldown
    await self.assert_cooldown_active("cooldown_command")
```

## MCP Integration

All tests use the MCP (Model Context Protocol) server running in Docker to execute real commands. This ensures tests run against the actual bot implementation.

### MCP Server Location
- Container: `zgdk-mcp-1`
- Uses `mcp_bot_server.py` for command execution

### How It Works
1. Test sends command to MCP server
2. MCP server executes command in bot context
3. Response is captured and returned
4. Test validates the response

## Common Testing Scenarios

### 1. Testing New Commands
```bash
# After adding a new command, test it:
python test_command.py mynewcommand

# If it takes arguments:
python test_command.py mynewcommand arg1 arg2
```

### 2. Testing After Refactoring
```bash
# Run full test suite to ensure nothing broke:
python test_all_commands.py

# Check specific commands that were modified:
python test_command.py modified_command
```

### 3. Testing Error Handling
```bash
# Test with invalid arguments:
python test_command.py buy invalid_item_id
python test_command.py mute invalid_user
```

### 4. Performance Testing
```bash
# The test suite tracks execution times
python test_all_commands.py
# Check the report for slow commands
```

## Debugging Failed Tests

### 1. Check Docker Logs
```bash
# View recent errors:
docker-compose logs app --tail=100 | grep -E "(ERROR|Failed)"

# Or use the built-in option:
python test_command.py bump --check-logs
```

### 2. Test Individual Commands
```bash
# If a command fails in batch testing, test it individually:
python test_command.py failing_command
```

### 3. Check Command Registration
```bash
# Ensure no duplicate commands:
grep -r "@commands.hybrid_command" cogs/commands/ | grep "name="
```

## Best Practices

1. **Test After Every Change**
   - Run relevant command tests after modifying code
   - Use `test_command.py` for quick checks

2. **Regular Full Testing**
   - Run `test_all_commands.py` before commits
   - Check for any new failures

3. **Document New Commands**
   - Run `generate_command_docs.py` after adding commands
   - Update test cases for new commands

4. **Monitor Performance**
   - Check test reports for slow commands
   - Investigate commands taking >1s

5. **Handle Expected Failures**
   - Permission-based failures are expected
   - Test framework marks these as "EXPECTED_FAIL"

## Continuous Testing

For continuous testing during development:

```bash
# Watch mode (manual implementation):
while true; do
    clear
    python test_command.py bump
    sleep 5
done
```

Or create a custom watch script for specific commands you're working on.

## Integration with CI/CD

The test suite can be integrated into CI/CD pipelines:

```yaml
# Example GitHub Actions workflow
- name: Run Discord Bot Tests
  run: |
    docker-compose up -d
    sleep 10  # Wait for bot to start
    python test_all_commands.py
    exit_code=$?
    docker-compose down
    exit $exit_code
```

## Troubleshooting

### Container Not Found
```bash
# Ensure MCP container is running:
docker ps | grep zgdk-mcp
```

### Command Not Found
```bash
# Regenerate command list:
python generate_command_docs.py
```

### Timeout Errors
- Increase timeout in test scripts
- Check if bot is responding slowly
- Review Docker resource limits

### JSON Parse Errors
- Check MCP server output format
- Ensure bot responses are properly formatted

## Summary

This testing framework provides comprehensive tools for testing Discord bot commands:

1. **Single Command Testing** - Quick debugging
2. **Batch Testing** - Full regression testing  
3. **Documentation Generation** - Keep track of all commands
4. **Performance Monitoring** - Identify slow commands
5. **Error Detection** - Catch issues early

Use these tools regularly to maintain code quality and catch issues before they reach production.