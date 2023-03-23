"""Pytest fixtures for the commands cog."""

from unittest.mock import MagicMock

import pytest
from discord.ext import commands


@pytest.fixture
def bot() -> MagicMock:
    """Fixture for the Bot"""
    return MagicMock(spec=commands.Bot)


@pytest.fixture
def ctx() -> MagicMock:
    """Fixture for the Context"""
    return MagicMock(spec=commands.Context)
