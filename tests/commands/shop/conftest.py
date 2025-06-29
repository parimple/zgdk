"""
Shop command test fixtures with proper Discord mocking
"""
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

# Mock discord completely before any imports
discord_mock = MagicMock()
discord_mock.ui = MagicMock()
discord_mock.ui.View = MagicMock()
discord_mock.ui.Button = MagicMock()
discord_mock.ui.Select = MagicMock()
discord_mock.ext = MagicMock()
# Note: discord.ext.commands now stubbed per-test for flexibility
# Removed: discord_mock.ext.commands = MagicMock() to allow per-test stubbing
discord_mock.Member = MagicMock()
discord_mock.User = MagicMock()
discord_mock.Guild = MagicMock()
discord_mock.Role = MagicMock()
discord_mock.Embed = MagicMock()
discord_mock.utils = MagicMock()
discord_mock.utils.format_dt = MagicMock()
discord_mock.Forbidden = Exception
sys.modules["discord"] = discord_mock
sys.modules["discord.ui"] = discord_mock.ui
sys.modules["discord.ext"] = discord_mock.ext
# Note: discord.ext.commands now stubbed per-test for flexibility

# Mock the permission decorators
permissions_mock = MagicMock()


def is_zagadka_owner():
    def decorator(func):
        return func

    return decorator


def is_admin():
    def decorator(func):
        return func

    return decorator


permissions_mock.is_zagadka_owner = is_zagadka_owner
permissions_mock.is_admin = is_admin
sys.modules["utils.permissions"] = permissions_mock

from tests.data.test_constants import (
    BOT_CONFIG,
    GUILD_ID,
    TEST_CHANNEL_ID,
    TEST_USER_1_ID,
    WALLET_BALANCES,
)


@pytest.fixture
def mock_bot():
    """Create properly configured bot mock"""
    bot = MagicMock()
    bot.config = BOT_CONFIG
    bot.get_db = AsyncMock()
    bot.get_service = AsyncMock()
    return bot


@pytest.fixture
def mock_session():
    """Create database session mock"""
    return AsyncMock()


@pytest.fixture
def mock_ctx():
    """Create command context mock"""
    ctx = MagicMock()
    ctx.author = MagicMock()
    ctx.author.id = TEST_USER_1_ID
    ctx.author.display_name = "TestUser"
    ctx.author.mention = f"<@{TEST_USER_1_ID}>"
    ctx.reply = AsyncMock()
    ctx.send = AsyncMock()
    ctx.guild = MagicMock()
    ctx.guild.id = GUILD_ID
    ctx.channel = MagicMock()
    ctx.channel.id = TEST_CHANNEL_ID
    return ctx


@pytest.fixture
def mock_user():
    """Create user mock"""
    user = MagicMock()
    user.id = TEST_USER_1_ID
    user.mention = f"<@{TEST_USER_1_ID}>"
    user.display_name = "TestUser"
    user.send = AsyncMock()
    return user


@pytest.fixture
def mock_member_service():
    """Create member service mock"""
    service = AsyncMock()

    # Mock database member
    db_member = MagicMock()
    db_member.wallet_balance = WALLET_BALANCES["medium"]
    db_member.id = TEST_USER_1_ID

    service.get_or_create_member.return_value = db_member
    service.update_member_info = AsyncMock()

    return service


@pytest.fixture
def mock_premium_service():
    """Create premium service mock"""
    service = AsyncMock()
    service.get_member_premium_roles.return_value = []
    service.has_premium_role.return_value = False
    service.extend_premium_role = AsyncMock()
    service.set_guild = MagicMock()
    return service
