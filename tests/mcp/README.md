# MCP Testing Suite

This directory contains all Model Context Protocol (MCP) test utilities for the zaGadka Discord bot.

## Directory Structure

```
tests/mcp/
├── README.md           # This file
├── bump/              # Bump command tests
├── premium/           # Premium features tests  
├── commands/          # General command tests
└── utils/            # MCP utilities and clients
```

## Core MCP Components

### MCP Server (`mcp_bot_server.py`)
The main MCP server that provides Discord bot functionality as tools for Claude.

### MCP Client (`mcp_client.py`)
Interactive client for testing Discord commands through MCP.

### Test Command Script (`test_commands_mcp.py`)
Utility script for testing specific commands via the bot's HTTP API.

## How to Use

### 1. Start the Bot with Docker
```bash
docker-compose up -d
```

### 2. Test Commands via MCP Client
```bash
python tests/mcp/utils/mcp_client.py

# In interactive mode:
mcp> exec ranking
mcp> exec stats
mcp> exec bump
```

### 3. Test Specific Commands
```bash
# Test single command
python tests/mcp/utils/test_commands_mcp.py ranking

# Test all ranking commands
python tests/mcp/utils/test_commands_mcp.py
```

### 4. Test Bump Functionality
```bash
# Test bump status display
python tests/mcp/bump/test_bump_mcp.py
```

## Command Testing Examples

### Testing Ranking Commands
```python
# From test_commands_mcp.py
commands = [
    ("ranking", ""),      # Show server ranking
    ("stats", ""),        # Show user stats
    ("my_rank", ""),      # Show my rank
    ("top", "100"),       # Show top 100
]
```

### Testing Voice Commands
```python
commands = [
    ("vc", ""),           # Show voice channel info
    ("limit", "5"),       # Set channel limit
    ("voicechat", ""),    # Get channel link
]
```

### Testing Premium Commands
```python
commands = [
    ("shop", ""),         # Show premium shop
    ("profile", ""),      # Show user profile
    ("check_balance", ""), # Check G balance
]
```

## API Endpoints

The bot exposes these endpoints for testing:

- `POST http://localhost:8090/execute` - Execute Discord commands
  ```json
  {
    "command": "ranking",
    "args": ""
  }
  ```

- `GET http://localhost:8090/status` - Check bot status

## Common Issues

1. **Connection Refused**
   - Ensure Docker containers are running
   - Check if port 8090 is mapped correctly
   - Wait 10 seconds after starting containers

2. **Token Authentication**
   - Ensure ZAGADKA_TOKEN is not set as system env variable
   - Token should come from .env file only

3. **Command Not Found**
   - Check if the cog is loaded properly
   - Verify command aliases are correct

## Adding New Tests

1. Create test file in appropriate subdirectory
2. Import necessary utilities:
   ```python
   import asyncio
   import aiohttp
   
   async def test_command(command, args=""):
       async with aiohttp.ClientSession() as session:
           async with session.post('http://localhost:8090/execute', 
                                 json={'command': command, 'args': args}) as resp:
               result = await resp.json()
               return result
   ```

3. Add test cases and run with asyncio

## Cleanup

Old test files have been moved here and organized. Original locations were in the project root directory.