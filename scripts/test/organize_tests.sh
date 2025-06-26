#!/bin/bash
# Organize existing tests into proper structure

echo "🔧 Organizing tests into proper structure..."

# Create __init__.py files
echo "Creating __init__.py files..."
touch tests/unit/__init__.py
touch tests/e2e/__init__.py
touch tests/tools/__init__.py
touch tests/fixtures/__init__.py

# Extract unit tests from existing files
echo "Extracting unit tests..."
cat > tests/unit/test_permissions.py << 'EOF'
"""Unit tests for permission system."""
import pytest
from unittest.mock import Mock, MagicMock
from utils.permissions import check_permission_level, PermissionLevel


class TestPermissionSystem:
    """Test permission system functionality."""
    
    def test_owner_permission_with_owner_ids_list(self):
        """Test owner permission with owner_ids list."""
        # Mock bot and config
        bot = Mock()
        bot.config = {
            "owner_ids": [123456789, 987654321],
            "owner_id": 123456789
        }
        
        # Mock member
        member = Mock()
        member.id = 987654321
        
        # Test
        result = check_permission_level(bot, member, PermissionLevel.OWNER)
        assert result is True
    
    def test_non_owner_permission(self):
        """Test non-owner user."""
        bot = Mock()
        bot.config = {
            "owner_ids": [123456789],
            "owner_id": 123456789
        }
        
        member = Mock()
        member.id = 555555555  # Not in owner list
        
        result = check_permission_level(bot, member, PermissionLevel.OWNER)
        assert result is False
EOF

# Create E2E test structure
echo "Creating E2E test files..."
cat > tests/e2e/test_discord_commands.py << 'EOF'
"""End-to-end tests for Discord commands."""
import pytest
import asyncio
import os
from tests.tools.discord_tester import DiscordTester


@pytest.mark.e2e
@pytest.mark.discord
@pytest.mark.asyncio
async def test_addbalance_command():
    """Test addbalance command end-to-end."""
    token = os.getenv("CLAUDE_BOT_TOKEN")
    if not token:
        pytest.skip("Discord token not available")
    
    tester = DiscordTester(token)
    
    result = await tester.test_command(
        ",addbalance <@968632323916566579> 1000",
        expected_contains="Dodano 1000 do portfela"
    )
    
    assert result["status"] == "SUCCESS"
    assert "Dodano" in result["response"]


@pytest.mark.e2e
@pytest.mark.discord
@pytest.mark.asyncio
async def test_shop_command():
    """Test shop command end-to-end."""
    token = os.getenv("CLAUDE_BOT_TOKEN")
    if not token:
        pytest.skip("Discord token not available")
    
    tester = DiscordTester(token)
    
    result = await tester.test_command(
        ",shop",
        expected_contains="shop"  # Should show shop interface
    )
    
    assert result["status"] == "SUCCESS"
EOF

# Create testing tools
echo "Creating testing tools..."
cat > tests/tools/discord_tester.py << 'EOF'
"""Discord testing utilities."""
import discord
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional


class DiscordTester:
    """Utility for testing Discord bot commands."""
    
    def __init__(self, token: str, guild_id: int = 960665311701528596, 
                 channel_id: int = 1387864734002446407):
        self.token = token
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.client = None
    
    async def setup(self):
        """Setup Discord client."""
        intents = discord.Intents.default()
        intents.message_content = True
        intents.guilds = True
        self.client = discord.Client(intents=intents)
        
        @self.client.event
        async def on_ready():
            pass
            
        await self.client.start(self.token)
    
    async def test_command(self, command: str, expected_contains: str = None, 
                          timeout: int = 15) -> Dict[str, Any]:
        """Test a single Discord command."""
        if not self.client:
            await self.setup()
        
        guild = self.client.get_guild(self.guild_id)
        channel = guild.get_channel(self.channel_id)
        
        # Send command
        before_time = datetime.utcnow()
        message = await channel.send(command)
        
        # Wait for response
        responses = []
        for _ in range(timeout):
            await asyncio.sleep(1)
            
            async for msg in channel.history(limit=10, after=before_time):
                if msg.author.bot and msg != message and msg not in responses:
                    responses.append(msg)
        
        # Analyze result
        if responses:
            response_text = responses[0].content
            status = "SUCCESS"
            if expected_contains and expected_contains not in response_text:
                status = "PARTIAL"
        else:
            response_text = ""
            status = "NO_RESPONSE"
        
        return {
            "status": status,
            "command": command,
            "response": response_text,
            "timestamp": datetime.now().isoformat()
        }
    
    async def close(self):
        """Close Discord client."""
        if self.client:
            await self.client.close()
EOF

# Create test configuration
echo "Creating test configuration..."
cat > tests/pytest.ini << 'EOF'
[tool:pytest]
testpaths = .
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
markers =
    unit: Unit tests - fast, no external dependencies
    integration: Integration tests - database required
    e2e: End-to-end tests - full system
    slow: Slow tests
    discord: Tests requiring Discord API tokens
EOF

# Create gitignore for test results
echo "Creating gitignore for test results..."
cat > tests/results/.gitignore << 'EOF'
# Test results
*.json
*.xml
*.html
reports/
coverage/
.coverage
*.log

# Keep directory structure
!.gitignore
!reports/.gitkeep
EOF

touch tests/results/reports/.gitkeep

echo "✅ Test organization completed!"
echo ""
echo "📁 Created structure:"
echo "   tests/unit/test_permissions.py"
echo "   tests/e2e/test_discord_commands.py" 
echo "   tests/tools/discord_tester.py"
echo "   tests/pytest.ini"
echo "   tests/results/.gitignore"
echo ""
echo "🔧 Next steps:"
echo "   1. Run unit tests: pytest tests/unit/ -m unit"
echo "   2. Run integration tests: pytest tests/integration/ -m integration"
echo "   3. Run E2E tests: CLAUDE_BOT_TOKEN=xxx pytest tests/e2e/ -m e2e"