"""Test functions for the voice.py cog"""

import discord.ext.test as dpytest
import pytest

from ..cogs.commands.voice import VoiceCog


class TestVoiceCog:
    """Test functions for voice.py cog"""

    @staticmethod
    @pytest.mark.asyncio
    async def test_voice_cog_loaded(bot):
        """Test if the VoiceCog cog is loaded."""
        assert isinstance(bot.get_cog("VoiceCog"), VoiceCog)

    @staticmethod
    @pytest.mark.asyncio
    async def test_join(bot):  # pylint: disable=unused-argument
        """Test the join command."""
        await dpytest.message("!join")
        assert (
            dpytest.verify()
            .message()
            .contains()
            .content("Nie jesteś na żadnym kanale głosowym!")
        )

    @staticmethod
    @pytest.mark.asyncio
    async def test_leave(bot):  # pylint: disable=unused-argument
        """Test the leave command."""
        await dpytest.message("!leave")
        assert (
            dpytest.verify()
            .message()
            .contains()
            .content("Nie jestem na żadnym kanale głosowym!")
        )
