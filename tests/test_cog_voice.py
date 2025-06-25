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
    # Bot teraz wysyła embed zamiast prostego tekstu
    ctx.reply.assert_called_once()
    assert 'embed' in ctx.reply.call_args.kwargs
    ctx.send.reset_mock()
    ctx.reply.reset_mock()

    # Test when the user is in a voice channel
    voice_channel = MagicMock()
    voice_channel.edit = AsyncMock()
    ctx.author.voice = MagicMock(channel=voice_channel)

    # Test when max_members is 0 (should be converted to 1)
    await limit_command.callback(voice_cog, ctx, 0)
    voice_channel.edit.assert_called_once_with(user_limit=1)  # 0 -> 1
    ctx.reply.assert_called_once()
    assert 'embed' in ctx.reply.call_args.kwargs
    ctx.reply.reset_mock()
    voice_channel.edit.reset_mock()

    # Test when max_members is within the valid range (1 to 99)
    max_members = 5
    await limit_command.callback(voice_cog, ctx, max_members)
    voice_channel.edit.assert_called_once_with(user_limit=max_members)
    # Bot teraz wysyła embed zamiast prostego tekstu
    ctx.reply.assert_called_once()
    assert 'embed' in ctx.reply.call_args.kwargs
