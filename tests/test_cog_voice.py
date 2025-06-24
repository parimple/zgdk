"""Tests for the VoiceCog."""
from unittest.mock import AsyncMock, MagicMock, call

import discord

import pytest
from discord.ext import commands

from ..cogs.commands.voice import VoiceCog
from .utils import get_command


@pytest.fixture
def voice_cog(bot) -> VoiceCog:
    """Fixture for the VoiceCog"""
    bot.session = MagicMock()
    bot.config = {}
    return VoiceCog(bot)


@pytest.mark.asyncio
async def test_limit_command(
    voice_cog: VoiceCog, ctx: commands.Context
):  # pylint: disable=redefined-outer-name
    """Test the limit command."""
    limit_command = get_command(voice_cog, "limit")

    # Test when the user is not in a voice channel
    ctx.author.voice = None
    ctx.author.color = discord.Color.default()
    await limit_command.callback(voice_cog, ctx, 5)
    ctx.reply.assert_called_once()
    embed = ctx.reply.call_args.kwargs["embed"]
    assert "Nie jesteś na żadnym kanale głosowym!" in embed.description
    ctx.send.reset_mock()
    ctx.reply.reset_mock()  # Add this line to reset the reply mock

    # Test when the user is in a voice channel
    voice_channel = MagicMock()
    voice_channel.edit = AsyncMock()  # Use AsyncMock for edit()
    ctx.author.voice = MagicMock(channel=voice_channel)

    # Test when max_members is not within the valid range (1 to 99)
    await limit_command.callback(voice_cog, ctx, 0)
    ctx.reply.assert_called_once()
    embed = ctx.reply.call_args.kwargs["embed"]
    assert "Limit członków" in embed.description
    ctx.reply.reset_mock()  # Reset the reply mock before the final test case

    # Test when max_members is within the valid range (1 to 99)
    max_members = 5
    await limit_command.callback(voice_cog, ctx, max_members)
    assert voice_channel.edit.call_args_list[-1] == call(user_limit=max_members)
    ctx.reply.assert_called_once()
    embed = ctx.reply.call_args.kwargs["embed"]
    assert str(max_members) in embed.description
