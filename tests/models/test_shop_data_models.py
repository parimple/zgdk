"""
Shop command tests using realistic constants from config.yml
"""
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from tests.data.test_constants import (
    BOT_CONFIG,
    ERROR_MESSAGES,
    MAIN_OWNER_ID,
    PREMIUM_ROLES_CONFIG,
    ROLE_ZG50_ID,
    ROLE_ZG100_ID,
    SAMPLE_PAYMENT_DATA,
    TEST_USER_1_ID,
    WALLET_BALANCES,
)


def test_premium_roles_configuration():
    """Test that premium roles configuration matches config.yml"""
    # Arrange & Act
    zg50_config = next(role for role in PREMIUM_ROLES_CONFIG if role["name"] == "zG50")
    zg100_config = next(role for role in PREMIUM_ROLES_CONFIG if role["name"] == "zG100")
    
    # Assert
    assert zg50_config["price"] == 49
    assert zg50_config["moderator_count"] == 1
    assert zg50_config["team_size"] == 0
    
    assert zg100_config["price"] == 99
    assert zg100_config["moderator_count"] == 2
    assert zg100_config["team_size"] == 10


def test_wallet_balances_realistic():
    """Test wallet balance constants are realistic"""
    # Arrange & Act & Assert
    assert WALLET_BALANCES["empty"] == 0
    assert WALLET_BALANCES["zg50_price"] == 49
    assert WALLET_BALANCES["zg100_price"] == 99
    assert WALLET_BALANCES["medium"] >= WALLET_BALANCES["zg100_price"]
    assert WALLET_BALANCES["high"] >= WALLET_BALANCES["zg500_price"]


def test_bot_config_structure():
    """Test bot configuration structure"""
    # Arrange & Act & Assert
    assert "admin_roles" in BOT_CONFIG
    assert "premium_roles" in BOT_CONFIG
    assert "emojis" in BOT_CONFIG
    assert "channels" in BOT_CONFIG
    
    assert len(BOT_CONFIG["premium_roles"]) == 4
    assert BOT_CONFIG["prefix"] == ","


def test_error_messages_localized():
    """Test error messages are in Polish (localized)"""
    # Arrange & Act & Assert
    assert "Brak" in ERROR_MESSAGES["no_balance"]
    assert "Nie znaleziono" in ERROR_MESSAGES["role_not_found"]
    assert "administratorów" in ERROR_MESSAGES["admin_only"]


def test_role_ids_realistic():
    """Test role IDs are realistic Discord snowflakes"""
    # Arrange & Act & Assert
    assert ROLE_ZG50_ID > 1000000000000000000  # Valid Discord snowflake
    assert ROLE_ZG100_ID > 1000000000000000000
    assert ROLE_ZG50_ID != ROLE_ZG100_ID  # Different roles have different IDs


def test_user_ids_realistic():
    """Test user IDs are realistic Discord snowflakes"""
    # Arrange & Act & Assert
    assert MAIN_OWNER_ID > 100000000000000000  # Valid Discord user ID
    assert TEST_USER_1_ID > 100000000000000000
    assert MAIN_OWNER_ID != TEST_USER_1_ID


def test_sample_payment_data_structure():
    """Test sample payment data has correct structure"""
    # Arrange & Act & Assert
    assert "id" in SAMPLE_PAYMENT_DATA
    assert "member_id" in SAMPLE_PAYMENT_DATA
    assert "amount" in SAMPLE_PAYMENT_DATA
    assert "payment_type" in SAMPLE_PAYMENT_DATA
    
    assert SAMPLE_PAYMENT_DATA["member_id"] == TEST_USER_1_ID
    assert SAMPLE_PAYMENT_DATA["amount"] > 0
    assert SAMPLE_PAYMENT_DATA["payment_type"] in ["role_purchase", "balance_add", "refund"]


def test_premium_roles_features():
    """Test premium roles have expected features"""
    # Arrange
    zg500_config = next(role for role in PREMIUM_ROLES_CONFIG if role["name"] == "zG500")
    zg1000_config = next(role for role in PREMIUM_ROLES_CONFIG if role["name"] == "zG1000")
    
    # Act & Assert
    assert "auto_kick" in zg500_config
    assert zg500_config["auto_kick"] == 1
    
    assert "auto_kick" in zg1000_config
    assert zg1000_config["auto_kick"] == 3
    
    assert len(zg1000_config["features"]) > len(zg500_config["features"])


@pytest.mark.asyncio
async def test_mock_shop_with_realistic_data():
    """Test shop mock with realistic constants"""
    # Arrange
    mock_shop_cog = MagicMock()
    
    # Mock database member with realistic balance
    db_member = MagicMock()
    db_member.wallet_balance = WALLET_BALANCES["medium"]  # 1000
    db_member.id = TEST_USER_1_ID
    
    # Mock premium role data
    premium_role_data = {
        "role_id": ROLE_ZG50_ID,
        "role_name": "zG50", 
        "expiration_date": datetime.now(timezone.utc),
        "is_active": True
    }
    
    async def mock_shop_method(ctx, member=None):
        # Simulate shop logic with realistic data
        if db_member.wallet_balance >= WALLET_BALANCES["zg50_price"]:
            return "Can afford zG50"
        else:
            return ERROR_MESSAGES["no_balance"]
    
    mock_shop_cog.shop = mock_shop_method
    mock_ctx = MagicMock()
    
    # Act
    result = await mock_shop_cog.shop(mock_ctx)
    
    # Assert
    assert result == "Can afford zG50"


def test_premium_role_pricing_progression():
    """Test that premium role prices increase logically"""
    # Arrange
    roles = sorted(PREMIUM_ROLES_CONFIG, key=lambda x: x["price"])
    
    # Act & Assert
    assert roles[0]["name"] == "zG50"
    assert roles[1]["name"] == "zG100" 
    assert roles[2]["name"] == "zG500"
    assert roles[3]["name"] == "zG1000"
    
    # Verify price progression
    for i in range(len(roles) - 1):
        assert roles[i]["price"] < roles[i + 1]["price"]


def test_moderator_count_progression():
    """Test that moderator counts increase with role tier"""
    # Arrange
    roles = sorted(PREMIUM_ROLES_CONFIG, key=lambda x: x["price"])
    
    # Act & Assert
    moderator_counts = [role["moderator_count"] for role in roles]
    
    # Verify moderator count progression
    for i in range(len(moderator_counts) - 1):
        assert moderator_counts[i] <= moderator_counts[i + 1]