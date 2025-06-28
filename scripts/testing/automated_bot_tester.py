#!/usr/bin/env python3
"""
Automated bot testing utility for development.
Tests commands by connecting to the running bot via Discord API.
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

import discord
import aiohttp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class AutomatedBotTester:
    """Test bot commands automatically without manual intervention."""
    
    def __init__(self, bot_token: str, test_channel_id: int):
        """
        Initialize the tester.
        
        Args:
            bot_token: Bot token for authentication
            test_channel_id: Channel ID where tests will be run
        """
        self.bot_token = bot_token
        self.test_channel_id = test_channel_id
        self.base_url = "https://discord.com/api/v10"
        self.headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json"
        }
        self.session = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    async def send_command(self, command: str) -> Dict[str, Any]:
        """
        Send a command to the test channel.
        
        Args:
            command: Command string (e.g., "!profile")
            
        Returns:
            Response data from Discord API
        """
        url = f"{self.base_url}/channels/{self.test_channel_id}/messages"
        payload = {"content": command}
        
        async with self.session.post(url, headers=self.headers, json=payload) as response:
            if response.status == 200:
                return await response.json()
            else:
                error = await response.text()
                logger.error(f"Failed to send command: {error}")
                return {"error": error, "status": response.status}
                
    async def get_bot_response(self, after_message_id: str, timeout: int = 5) -> List[Dict[str, Any]]:
        """
        Get bot responses after sending a command.
        
        Args:
            after_message_id: Message ID to get responses after
            timeout: Max seconds to wait for response
            
        Returns:
            List of bot response messages
        """
        url = f"{self.base_url}/channels/{self.test_channel_id}/messages"
        params = {"after": after_message_id, "limit": 10}
        
        start_time = asyncio.get_event_loop().time()
        responses = []
        
        while asyncio.get_event_loop().time() - start_time < timeout:
            async with self.session.get(url, headers=self.headers, params=params) as response:
                if response.status == 200:
                    messages = await response.json()
                    # Filter for bot messages
                    bot_messages = [
                        msg for msg in messages 
                        if msg.get("author", {}).get("bot", False)
                    ]
                    if bot_messages:
                        responses.extend(bot_messages)
                        break
                        
            await asyncio.sleep(0.5)
            
        return responses
        
    async def test_command(self, command: str, expected_patterns: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Test a single command and verify response.
        
        Args:
            command: Command to test (e.g., "!profile")
            expected_patterns: Optional list of patterns to check in response
            
        Returns:
            Test result dictionary
        """
        logger.info(f"Testing command: {command}")
        
        # Send command
        sent_message = await self.send_command(command)
        if "error" in sent_message:
            return {
                "command": command,
                "success": False,
                "error": sent_message["error"],
                "responses": []
            }
            
        # Get bot response
        await asyncio.sleep(1)  # Give bot time to process
        responses = await self.get_bot_response(sent_message["id"])
        
        # Analyze responses
        result = {
            "command": command,
            "success": len(responses) > 0,
            "responses": responses,
            "embeds": [],
            "components": [],
            "patterns_found": []
        }
        
        for response in responses:
            # Extract embeds
            if "embeds" in response:
                result["embeds"].extend(response["embeds"])
                
            # Extract components (buttons, selects, etc.)
            if "components" in response:
                result["components"].extend(response["components"])
                
            # Check patterns if provided
            if expected_patterns:
                content = response.get("content", "")
                embed_content = " ".join([
                    embed.get("title", "") + " " + embed.get("description", "")
                    for embed in response.get("embeds", [])
                ])
                full_content = content + " " + embed_content
                
                for pattern in expected_patterns:
                    if pattern.lower() in full_content.lower():
                        result["patterns_found"].append(pattern)
                        
        # Determine success based on patterns if provided
        if expected_patterns:
            result["success"] = len(result["patterns_found"]) > 0
            
        return result
        
    def format_test_result(self, result: Dict[str, Any]) -> str:
        """Format test result for display."""
        lines = []
        lines.append(f"Command: {result['command']}")
        lines.append(f"Success: {'✅' if result['success'] else '❌'}")
        
        if "error" in result:
            lines.append(f"Error: {result['error']}")
            
        if result['responses']:
            lines.append(f"Responses: {len(result['responses'])}")
            
        if result['embeds']:
            lines.append(f"Embeds: {len(result['embeds'])}")
            for embed in result['embeds']:
                if "title" in embed:
                    lines.append(f"  - {embed['title']}")
                    
        if result['components']:
            lines.append(f"Components: {len(result['components'])}")
            
        if result.get('patterns_found'):
            lines.append(f"Patterns found: {', '.join(result['patterns_found'])}")
            
        return "\n".join(lines)
        

class TestSuite:
    """Collection of automated tests for bot commands."""
    
    def __init__(self, tester: AutomatedBotTester):
        self.tester = tester
        self.results = []
        
    async def test_profile_command(self):
        """Test profile command."""
        result = await self.tester.test_command(
            "!profile",
            expected_patterns=["Profil użytkownika", "Portfel", "Zaproszenia"]
        )
        self.results.append(("Profile Command", result))
        
    async def test_shop_command(self):
        """Test shop command."""
        result = await self.tester.test_command(
            "!shop",
            expected_patterns=["Sklep", "Premium", "zG"]
        )
        self.results.append(("Shop Command", result))
        
    async def test_help_command(self):
        """Test help command."""
        result = await self.tester.test_command(
            "!help",
            expected_patterns=["Komendy", "pomoc", "help"]
        )
        self.results.append(("Help Command", result))
        
    async def run_all_tests(self):
        """Run all tests in the suite."""
        logger.info("Starting automated test suite...")
        
        await self.test_profile_command()
        await asyncio.sleep(1)
        
        await self.test_shop_command()
        await asyncio.sleep(1)
        
        await self.test_help_command()
        
        # Print summary
        print("\n" + "=" * 60)
        print("TEST SUITE RESULTS")
        print("=" * 60)
        
        passed = 0
        failed = 0
        
        for test_name, result in self.results:
            print(f"\n{test_name}:")
            print("-" * 40)
            print(self.tester.format_test_result(result))
            
            if result["success"]:
                passed += 1
            else:
                failed += 1
                
        print("\n" + "=" * 60)
        print(f"SUMMARY: {passed} passed, {failed} failed")
        print("=" * 60)
        
        # Save results to file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_results_{timestamp}.json"
        with open(filename, "w") as f:
            json.dump([
                {"test": name, "result": result}
                for name, result in self.results
            ], f, indent=2)
        print(f"\nResults saved to: {filename}")
        

async def main():
    """Main function to run tests."""
    # Load bot token from environment or config
    bot_token = os.getenv("DISCORD_BOT_TOKEN")
    if not bot_token:
        # Try to load from config
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            from core.config import config
            bot_token = config["discord"]["token"]
        except:
            logger.error("Bot token not found in environment or config")
            return
            
    test_channel_id = 1387864734002446407
    
    async with AutomatedBotTester(bot_token, test_channel_id) as tester:
        suite = TestSuite(tester)
        await suite.run_all_tests()
        

if __name__ == "__main__":
    asyncio.run(main())