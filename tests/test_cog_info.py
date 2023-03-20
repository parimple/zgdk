"""Test functions for client.py cog"""
import discord.ext.test as dpytest
import pytest

from ..cogs.commands.info import InfoCog


class TestInfoCog:  # pylint: disable=too-few-public-methods
    """Test functions for client.py cog"""

    @staticmethod
    @pytest.mark.asyncio
    async def test_client_cog_loaded(bot):
        """Test if the InfoCog cog is loaded."""
        assert isinstance(bot.get_cog("InfoCog"), InfoCog)

    @staticmethod
    @pytest.mark.asyncio
    async def test_ping(bot):  # pylint: disable=unused-argument
        """Test the ping command."""
        await dpytest.message("!ping")
        assert dpytest.verify().message().contains().content("pong")
