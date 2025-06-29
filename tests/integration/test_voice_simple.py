"""Simple test to verify test setup works."""

from unittest.mock import AsyncMock, MagicMock

import discord
import pytest


@pytest.mark.asyncio
async def test_simple_voice():
    """Simple test to verify basic functionality."""
    # Create mock bot
    bot = MagicMock()
    bot.config = {"premium_roles": [], "mute_roles": []}

    # Create mock guild
    guild = MagicMock(spec=discord.Guild)
    guild.id = 960665311701528596
    guild.name = "Test Guild"

    # Create mock member
    member = MagicMock(spec=discord.Member)
    member.id = 123456789
    member.name = "TestUser"
    member.mention = f"<@{member.id}>"

    # Create mock voice channel
    voice_channel = MagicMock(spec=discord.VoiceChannel)
    voice_channel.id = 12345
    voice_channel.name = "Test Voice"
    voice_channel.overwrites = {}

    # Test permission setting
    perms = discord.PermissionOverwrite(speak=False)
    voice_channel.overwrites[member] = perms

    # Verify permission was set
    assert member in voice_channel.overwrites
    assert voice_channel.overwrites[member].speak is False

    print("✅ Simple voice test passed!")


@pytest.mark.asyncio
async def test_mock_cog():
    """Test mock cog functionality."""
    from cogs.commands.voice import VoiceCog

    # Create mock bot
    bot = MagicMock()
    bot.config = {"premium_roles": [], "mute_roles": [], "team": {}, "channels_voice": {"afk": 12345}}
    bot.get_db = MagicMock()
    bot.get_service = AsyncMock()

    # Try to create cog (this will test imports)
    try:
        cog = VoiceCog(bot)
        print("✅ Voice cog created successfully!")
    except Exception as e:
        print(f"❌ Failed to create voice cog: {e}")
        raise
