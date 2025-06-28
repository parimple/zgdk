"""
Shared fixtures and mocks for command tests
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import discord
import pytest

# Note: discord.ext.commands is now stubbed per-test for flexibility


@pytest.fixture
def mock_bot():
    """Mock Discord bot instance"""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 123456789
    bot.user.name = "TestBot"
    
    # Mock config
    bot.config = {
        "premium_roles": [
            {"name": "zG50", "price": 500, "duration": 30},
            {"name": "zG100", "price": 999, "duration": 30},
            {"name": "zG500", "price": 4999, "duration": 30},
            {"name": "zG1000", "price": 9999, "duration": 30}
        ],
        "emojis": {
            "mastercard": "💳",
            "success": "✅",
            "error": "❌"
        },
        "admin_roles": ["Admin", "Moderator"]
    }
    
    # Mock get_db
    bot.get_db = AsyncMock()
    
    # Mock get_service
    bot.get_service = AsyncMock()
    
    return bot


@pytest.fixture
def mock_guild():
    """Mock Discord guild"""
    guild = MagicMock()
    guild.id = 960665311701528596
    guild.name = "Test Guild"
    guild.member_count = 1000
    guild.get_role = MagicMock()
    guild.get_member = MagicMock()
    return guild


@pytest.fixture
def mock_channel():
    """Mock Discord channel"""
    channel = MagicMock()
    channel.id = 123456789
    channel.name = "test-channel"
    channel.mention = "#test-channel"
    return channel


@pytest.fixture
def mock_member():
    """Mock Discord member"""
    member = MagicMock()
    member.id = 968632323916566579
    member.name = "TestUser"
    member.display_name = "TestUser"
    member.mention = "<@968632323916566579>"
    member.roles = []
    member.guild = mock_guild()
    return member


@pytest.fixture
def mock_author():
    """Mock command author (admin)"""
    author = MagicMock()
    author.id = 956602391891947592
    author.name = "AdminUser"
    author.display_name = "AdminUser"
    author.mention = "<@956602391891947592>"
    
    # Mock admin role
    admin_role = MagicMock()
    admin_role.name = "Admin"
    author.roles = [admin_role]
    
    return author


@pytest.fixture
def mock_ctx(mock_bot, mock_guild, mock_channel, mock_author):
    """Mock Discord command context"""
    ctx = MagicMock()
    ctx.bot = mock_bot
    ctx.guild = mock_guild
    ctx.channel = mock_channel
    ctx.author = mock_author
    ctx.send = AsyncMock()
    ctx.reply = AsyncMock()
    
    return ctx


@pytest.fixture
def mock_db_session():
    """Mock database session"""
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    return session


@pytest.fixture
def mock_member_service():
    """Mock member service"""
    service = AsyncMock()
    
    # Mock database member object
    db_member = MagicMock()
    db_member.id = 968632323916566579
    db_member.wallet_balance = 1000
    db_member.total_activity_points = 500
    
    service.get_or_create_member = AsyncMock(return_value=db_member)
    service.add_balance = AsyncMock()
    service.update_balance = AsyncMock()
    
    return service


@pytest.fixture
def mock_premium_service():
    """Mock premium service"""
    service = AsyncMock()
    
    # Mock premium roles data
    premium_roles = [
        {
            "role_id": 123456789,
            "role_name": "zG50", 
            "expiration_date": datetime.now(timezone.utc),
            "is_active": True
        }
    ]
    
    service.get_member_premium_roles = AsyncMock(return_value=premium_roles)
    service.assign_role = AsyncMock()
    service.remove_expired_roles = AsyncMock()
    
    return service


@pytest.fixture
def mock_moderation_service():
    """Mock moderation service"""
    service = AsyncMock()
    service.mute_user = AsyncMock()
    service.unmute_user = AsyncMock()
    service.get_mute_history = AsyncMock(return_value=[])
    return service


@pytest.fixture
def mock_activity_service():
    """Mock activity tracking service"""
    service = AsyncMock()
    
    # Mock leaderboard data
    leaderboard = [
        {"member_id": 111, "points": 1000, "rank": 1},
        {"member_id": 222, "points": 800, "rank": 2},
        {"member_id": 333, "points": 600, "rank": 3}
    ]
    
    service.get_leaderboard = AsyncMock(return_value=leaderboard)
    service.get_member_stats = AsyncMock(return_value={"points": 500, "rank": 10})
    
    return service


@pytest.fixture
def mock_shop_view():
    """Mock role shop view"""
    view = MagicMock()
    view.add_item = MagicMock()
    return view


@pytest.fixture
def mock_embed():
    """Mock Discord embed"""
    embed = MagicMock()
    embed.add_field = MagicMock()
    embed.set_footer = MagicMock()
    embed.set_author = MagicMock()
    return embed


# Payment fixtures for shop tests
@pytest.fixture
def mock_payment_data():
    """Mock payment data"""
    return {
        "id": "payment_123",
        "member_id": 968632323916566579,
        "amount": 500,
        "payment_type": "role_purchase",
        "role_name": "zG50",
        "duration_days": 30
    }


@pytest.fixture
def mock_handled_payment():
    """Mock handled payment object"""
    payment = MagicMock()
    payment.id = "payment_123"
    payment.member_id = 968632323916566579
    payment.name = "Test Payment"
    payment.amount = 500
    payment.payment_type = "role_purchase"
    payment.paid_at = datetime.now(timezone.utc)
    return payment


# Role fixtures
@pytest.fixture
def mock_premium_role():
    """Mock premium Discord role"""
    role = MagicMock()
    role.id = 123456789
    role.name = "zG50"
    role.color = discord.Color.gold()
    role.position = 10
    return role


@pytest.fixture
def mock_role_config():
    """Mock role configuration"""
    return {
        "name": "zG50",
        "price": 500,
        "duration": 30,
        "color": "#FFD700",
        "permissions": ["premium_access"]
    }


# Error scenarios
@pytest.fixture
def mock_db_error():
    """Mock database error"""
    from sqlalchemy.exc import SQLAlchemyError
    return SQLAlchemyError("Database connection failed")


@pytest.fixture
def mock_discord_error():
    """Mock Discord API error"""
    return discord.HTTPException(MagicMock(), "Discord API error")


@pytest.fixture
def mock_permission_error():
    """Mock permission error"""
    # Create a generic permission error since commands.MissingPermissions not available
    error = Exception("Missing permissions: administrator")
    error.missing_permissions = ["administrator"]
    return error


# Test data sets
@pytest.fixture
def sample_users():
    """Sample user data for testing"""
    return [
        {"id": 111, "name": "User1", "balance": 1000, "roles": []},
        {"id": 222, "name": "User2", "balance": 0, "roles": ["zG50"]},
        {"id": 333, "name": "User3", "balance": 5000, "roles": ["zG100", "zG500"]}
    ]


@pytest.fixture
def sample_roles():
    """Sample role data for testing"""
    return [
        {"name": "zG50", "price": 500, "members": 100},
        {"name": "zG100", "price": 999, "members": 50},
        {"name": "zG500", "price": 4999, "members": 10},
        {"name": "zG1000", "price": 9999, "members": 5}
    ]