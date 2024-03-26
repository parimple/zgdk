"""Tests for the VoiceCog."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord.ext import commands

from ..cogs.commands.voice import VoiceCog
from .utils import get_command


@pytest.fixture
def voice_cog(bot) -> VoiceCog:
    """Fixture for the VoiceCog"""
    bot.session = MagicMock()
    return VoiceCog(bot)


@pytest.mark.asyncio
async def test_limit_command(
    voice_cog: VoiceCog, ctx: commands.Context
):  # pylint: disable=redefined-outer-name
    """Test the limit command."""
    limit_command = get_command(voice_cog, "limit")

    # Test when the user is not in a voice channel
    ctx.author.voice = None
    await limit_command.callback(voice_cog, ctx, 5)
    ctx.reply.assert_called_once_with("Nie jesteś na żadnym kanale głosowym!")
    ctx.send.reset_mock()
    ctx.reply.reset_mock()  # Add this line to reset the reply mock

    # Test when the user is in a voice channel
    voice_channel = MagicMock()
    voice_channel.edit = AsyncMock()  # Use AsyncMock for edit()
    ctx.author.voice = MagicMock(channel=voice_channel)

    # Test when max_members is not within the valid range (1 to 99)
    await limit_command.callback(voice_cog, ctx, 0)
    ctx.reply.assert_called_once_with("Podaj liczbę członków od 1 do 99.")
    ctx.reply.reset_mock()  # Reset the reply mock before the final test case

    # Test when max_members is within the valid range (1 to 99)
    max_members = 5
    await limit_command.callback(voice_cog, ctx, max_members)
    voice_channel.edit.assert_called_once_with(user_limit=max_members)
    ctx.reply.assert_called_once_with(
        f"Limit członków na kanale {voice_channel} ustawiony na {max_members}."
    )
