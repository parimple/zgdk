# zaGadka Discord Bot - Project Structure

## 📁 Project Organization

```
zgdk/
├── 📄 main.py                 # Bot entry point
├── 📄 setup.py                # Package setup
├── 📄 requirements.txt        # Python dependencies
├── 📄 docker-compose.yml      # Docker configuration
├── 📄 .env                    # Environment variables
├── 📄 config.yml              # Bot configuration
├── 📄 CLAUDE.md               # AI assistant guidelines
├── 📄 README.md               # Project overview
│
├── 📁 app/                    # Main application code
│   ├── 📁 cogs/              # Discord bot commands and events
│   │   ├── 📁 commands/      # Command modules
│   │   ├── 📁 events/        # Event handlers
│   │   ├── 📁 ui/            # UI components
│   │   └── 📁 views/         # Discord views
│   │
│   ├── 📁 core/              # Core business logic
│   │   ├── 📁 interfaces/    # Protocol interfaces
│   │   ├── 📁 services/      # Business services
│   │   ├── 📁 repositories/  # Data access layer
│   │   └── 📁 adapters/      # External adapters
│   │
│   ├── 📁 datasources/       # Database layer
│   │   ├── 📁 models/        # SQLAlchemy models
│   │   └── 📁 queries/       # Legacy queries (migrating to repositories)
│   │
│   └── 📁 utils/             # Utility functions
│       ├── 📁 managers/      # Legacy managers (migrating to services)
│       └── 📁 voice/         # Voice channel utilities
│
├── 📁 docs/                  # Documentation
│   ├── 📁 architecture/      # System design docs
│   ├── 📁 refactoring/       # Refactoring plans
│   ├── 📁 ai/                # AI integration docs
│   └── 📁 planning/          # Project planning
│
├── 📁 scripts/               # Utility scripts
│   ├── 📁 debug/            # Debugging tools
│   ├── 📁 testing/          # Test scripts
│   ├── 📁 migration/        # Migration scripts
│   └── 📁 fixes/            # Quick fixes
│
├── 📁 tests/                 # Test suite
│   ├── 📁 unit/             # Unit tests
│   ├── 📁 integration/      # Integration tests
│   └── 📁 mcp/              # MCP testing tools
│
├── 📁 logs/                  # Application logs
└── 📁 pg_log/               # PostgreSQL logs
```

## 🔧 Key Components

### Core Services (Protocol-based Architecture)
- **ICurrencyService** - Currency conversion (G ↔ PLN)
- **IActivityTrackingService** - User activity tracking
- **IPremiumService** - Premium features management
- **IRoleService** - Role management
- **ITeamManagementService** - Team operations

### Command Modules (Cogs)
- **info/** - User information commands
- **mod/** - Moderation commands
- **premium/** - Premium features
- **voice/** - Voice channel management
- **team/** - Team management
- **ranking.py** - Activity ranking

### Event Handlers
- **bump/** - Server bump tracking
- **member_join/** - Welcome system
- **on_message.py** - Message tracking
- **on_payment.py** - Payment processing
- **on_voice_state_update.py** - Voice activity

## 🚀 Getting Started

1. **Setup Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your tokens
   ```

2. **Start Services**
   ```bash
   docker-compose up -d
   ```

3. **Run Tests**
   ```bash
   python -m pytest tests/
   ```

4. **Debug Commands**
   ```bash
   python scripts/testing/bot_command_tester.py <command>
   ```

## 📚 Documentation

- **Architecture**: See `docs/architecture/MODULAR_ARCHITECTURE_DESIGN.md`
- **Refactoring**: See `docs/refactoring/REFACTORING_PLAN.md`
- **Testing**: See `tests/mcp/README.md`
- **Scripts**: See `scripts/README.md`

## 🔄 Migration Status

Currently migrating from:
- ❌ Utils → ✅ Services (Protocol-based)
- ❌ Queries → ✅ Repositories (Repository pattern)
- ❌ Managers → ✅ Services (Dependency injection)

## 🛠️ Development

### Adding New Features
1. Define interface in `core/interfaces/`
2. Implement service in `core/services/`
3. Create repository in `core/repositories/`
4. Add commands in `cogs/commands/`
5. Write tests in `tests/`

### Testing
- Unit tests: `pytest tests/unit/`
- Integration tests: `pytest tests/integration/`
- MCP tests: `python tests/mcp/utils/test_commands_mcp.py`

### Debugging
- Interactive debug: `python scripts/debug/debug_interface.py`
- Command testing: `python scripts/testing/bot_command_tester.py`
- Docker logs: `docker-compose logs -f app`