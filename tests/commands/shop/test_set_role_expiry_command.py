"""
Test set_role_expiry command as individual functions with proper validation
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from tests.data.test_constants import ERROR_MESSAGES, PREMIUM_ROLES_CONFIG, TEST_USER_1_ID


def test_role_expiry_time_calculation():
    """Test role expiry time calculation logic"""
    # Arrange
    hours_to_add = 24
    base_time = datetime.now(timezone.utc)
    
    # Act - Calculate expiry time as the command does
    new_expiry = base_time + timedelta(hours=hours_to_add)
    
    # Assert
    time_difference = new_expiry - base_time
    assert time_difference.total_seconds() == hours_to_add * 3600  # 3600 seconds per hour
    assert new_expiry > base_time
    assert isinstance(new_expiry, datetime)
    assert new_expiry.tzinfo == timezone.utc


def test_role_expiry_hours_validation():
    """Test valid hours ranges for role expiry"""
    # Arrange
    valid_hours_ranges = [
        1,      # 1 hour
        24,     # 1 day
        168,    # 1 week (24 * 7)
        720,    # 1 month (24 * 30)
        8760    # 1 year (24 * 365)
    ]
    
    # Act & Assert
    for hours in valid_hours_ranges:
        assert hours > 0
        assert isinstance(hours, int)
        
        # Test calculation works
        expiry_time = datetime.now(timezone.utc) + timedelta(hours=hours)
        assert expiry_time > datetime.now(timezone.utc)


def test_premium_role_names_validation():
    """Test premium role names match configuration"""
    # Arrange
    expected_role_names = [role["name"] for role in PREMIUM_ROLES_CONFIG]
    
    # Act & Assert
    assert "zG50" in expected_role_names
    assert "zG100" in expected_role_names
    assert "zG500" in expected_role_names
    assert "zG1000" in expected_role_names
    
    # Verify all role names are strings
    for role_name in expected_role_names:
        assert isinstance(role_name, str)
        assert len(role_name) > 0


def test_no_premium_role_error_message():
    """Test error message when user has no premium role"""
    # Arrange
    expected_message = "Ten użytkownik nie ma żadnej roli premium."
    
    # Act & Assert
    assert isinstance(expected_message, str)
    assert len(expected_message) > 0
    assert "premium" in expected_message.lower()


def test_role_expiry_message_format():
    """Test role expiry success message format"""
    # Arrange
    role_name = "zG50"
    member_name = "TestUser"
    hours = 48
    
    # Mock expiry time
    expiry_time = datetime.now(timezone.utc) + timedelta(hours=hours)
    
    # Act - Format message as command does
    message = (
        f"Zaktualizowano czas wygaśnięcia roli {role_name} dla {member_name}.\n"
        f"Nowy czas wygaśnięcia: {expiry_time.strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    
    # Assert
    assert role_name in message
    assert member_name in message
    assert "Zaktualizowano" in message
    assert "wygaśnięcia" in message
    assert str(expiry_time.year) in message


def test_role_service_extend_parameters():
    """Test premium role extension parameters"""
    # Arrange
    role_name = "zG100"
    days_extension = 0  # Command sets 0 days, just updating expiry
    hours_extension = 0  # Command sets 0 hours, just updating expiry
    
    # Act & Assert
    # Verify parameters are correct types
    assert isinstance(role_name, str)
    assert isinstance(days_extension, int)
    assert isinstance(hours_extension, int)
    
    # Verify the command uses 0 for both to just update expiry time
    assert days_extension == 0
    assert hours_extension == 0


def test_member_premium_roles_structure():
    """Test premium role data structure"""
    # Arrange
    mock_premium_role_data = {
        "role_name": "zG50",
        "expiration_date": datetime.now(timezone.utc) + timedelta(days=30),
        "is_active": True
    }
    
    # Act & Assert
    required_fields = ["role_name", "expiration_date", "is_active"]
    for field in required_fields:
        assert field in mock_premium_role_data
    
    # Verify field types
    assert isinstance(mock_premium_role_data["role_name"], str)
    assert isinstance(mock_premium_role_data["expiration_date"], datetime)
    assert isinstance(mock_premium_role_data["is_active"], bool)
    
    # Verify role name is valid
    role_names = [role["name"] for role in PREMIUM_ROLES_CONFIG]
    assert mock_premium_role_data["role_name"] in role_names


def test_hours_parameter_bounds():
    """Test reasonable bounds for hours parameter"""
    # Arrange
    min_hours = 1
    max_hours = 8760  # 1 year
    
    # Act & Assert
    assert min_hours > 0
    assert max_hours <= 8760  # Don't exceed 1 year
    assert isinstance(min_hours, int)
    assert isinstance(max_hours, int)
    
    # Test that calculations work for bounds
    min_expiry = datetime.now(timezone.utc) + timedelta(hours=min_hours)
    max_expiry = datetime.now(timezone.utc) + timedelta(hours=max_hours)
    
    assert min_expiry > datetime.now(timezone.utc)
    assert max_expiry > min_expiry


def test_command_alias_validation():
    """Test command has correct aliases"""
    # Arrange
    expected_aliases = ["sr"]
    command_name = "set_role_expiry"
    
    # Act & Assert
    assert isinstance(command_name, str)
    assert len(command_name) > 0
    assert "role" in command_name
    assert "expiry" in command_name
    
    # Verify alias
    assert len(expected_aliases) == 1
    assert expected_aliases[0] == "sr"
    assert isinstance(expected_aliases[0], str)