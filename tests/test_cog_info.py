"""Test functions for client.py cog"""
import pytest
from discord.ext import commands

from ..cogs.commands.info import InfoCog
from .utils import get_command


@pytest.fixture
def info_cog(bot: commands.Bot) -> InfoCog:  # pylint: disable=redefined-outer-name
    """Fixture for the InfoCog"""
    return InfoCog(bot)


@pytest.mark.asyncio
async def test_ping_command(
    info_cog: InfoCog, ctx: commands.Context
):  # pylint: disable=redefined-outer-name
    """Test the ping command."""
    ping_command = get_command(info_cog, "ping")
    await ping_command.callback(info_cog, ctx)

    ctx.send.assert_called_once_with("pong")
