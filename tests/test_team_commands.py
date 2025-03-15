from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest
from sqlalchemy import select

from cogs.commands.premium import PremiumCog
from datasources.models import Role as DBRole


@pytest.mark.asyncio
async def test_team_create_when_user_is_team_member_only():
    """Test creating a team when user is a member of another team but not an owner of any team."""
    # Mock context, bot, and session
    ctx = AsyncMock()
    ctx.author = MagicMock(spec=discord.Member)
    ctx.author.id = 12345
    ctx.author.roles = [MagicMock(spec=discord.Role)]
    ctx.guild = MagicMock(spec=discord.Guild)

    # Setup mock bot and session
    bot = MagicMock()
    bot.config = {"team": {"symbol": "☫", "category_id": 123}, "premium_roles": []}

    # Create test team role that the user is a member of
    team_role = MagicMock(spec=discord.Role)
    team_role.name = "☫ TestTeam"
    ctx.author.roles.append(team_role)  # User is a member of this team

    # Mock database session
    session = AsyncMock()
    session_result = AsyncMock()
    session_result.scalar_one_or_none.return_value = None  # User is not an owner of any team
    session.execute.return_value = session_result

    # Setup bot.get_db context manager
    bot.get_db = MagicMock()
    bot.get_db.return_value.__aenter__.return_value = session

    # Mock guild.create_role and other necessary methods
    ctx.guild.create_role = AsyncMock(return_value=MagicMock(spec=discord.Role))
    ctx.guild.edit_role_positions = AsyncMock()
    ctx.guild.get_role = MagicMock(return_value=MagicMock(spec=discord.Role))
    ctx.author.add_roles = AsyncMock()
    ctx.guild.create_text_channel = AsyncMock(return_value=MagicMock(spec=discord.TextChannel))

    # Create premium cog instance and patch _send_premium_embed and _get_user_team_role
    cog = PremiumCog(bot)
    cog._send_premium_embed = AsyncMock()
    cog._save_team_to_database = AsyncMock()
    cog._get_user_team_role = AsyncMock(return_value=team_role)  # User is a member of another team

    # Call the method under test
    await cog.team_create(ctx, "NewTeam")

    # Assert that _save_team_to_database was called (team creation proceeded)
    cog._save_team_to_database.assert_called_once()

    # Assert that session.execute was called with the correct query
    session.execute.assert_called_once()
    args, _ = session.execute.call_args
    query = args[0]
    assert isinstance(query, select)

    # Check that additional_info about existing team membership was included
    description = cog._send_premium_embed.call_args[1]["description"]
    assert "Jesteś obecnie również członkiem teamu" in description


@pytest.mark.asyncio
async def test_team_create_when_user_is_already_team_owner():
    """Test creating a team when user is already an owner of another team."""
    # Mock context, bot, and session
    ctx = AsyncMock()
    ctx.author = MagicMock(spec=discord.Member)
    ctx.author.id = 12345
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
    session_result.scalar_one_or_none.return_value = existing_team_db  # User is already an owner
    session.execute.return_value = session_result

    # Setup bot.get_db context manager
    bot.get_db = MagicMock()
    bot.get_db.return_value.__aenter__.return_value = session

    # Create premium cog instance and patch methods
    cog = PremiumCog(bot)
    cog._send_premium_embed = AsyncMock()

    # Call the method under test
    await cog.team_create(ctx, "NewTeam")

    # Assert that team creation was blocked
    cog._send_premium_embed.assert_called_once()
    description = cog._send_premium_embed.call_args[1]["description"]
    assert "Jesteś już właścicielem teamu" in description
    assert "Nie możesz stworzyć drugiego teamu" in description


@pytest.mark.asyncio
async def test_team_create_with_new_topic_format_and_pinned_message():
    """Test creating a team with the new topic format and pinned message."""
    # Mock context, bot, and session
    ctx = AsyncMock()
    ctx.author = MagicMock(spec=discord.Member)
    ctx.author.id = 12345
    ctx.author.roles = [MagicMock(spec=discord.Role)]
    ctx.author.mention = "<@12345>"
    ctx.guild = MagicMock(spec=discord.Guild)

    # Setup mock bot
    bot = MagicMock()
    bot.config = {
        "team": {"symbol": "☫", "category_id": 123},
        "premium_roles": [{"name": "zG100", "team_size": 10}],
    }

    # Mock database session
    session = AsyncMock()
    session_result = AsyncMock()
    session_result.scalar_one_or_none.return_value = None  # User is not an owner of any team
    session.execute.return_value = session_result

    # Setup bot.get_db context manager
    bot.get_db = MagicMock()
    bot.get_db.return_value.__aenter__.return_value = session

    # Mock new team role
    new_team_role = MagicMock(spec=discord.Role)
    new_team_role.id = 98765
    new_team_role.mention = "<@&98765>"
    new_team_role.name = "☫ TestTeam"
    new_team_role.color = discord.Color.default()

    # Mock guild.create_role and other necessary methods
    ctx.guild.create_role = AsyncMock(return_value=new_team_role)
    ctx.guild.edit_role_positions = AsyncMock()
    ctx.guild.get_role = MagicMock(return_value=MagicMock(spec=discord.Role))
    ctx.author.add_roles = AsyncMock()

    # Mock text channel
    text_channel = MagicMock(spec=discord.TextChannel)
    text_channel.mention = "<#123456>"
    text_channel.send = AsyncMock()
    text_channel.send.return_value = MagicMock(spec=discord.Message)
    text_channel.send.return_value.pin = AsyncMock()

    # Mock guild.create_text_channel
    ctx.guild.create_text_channel = AsyncMock(return_value=text_channel)

    # Create premium cog instance and patch methods
    cog = PremiumCog(bot)
    cog._send_premium_embed = AsyncMock()
    cog._save_team_to_database = AsyncMock()
    cog._get_user_team_role = AsyncMock(return_value=None)

    # Call the method under test
    await cog.team_create(ctx, "TestTeam")

    # Assert team was created
    ctx.guild.create_role.assert_called_once()
    cog._save_team_to_database.assert_called_once_with(ctx.author.id, new_team_role.id)

    # Assert text channel was created with correct topic format
    call_args = ctx.guild.create_text_channel.call_args
    kwargs = call_args[1]
    assert kwargs["topic"] == f"{ctx.author.id} {new_team_role.id}"

    # Assert message was sent and pinned
    text_channel.send.assert_called_once()
    text_channel.send.return_value.pin.assert_called_once()
