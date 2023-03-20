"""Test functions for on_ready.py cog"""
import pytest

from ..cogs.events.on_ready import OnReadyEvent


class TestOnReadyEvent:  # pylint: disable=too-few-public-methods
    """Test functions for on_ready.py cog"""

    @staticmethod
    @pytest.mark.asyncio
    async def test_on_ready_cog_loaded(bot):
        """Test if the EventOnReady cog is loaded."""
        assert isinstance(bot.get_cog("OnReadyEvent"), OnReadyEvent)
