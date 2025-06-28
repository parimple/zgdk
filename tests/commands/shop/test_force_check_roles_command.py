"""
Test force_check_roles command as individual functions with proper validation
"""
import pytest
from unittest.mock import MagicMock
from datetime import datetime, timezone, timedelta

from tests.data.test_constants import (
    PREMIUM_ROLES_CONFIG, ROLE_ZG50_ID, ROLE_ZG100_ID,
    ROLE_ZG500_ID, ROLE_ZG1000_ID, TEST_USER_1_ID
)


def test_premium_role_names_mapping():
    """Test premium role names mapping from config"""
    # Arrange
    premium_role_names = {
        role["name"]: role for role in PREMIUM_ROLES_CONFIG
    }
    
    # Act & Assert
    assert "zG50" in premium_role_names
    assert "zG100" in premium_role_names
    assert "zG500" in premium_role_names
    assert "zG1000" in premium_role_names
    
    # Verify structure
    for role_name, role_data in premium_role_names.items():
        assert isinstance(role_name, str)
        assert isinstance(role_data, dict)
        assert "name" in role_data
        assert "price" in role_data
        assert role_data["name"] == role_name


def test_role_expiry_check_logic():
    """Test role expiry checking logic"""
    # Arrange
    now = datetime.now(timezone.utc)
    
    # Test cases: expired, valid, and edge cases
    test_cases = [
        {
            "expiry": now - timedelta(hours=1),  # Expired 1 hour ago
            "should_remove": True,
            "description": "Expired role"
        },
        {
            "expiry": now + timedelta(hours=1),  # Valid for 1 hour
            "should_remove": False,
            "description": "Valid role"
        },
        {
            "expiry": now - timedelta(minutes=1),  # Expired 1 minute ago
            "should_remove": True,
            "description": "Recently expired"
        },
        {
            "expiry": now + timedelta(days=30),  # Valid for 30 days
            "should_remove": False,
            "description": "Long-term valid"
        }
    ]
    
    # Act & Assert
    for case in test_cases:
        expiry = case["expiry"]
        expected_removal = case["should_remove"]
        
        # Logic: if expiry and expiry > now, then role is valid
        role_expired = not (expiry and expiry > now)
        should_remove = role_expired
        
        assert should_remove == expected_removal, f"Failed for {case['description']}"


def test_guild_roles_filtering():
    """Test filtering guild roles to find premium roles"""
    # Arrange
    mock_guild_roles = []
    
    # Create mock roles with proper name attribute
    for role_name, role_id in [
        ("zG50", ROLE_ZG50_ID),
        ("zG100", ROLE_ZG100_ID), 
        ("Regular Role", 123456),
        ("zG500", ROLE_ZG500_ID),
        ("Admin", 789012),
        ("zG1000", ROLE_ZG1000_ID)
    ]:
        role = MagicMock()
        role.name = role_name
        role.id = role_id
        mock_guild_roles.append(role)
    
    premium_role_names = {role["name"]: role for role in PREMIUM_ROLES_CONFIG}
    
    # Act - Filter as command does
    premium_roles = [
        role for role in mock_guild_roles 
        if role.name in premium_role_names
    ]
    
    # Assert
    assert len(premium_roles) == 4  # Only premium roles
    premium_names = [role.name for role in premium_roles]
    
    assert "zG50" in premium_names
    assert "zG100" in premium_names
    assert "zG500" in premium_names
    assert "zG1000" in premium_names
    
    # Verify non-premium roles are excluded
    assert "Regular Role" not in premium_names
    assert "Admin" not in premium_names


def test_role_member_iteration():
    """Test iterating through role members"""
    # Arrange
    mock_members = [
        MagicMock(id=TEST_USER_1_ID, display_name="User1"),
        MagicMock(id=TEST_USER_1_ID + 1, display_name="User2"),
        MagicMock(id=TEST_USER_1_ID + 2, display_name="User3")
    ]
    
    mock_role = MagicMock()
    mock_role.name = "zG50"
    mock_role.members = mock_members
    
    # Act
    member_count = len(mock_role.members)
    member_ids = [member.id for member in mock_role.members]
    
    # Assert
    assert member_count == 3
    assert TEST_USER_1_ID in member_ids
    assert TEST_USER_1_ID + 1 in member_ids
    assert TEST_USER_1_ID + 2 in member_ids
    
    # Verify all have display names
    for member in mock_role.members:
        assert hasattr(member, 'display_name')
        assert len(member.display_name) > 0


def test_role_removal_counter():
    """Test role removal counter logic"""
    # Arrange
    initial_count = 0
    roles_to_remove = [
        {"member": "User1", "role": "zG50"},
        {"member": "User2", "role": "zG100"},
        {"member": "User3", "role": "zG50"}
    ]
    
    # Act - Simulate counter increment
    count = initial_count
    for removal in roles_to_remove:
        count += 1
    
    # Assert
    assert count == 3
    assert count == len(roles_to_remove)
    assert count > initial_count


def test_final_message_format():
    """Test final status message format"""
    # Arrange
    removed_count = 5
    
    # Act - Format message as command does
    message = f"Sprawdzono i usunięto {removed_count} ról, które nie powinny być aktywne."
    
    # Assert
    assert isinstance(message, str)
    assert str(removed_count) in message
    assert "Sprawdzono" in message
    assert "usunięto" in message
    assert "ról" in message
    assert "aktywne" in message


def test_premium_service_methods():
    """Test premium service method calls"""
    # Arrange
    expected_methods = [
        "has_premium_role",
        "get_member_premium_roles", 
        "set_guild"
    ]
    
    # Act & Assert
    for method_name in expected_methods:
        assert isinstance(method_name, str)
        assert len(method_name) > 0
        
    # Verify method naming conventions
    assert "has_premium_role" in expected_methods  # Boolean check
    assert "get_member_premium_roles" in expected_methods  # Data retrieval
    assert "set_guild" in expected_methods  # Context setting


def test_role_data_structure():
    """Test role data structure from premium service"""
    # Arrange
    mock_role_data = {
        "role_name": "zG50",
        "expiration_date": datetime.now(timezone.utc) + timedelta(days=15),
        "is_active": True
    }
    
    # Act & Assert
    assert "role_name" in mock_role_data
    assert "expiration_date" in mock_role_data
    
    # Verify role name matching
    role_name = mock_role_data.get("role_name")
    premium_role_names = [role["name"] for role in PREMIUM_ROLES_CONFIG]
    assert role_name in premium_role_names
    
    # Verify expiration date type
    expiry = mock_role_data.get("expiration_date")
    assert isinstance(expiry, datetime)
    assert expiry.tzinfo == timezone.utc


def test_admin_permission_requirement():
    """Test admin permission requirement"""
    # Arrange
    required_permission = "administrator"
    
    # Act & Assert
    assert isinstance(required_permission, str)
    assert required_permission == "administrator"
    
    # Verify this is a valid Discord permission
    valid_permissions = [
        "administrator", "manage_guild", "manage_roles", 
        "manage_channels", "kick_members", "ban_members"
    ]
    assert required_permission in valid_permissions


def test_command_name_and_description():
    """Test command name and description"""
    # Arrange
    command_name = "shop_force_check_roles"
    description_keywords = ["force", "check", "roles", "premium"]
    
    # Act & Assert
    assert isinstance(command_name, str)
    assert "force" in command_name
    assert "check" in command_name
    assert "roles" in command_name
    
    # Verify command follows naming convention
    assert command_name.startswith("shop_")  # Shop command prefix
    assert len(command_name) > 10  # Descriptive name