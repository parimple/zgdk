"""
Minimal test to isolate the exact issue
"""
from unittest.mock import AsyncMock, patch

import pytest


def test_import_shopcog():
    """Test that ShopCog can be imported"""
    from cogs.commands.shop import ShopCog
    assert ShopCog is not None


def test_create_shopcog(mock_bot_with_services):
    """Test that ShopCog can be created"""
    from cogs.commands.shop import ShopCog
    shop_cog = ShopCog(mock_bot_with_services)
    assert shop_cog is not None
    assert shop_cog.bot == mock_bot_with_services


@pytest.mark.asyncio
async def test_shopcog_method_exists(mock_bot_with_services):
    """Test that add_balance method exists"""
    from cogs.commands.shop import ShopCog
    shop_cog = ShopCog(mock_bot_with_services)
    assert hasattr(shop_cog, 'add_balance')
    assert callable(shop_cog.add_balance)


@pytest.mark.asyncio
@patch('cogs.commands.shop.HandledPaymentQueries.add_payment', new_callable=AsyncMock)
@patch('utils.premium.PaymentData')
async def test_add_balance_minimal(mock_payment_data, mock_add_payment, mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Minimal test that patches everything that might be awaited"""
    from cogs.commands.shop import ShopCog

    # Mock PaymentData creation
    mock_payment_data.return_value = mock_payment_data
    mock_payment_data.name = "TestUser"
    mock_payment_data.amount = 500
    mock_payment_data.paid_at = None
    mock_payment_data.payment_type = "command"

    # Create ShopCog
    shop_cog = ShopCog(mock_bot_with_services)

    # CRITICAL FIX: Override the bot attribute because commands.Cog is mocked
    shop_cog.bot = mock_bot_with_services

    # Try to call add_balance
    try:
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, 500)
        print("SUCCESS: add_balance worked!")
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        # Re-raise to fail the test
        raise
