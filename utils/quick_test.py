"""Quick testing framework for Discord bot commands."""

import asyncio
import logging
from typing import Any, Dict, Optional, List
from unittest.mock import MagicMock, AsyncMock
import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class QuickTestContext:
    """Mock context for quick command testing."""
    
    def __init__(self, bot, command_name: str, **kwargs):
        self.bot = bot
        self.command = MagicMock(name=command_name)
        self.author = MagicMock(
            id=kwargs.get('author_id', 123456789),
            name=kwargs.get('author_name', 'TestUser'),
            mention='<@123456789>'
        )
        self.guild = MagicMock(
            id=kwargs.get('guild_id', 987654321),
            name=kwargs.get('guild_name', 'TestGuild')
        )
        self.channel = MagicMock(
            id=kwargs.get('channel_id', 111111111),
            name=kwargs.get('channel_name', 'test-channel')
        )
        self.message = MagicMock()
        self.interaction = None
        self.responses = []
        
        # Mock send method
        self.send = AsyncMock(side_effect=self._capture_send)
        self.reply = AsyncMock(side_effect=self._capture_reply)
        
    async def _capture_send(self, content=None, embed=None, **kwargs):
        """Capture sent messages."""
        self.responses.append({
            'type': 'send',
            'content': content,
            'embed': embed,
            'kwargs': kwargs
        })
        return MagicMock()
        
    async def _capture_reply(self, content=None, embed=None, **kwargs):
        """Capture replies."""
        self.responses.append({
            'type': 'reply',
            'content': content,
            'embed': embed,
            'kwargs': kwargs
        })
        return MagicMock()


class QuickTester:
    """Quick testing utility for bot commands."""
    
    def __init__(self, bot):
        self.bot = bot
        self.results = []
        
    async def test_command(self, command_path: str, *args, **context_kwargs) -> Dict[str, Any]:
        """Test a command quickly without full environment."""
        try:
            # Get the command
            parts = command_path.split('.')
            command = self.bot.get_command(parts[-1])
            
            if not command:
                return {
                    'success': False,
                    'error': f'Command {command_path} not found'
                }
            
            # Create mock context
            ctx = QuickTestContext(self.bot, command.name, **context_kwargs)
            
            # Run command
            await command.callback(command.cog, ctx, *args)
            
            return {
                'success': True,
                'responses': ctx.responses,
                'command': command.name
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'type': type(e).__name__
            }
    
    async def test_multiple(self, tests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run multiple tests concurrently."""
        tasks = []
        for test in tests:
            task = self.test_command(
                test['command'],
                *test.get('args', []),
                **test.get('context', {})
            )
            tasks.append(task)
        
        return await asyncio.gather(*tasks)


async def quick_test(bot, command: str, *args, **kwargs):
    """Quick test a single command."""
    tester = QuickTester(bot)
    result = await tester.test_command(command, *args, **kwargs)
    
    if result['success']:
        logger.info(f"✅ {command} - Success")
        for resp in result.get('responses', []):
            logger.info(f"  → {resp['type']}: {resp.get('content', 'embed')}")
    else:
        logger.error(f"❌ {command} - {result['error']}")
    
    return result