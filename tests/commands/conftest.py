"""Pytest fixtures for the commands cog."""

import discord.ext.test as dpytest
import pytest_asyncio

from ...cogs.commands.client import CommandsClient
from ...main import Zagadka


@pytest_asyncio.fixture()
async def bot():
    """Fixture for the bot."""
    test_bot = Zagadka(test=True)
    await test_bot._async_setup_hook()  # pylint: disable=protected-access
    await test_bot.add_cog(CommandsClient(test_bot))
    dpytest.configure(test_bot)
    return test_bot


@pytest_asyncio.fixture()
async def cleanup():
    """Fixture for cleaning up the bot."""
    yield
    await dpytest.empty_queue()
