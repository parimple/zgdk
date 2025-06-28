"""
Giveaway command test fixtures
Professional test setup with proper separation of concerns
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timezone
import discord

from cogs.commands.giveaway import GiveawayCog
from tests.data.test_constants import (
    ADMIN_USER_ID, TEST_USER_1_ID, TEST_USER_2_ID, TEST_USER_3_ID, 
    TEST_USER_4_ID, BOT_USER_ID, ADMIN_ROLE_ID, STAR_ROLE_ID,
    TEST_ROLE_1_ID, TEST_ROLE_2_ID, TEST_ROLE_3_ID, PREMIUM_ROLE_ID, VIP_ROLE_ID,
    MESSAGE_BASE_ID, BOT_MESSAGE_BASE_ID, WEBHOOK_MESSAGE_BASE_ID,
    GUILD_ID, CHANNEL_ID, ROLE_NAMES, BOT_CONFIG
)


@pytest.fixture
def giveaway_cog(mock_bot):
    """Create properly configured giveaway cog instance"""
    mock_bot.config = BOT_CONFIG
    return GiveawayCog(mock_bot)


@pytest.fixture
def mock_admin_role():
    """Create mock admin role with proper configuration"""
    role = MagicMock(spec=discord.Role)
    role.id = ADMIN_ROLE_ID
    role.name = ROLE_NAMES["admin"]
    return role


@pytest.fixture
def mock_star_role():
    """Create mock star role (✪) for permission testing"""
    role = MagicMock(spec=discord.Role)
    role.id = STAR_ROLE_ID
    role.name = ROLE_NAMES["star"]
    return role


@pytest.fixture
def mock_test_roles():
    """Create collection of test roles for role-based testing"""
    roles = {}
    role_configs = [
        ("test1", TEST_ROLE_1_ID, ROLE_NAMES["test1"]),
        ("test2", TEST_ROLE_2_ID, ROLE_NAMES["test2"]),
        ("test3", TEST_ROLE_3_ID, ROLE_NAMES["test3"]),
        ("premium", PREMIUM_ROLE_ID, ROLE_NAMES["premium"]),
        ("vip", VIP_ROLE_ID, ROLE_NAMES["vip"])
    ]
    
    for key, role_id, role_name in role_configs:
        role = MagicMock(spec=discord.Role)
        role.id = role_id
        role.name = role_name
        roles[key] = role
    
    return roles


@pytest.fixture
def mock_guild_roles(mock_test_roles, mock_admin_role, mock_star_role):
    """Create complete guild roles collection"""
    all_roles = list(mock_test_roles.values()) + [mock_admin_role, mock_star_role]
    return all_roles


class MockMemberFactory:
    """Factory for creating mock members with different role configurations"""
    
    @staticmethod
    def create_member(member_id: int, roles: list = None, is_bot: bool = False, name: str = None):
        """Create a mock member with specified configuration"""
        member = MagicMock(spec=discord.Member)
        member.id = member_id
        member.mention = f"<@{member_id}>"
        member.bot = is_bot
        member.name = name or f"User{member_id}"
        member.display_name = name or f"User{member_id}"
        member.roles = roles or []
        return member


@pytest.fixture
def mock_member_factory():
    """Provide member factory for flexible member creation"""
    return MockMemberFactory


@pytest.fixture
def mock_test_members(mock_test_roles, mock_member_factory):
    """Create diverse set of test members with different role combinations"""
    members = {}
    
    # Admin user with test role 1
    members["admin_with_test1"] = mock_member_factory.create_member(
        ADMIN_USER_ID,
        roles=[mock_test_roles["test1"]],
        name="AdminUser"
    )
    
    # Regular user with test roles 1 and 2
    members["user_test1_test2"] = mock_member_factory.create_member(
        TEST_USER_1_ID,
        roles=[mock_test_roles["test1"], mock_test_roles["test2"]],
        name="TestUser1"
    )
    
    # User with test roles 2 and 3
    members["user_test2_test3"] = mock_member_factory.create_member(
        TEST_USER_2_ID,
        roles=[mock_test_roles["test2"], mock_test_roles["test3"]],
        name="TestUser2"
    )
    
    # User with only premium role
    members["user_premium_only"] = mock_member_factory.create_member(
        TEST_USER_3_ID,
        roles=[mock_test_roles["premium"]],
        name="PremiumUser"
    )
    
    # Bot user (should be filtered out)
    members["bot_with_test1"] = mock_member_factory.create_member(
        BOT_USER_ID,
        roles=[mock_test_roles["test1"]],
        is_bot=True,
        name="BotUser"
    )
    
    # User with no relevant roles
    members["user_no_roles"] = mock_member_factory.create_member(
        TEST_USER_4_ID,
        roles=[],
        name="NoRolesUser"
    )
    
    return members


class MockMessageFactory:
    """Factory for creating mock messages with different configurations"""
    
    @staticmethod
    def create_message(message_id: int, author_id: int, is_bot: bool = False, 
                      webhook_id: str = None, content: str = None):
        """Create a mock message with specified configuration"""
        message = MagicMock(spec=discord.Message)
        message.id = message_id
        message.content = content or f"Test message {message_id}"
        message.webhook_id = webhook_id
        message.jump_url = f"https://discord.com/channels/{GUILD_ID}/{CHANNEL_ID}/{message_id}"
        message.created_at = datetime.now(timezone.utc)
        
        # Create author mock
        author = MagicMock(spec=discord.Member)
        author.id = author_id
        author.bot = is_bot
        author.mention = f"<@{author_id}>"
        author.name = f"User{author_id}"
        
        message.author = author
        return message


@pytest.fixture
def mock_message_factory():
    """Provide message factory for flexible message creation"""
    return MockMessageFactory


@pytest.fixture
def mock_regular_messages(mock_message_factory):
    """Create collection of regular user messages for giveaway testing"""
    messages = []
    for i in range(10):
        message = mock_message_factory.create_message(
            message_id=MESSAGE_BASE_ID + i,
            author_id=TEST_USER_1_ID + i,
            content=f"Regular message {i}"
        )
        messages.append(message)
    return messages


@pytest.fixture
def mock_bot_messages(mock_message_factory):
    """Create collection of bot messages (should be filtered out)"""
    messages = []
    for i in range(3):
        message = mock_message_factory.create_message(
            message_id=BOT_MESSAGE_BASE_ID + i,
            author_id=BOT_USER_ID + i,
            is_bot=True,
            content=f"Bot message {i}"
        )
        messages.append(message)
    return messages


@pytest.fixture
def mock_webhook_messages(mock_message_factory):
    """Create collection of webhook messages (should be included)"""
    messages = []
    for i in range(2):
        message = mock_message_factory.create_message(
            message_id=WEBHOOK_MESSAGE_BASE_ID + i,
            author_id=BOT_USER_ID + i,
            is_bot=True,
            webhook_id=f"webhook_{i}",
            content=f"Webhook message {i}"
        )
        messages.append(message)
    return messages


@pytest.fixture
def mock_messages_same_author(mock_message_factory):
    """Create multiple messages from the same author for uniqueness testing"""
    messages = []
    for i in range(5):
        message = mock_message_factory.create_message(
            message_id=MESSAGE_BASE_ID + 100 + i,
            author_id=TEST_USER_1_ID,  # Same author
            content=f"Same author message {i}"
        )
        messages.append(message)
    return messages


@pytest.fixture
def mock_channel_with_history(mock_ctx):
    """Create mock channel with configurable message history"""
    def setup_history(messages):
        """Setup channel history with provided messages"""
        async def async_iter():
            for message in messages:
                yield message
        
        mock_ctx.channel.history.return_value.__aiter__ = async_iter
        return mock_ctx.channel
    
    return setup_history


@pytest.fixture
def mock_guild_with_members(mock_guild_roles, mock_test_members):
    """Create mock guild with complete member and role setup"""
    guild = MagicMock(spec=discord.Guild)
    guild.id = GUILD_ID
    guild.name = "Test Guild"
    guild.roles = mock_guild_roles
    guild.members = list(mock_test_members.values())
    
    # Setup role lookup functionality
    def get_role_by_name(name):
        for role in mock_guild_roles:
            if role.name == name:
                return role
        return None
    
    # Mock discord.utils.get behavior
    guild.get_role_by_name = get_role_by_name
    
    return guild


@pytest.fixture
def mock_admin_context(mock_ctx, mock_admin_role):
    """Create context with admin permissions"""
    mock_ctx.author.id = ADMIN_USER_ID
    mock_ctx.author.roles = [mock_admin_role]
    return mock_ctx


@pytest.fixture
def mock_regular_context(mock_ctx):
    """Create context without admin permissions"""
    regular_role = MagicMock(spec=discord.Role)
    regular_role.id = 999999999
    regular_role.name = "Regular"
    
    mock_ctx.author.id = TEST_USER_1_ID
    mock_ctx.author.roles = [regular_role]
    return mock_ctx


class GiveawayTestHelpers:
    """Helper functions for giveaway testing"""
    
    @staticmethod
    def count_eligible_members(members, roles, mode="and"):
        """Count eligible members based on role requirements"""
        eligible = []
        for member in members:
            if member.bot:
                continue
                
            if mode == "or":
                if any(role in member.roles for role in roles):
                    eligible.append(member)
            else:  # and mode
                if all(role in member.roles for role in roles):
                    eligible.append(member)
        
        return len(eligible)
    
    @staticmethod
    def get_members_by_role_criteria(members, roles, mode="and"):
        """Get members matching role criteria"""
        eligible = []
        for member in members:
            if member.bot:
                continue
                
            if mode == "or":
                if any(role in member.roles for role in roles):
                    eligible.append(member)
            else:  # and mode
                if all(role in member.roles for role in roles):
                    eligible.append(member)
        
        return eligible


@pytest.fixture
def giveaway_helpers():
    """Provide helper functions for giveaway testing"""
    return GiveawayTestHelpers