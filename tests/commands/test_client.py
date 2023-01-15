" test functions for client.py cog"
import pytest
import discord.ext.test as dpytest 

class TestClient:

    @staticmethod
    @pytest.mark.asyncio
    async def test_ping(bot):
        await dpytest.message("!ping")
        assert dpytest.verify().message().content("pong")
    