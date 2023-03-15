"""Test functions for client.py cog"""
import discord.ext.test as dpytest
import pytest


class TestClient:  # pylint: disable=too-few-public-methods
    """Test functions for client.py cog"""

    @staticmethod
    @pytest.mark.asyncio
    async def test_ping(bot):  # pylint: disable=unused-argument
        """Test the ping command."""
        await dpytest.message("!ping")
        assert dpytest.verify().message().content("pong")
