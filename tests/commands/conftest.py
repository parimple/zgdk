import pytest
import pytest_asyncio
import discord.ext.test as dpytest

from ...main import Zagadka
from ... import cogs

@pytest_asyncio.fixture()
async def bot():
    b = Zagadka(test=True)
    await b._async_setup_hook()  # setup the loop
    await b.add_cog(cogs.commands.client.CommandsClient(b))
    dpytest.configure(b)
    return b

@pytest_asyncio.fixture()
async def cleanup():
    yield
    await dpytest.empty_queue()
