"""
Service fixtures for testing bot services
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from tests.data.test_constants import ROLE_ZG50_ID, TEST_USER_1_ID, WALLET_BALANCES


@pytest.fixture
def mock_member_service():
    """Mock member service with realistic behavior"""
    service = AsyncMock()

    # Mock database member object
    db_member = MagicMock()
    db_member.id = TEST_USER_1_ID
    db_member.wallet_balance = WALLET_BALANCES["medium"]

    service.get_or_create_member = AsyncMock(return_value=db_member)
    service.update_member_info = AsyncMock()
    service.add_balance = AsyncMock()
    service.get_member_by_discord_id = AsyncMock(return_value=db_member)
    service.create_member = AsyncMock(return_value=db_member)

    return service


@pytest.fixture
def mock_premium_service():
    """Mock premium service with realistic behavior"""
    service = AsyncMock()

    # Mock premium roles data
    premium_roles = [
        {
            "role_id": ROLE_ZG50_ID,
            "role_name": "zG50",
            "expiration_date": datetime(2025, 12, 31, tzinfo=timezone.utc),
            "is_active": True,
        }
    ]

    service.get_member_premium_roles = AsyncMock(return_value=premium_roles)
    service.has_premium_role = AsyncMock(return_value=True)
    service.assign_premium_role = AsyncMock()
    service.remove_premium_role = AsyncMock()
    service.extend_premium_role = AsyncMock()
    service.set_guild = MagicMock()

    # Mock successful operation result
    success_result = MagicMock()
    success_result.success = True
    success_result.message = "Operation successful"
    service.extend_premium_role.return_value = success_result

    return service


@pytest.fixture
def mock_activity_service():
    """Mock activity tracking service"""
    service = AsyncMock()

    # Mock leaderboard data
    leaderboard = [
        {"member_id": TEST_USER_1_ID, "points": 1000, "rank": 1},
        {"member_id": TEST_USER_1_ID + 1, "points": 800, "rank": 2},
        {"member_id": TEST_USER_1_ID + 2, "points": 600, "rank": 3},
    ]

    service.get_leaderboard = AsyncMock(return_value=leaderboard)
    service.get_member_stats = AsyncMock(return_value={"points": 1000, "rank": 1})
    service.add_activity = AsyncMock()
    service.get_activity_history = AsyncMock(return_value=[])

    return service


@pytest.fixture
def mock_moderation_service():
    """Mock moderation service"""
    service = AsyncMock()

    service.mute_user = AsyncMock()
    service.unmute_user = AsyncMock()
    service.get_mute_history = AsyncMock(return_value=[])
    service.kick_user = AsyncMock()
    service.ban_user = AsyncMock()
    service.get_moderation_logs = AsyncMock(return_value=[])

    return service


@pytest.fixture
def mock_invite_service():
    """Mock invite tracking service"""
    service = AsyncMock()

    # Mock invite data
    invite_data = {"code": "TEST123", "creator_id": TEST_USER_1_ID, "uses": 5, "max_uses": 10}

    service.get_invite_by_code = AsyncMock(return_value=invite_data)
    service.create_invite = AsyncMock(return_value=invite_data)
    service.update_invite_uses = AsyncMock()
    service.get_member_invites = AsyncMock(return_value=[invite_data])
    service.sync_server_invites = AsyncMock()

    return service


@pytest.fixture
def mock_notification_service():
    """Mock notification service"""
    service = AsyncMock()

    service.send_notification = AsyncMock()
    service.send_dm = AsyncMock()
    service.send_channel_message = AsyncMock()
    service.log_notification = AsyncMock()
    service.is_user_opted_out = AsyncMock(return_value=False)

    return service


@pytest.fixture
def mock_service_manager():
    """Mock service manager that provides all services"""
    manager = MagicMock()

    # Create all service mocks directly (not calling fixtures)
    member_service = AsyncMock()
    db_member = MagicMock()
    db_member.id = TEST_USER_1_ID
    db_member.wallet_balance = WALLET_BALANCES["medium"]
    member_service.get_or_create_member = AsyncMock(return_value=db_member)
    member_service.update_member_info = AsyncMock()

    premium_service = AsyncMock()
    premium_roles = [
        {
            "role_id": ROLE_ZG50_ID,
            "role_name": "zG50",
            "expiration_date": datetime(2025, 12, 31, tzinfo=timezone.utc),
            "is_active": True,
        }
    ]
    premium_service.get_member_premium_roles = AsyncMock(return_value=premium_roles)
    premium_service.has_premium_role = AsyncMock(return_value=True)

    activity_service = AsyncMock()
    moderation_service = AsyncMock()
    invite_service = AsyncMock()
    notification_service = AsyncMock()

    # Map service interfaces to implementations
    service_map = {
        "IMemberService": member_service,
        "IPremiumService": premium_service,
        "IActivityService": activity_service,
        "IModerationService": moderation_service,
        "IInviteService": invite_service,
        "INotificationService": notification_service,
    }

    async def get_service(interface, session=None):
        # Simple interface matching - just return member_service for any interface containing "Member"
        interface_str = str(interface)
        if "IMemberService" in interface_str or "Member" in interface_str:
            return member_service
        elif "IPremiumService" in interface_str or "Premium" in interface_str:
            return premium_service
        elif "IActivityService" in interface_str or "Activity" in interface_str:
            return activity_service
        else:
            return AsyncMock()

    manager.get_service = get_service

    return manager


@pytest.fixture
def mock_bot_with_services(mock_service_manager, mock_database_context_manager):
    """Mock bot with full service integration"""
    bot = MagicMock()

    # Bot configuration
    bot.config = {
        "premium_roles": [
            {"name": "zG50", "price": 49, "duration": 30},
            {"name": "zG100", "price": 99, "duration": 30},
            {"name": "zG500", "price": 499, "duration": 30},
            {"name": "zG1000", "price": 999, "duration": 30},
        ],
        "emojis": {"success": "✅", "error": "❌", "mastercard": "💳"},
        "channels": {"premium_info": 123456789, "mute_logs": 987654321},
    }

    # Database and services
    bot.get_db = MagicMock(return_value=mock_database_context_manager)
    bot.get_service = mock_service_manager.get_service
    bot.service_manager = mock_service_manager

    return bot


@pytest.fixture
def mock_discord_context():
    """Mock Discord command context with realistic behavior"""
    ctx = MagicMock()

    # Author
    ctx.author = MagicMock()
    ctx.author.id = TEST_USER_1_ID
    ctx.author.display_name = "TestUser"
    ctx.author.mention = f"<@{TEST_USER_1_ID}>"

    # Guild
    ctx.guild = MagicMock()
    ctx.guild.id = 960665311701528596
    ctx.guild.name = "Test Guild"

    # Channel
    ctx.channel = MagicMock()
    ctx.channel.id = 123456789
    ctx.channel.name = "test-channel"

    # Async methods
    ctx.send = AsyncMock()
    ctx.reply = AsyncMock()

    return ctx


@pytest.fixture
def mock_discord_user():
    """Mock Discord user"""
    user = MagicMock()
    user.id = TEST_USER_1_ID
    user.name = "TestUser"
    user.display_name = "TestUser"
    user.mention = f"<@{TEST_USER_1_ID}>"
    user.send = AsyncMock()

    return user


@pytest.fixture
def mock_discord_member(mock_discord_user):
    """Mock Discord member (user with guild context)"""
    member = mock_discord_user

    # Add guild-specific properties
    member.guild = MagicMock()
    member.guild.id = 960665311701528596
    member.roles = []
    member.nick = None
    member.joined_at = datetime.now(timezone.utc)

    return member


@pytest.fixture
def integration_test_setup(mock_bot_with_services, mock_discord_context):
    """Complete setup for integration testing"""
    return {"bot": mock_bot_with_services, "ctx": mock_discord_context, "user": mock_discord_context.author}
