from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

from cogs.commands.premium import PremiumCog
from datasources.models import Role as DBRole


@pytest.mark.asyncio
async def test_team_create_when_user_is_already_team_owner():
    """Test creating a team when user is already an owner of another team."""
    # Mock context, bot, and session
    ctx = AsyncMock()
    ctx.author = MagicMock(spec=discord.Member)
    ctx.author.id = 12345
    ctx.author.display_name = "TestUser"
    ctx.guild = MagicMock(spec=discord.Guild)

    # Setup mock bot
    bot = MagicMock()
    bot.config = {"team": {"symbol": "☫", "category_id": 123}, "premium_roles": []}

    # Create a mock existing team
    existing_team_role = MagicMock(spec=discord.Role)
    existing_team_role.id = 98765
    existing_team_role.mention = "MockMention"
    ctx.guild.get_role.return_value = existing_team_role

    # Mock existing team in database
    existing_team_db = MagicMock(spec=DBRole)
    existing_team_db.id = 98765

    # Mock database session to return existing team
    session = AsyncMock()
    session_result = AsyncMock()
    session_result.scalar_one_or_none.return_value = (
        existing_team_db  # User is already an owner
    )
    session.execute.return_value = session_result

    # Setup bot.get_db context manager
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=session)
    mock_context_manager.__aexit__ = AsyncMock(return_value=False)
    bot.get_db = MagicMock(return_value=mock_context_manager)

    # Create premium cog instance and patch methods
    cog = PremiumCog(bot)
    cog._send_premium_embed = AsyncMock()

    # Call the method under test
    await cog.team_create.callback(cog, ctx, name="NewTeam")

    # Assert that team creation was blocked
    cog._send_premium_embed.assert_called_once()
    description = cog._send_premium_embed.call_args[1]["description"]
    assert "Posiadasz już team" in description
    assert "Nie możesz stworzyć kolejnego" in description 