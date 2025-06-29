"""Tests for refactored bump event module."""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from discord.ext import commands

from cogs.events.bump.bump_event import OnBumpEvent
from cogs.events.bump.constants import BYPASS_DURATIONS, SERVICE_COOLDOWNS
from cogs.events.bump.handlers import DisboardHandler, DzikHandler


class TestBumpHandlers:
    """Test bump handlers."""

    @pytest.fixture
    def mock_bot(self):
        """Create a mock bot."""
        bot = MagicMock(spec=commands.Bot)
        bot.get_db = AsyncMock()
        bot.config = {
            "channels": {"lounge": 123456789},
        }
        return bot

    @pytest.fixture
    def mock_message_sender(self):
        """Create a mock message sender."""
        sender = MagicMock()
        sender.create_embed = MagicMock(return_value=discord.Embed())
        return sender

    @pytest.mark.asyncio
    async def test_disboard_handler_adds_bypass_time(self, mock_bot, mock_message_sender):
        """Test that Disboard handler adds bypass time correctly."""
        handler = DisboardHandler(mock_bot, mock_message_sender)

        # Mock member
        member = MagicMock()
        member.voice_bypass_until = None
        member.bump_count = 0

        # Test adding bypass time
        await handler.add_bypass_time(member, BYPASS_DURATIONS["disboard"], "disboard")

        # Check that bypass expiry was set
        assert member.voice_bypass_until is not None
        assert isinstance(member.voice_bypass_until, datetime)

    @pytest.mark.asyncio
    async def test_cooldown_check(self, mock_bot, mock_message_sender):
        """Test cooldown checking."""
        handler = DzikHandler(mock_bot, mock_message_sender)

        # Mock session and notification queries
        mock_session = MagicMock()

        with patch("cogs.events.bump.handlers.NotificationLogQueries") as mock_queries:
            # Test no previous notification (not on cooldown)
            mock_queries.get_last_notification.return_value = None
            is_on_cooldown = await handler.check_cooldown(mock_session, 123456, "dzik", SERVICE_COOLDOWNS["dzik"])
            assert not is_on_cooldown

            # Test recent notification (on cooldown)
            mock_notification = MagicMock()
            mock_notification.timestamp = datetime.now(timezone.utc) - timedelta(hours=1)
            mock_queries.get_last_notification.return_value = mock_notification

            is_on_cooldown = await handler.check_cooldown(mock_session, 123456, "dzik", SERVICE_COOLDOWNS["dzik"])
            assert is_on_cooldown  # Should be on cooldown (3 hour cooldown, only 1 hour passed)


class TestBumpEvent:
    """Test main bump event handler."""

    @pytest.fixture
    def bump_event(self, mock_bot):
        """Create bump event instance."""
        bot = MagicMock(spec=commands.Bot)
        bot.config = {}
        return OnBumpEvent(bot)

    @pytest.mark.asyncio
    async def test_handle_slash_command_disboard(self, bump_event):
        """Test handling Disboard slash command."""
        # Create mock message with interaction
        message = MagicMock(spec=discord.Message)
        message.author.id = 302050872383242240  # Disboard ID
        message.interaction = MagicMock()
        message.interaction.name = "bump"
        message.interaction.user = MagicMock(spec=discord.Member)

        # Mock the handler
        bump_event.disboard_handler.handle = AsyncMock()

        # Test handling
        result = await bump_event.handle_slash_command(message)

        assert result is True
        bump_event.disboard_handler.handle.assert_called_once_with(message)

    @pytest.mark.asyncio
    async def test_marketing_message(self, bump_event):
        """Test marketing message generation."""
        # Create mock channel and user
        channel = MagicMock(spec=discord.TextChannel)
        channel.send = AsyncMock()

        user = MagicMock(spec=discord.Member)
        user.name = "TestUser"

        # Test marketing message
        await bump_event.send_bump_marketing(channel, "disboard", user)

        # Check that message was sent
        channel.send.assert_called_once()

        # Check embed content
        call_args = channel.send.call_args
        embed = call_args.kwargs.get("embed")
        assert embed is not None
        assert "Chcesz więcej nagród?" in embed.description
