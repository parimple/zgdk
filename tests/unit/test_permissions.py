"""Unit tests for permission system."""
import pytest
from unittest.mock import Mock, MagicMock
from utils.permissions import check_permission_level, PermissionLevel


@pytest.mark.unit
class TestPermissionSystem:
    """Test permission system functionality."""
    
    @pytest.mark.unit
    def test_owner_permission_with_owner_ids_list(self):
        """Test owner permission with owner_ids list."""
        # Mock bot and config
        bot = Mock()
        bot.config = {
            "owner_ids": [123456789, 987654321],
            "owner_id": 123456789
        }
        
        # Mock member
        member = Mock()
        member.id = 987654321
        
        # Test
        result = check_permission_level(bot, member, PermissionLevel.OWNER)
        assert result is True
    
    @pytest.mark.unit
    def test_non_owner_permission(self):
        """Test non-owner user."""
        bot = Mock()
        bot.config = {
            "owner_ids": [123456789],
            "owner_id": 123456789
        }
        
        member = Mock()
        member.id = 555555555  # Not in owner list
        
        result = check_permission_level(bot, member, PermissionLevel.OWNER)
        assert result is False
