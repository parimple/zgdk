# 🧪 Testing Framework Documentation

Comprehensive testing framework for zaGadka Discord Bot with organized structure, automated CI/CD, and professional tools.

---

## 🚀 Quick Start

```bash
# 1. Clean up and organize
./scripts/cleanup/cleanup_temp_files.sh
./scripts/test/organize_tests.sh

# 2. Run all tests
./scripts/test/run_all_tests.sh

# 3. Check bot health
./scripts/docker/health_check.sh

# 4. Run specific test category
pytest tests/unit/ -m unit -v
```

---

## 📁 Project Structure

```
zgdk/
├── tests/                          # All testing code
│   ├── unit/                       # Fast unit tests
│   ├── integration/                # Database integration tests
│   ├── e2e/                        # End-to-end Discord tests
│   ├── tools/                      # Testing utilities
│   ├── fixtures/                   # Test data and mocks
│   └── results/                    # Test outputs and reports
├── scripts/                        # Automation scripts
│   ├── cleanup/                    # Project cleanup
│   ├── test/                       # Test execution
│   ├── docker/                     # Docker utilities
│   └── lint/                       # Code quality
├── docs/testing/                   # Testing documentation
└── .github/workflows/              # CI/CD pipelines
```

---

## 🧪 Test Categories

### 1. **Unit Tests** (`tests/unit/`)
- **Speed**: Fast (< 1s per test)
- **Dependencies**: None (all mocked)
- **Purpose**: Test individual functions/classes

```bash
# Run unit tests
pytest tests/unit/ -m unit -v

# Run specific unit test
pytest tests/unit/test_permissions.py -v
```

### 2. **Integration Tests** (`tests/integration/`)
- **Speed**: Medium (1-10s per test)
- **Dependencies**: Test database
- **Purpose**: Test component interactions

```bash
# Run integration tests
pytest tests/integration/ -m integration -v

# Run with coverage
pytest tests/integration/ --cov=core --cov=utils
```

### 3. **End-to-End Tests** (`tests/e2e/`)
- **Speed**: Slow (10s+ per test)
- **Dependencies**: Real Discord API
- **Purpose**: Test complete user workflows

```bash
# Run E2E tests (requires Discord token)
CLAUDE_BOT_TOKEN=your_token pytest tests/e2e/ -m e2e -v

# Run single E2E test
CLAUDE_BOT_TOKEN=your_token pytest tests/e2e/test_discord_commands.py::test_addbalance_command -v
```

---

## 🛠️ Testing Tools

### **Discord Tester** (`tests/tools/discord_tester.py`)
Utility for testing Discord bot commands with real API:

```python
from tests.tools.discord_tester import DiscordTester

tester = DiscordTester(token)
result = await tester.test_command(
    ",addbalance @user 1000",
    expected_contains="Dodano 1000"
)
```

### **Log Monitor** (`tests/tools/log_monitor.py`)
Real-time Docker log monitoring for debugging:

```bash
python tests/tools/log_monitor.py --filter="ERROR|permission"
```

### **Mock Factories** (`tests/tools/mock_factories.py`)
Generate consistent test data:

```python
from tests.tools.mock_factories import create_mock_user, create_mock_guild

user = create_mock_user(id=123456789)
guild = create_mock_guild(id=960665311701528596)
```

---

## 📊 Test Configuration

### **pytest.ini** (`tests/pytest.ini`)
```ini
[tool:pytest]
testpaths = .
addopts = 
    -v --tb=short --strict-markers
    --cov=core --cov=utils --cov=cogs
    --html=results/reports/report.html
markers =
    unit: Unit tests - fast, no external dependencies
    integration: Integration tests - database required
    e2e: End-to-end tests - full system
    discord: Tests requiring Discord API tokens
```

### **Test Markers**
```python
@pytest.mark.unit
def test_permissions():
    """Fast unit test."""
    pass

@pytest.mark.integration
def test_database_integration():
    """Test with real database."""
    pass

@pytest.mark.e2e
@pytest.mark.discord
async def test_discord_command():
    """Test with real Discord API."""
    pass
```

---

## 🚀 Automation Scripts

### **Cleanup & Organization**
```bash
# Clean temporary files
./scripts/cleanup/cleanup_temp_files.sh

# Organize test structure
./scripts/test/organize_tests.sh
```

