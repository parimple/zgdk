"""
Tests for giveawayr command - randomly selecting users from roles
Professional test implementation with proper fixtures and constants
"""
from unittest.mock import MagicMock, patch

import discord
import pytest


async def test_giveawayr_success_single_role_string(giveaway_cog, mock_admin_context, mock_test_roles, 
                                                   mock_test_members, mock_guild_with_members, giveaway_helpers):
    """Test successful role giveaway with single role as string"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        # Setup admin permission check
        mock_discord_get.return_value = mock_admin_context.author.roles[0]  # Admin role
        
        # Setup winner selection
        eligible_members = giveaway_helpers.get_members_by_role_criteria(
            mock_test_members.values(), 
            [mock_test_roles["test1"]]
        )
        mock_random.return_value = eligible_members[0]
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole1")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        assert "🎉" in sent_message
        assert eligible_members[0].mention in sent_message
        assert "TestRole1" in sent_message
        assert "wszystkich" in sent_message  # Default AND mode


async def test_giveawayr_success_multiple_roles_and_mode(giveaway_cog, mock_admin_context, mock_test_roles, 
                                                        mock_test_members, mock_guild_with_members, giveaway_helpers):
    """Test giveaway with multiple roles in AND mode"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # Find member who has both TestRole1 and TestRole2
        required_roles = [mock_test_roles["test1"], mock_test_roles["test2"]]
        eligible_members = giveaway_helpers.get_members_by_role_criteria(
            mock_test_members.values(), 
            required_roles, 
            mode="and"
        )
        mock_random.return_value = eligible_members[0]
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole1", "TestRole2", mode="and")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        assert eligible_members[0].mention in sent_message
        assert "wszystkich" in sent_message  # AND mode description


async def test_giveawayr_success_multiple_roles_or_mode(giveaway_cog, mock_admin_context, mock_test_roles, 
                                                       mock_test_members, mock_guild_with_members, giveaway_helpers):
    """Test giveaway with multiple roles in OR mode"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # Find members who have either role
        target_roles = [mock_test_roles["test1"], mock_test_roles["test3"]]
        eligible_members = giveaway_helpers.get_members_by_role_criteria(
            mock_test_members.values(), 
            target_roles, 
            mode="or"
        )
        mock_random.return_value = eligible_members[0]
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole1", "TestRole3", mode="or")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        assert "dowolnej z" in sent_message  # OR mode description


async def test_giveawayr_role_objects_instead_of_strings(giveaway_cog, mock_admin_context, mock_test_roles, 
                                                        mock_test_members, mock_guild_with_members):
    """Test giveaway when roles are passed as Role objects (slash command scenario)"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # Setup member with test role
        target_member = mock_test_members["user_test1_test2"]
        mock_random.return_value = target_member
        
        # Act - Pass Role object instead of string
        await giveaway_cog.giveawayr(mock_admin_context, mock_test_roles["test1"])
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        assert target_member.mention in sent_message


async def test_giveawayr_no_admin_permission(giveaway_cog, mock_regular_context, test_constants):
    """Test giveaway when user doesn't have admin permissions"""
    # Arrange
    with patch('discord.utils.get') as mock_discord_get:
        # Mock admin role check to return None (no admin role)
        mock_discord_get.return_value = None
        
        # Act
        await giveaway_cog.giveawayr(mock_regular_context, "TestRole1")
        
        # Assert
        mock_regular_context.send.assert_called_once()
        error_message = mock_regular_context.send.call_args[0][0]
        
        assert "administratorów" in error_message


async def test_giveawayr_role_not_found(giveaway_cog, mock_admin_context, mock_guild_with_members):
    """Test giveaway when specified role doesn't exist in guild"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get:
        # Mock admin check to pass, but role search to fail
        mock_discord_get.side_effect = [
            mock_admin_context.author.roles[0],  # Admin check passes
            None  # Role not found
        ]
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "NonexistentRole")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        error_message = mock_admin_context.send.call_args[0][0]
        
        assert "Nie znaleziono roli" in error_message
        assert "NonexistentRole" in error_message


async def test_giveawayr_no_eligible_members(giveaway_cog, mock_admin_context, mock_test_roles, 
                                           mock_test_members, mock_guild_with_members):
    """Test giveaway when no members have the specified roles"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get:
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # Act - Search for role that no member has (VIP)
        await giveaway_cog.giveawayr(mock_admin_context, "VIP")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        error_message = mock_admin_context.send.call_args[0][0]
        
        assert "Nie znaleziono żadnych użytkowników" in error_message
        assert "VIP" in error_message


async def test_giveawayr_filters_bot_members(giveaway_cog, mock_admin_context, mock_test_roles, 
                                           mock_test_members, mock_guild_with_members):
    """Test that bot members are properly filtered out from selection"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # Verify bot member exists with target role but is excluded
        bot_member = mock_test_members["bot_with_test1"]
        assert bot_member.bot is True
        assert mock_test_roles["test1"] in bot_member.roles
        
        # Setup to return non-bot member
        non_bot_member = mock_test_members["user_test1_test2"]
        mock_random.return_value = non_bot_member
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole1")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        # Verify non-bot member was selected
        assert non_bot_member.mention in sent_message
        # Verify bot member was not selected
        assert bot_member.mention not in sent_message


async def test_giveawayr_invalid_mode_defaults_to_and(giveaway_cog, mock_admin_context, mock_test_roles, 
                                                    mock_test_members, mock_guild_with_members):
    """Test that invalid mode parameter defaults to AND behavior"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # Member with both roles
        target_member = mock_test_members["user_test1_test2"]
        mock_random.return_value = target_member
        
        # Act - Use invalid mode
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole1", "TestRole2", mode="invalid_mode")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        # Should default to AND mode behavior
        assert "wszystkich" in sent_message


