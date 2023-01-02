import os
import pytest
from discord.ext import commands
import discord
import sys
import threading
import asyncio

sys.path.append("/Users/patrykpyzel/Projects/zgdk")

# Import your bot class
from main import Zagadka

import pytest

@pytest.fixture
def bot(mocker):
    mock_bot = mocker.Mock()
    mock_bot.get_command.return_value = mocker.Mock(spec=commands.Command, invoke=lambda ctx: ctx.send("pong"))
    mock_bot.on_ready = mocker.Mock()
    return mock_bot

@pytest.fixture
async def start_bot(bot):
    await bot.start(os.environ.get("DISCORD_TOKEN"))

@pytest.mark.asyncio
async def test_bot_ready(bot):
     # Start the bot in the main thread
    asyncio.run(start_bot(bot))

    # Wait for the bot to be ready, or for the bot to be closed (whichever comes first)
    await asyncio.wait_for(bot.wait_until_ready() or bot.is_closed(), timeout=10)

    # Ensure that the bot is in the "ready" state
    assert bot.is_ready() == True

    # Close the event loop
    asyncio.AbstractEventLoop.stop()