### **Test Execution**
```bash
# Run all tests with reporting
./scripts/test/run_all_tests.sh

# Run tests by category
./scripts/test/run_unit_tests.sh
./scripts/test/run_integration_tests.sh
./scripts/test/run_e2e_tests.sh
```

### **Docker Management**
```bash
# Check bot health
./scripts/docker/health_check.sh

# Restart with logs
./scripts/docker/restart_with_logs.sh
```

---

## 📈 CI/CD Integration

### **GitHub Actions** (`.github/workflows/discord-bot-tests.yml`)
Automated testing on every push/PR:

1. **Unit Tests**: Fast validation
2. **Integration Tests**: Database testing
3. **Code Quality**: Linting and formatting
4. **Security Scanning**: Dependency vulnerabilities
5. **Coverage Reports**: Code coverage analysis

### **Local CI Simulation**
```bash
# Run same tests as CI
./scripts/test/run_ci_locally.sh
```

---

## 🔧 Development Workflow

### **Adding New Tests**

1. **Unit Test**:
   ```python
   # tests/unit/test_new_feature.py
   @pytest.mark.unit
   def test_new_feature():
       # Mock dependencies
       # Test logic
       # Assert results
   ```

2. **Integration Test**:
   ```python
   # tests/integration/test_new_feature_integration.py
   @pytest.mark.integration
   @pytest.mark.asyncio
   async def test_new_feature_with_db():
       # Use real database
       # Test integration
   ```

3. **E2E Test**:
   ```python
   # tests/e2e/test_new_feature_e2e.py
   @pytest.mark.e2e
   @pytest.mark.discord
   async def test_new_feature_end_to_end():
       # Use Discord API
       # Test complete workflow
   ```

### **Test Data Management**
```python
# tests/fixtures/user_fixtures.py
@pytest.fixture
def mock_owner_user():
    return create_mock_user(id=956602391891947592, is_owner=True)

@pytest.fixture
def test_guild_config():
    return {
        "owner_ids": [956602391891947592, 968632323916566579],
        "premium_roles": [...]
    }
```

---

## 📊 Reporting & Analysis

### **HTML Reports**
Generated automatically in `tests/results/reports/`:
- `unit_report.html` - Unit test results
- `integration_report.html` - Integration test results
- `e2e_report.html` - End-to-end test results
- `coverage/index.html` - Code coverage analysis

### **Coverage Analysis**
```bash
# Generate coverage report
pytest tests/ --cov=core --cov=utils --cov=cogs --cov-report=html

# View coverage
open tests/results/coverage/index.html
```

### **Performance Metrics**
```bash
# Test execution time analysis
pytest tests/ --durations=10

# Memory usage profiling
pytest tests/ --profile
```

---

## 🎯 Best Practices

### **Test Organization**
- ✅ One test file per module
- ✅ Clear test names describing behavior
- ✅ Arrange-Act-Assert pattern
- ✅ Mock external dependencies

### **Test Data**
- ✅ Use fixtures for reusable test data
- ✅ Keep test data minimal and focused
- ✅ Avoid hard-coded values in tests
- ✅ Clean up test data after tests

### **Discord Testing**
- ✅ Use rate limiting (3-5 second delays)
- ✅ Mock Discord API for unit/integration tests
- ✅ Only use real API for E2E tests
- ✅ Handle token availability gracefully

### **Debugging**
- ✅ Use descriptive assertions
- ✅ Add logging for complex test scenarios
- ✅ Use Docker logs for integration debugging
- ✅ Run tests in isolation when debugging

---

## 🔍 Troubleshooting

### **Common Issues**

1. **Import Errors**:
   ```bash
   export PYTHONPATH="/home/ubuntu/Projects/zgdk:$PYTHONPATH"
   ```

2. **Discord API Rate Limits**:
   ```bash
   # Increase delays in tests
   await asyncio.sleep(5)  # Between Discord commands
   ```

3. **Database Connection Issues**:
   ```bash
   # Check Docker services
   docker-compose ps
   docker-compose logs db
   ```

4. **Permission Errors**:
   ```bash
   # Make scripts executable
   chmod +x scripts/**/*.sh
   ```

---

## 📚 Additional Resources

- [Testing Best Practices](./best_practices.md)
- [Discord API Testing Guide](./discord_testing.md)
- [CI/CD Configuration](./ci_cd.md)
- [Debugging Guide](./debugging.md)

---

**Status**: ✅ Professional testing framework ready for production use!

*This testing framework provides comprehensive coverage, automated execution, and professional reporting suitable for enterprise Discord bot development.*