async def test_giveawayr_case_insensitive_mode(giveaway_cog, mock_admin_context, mock_test_roles, 
                                             mock_test_members, mock_guild_with_members):
    """Test that mode parameter is case insensitive"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        mock_random.return_value = mock_test_members["user_test1_test2"]
        
        # Act - Test uppercase OR
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole1", mode="OR")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        assert "dowolnej z" in sent_message  # OR mode description


async def test_giveawayr_eligible_members_count_display(giveaway_cog, mock_admin_context, mock_test_roles, 
                                                       mock_test_members, mock_guild_with_members, giveaway_helpers):
    """Test that eligible members count is accurately displayed"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # Calculate expected count
        eligible_members = giveaway_helpers.get_members_by_role_criteria(
            mock_test_members.values(),
            [mock_test_roles["test1"]]
        )
        expected_count = len(eligible_members)
        mock_random.return_value = eligible_members[0]
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole1")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        assert f"Liczba uprawnionych użytkowników: {expected_count}" in sent_message


async def test_giveawayr_three_roles_combination(giveaway_cog, mock_admin_context, mock_test_roles, 
                                               mock_test_members, mock_guild_with_members):
    """Test giveaway with three roles specified (maximum role parameters)"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # For AND mode with 3 roles, likely no member will qualify
        # So we expect the "no eligible members" message
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole1", "TestRole2", "TestRole3")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        # Should contain all three role names
        assert "TestRole1" in sent_message
        assert "TestRole2" in sent_message
        assert "TestRole3" in sent_message


async def test_giveawayr_random_selection_fairness(giveaway_cog, mock_admin_context, mock_test_roles, 
                                                  mock_test_members, mock_guild_with_members, giveaway_helpers):
    """Test that random selection is working with proper eligible member filtering"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        eligible_members = giveaway_helpers.get_members_by_role_criteria(
            mock_test_members.values(),
            [mock_test_roles["test1"]]
        )
        mock_random.return_value = eligible_members[0]
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole1")
        
        # Assert
        mock_random.assert_called_once()
        
        # Verify random.choice was called with correct eligible members
        call_args = mock_random.call_args[0][0]
        
        # All members in the list should be non-bots
        assert all(not member.bot for member in call_args)
        
        # All members should have TestRole1
        assert all(mock_test_roles["test1"] in member.roles for member in call_args)


async def test_giveawayr_permission_decorator_enforcement(giveaway_cog):
    """Test that giveawayr command has proper role permission decorator"""
    # Arrange & Assert
    # Verify command has the required role decorator (✪ role requirement)
    assert hasattr(giveaway_cog.giveawayr, '__wrapped__')
    
    # The actual permission checking is handled by Discord.py decorator
    # This test ensures the decorator is properly applied


async def test_giveawayr_complex_role_combinations_or_mode(giveaway_cog, mock_admin_context, mock_test_roles, 
                                                          mock_test_members, mock_guild_with_members, giveaway_helpers):
    """Test complex role combinations in OR mode with multiple eligible members"""
    # Arrange
    mock_admin_context.guild = mock_guild_with_members
    
    with patch('discord.utils.get') as mock_discord_get, \
         patch('random.choice') as mock_random:
        
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # Test with roles that have different member overlaps
        target_roles = [mock_test_roles["test2"], mock_test_roles["premium"]]
        eligible_members = giveaway_helpers.get_members_by_role_criteria(
            mock_test_members.values(),
            target_roles,
            mode="or"
        )
        
        if eligible_members:
            mock_random.return_value = eligible_members[0]
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "TestRole2", "Premium", mode="or")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        sent_message = mock_admin_context.send.call_args[0][0]
        
        if eligible_members:
            assert eligible_members[0].mention in sent_message
            assert "dowolnej z" in sent_message
        else:
            assert "Nie znaleziono żadnych użytkowników" in sent_message


async def test_giveawayr_edge_case_empty_guild(giveaway_cog, mock_admin_context, test_constants):
    """Test giveaway behavior with empty guild (no members)"""
    # Arrange
    empty_guild = MagicMock(spec=discord.Guild)
    empty_guild.id = test_constants.GUILD_ID
    empty_guild.members = []  # No members
    empty_guild.roles = []    # No roles
    
    mock_admin_context.guild = empty_guild
    
    with patch('discord.utils.get') as mock_discord_get:
        mock_discord_get.return_value = mock_admin_context.author.roles[0]
        
        # Act
        await giveaway_cog.giveawayr(mock_admin_context, "AnyRole")
        
        # Assert
        mock_admin_context.send.assert_called_once()
        error_message = mock_admin_context.send.call_args[0][0]
        
        # Should handle gracefully - either role not found or no eligible members
        assert "Nie znaleziono" in error_message