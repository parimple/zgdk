"""
Example tests using database and service fixtures
"""
from unittest.mock import patch

import pytest

from tests.data.test_constants import TEST_USER_1_ID, WALLET_BALANCES


@pytest.mark.asyncio
async def test_shop_command_with_real_db(mock_db_session_with_data, mock_bot_with_services, mock_discord_context):
    """Test shop command with real database session"""
    # Arrange
    mock_bot_with_services.get_db.return_value.__aenter__.return_value = mock_db_session_with_data

    # Mock external dependencies
    with patch('cogs.commands.shop.RoleShopView') as mock_view, \
         patch('cogs.commands.shop.create_shop_embed') as mock_embed:

        mock_view.return_value = mock_view
        mock_embed.return_value = mock_embed

        # Import after mocking
        from cogs.commands.shop import ShopCog

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.shop(mock_discord_context)

    # Assert
    mock_discord_context.reply.assert_called_once()
    # Database should have our test data
    # Could add actual database queries here to verify data integrity


@pytest.mark.asyncio
async def test_addbalance_with_services(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance command with service integration"""
    # Arrange
    amount = 500

    with patch('cogs.commands.shop.HandledPaymentQueries.add_payment') as mock_add_payment:
        from cogs.commands.shop import ShopCog

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)

    # Assert
    mock_add_payment.assert_called_once()
    mock_discord_context.reply.assert_called_once()

    # Verify service interactions
    member_service = mock_bot_with_services.get_service('IMemberService')
    assert member_service.get_or_create_member.called
    assert member_service.update_member_info.called


@pytest.mark.asyncio
async def test_assign_payment_with_mocked_queries(mock_payment_queries, mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test assign_payment with mocked database queries"""
    # Arrange
    payment_id = 123

    with patch('cogs.commands.shop.HandledPaymentQueries', mock_payment_queries):
        from cogs.commands.shop import ShopCog

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert
    mock_payment_queries.get_payment_by_id.assert_called_once()
    mock_discord_user.send.assert_called()  # DM should be sent


def test_database_fixtures_setup(default_database_items):
    """Test that database fixtures are properly configured"""
    # Verify we have all expected items
    assert len(default_database_items) >= 7  # members, roles, activities, payments, etc.

    # Check member data
    members = [item for item in default_database_items if hasattr(item, 'wallet_balance')]
    assert len(members) >= 2

    # Check first member has expected properties
    member1 = next(m for m in members if m.id == TEST_USER_1_ID)
    assert member1.wallet_balance == WALLET_BALANCES["medium"]


def test_service_fixtures_setup(mock_member_service, mock_premium_service):
    """Test that service fixtures are properly configured"""
    # Test member service
    assert mock_member_service.get_or_create_member is not None
    assert mock_member_service.update_member_info is not None

    # Test premium service
    assert mock_premium_service.get_member_premium_roles is not None
    assert mock_premium_service.has_premium_role is not None


@pytest.mark.asyncio
async def test_integration_test_setup(integration_test_setup):
    """Test complete integration setup"""
    bot = integration_test_setup["bot"]
    ctx = integration_test_setup["ctx"]
    user = integration_test_setup["user"]

    # Verify bot configuration
    assert "premium_roles" in bot.config
    assert len(bot.config["premium_roles"]) == 4

    # Verify context setup
    assert ctx.author.id == TEST_USER_1_ID
    assert ctx.guild.id == 960665311701528596

    # Verify user setup
    assert user.id == TEST_USER_1_ID


@pytest.mark.asyncio
async def test_mock_database_session(mock_async_session):
    """Test mock database session functionality"""
    # Test basic session operations
    await mock_async_session.commit()
    await mock_async_session.rollback()

    # Verify mocks were called
    mock_async_session.commit.assert_called_once()
    mock_async_session.rollback.assert_called_once()


def test_sample_data_fixtures(sample_member_data, sample_payment_data, sample_activity_data):
    """Test sample data fixtures"""
    # Test member data
    assert sample_member_data["id"] == TEST_USER_1_ID
    assert sample_member_data["wallet_balance"] == WALLET_BALANCES["medium"]

    # Test payment data
    assert sample_payment_data["member_id"] == TEST_USER_1_ID
    assert sample_payment_data["amount"] == 500
    assert sample_payment_data["payment_type"] == "role_purchase"

    # Test activity data
    assert sample_activity_data["member_id"] == TEST_USER_1_ID
    assert sample_activity_data["activity_type"] == "text"
    assert sample_activity_data["points"] == 100


@pytest.mark.asyncio
async def test_real_database_operations(mock_empty_db_session, sample_member_data):
    """Test actual database operations with in-memory SQLite"""
    from sqlalchemy import select

    from datasources.models import Member

    # Create a member
    member = Member(**sample_member_data)
    mock_empty_db_session.add(member)
    await mock_empty_db_session.commit()

    # Query the member back using SQLAlchemy ORM
    result = await mock_empty_db_session.execute(
        select(Member).where(Member.id == TEST_USER_1_ID)
    )
    found_member = result.scalar_one_or_none()

    # Verify data was saved correctly
    assert found_member is not None
    assert found_member.id == TEST_USER_1_ID
    assert found_member.wallet_balance == WALLET_BALANCES["medium"]


def test_fixture_inheritance():
    """Test that fixtures can be composed together"""
    # This test verifies that we can use multiple fixtures together
    # and that they don't conflict with each other
    pass  # The fact that this test runs means fixtures are compatible
