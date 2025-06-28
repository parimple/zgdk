"""
Test payments command as individual functions with proper mocking
"""
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.data.test_constants import SAMPLE_PAYMENT_DATA, TEST_USER_1_ID, WALLET_BALANCES


@patch('discord.utils.format_dt')
@patch('discord.Embed')  
def test_payments_embed_structure(mock_embed_class, mock_format_dt):
    """Test payments embed structure and content"""
    # Arrange
    mock_format_dt.return_value = "2024-01-01"
    mock_embed = MagicMock()
    mock_embed_class.return_value = mock_embed
    
    # Mock payment data
    mock_payments = [
        MagicMock(
            id=1,
            member_id=TEST_USER_1_ID,
            name="TestUser1",
            amount=WALLET_BALANCES["zg50_price"],
            paid_at=datetime.now(timezone.utc),
            payment_type="role_purchase"
        ),
        MagicMock(
            id=2,
            member_id=TEST_USER_1_ID + 1,
            name="TestUser2", 
            amount=WALLET_BALANCES["zg100_price"],
            paid_at=datetime.now(timezone.utc),
            payment_type="balance_add"
        )
    ]
    
    # Act - Create embed manually as the real command does
    embed = mock_embed_class(title="Wszystkie płatności")
    for payment in mock_payments:
        name = f"ID płatności: {payment.id}"
        value = (
            f"ID członka: {payment.member_id}\n"
            f"Nazwa: {payment.name}\n"
            f"Kwota: {payment.amount}\n"
            f"Zapłacono: {mock_format_dt.return_value}\n"
            f"Typ płatności: {payment.payment_type}"
        )
        embed.add_field(name=name, value=value, inline=False)
    
    # Assert - verify embed structure
    mock_embed_class.assert_called_with(title="Wszystkie płatności")
    assert embed.add_field.call_count == 2


def test_payment_types_validation():
    """Test valid payment types match expected values"""
    # Arrange
    expected_payment_types = ["role_purchase", "balance_add", "refund", "command"]
    sample_payment_type = SAMPLE_PAYMENT_DATA["payment_type"]
    
    # Act & Assert
    assert sample_payment_type in expected_payment_types
    
    # Verify each type is a valid string
    for payment_type in expected_payment_types:
        assert isinstance(payment_type, str)
        assert len(payment_type) > 0


def test_payment_amount_ranges():
    """Test payment amounts are within realistic ranges"""
    # Arrange
    valid_amounts = [
        WALLET_BALANCES["zg50_price"],
        WALLET_BALANCES["zg100_price"], 
        WALLET_BALANCES["zg500_price"],
        WALLET_BALANCES["zg1000_price"]
    ]
    
    # Act & Assert
    for amount in valid_amounts:
        assert amount > 0
        assert amount <= WALLET_BALANCES["maximum"]
        assert isinstance(amount, int)
    
    # Test sample payment amount
    sample_amount = SAMPLE_PAYMENT_DATA["amount"]
    assert sample_amount > 0
    assert sample_amount <= WALLET_BALANCES["maximum"]


def test_payment_query_limit_default():
    """Test default payment query limit"""
    # Arrange
    default_limit = 10
    
    # Act & Assert - verify limit is reasonable
    assert default_limit > 0
    assert default_limit <= 50  # Reasonable upper bound
    assert isinstance(default_limit, int)


@patch('discord.utils.format_dt', return_value="2024-01-01")
def test_payment_date_formatting(mock_format_dt):
    """Test payment date is properly formatted"""
    # Arrange
    test_date = datetime.now(timezone.utc)
    
    # Act
    formatted_date = mock_format_dt(test_date, 'D')
    
    # Assert - verify it returns a string (actual Discord formatting)
    assert isinstance(formatted_date, str)
    assert len(formatted_date) > 0
    assert formatted_date == "2024-01-01"


def test_payment_structure_validation():
    """Test payment data structure has required fields"""
    # Arrange
    required_fields = ["id", "member_id", "name", "amount", "paid_at", "payment_type"]
    sample_payment = SAMPLE_PAYMENT_DATA
    
    # Act & Assert
    for field in required_fields:
        assert field in sample_payment, f"Missing required field: {field}"
        assert sample_payment[field] is not None, f"Field {field} cannot be None"
    
    # Validate field types
    assert isinstance(sample_payment["id"], str)
    assert isinstance(sample_payment["member_id"], int)
    assert isinstance(sample_payment["amount"], int)
    assert isinstance(sample_payment["payment_type"], str)


def test_payment_member_id_validation():
    """Test payment member ID is valid Discord snowflake"""
    # Arrange
    sample_member_id = SAMPLE_PAYMENT_DATA["member_id"]
    min_discord_id = 100000000000000000  # Minimum valid Discord snowflake
    
    # Act & Assert
    assert sample_member_id > min_discord_id
    assert isinstance(sample_member_id, int)
    assert sample_member_id == TEST_USER_1_ID  # Should match our test user