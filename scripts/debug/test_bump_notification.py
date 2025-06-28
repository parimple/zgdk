#!/usr/bin/env python3
"""Test script to simulate DISBOARD bump message"""

import asyncio
import logging
import sys
from datetime import datetime, timezone

import discord
from discord.ext import commands

# Add project root to path
sys.path.append("/home/ubuntu/Projects/zgdk")

from cogs.events.bump.bump_event import OnBumpEvent
from cogs.events.bump.constants import DISBOARD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FakeBot(commands.Bot):
    """Fake bot for testing"""

    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix=",", intents=intents)
        self.guild_id = 960665311701528596  # From config

    async def get_db(self):
        """Mock database session"""
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_session():
            yield None

        return mock_session()


async def test_disboard_bump():
    """Test DISBOARD bump detection"""
    bot = FakeBot()

    # Create bump cog
    bump_cog = OnBumpEvent(bot)

    # Create mock objects
    guild = discord.Object(id=960665311701528596)
    user = discord.Object(id=123456789)  # Test user
    user.display_name = "TestUser"
    user.display_avatar = None
    user.name = "TestUser"
    user.id = 123456789

    channel = discord.Object(id=1326322441383051385)  # Bump channel
    channel.name = "bump"
    channel.guild = guild

    # Create mock DISBOARD message
    message = discord.Object(id=999999999)
    message.guild = guild
    message.channel = channel
    message.author = discord.Object(id=DISBOARD["id"])
    message.author.bot = True
    message.author.name = "DISBOARD"
    message.author.id = DISBOARD["id"]
    message.content = ""
    message.webhook_id = None

    # Create embed similar to DISBOARD's
    embed = discord.Embed(
        title="Server Bumped!",
        description=f"<@{user.id}>, Bump done :thumbsup:\nCheck it on DISBOARD: https://disboard.org/",
        color=discord.Color.green(),
    )
    message.embeds = [embed]

    # Create interaction
    class FakeInteraction:
        def __init__(self, user):
            self.user = user
            self.name = "bump"

    message.interaction = FakeInteraction(user)

    # Test message handling
    logger.info("Testing DISBOARD bump message handling...")
    try:
        await bump_cog.on_message(message)
        logger.info("Message handling completed")
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(test_disboard_bump())
