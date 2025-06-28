"""
Tests for addbalance command execution
"""
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import sys

# Mock Discord before any imports
sys.modules['discord'] = MagicMock()
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['utils.permissions'] = MagicMock()
sys.modules['core.interfaces.member_interfaces'] = MagicMock()
sys.modules['datasources.queries'] = MagicMock()

# Mock utils.premium but allow PaymentData import
from unittest.mock import MagicMock as MockModule
import types
mock_premium = types.ModuleType('utils.premium')

# Create a real PaymentData class for testing
class PaymentData:
    def __init__(self, name, amount, paid_at, payment_type):
        self.name = name
        self.amount = amount
        self.paid_at = paid_at
        self.payment_type = payment_type

mock_premium.PaymentData = PaymentData
mock_premium.PremiumManager = MagicMock()
mock_premium.TipplyDataProvider = MagicMock()
sys.modules['utils.premium'] = mock_premium

# Also mock utils module
mock_utils = types.ModuleType('utils')
mock_utils.PremiumManager = MagicMock()
mock_utils.TipplyDataProvider = MagicMock()
sys.modules['utils'] = mock_utils

from cogs.commands.shop import ShopCog


@pytest.mark.asyncio
@patch('cogs.commands.shop.HandledPaymentQueries.add_payment', new_callable=AsyncMock)
async def test_addbalance_positive_amount(mock_add_payment, mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance command with positive amount"""
    # Arrange
    amount = 500
    mock_session = mock_bot_with_services.get_db.return_value.__aenter__.return_value
    
    # Act
    shop_cog = ShopCog(mock_bot_with_services)
    await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)
    
    # Assert payment was added with correct parameters
    call_args = mock_add_payment.call_args
    assert call_args[0][0] == mock_session  # session
    assert call_args[0][1] == mock_discord_user.id  # member_id
    assert call_args[0][2] == mock_discord_context.author.display_name  # name
    assert call_args[0][3] == amount  # amount
    assert call_args[0][5] == "command"  # payment_type
    
    mock_discord_context.reply.assert_called_once()
    
    # Check reply message
    reply_message = mock_discord_context.reply.call_args[0][0]
    assert f"Dodano {amount}" in reply_message
    assert mock_discord_user.mention in reply_message


@pytest.mark.asyncio
async def test_addbalance_negative_amount(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance command with negative amount (deduction)"""
    # Arrange
    amount = -100
    
    with patch('cogs.commands.shop.HandledPaymentQueries.add_payment') as mock_add_payment:
        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)
    
    # Assert
    mock_add_payment.assert_called_once()
    mock_discord_context.reply.assert_called_once()
    
    # Check reply message contains negative amount
    reply_message = mock_discord_context.reply.call_args[0][0]
    assert str(amount) in reply_message


@pytest.mark.asyncio
async def test_addbalance_zero_amount(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance command with zero amount"""
    # Arrange
    amount = 0
    
    with patch('cogs.commands.shop.HandledPaymentQueries.add_payment') as mock_add_payment:
        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)
    
    # Assert
    mock_add_payment.assert_called_once()
    mock_discord_context.reply.assert_called_once()


@pytest.mark.asyncio
async def test_addbalance_large_amount(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance command with large amount"""
    # Arrange
    amount = 999999
    
    with patch('cogs.commands.shop.HandledPaymentQueries.add_payment') as mock_add_payment:
        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)
    
    # Assert
    mock_add_payment.assert_called_once()
    mock_discord_context.reply.assert_called_once()


@pytest.mark.asyncio
async def test_addbalance_payment_data_creation(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance creates correct PaymentData"""
    # Arrange
    amount = 500
    
    with patch('cogs.commands.shop.HandledPaymentQueries.add_payment') as mock_add_payment:
        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)
    
    # Assert payment data structure
    call_args = mock_add_payment.call_args[0]
    
    # Check payment parameters
    assert call_args[1] == mock_discord_user.id  # member_id
    assert call_args[2] == mock_discord_context.author.display_name  # name
    assert call_args[3] == amount  # amount
    assert call_args[5] == "command"  # payment_type


@pytest.mark.asyncio
async def test_addbalance_member_service_integration(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance integrates with member service"""
    # Arrange
    amount = 500
    
    with patch('cogs.commands.shop.HandledPaymentQueries.add_payment'):
        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)
    
    # Assert member service was called
    member_service = mock_bot_with_services.get_service('IMemberService')
    member_service.get_or_create_member.assert_called_once_with(mock_discord_user)
    member_service.update_member_info.assert_called_once()


@pytest.mark.asyncio
async def test_addbalance_database_session_usage(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance uses database session correctly"""
    # Arrange
    amount = 500
    
    with patch('cogs.commands.shop.HandledPaymentQueries.add_payment'):
        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)
    
    # Assert database session was used
    mock_bot_with_services.get_db.assert_called_once()


def test_addbalance_command_signature():
    """Test addbalance command has correct signature"""
    # Test the command exists and has correct parameters
    shop_cog = ShopCog(None)
    assert hasattr(shop_cog, 'add_balance')
    assert callable(shop_cog.add_balance)


@pytest.mark.asyncio  
async def test_addbalance_commit_transaction(mock_bot_with_services, mock_discord_context, mock_discord_user):
    """Test addbalance commits database transaction"""
    # Arrange
    amount = 500
    mock_session = mock_bot_with_services.get_db.return_value.__aenter__.return_value
    
    with patch('cogs.commands.shop.HandledPaymentQueries.add_payment'):
        # Act
        shop_cog = ShopCog(mock_bot_with_services)
        await shop_cog.add_balance(mock_discord_context, mock_discord_user, amount)
    
    # Assert transaction was committed
    mock_session.commit.assert_called_once()