"""
Tests for shop command - testing actual command functionality
"""
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock Discord before any imports
sys.modules["discord"] = MagicMock()
sys.modules["discord.ext"] = MagicMock()
sys.modules["discord.ext.commands"] = MagicMock()
sys.modules["cogs.views.shop_views"] = MagicMock()
sys.modules["cogs.ui.shop_embeds"] = MagicMock()
sys.modules["utils.permissions"] = MagicMock()
sys.modules["utils.premium"] = MagicMock()
sys.modules["core.interfaces.member_interfaces"] = MagicMock()
sys.modules["core.interfaces.premium_interfaces"] = MagicMock()
sys.modules["datasources.queries"] = MagicMock()

from cogs.commands.shop import ShopCog  # noqa: E402


@pytest.mark.asyncio
async def test_shop_command_execution(mock_bot_with_services, mock_discord_context):
    """Test shop command executes without errors"""
    # Arrange
    with patch("cogs.commands.shop.RoleShopView") as mock_view, patch(
        "cogs.commands.shop.create_shop_embed"
    ) as mock_embed:

        mock_view.return_value = MagicMock()
        mock_view.return_value.role_price_map = {}
        mock_embed.return_value = MagicMock()

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.shop(mock_discord_context)

    # Assert - command executed successfully
    mock_discord_context.reply.assert_called_once()
    assert mock_view.called
    assert mock_embed.called


@pytest.mark.asyncio
async def test_addbalance_command_execution(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance command executes without errors"""
    # Arrange
    amount = 500

    with patch("cogs.commands.shop.HandledPaymentQueries.add_payment") as mock_add_payment:
        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)

    # Assert - command executed successfully
    mock_add_payment.assert_called_once()
    mock_discord_context.reply.assert_called_once()


@pytest.mark.asyncio
async def test_assign_payment_command_execution(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test assign_payment command executes without errors"""
    # Arrange
    payment_id = 123

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        # Setup mock payment
        mock_payment = MagicMock()
        mock_payment.id = payment_id
        mock_payment.amount = 500
        mock_payment.member_id = None
        mock_get_payment.return_value = mock_payment

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert - command executed successfully
    mock_get_payment.assert_called_once()
    assert mock_payment.member_id is not None  # Payment was assigned


@pytest.mark.asyncio
async def test_payments_command_execution(mock_bot_with_services, mock_discord_context):
    """Test payments command executes without errors"""
    # Arrange
    with patch("cogs.commands.shop.HandledPaymentQueries.get_last_payments") as mock_get_payments, patch(
        "cogs.commands.shop.PaymentsView"
    ) as mock_view:

        # Setup mock payments
        mock_payments = [MagicMock(id=1, member_id=123, name="Test", amount=100, payment_type="test")]
        mock_get_payments.return_value = mock_payments
        mock_view.return_value = MagicMock()

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.all_payments(mock_discord_context)

    # Assert - command executed successfully
    mock_get_payments.assert_called_once()
    mock_discord_context.send.assert_called_once()


@pytest.mark.asyncio
async def test_set_role_expiry_command_execution(mock_bot_with_services, mock_discord_context, mock_discord_member):
    """Test set_role_expiry command executes without errors"""
    # Arrange
    hours = 24

    # Act
    shop_cog = ShopCog(mock_bot_with_services)
    await shop_cog.set_role_expiry(mock_discord_context, mock_discord_member, hours)

    # Assert - command executed successfully
    mock_discord_context.reply.assert_called_once()


@pytest.mark.asyncio
async def test_force_check_roles_command_execution(mock_bot_with_services, mock_discord_context):
    """Test force_check_roles command executes without errors"""
    # Arrange
    mock_discord_context.guild.roles = []  # No roles to check

    # Act
    shop_cog = ShopCog(mock_bot_with_services)
    await shop_cog.force_check_roles(mock_discord_context)

    # Assert - command executed successfully
    mock_discord_context.reply.assert_called_once()


def test_shop_cog_initialization(mock_bot_with_services):
    """Test ShopCog can be initialized"""
    # Act
    shop_cog = ShopCog(mock_bot_with_services)

    # Assert
    assert shop_cog.bot == mock_bot_with_services
    assert hasattr(shop_cog, "shop")
    assert hasattr(shop_cog, "add_balance")
    assert hasattr(shop_cog, "assign_payment")
    assert hasattr(shop_cog, "all_payments")
    assert hasattr(shop_cog, "set_role_expiry")
    assert hasattr(shop_cog, "force_check_roles")


def test_shop_cog_setup_function():
    """Test cog setup function exists"""
    from cogs.commands.shop import setup

    assert callable(setup)


@pytest.mark.asyncio
async def test_shop_command_with_member_parameter(mock_bot_with_services, mock_discord_context, mock_discord_member):
    """Test shop command with specific member parameter"""
    # Arrange
    with patch("cogs.commands.shop.RoleShopView") as mock_view, patch(
        "cogs.commands.shop.create_shop_embed"
    ) as mock_embed:

        mock_view.return_value = MagicMock()
        mock_view.return_value.role_price_map = {}
        mock_embed.return_value = MagicMock()

        # Act - call shop command with member parameter
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.shop(mock_discord_context, mock_discord_member)

    # Assert - command executed successfully with member parameter
    mock_discord_context.reply.assert_called_once()
    # View should be created with the specified member
    mock_view.assert_called_once()


@pytest.mark.asyncio
async def test_assign_payment_not_found(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test assign_payment command when payment not found"""
    # Arrange
    payment_id = 999

    with patch("cogs.commands.shop.HandledPaymentQueries.get_payment_by_id") as mock_get_payment:
        mock_get_payment.return_value = None  # Payment not found

        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.assign_payment(mock_discord_context, payment_id, mock_discord_user)

    # Assert - error message sent
    mock_discord_context.send.assert_called_once()
    call_args = mock_discord_context.send.call_args[0][0]
    assert "Nie znaleziono płatności o ID:" in call_args
