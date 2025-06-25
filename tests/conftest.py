"""Pytest fixtures for the commands cog."""

from unittest.mock import MagicMock

import pytest
import discord
from discord.ext import commands


@pytest.fixture
def bot() -> MagicMock:
    """Fixture for the Bot"""
    bot_mock = MagicMock(spec=commands.Bot)
    # Dodaj podstawową konfigurację dla testów
    bot_mock.config = {
        "voice_permission_levels": {},
        "team": {},
        "premium_roles": [
            {"name": "zG50", "moderator_count": 1},
            {"name": "zG100", "moderator_count": 2},
            {"name": "zG500", "moderator_count": 5},
            {"name": "zG1000", "moderator_count": 10}
        ],
        "prefix": ",",
        "channels_voice": {"afk": 123456789},
        "voice_permissions": {
            "commands": {
                "speak": {"require_bypass_if_no_role": True},
                "view": {"require_bypass_if_no_role": True},
                "connect": {"require_bypass_if_no_role": True},
                "text": {"require_bypass_if_no_role": True},
                "live": {"require_bypass_if_no_role": True},
                "mod": {"require_bypass_if_no_role": False, "allowed_roles": ["zG50", "zG100", "zG500", "zG1000"]},
                "autokick": {"require_bypass_if_no_role": False, "allowed_roles": ["zG500", "zG1000"]}
            }
        }
    }
    return bot_mock


@pytest.fixture
def ctx() -> MagicMock:
    """Fixture for the Context"""
    ctx_mock = MagicMock(spec=commands.Context)
    # Popraw kolor żeby był prawidłowym obiektem Discord Color
    ctx_mock.author.color = discord.Color.blue()
    return ctx_mock
