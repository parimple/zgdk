"""Tests for Team Manager utility."""

from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from datasources.models import Role as DBRole
from utils.team_manager import TeamManager


@pytest.mark.asyncio
async def test_delete_user_teams_no_teams():
    """Test case for deleting teams when user doesn't own any teams."""
    # Prepare mocks
    session = AsyncMock()
    bot = MagicMock()

    # Mock scalars method
    mock_scalars = AsyncMock()
    mock_scalars.all.return_value = []  # No teams found

    # Mock execute result
    mock_result = AsyncMock()
    mock_result.scalars.return_value = mock_scalars

    # Set up session.execute to return our mock
    session.execute.return_value = mock_result

    # Call the function under test
    deleted_count = await TeamManager.delete_user_teams(session, bot, 12345)

    # Assert
    assert deleted_count == 0
    session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_delete_user_teams_with_teams():
    """Test case for deleting teams when user owns teams."""
    # Prepare mocks
    session = AsyncMock()
    bot = MagicMock()
    bot.guild = MagicMock()

    # Mock team roles in database
    team_role_db1 = MagicMock(spec=DBRole)
    team_role_db1.id = 111
    team_role_db1.name = "12345"  # Owner ID

    team_role_db2 = MagicMock(spec=DBRole)
    team_role_db2.id = 222
    team_role_db2.name = "12345"  # Same owner

    # Mock scalars method
    mock_scalars = AsyncMock()
    mock_scalars.all.return_value = [team_role_db1, team_role_db2]

    # Mock execute result
    mock_result = AsyncMock()
    mock_result.scalars.return_value = mock_scalars

    # Set up session.execute to return our mock
    session.execute.return_value = mock_result

    # Mock guild roles
    team_role1 = MagicMock(spec=discord.Role)
    team_role1.id = 111
    team_role2 = MagicMock(spec=discord.Role)
    team_role2.id = 222

    bot.guild.get_role.side_effect = lambda id: {111: team_role1, 222: team_role2}.get(
        id
    )

    # Mock channels
    channel1 = MagicMock(spec=discord.TextChannel)
    channel1.topic = "12345 111"  # New format: "owner_id role_id"
    channel1.id = 1001
    channel1.delete = AsyncMock()

    channel2 = MagicMock(spec=discord.TextChannel)
    channel2.topic = "Team Channel for Team2. Owner: 12345"  # Old format
    channel2.id = 1002
    channel2.delete = AsyncMock()

    bot.guild.channels = [channel1, channel2]

    # Mock role delete methods
    team_role1.delete = AsyncMock()
    team_role2.delete = AsyncMock()

    # Call the function under test
    deleted_count = await TeamManager.delete_user_teams(session, bot, 12345)

    # Assert
    assert deleted_count == 2
    assert channel1.delete.called
    assert channel2.delete.called
    assert team_role1.delete.called
    assert team_role2.delete.called
    assert session.delete.call_count == 2


@pytest.mark.asyncio
async def test_delete_user_teams_with_exceptions():
    """Test case for handling exceptions when deleting teams."""
    # Prepare mocks
    session = AsyncMock()
    bot = MagicMock()
    bot.guild = MagicMock()

    # Mock team role in database
    team_role_db = MagicMock(spec=DBRole)
    team_role_db.id = 111
    team_role_db.name = "12345"  # Owner ID

    # Mock scalars method
    mock_scalars = AsyncMock()
    mock_scalars.all.return_value = [team_role_db]

    # Mock execute result
    mock_result = AsyncMock()
    mock_result.scalars.return_value = mock_scalars

    # Set up session.execute to return our mock
    session.execute.return_value = mock_result

    # Mock guild role
    team_role = MagicMock(spec=discord.Role)
    team_role.id = 111
    team_role.delete = AsyncMock(side_effect=Exception("Test exception"))

    bot.guild.get_role.return_value = team_role

    # Mock channel
    channel = MagicMock(spec=discord.TextChannel)
    channel.topic = "12345 111"
    channel.id = 1001
    channel.delete = AsyncMock(side_effect=Exception("Test exception"))

    bot.guild.channels = [channel]

    # Call the function under test
    with patch("utils.team_manager.logger") as mock_logger:
        deleted_count = await TeamManager.delete_user_teams(session, bot, 12345)

    # Assert
    assert deleted_count == 0  # No successful deletions due to exceptions
    assert mock_logger.error.called
    assert session.delete.call_count == 0  # Database entry not deleted due to exception
