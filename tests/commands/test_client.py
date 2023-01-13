" test functions for client.py cog"
import pytest
import discord.ext.test as dpytest 

from ...cogs.commands import client

class TestClient:

    @staticmethod
    def test_add_numbers():
        assert client.add_numbers(1, 2, 3) == 6, "Should be 6"

    @staticmethod
    def test_add_numbers2():
        assert client.add_numbers(1, 2, 5) == 8, "Should be 8"

    @staticmethod
    def test_add_numbers3():
        assert client.add_numbers(1, 2, 10) == 13, "Should be 13"

    @staticmethod
    @pytest.mark.asyncio
    async def test_ping(bot):
        await dpytest.message("!ping")
        assert dpytest.verify().message().content("pong")
    