#!/usr/bin/env python3
"""
Automated bot command tester for development.
This script allows testing bot commands programmatically without manual intervention.
"""

import asyncio
import logging
import os
import sys
from typing import Optional

import discord
from discord.ext import commands

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import config
from datasources.database import Database

logger = logging.getLogger(__name__)


class BotCommandTester:
    """Automated command tester for the Discord bot."""

    def __init__(self):
        self.config = config
        self.owner_id = 956602391891947592
        self.test_channel_id = 1387864734002446407
        self.guild_id = 960665311701528596
        self.bot = None
        self.db = None

    async def setup(self):
        """Initialize the tester with bot connection."""
        # Initialize database
        self.db = Database(self.config["database"]["url"])
        await self.db.create_tables()

        # Create minimal bot instance
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True

        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

        # Add necessary attributes
        self.bot.config = self.config
        self.bot.db = self.db
        self.bot.get_db = self.db.session

        # Add service getter
        async def get_service(interface, session):
            from core.service_container import ServiceContainer

            container = ServiceContainer(self.bot)
            return await container.get_service(interface, session)

        self.bot.get_service = get_service

        logger.info("Bot command tester initialized")

    async def simulate_command(self, command_string: str, channel_id: Optional[int] = None) -> dict:
        """
        Simulate a command execution and return results.

        Args:
            command_string: The command to execute (e.g., "profile", "shop")
            channel_id: Optional channel ID to execute in (defaults to test channel)

        Returns:
            dict with execution results
        """
        if not self.bot:
            await self.setup()

        result = {
            "success": False,
            "command": command_string,
            "response": None,
            "error": None,
            "embeds": [],
            "views": [],
        }

        try:
            # Get guild and channel
            guild = self.bot.get_guild(self.guild_id)
            if not guild:
                # Try to fetch if not in cache
                guild = await self.bot.fetch_guild(self.guild_id)

            channel = guild.get_channel(channel_id or self.test_channel_id)
            if not channel:
                channel = await guild.fetch_channel(channel_id or self.test_channel_id)

            # Get owner member
            owner = guild.get_member(self.owner_id)
            if not owner:
                owner = await guild.fetch_member(self.owner_id)

            # Create fake message
            class FakeMessage:
                def __init__(self, content, author, channel, guild):
                    self.content = content
                    self.author = author
                    self.channel = channel
                    self.guild = guild
                    self.id = 0
                    self._state = channel._state
                    self.type = discord.MessageType.default
                    self.webhook_id = None
                    self.mentions = []
                    self.mention_everyone = False
                    self.pinned = False
                    self.tts = False
                    self.embeds = []
                    self.attachments = []
                    self.stickers = []
                    self.reactions = []
                    self.reference = None
                    self.application = None
                    self.activity = None
                    self.created_at = discord.utils.utcnow()

                async def reply(self, content=None, **kwargs):
                    """Capture reply content."""
                    nonlocal result
                    if content:
                        result["response"] = content
                    if "embed" in kwargs:
                        result["embeds"].append(kwargs["embed"])
                    if "view" in kwargs:
                        result["views"].append(kwargs["view"])
                    return self

                async def send(self, content=None, **kwargs):
                    """Capture send content."""
                    return await self.reply(content, **kwargs)

            # Create message and context
            fake_msg = FakeMessage(content=f"!{command_string}", author=owner, channel=channel, guild=guild)

            # Monkey patch channel.send to capture output
            original_send = channel.send

            async def capture_send(content=None, **kwargs):
                if content:
                    result["response"] = content
                if "embed" in kwargs:
                    result["embeds"].append(kwargs["embed"])
                if "embeds" in kwargs:
                    result["embeds"].extend(kwargs["embeds"])
                if "view" in kwargs:
                    result["views"].append(kwargs["view"])
                return fake_msg

            channel.send = capture_send

            # Get context and invoke
            ctx = await self.bot.get_context(fake_msg)
            if ctx.valid:
                await self.bot.invoke(ctx)
                result["success"] = True
                logger.info(f"Successfully executed command: {command_string}")
            else:
                result["error"] = "Invalid command"
                logger.error(f"Invalid command: {command_string}")

            # Restore original send
            channel.send = original_send

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error executing command '{command_string}': {e}")

        return result

    async def test_profile_command(self, member_id: Optional[int] = None) -> dict:
        """Test the profile command."""
        command = "profile"
        if member_id:
            command += f" <@{member_id}>"
        return await self.simulate_command(command)

    async def test_shop_command(self) -> dict:
        """Test the shop command."""
        return await self.simulate_command("shop")

    async def test_help_command(self) -> dict:
        """Test the help command."""
        return await self.simulate_command("help")

    def format_result(self, result: dict) -> str:
        """Format test result for display."""
        output = []
        output.append(f"Command: !{result['command']}")
        output.append(f"Success: {result['success']}")

        if result["error"]:
            output.append(f"Error: {result['error']}")

        if result["response"]:
            output.append(f"Response: {result['response']}")

        if result["embeds"]:
            output.append(f"Embeds: {len(result['embeds'])}")
            for i, embed in enumerate(result["embeds"]):
                output.append(f"  Embed {i+1}: {embed.title}")
                if embed.description:
                    output.append(f"    Description: {embed.description[:100]}...")

        if result["views"]:
            output.append(f"Views: {len(result['views'])}")

        return "\n".join(output)


async def test_commands():
    """Run automated command tests."""
    tester = BotCommandTester()
    await tester.setup()

    print("=" * 60)
    print("BOT COMMAND AUTOMATED TESTING")
    print("=" * 60)

    # Test profile command
    print("\n1. Testing Profile Command:")
    print("-" * 40)
    result = await tester.test_profile_command()
    print(tester.format_result(result))

    # Test shop command
    print("\n2. Testing Shop Command:")
    print("-" * 40)
    result = await tester.test_shop_command()
    print(tester.format_result(result))

    # Test help command
    print("\n3. Testing Help Command:")
    print("-" * 40)
    result = await tester.test_help_command()
    print(tester.format_result(result))

    print("\n" + "=" * 60)
    print("TESTING COMPLETED")
    print("=" * 60)


# CLI interface for quick testing
async def test_single_command(command: str):
    """Test a single command from CLI."""
    tester = BotCommandTester()
    await tester.setup()

    result = await tester.simulate_command(command)
    print(tester.format_result(result))


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Test specific command from CLI
        command = " ".join(sys.argv[1:])
        asyncio.run(test_single_command(command))
    else:
        # Run full test suite
        asyncio.run(test_commands())
