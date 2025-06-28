<file name=tests/conftest.py>#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pytest fixtures and helpers for the bot tests.
"""

import pytest
import sys
from unittest.mock import MagicMock, AsyncMock

import discord
import discord.ext.commands

# Mock discord modules at the very top
import types

discord_mock = types.ModuleType("discord")
discord_mock.Member = MagicMock
discord_mock.User = MagicMock
discord_mock.Guild = MagicMock
discord_mock.TextChannel = MagicMock
discord_mock.VoiceChannel = MagicMock
discord_mock.Role = MagicMock
discord_mock.Message = MagicMock
discord_mock.Embed = MagicMock
discord_mock.AllowedMentions = MagicMock
discord_mock.File = MagicMock
discord_mock.Attachment = MagicMock
discord_mock.Interaction = MagicMock
discord_mock.SelectOption = MagicMock
discord_mock.ButtonStyle = MagicMock

discord_mock.Color = MagicMock()
discord_mock.Color.blue = MagicMock(return_value=MagicMock())
discord_mock.Color.green = MagicMock(return_value=MagicMock())
discord_mock.Color.red = MagicMock(return_value=MagicMock())
discord_mock.Color.yellow = MagicMock(return_value=MagicMock())
discord_mock.Color.orange = MagicMock(return_value=MagicMock())
discord_mock.Color.purple = MagicMock(return_value=MagicMock())

discord_mock.Forbidden = Exception
discord_mock.HTTPException = Exception
discord_mock.NotFound = Exception

discord_mock.utils = MagicMock()

discord_ui_mock = types.ModuleType("discord.ui")
discord_ui_mock.View = MagicMock
discord_ui_mock.Button = MagicMock
discord_ui_mock.Select = MagicMock
discord_ui_mock.button = lambda **kwargs: lambda func: func
discord_ui_mock.select = lambda **kwargs: lambda func: func
discord_mock.ui = discord_ui_mock

sys.modules["discord"] = discord_mock
sys.modules["discord.ext"] = types.ModuleType("discord.ext")
sys.modules["discord.ui"] = discord_ui_mock

# Removed: sys.modules['discord.ext.commands'] = MagicMock()

# Removed import that now fails:
# from discord.ext import commands

@pytest.fixture
def bot():
    bot_mock = MagicMock()  # Changed from MagicMock(spec=commands.Bot)
    # Setup bot mock attributes
    session = AsyncMock()
    session.commit = AsyncMock()
    bot_mock.get_db.return_value.__aenter__.return_value = session

    member_service = AsyncMock()
    member_service.get_or_create_member = AsyncMock(
        return_value=AsyncMock(wallet_balance=0)
    )
    member_service.update_member_info = AsyncMock()
    bot_mock.get_service = AsyncMock(return_value=member_service)

    return bot_mock

@pytest.fixture
def ctx():
    ctx_mock = MagicMock()  # Changed from MagicMock(spec=commands.Context)
    ctx_mock.reply = AsyncMock()
    ctx_mock.author.display_name = "TestUser"
    return ctx_mock

@pytest.fixture
def mock_permission_error():
    error = Exception("Missing permissions: administrator")
    error.missing_permissions = ["administrator"]
    return error

# other fixtures and helpers remain unchanged
</file>

<file name=tests/utils/commands_stub.py>"""
Light‑weight stub for discord.ext.commands used in ultra‑clean tests.

Usage:
    from tests.utils.commands_stub import install_commands_stub
    install_commands_stub()  # call **before** importing the cog under test
"""
import sys
import types
from unittest.mock import MagicMock


def passthrough_decorator(*_args, **_kwargs):
    def wrapper(fn):
        return fn
    return wrapper


class _Cog:
    def __init__(self, bot):
        self.bot = bot


def install_commands_stub() -> types.ModuleType:
    """Inject a minimal discord.ext.commands module and return it."""
    commands_stub = types.ModuleType("discord.ext.commands")
    commands_stub.Cog = _Cog
    commands_stub.Command = type("Cmd", (), {})
    commands_stub.Bot = MagicMock
    commands_stub.Context = MagicMock
    commands_stub.hybrid_command = passthrough_decorator
    commands_stub.command = passthrough_decorator
    commands_stub.has_permissions = passthrough_decorator

    # Register in sys.modules so later imports pick it up
    sys.modules["discord.ext.commands"] = commands_stub
    return commands_stub
</file>

<file name=tests/commands/shop/test_addbalance_ultraclean.py>import pytest
from unittest.mock import MagicMock, AsyncMock

from tests.utils.commands_stub import install_commands_stub

def make_mock_bot():
    bot = MagicMock()
    session = AsyncMock()
    session.commit = AsyncMock()
    bot.get_db.return_value.__aenter__.return_value = session

    member_service = AsyncMock()
    member_service.get_or_create_member = AsyncMock(
        return_value=AsyncMock(wallet_balance=0)
    )
    member_service.update_member_info = AsyncMock()
    bot.get_service = AsyncMock(return_value=member_service)
    return bot

def make_mock_context():
    ctx = MagicMock()
    ctx.reply = AsyncMock()
    ctx.author.display_name = "TestUser"
    return ctx

def make_mock_user():
    user = MagicMock()
    user.id = 12345
    user.mention = "<@12345>"
    return user

@pytest.mark.asyncio
async def test_addbalance_ultraclean():
    install_commands_stub()              # stub BEFORE import

    from cogs.commands.shop import ShopCog

    bot  = make_mock_bot()
    ctx  = make_mock_context()
    user = make_mock_user()

    shop = ShopCog(bot)
    await shop.add_balance(ctx, user, 500)

    ctx.reply.assert_awaited_once()
    bot.get_db.assert_called_once()
</file>