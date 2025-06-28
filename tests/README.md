# Discord Bot Tests

Modular test suite for testing Discord bot commands and functionality.

## Structure

```
tests/
├── config.py                    # Test configuration (user IDs, channels, etc.)
├── base/                        # Base test classes
│   └── test_base.py            # BaseDiscordTest and CommandTestCase
├── utils/                       # Test utilities
│   ├── client.py               # TestClient for API communication
│   └── assertions.py           # Custom assertions for Discord responses
├── commands/                    # Command-specific tests
│   ├── test_mute_commands.py   # Mute/unmute command tests
│   ├── test_info_commands.py   # Info command tests
│   └── ...                     # Other command tests
├── integration/                 # Integration tests
│   └── test_mute_workflow.py   # Complete workflow tests
└── run_tests.py               # Main test runner
```

## Running Tests

### Prerequisites

1. Bot must be running with `command_tester` cog loaded
2. Docker containers must be up: `docker-compose up --build`

### Run All Tests

```bash
cd tests
python run_tests.py
```

### Run Specific Test Module

```bash
python run_tests.py commands.test_mute_commands
```

### Run Multiple Modules

```bash
python run_tests.py commands.test_mute_commands integration.test_mute_workflow
```

### Options

- `-v, --verbose`: Increase output verbosity
- `-q, --quiet`: Decrease output verbosity  
- `-f, --failfast`: Stop on first failure

### Examples

```bash
# Run all tests with verbose output
python run_tests.py -v

# Run mute tests and stop on first failure
python run_tests.py -f commands.test_mute_commands

# Run integration tests quietly
python run_tests.py -q integration
```

## Writing New Tests

### Command Test Example

```python
from tests.base.test_base import CommandTestCase
from tests.config import TEST_USER_ID

class TestMyCommands(CommandTestCase):
    
    def test_my_command(self):
        """Test my command."""
        result = self.run_async(
            self.execute_command("mycommand", "args")
        )
        
        self.assert_command_success(result)
        self.assert_command_success(result, "Expected text")
```

### Using Assertions

```python
from tests.utils.assertions import (
    assert_user_mentioned,
    assert_has_timestamp,
    assert_premium_info
)

# In your test
response = result["responses"][0]
self.assertTrue(assert_user_mentioned(response, TEST_USER_ID))
self.assertTrue(assert_has_timestamp(response))
self.assertTrue(assert_premium_info(response))
```

### Configuration

Edit `tests/config.py` to set:
- Test user IDs
- Channel IDs
- API endpoints
- Test data (durations, colors, etc.)

## Test Coverage

Current test coverage includes:

- ✅ Mute/unmute commands (all types)
- ✅ Info commands (profile, help, games, etc.)
- ✅ Mute workflows and overrides
- 🔲 Premium commands
- 🔲 Moderation commands
- 🔲 Shop commands
- 🔲 Activity tracking

## Troubleshooting

### Bot Connection Failed

```
❌ Cannot connect to bot at http://localhost:8090
```

**Solution**: Ensure bot is running and command_tester cog is loaded.

### Import Errors

```
ModuleNotFoundError: No module named 'tests'
```

**Solution**: Run tests from the tests directory or project root.

### Timeout Errors

Increase timeouts in `config.py`:
```python
COMMAND_TIMEOUT = 30  # seconds
CONNECTION_TIMEOUT = 10  # seconds
```