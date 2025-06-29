"""
Tests for assign_payment command execution
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock Discord before any imports
sys.modules["discord"] = MagicMock()
sys.modules["discord.ext"] = MagicMock()
sys.modules["discord.ext.commands"] = MagicMock()
sys.modules["utils.permissions"] = MagicMock()
sys.modules["core.interfaces.member_interfaces"] = MagicMock()
sys.modules["datasources.queries"] = MagicMock()

from cogs.commands.shop import ShopCog  # noqa: E402


@pytest.mark.asyncio
@patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id")
async def test_assign_payment_success(
    mock_get_payment, mock_bot_with_services, mock_discord_context, mock_discord_user
):
    """Test successful payment assignment"""
    # Arrange
    payment_id = 123
    mock_session = mock_bot_with_services.get_db.return_value.__aenter__.return_value

    # Setup mock payment
    mock_payment = MagicMock()
    mock_payment.id = payment_id
    mock_payment.amount = 500
    mock_payment.member_id = None
    mock_get_payment.return_value = mock_payment

    # Act
    shop_cog = ShopCog(mock_bot_with_services)
    await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert payment query was called with correct parameters
    mock_get_payment.assert_called_once_with(mock_session, payment_id)
    assert mock_payment.member_id == mock_discord_user.id
    mock_discord_user.send.assert_called()


@pytest.mark.asyncio
async def test_assign_payment_not_found(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test payment assignment when payment not found"""
    # Arrange
    payment_id = 999

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        mock_get_payment.return_value = None

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert
    mock_discord_context.send.assert_called_once()
    error_message = mock_discord_context.send.call_args[0][0]
    assert f"Nie znaleziono płatności o ID: {payment_id}" in error_message


@pytest.mark.asyncio
async def test_assign_payment_dm_success(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test payment assignment sends DM successfully"""
    # Arrange
    payment_id = 123

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        mock_payment = MagicMock()
        mock_payment.amount = 500
        mock_payment.member_id = None
        mock_get_payment.return_value = mock_payment

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert DM messages were sent
    assert mock_discord_user.send.call_count == 2

    # Check DM content
    dm_calls = mock_discord_user.send.call_args_list
    first_dm = dm_calls[0][0][0]
    second_dm = dm_calls[1][0][0]

    assert "ID podczas dokonywania wpłat" in first_dm
    assert str(mock_discord_user.id) in second_dm


@pytest.mark.asyncio
async def test_assign_payment_dm_forbidden(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test payment assignment when DM fails"""
    # Arrange
    payment_id = 123

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        mock_payment = MagicMock()
        mock_payment.amount = 500
        mock_payment.member_id = None
        mock_get_payment.return_value = mock_payment

        # Mock DM failure
        import discord

        mock_discord_user.send.side_effect = discord.Forbidden(MagicMock(), "Cannot send DM")

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert fallback message was sent
    mock_discord_context.send.assert_called_once()
    fallback_message = mock_discord_context.send.call_args[0][0]
    assert "Nie mogłem wysłać DM" in fallback_message
    assert mock_discord_user.mention in fallback_message


@pytest.mark.asyncio
async def test_assign_payment_balance_update(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test payment assignment updates member balance"""
    # Arrange
    payment_id = 123
    payment_amount = 500

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        mock_payment = MagicMock()
        mock_payment.amount = payment_amount
        mock_payment.member_id = None
        mock_get_payment.return_value = mock_payment

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert member service was called
    member_service = mock_bot_with_services.get_service("IMemberService")
    member_service.get_or_create_member.assert_called_once_with(mock_discord_user)
    member_service.update_member_info.assert_called_once()


@pytest.mark.asyncio
async def test_assign_payment_transaction_commit(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test payment assignment commits transaction"""
    # Arrange
    payment_id = 123
    mock_session = mock_bot_with_services.get_db.return_value.__aenter__.return_value

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        mock_payment = MagicMock()
        mock_payment.amount = 500
        mock_payment.member_id = None
        mock_get_payment.return_value = mock_payment

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert transaction was committed
    mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_assign_payment_large_amount(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test payment assignment with large amount"""
    # Arrange
    payment_id = 123
    large_amount = 999999

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        mock_payment = MagicMock()
        mock_payment.amount = large_amount
        mock_payment.member_id = None
        mock_get_payment.return_value = mock_payment

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert payment was processed
    assert mock_payment.member_id == mock_discord_user.id


def test_assign_payment_command_signature():
    """Test assign_payment command has correct signature"""
    shop_cog = ShopCog(None)
    assert hasattr(shop_cog, "assign_payment")
    assert callable(shop_cog.assign_payment)


@pytest.mark.asyncio
async def test_assign_payment_database_session_usage(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test assign_payment uses database session correctly"""
    # Arrange
    payment_id = 123

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        mock_payment = MagicMock()
        mock_payment.amount = 500
        mock_payment.member_id = None
        mock_get_payment.return_value = mock_payment

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert database session was used
    mock_bot_with_services.get_db.assert_called_once()


@pytest.mark.asyncio
async def test_assign_payment_member_creation(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test assign_payment creates member if not exists"""
    # Arrange
    payment_id = 123

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        mock_payment = MagicMock()
        mock_payment.amount = 500
        mock_payment.member_id = None
        mock_get_payment.return_value = mock_payment

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert member service get_or_create was called
    member_service = mock_bot_with_services.get_service("IMemberService")
    member_service.get_or_create_member.assert_called_once_with(mock_discord_user)
