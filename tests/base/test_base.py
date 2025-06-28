"""
Base test class for Discord bot testing.
"""

import asyncio
import os
import sys
import unittest
from typing import Any, Dict, Optional

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))



class BaseDiscordTest(unittest.TestCase):
    """Base class for Discord bot tests."""

    @classmethod
    def setUpClass(cls):
        """Set up test class."""
        cls.client = None
        cls.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cls.loop)

    @classmethod
    def tearDownClass(cls):
        """Tear down test class."""
        if cls.client:
            cls.loop.run_until_complete(cls.client.close())
        cls.loop.close()

    def run_async(self, coro):
        """Run an async coroutine in the test."""
        return self.loop.run_until_complete(coro)


class CommandTestCase(BaseDiscordTest):
    """Base class for command testing."""

    def setUp(self):
        """Set up each test."""
        from tests.utils.client import TestClient
        self.client = TestClient()

        # Check bot connection
        status = self.run_async(self.client.check_status())
        if "error" in status:
            self.skipTest(f"Bot not connected: {status['error']}")

    def tearDown(self):
        """Clean up after each test."""
        if hasattr(self, 'client') and self.client:
            self.run_async(self.client.close())

    async def execute_command(self, command: str, args: str = "",
                            send_to_channel: bool = False) -> Dict[str, Any]:
        """Execute a command and return result."""
        return await self.client.execute_command(command, args, send_to_channel)

    def assert_command_success(self, result: Dict[str, Any],
                             expected_content: Optional[str] = None):
        """Assert that a command executed successfully."""
        self.assertTrue(result.get("success"),
                       f"Command failed: {result.get('error', 'Unknown error')}")

        if expected_content:
            responses = result.get("responses", [])
            self.assertTrue(responses, "No responses received")

            # Check if expected content is in any response
            found = False
            for response in responses:
                if isinstance(response, dict):
                    # Check embeds
                    embeds = response.get("embeds", [])
                    for embed in embeds:
                        desc = embed.get("description", "")
                        if expected_content in desc:
                            found = True
                            break

                    # Check content
                    content = response.get("content") or ""
                    if expected_content in content:
                        found = True

                elif isinstance(response, str) and expected_content in response:
                    found = True

                if found:
                    break

            self.assertTrue(found,
                          f"Expected content '{expected_content}' not found in responses")

    def assert_embed_field(self, result: Dict[str, Any], field_name: str,
                          expected_value: Optional[str] = None):
        """Assert that an embed contains a specific field."""
        responses = result.get("responses", [])
        self.assertTrue(responses, "No responses received")

        found = False
        for response in responses:
            if isinstance(response, dict):
                embeds = response.get("embeds", [])
                for embed in embeds:
                    fields = embed.get("fields", [])
                    for field in fields:
                        if field.get("name") == field_name:
                            found = True
                            if expected_value:
                                self.assertEqual(field.get("value"), expected_value)
                            break

        self.assertTrue(found, f"Field '{field_name}' not found in embed")

    def assert_embed_color(self, result: Dict[str, Any], expected_color: int):
        """Assert that an embed has a specific color."""
        responses = result.get("responses", [])
        self.assertTrue(responses, "No responses received")

        response = responses[0]
        if isinstance(response, dict):
            embeds = response.get("embeds", [])
            self.assertTrue(embeds, "No embeds in response")

            color = embeds[0].get("color")
            self.assertEqual(color, expected_color,
                           f"Expected color {expected_color}, got {color}")
