"""
Test client wrapper for Discord bot testing.
"""

import asyncio
from typing import Any, Dict, Optional, Union
from unittest.mock import MagicMock

import aiohttp

from tests.config import API_BASE_URL, COMMAND_TIMEOUT, CONNECTION_TIMEOUT


class TestClient:
    """Wrapper around the MCP client for testing."""
    
    def __init__(self, bot=None, base_url: str = API_BASE_URL):
        """Initialize test client."""
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
        self.bot = bot  # For unit tests with mock bot
    
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def check_status(self) -> Dict[str, Any]:
        """Check bot connection status."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.get(
                f"{self.base_url}/status",
                timeout=aiohttp.ClientTimeout(total=CONNECTION_TIMEOUT)
            ) as response:
                return await response.json()
        except asyncio.TimeoutError:
            return {"error": "Connection timeout"}
        except Exception as e:
            return {"error": str(e)}
    
    async def execute_command(self, command: str, args: str = "", 
                            send_to_channel: bool = False) -> Dict[str, Any]:
        """Execute a Discord command."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        payload = {
            "command": command,
            "args": args,
            "send_to_channel": send_to_channel
        }
        
        try:
            async with self.session.post(
                f"{self.base_url}/execute",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=COMMAND_TIMEOUT)
            ) as response:
                return await response.json()
        except asyncio.TimeoutError:
            return {"success": False, "error": "Command timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_responses(self) -> Dict[str, Any]:
        """Get captured responses from last command."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.get(
                f"{self.base_url}/responses",
                timeout=aiohttp.ClientTimeout(total=CONNECTION_TIMEOUT)
            ) as response:
                return await response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def test_endpoint(self) -> Dict[str, Any]:
        """Test the API endpoint."""
        if not self.session:
            self.session = aiohttp.ClientSession()
        
        try:
            async with self.session.get(
                f"{self.base_url}/test",
                timeout=aiohttp.ClientTimeout(total=CONNECTION_TIMEOUT)
            ) as response:
                return await response.json()
        except Exception as e:
            return {"error": str(e)}
    
    async def close(self):
        """Close the client session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def run_command(self, command: str, args: str = "") -> Union[MagicMock, Dict[str, Any]]:
        """
        Run a command in unit test mode.
        This is a simplified version for unit tests that doesn't use the API.
        """
        if self.bot:
            # Unit test mode - return mock response
            response = MagicMock()
            response.content = f"Command {command} executed with args: {args}"
            response.title = "Test Response"
            response.description = f"Test response for {command}"
            response.footer = MagicMock()
            response.footer.text = "Test Footer"
            response.fields = []
            return response
        else:
            # API mode - use execute_command
            return await self.execute_command(command, args)