"""Tests for the VoiceCog."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from discord.ext import commands

from ..cogs.commands.voice import VoiceCog
from .utils import get_command


@pytest.fixture
def voice_cog(bot) -> VoiceCog:
    """Fixture for the VoiceCog"""
    return VoiceCog(bot)


@pytest.mark.asyncio
async def test_join_command(
    voice_cog: VoiceCog, ctx: commands.Context
):  # pylint: disable=redefined-outer-name
    """Test the join command."""
    join_command = get_command(voice_cog, "join")

    # Test when the user is not in a voice channel
    ctx.author.voice = None
    await join_command.callback(voice_cog, ctx)
    ctx.send.assert_called_once_with("Nie jesteś na żadnym kanale głosowym!")
    ctx.send.reset_mock()

    # Test when the user is in a voice channel
    voice_channel = MagicMock()
    voice_channel.connect = AsyncMock()  # Use AsyncMock for connect()
    ctx.author.voice = MagicMock(channel=voice_channel)
    ctx.voice_client = None
    await join_command.callback(voice_cog, ctx)
    voice_channel.connect.assert_called_once()


@pytest.mark.asyncio
async def test_leave_command(
    voice_cog: VoiceCog, ctx: commands.Context
):  # pylint: disable=redefined-outer-name
    """Test the leave command."""
    leave_command = get_command(voice_cog, "leave")

    # Test when the bot is not in a voice channel
    ctx.voice_client = None
    await leave_command.callback(voice_cog, ctx)
    ctx.send.assert_called_once_with("Nie jestem na żadnym kanale głosowym!")
    ctx.send.reset_mock()

    # Test when the bot is in a voice channel
    ctx.voice_client = MagicMock()
    ctx.voice_client.disconnect = AsyncMock()  # Use AsyncMock for disconnect()
    await leave_command.callback(voice_cog, ctx)
    ctx.voice_client.disconnect.assert_called_once()
