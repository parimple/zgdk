"""
Tests for bump commands.
"""

import unittest
from datetime import datetime, timedelta

from tests.base.test_base import CommandTestCase
from tests.config import TEST_USER_ID
from tests.utils.assertions import assert_has_timestamp, assert_user_mentioned


class TestBumpCommands(CommandTestCase):
    """Test bump commands functionality."""
    
    def test_bump_success(self):
        """Test successful bump command."""
        result = self.run_async(
            self.execute_command("bump", send_to_channel=True)
        )
        
        self.assert_command_success(result)
        
        # Check if success message was sent
        responses = result.get("responses", [])
        self.assertTrue(responses, "No responses received")
        
        # Verify response contains expected elements
        response = responses[0]
        content = response.get("content", "")
        
        # Should contain bump success indicators
        self.assertIn("Bump", content, "Response should mention bump")
    
    def test_bump_cooldown(self):
        """Test bump command during cooldown."""
        # First bump
        result1 = self.run_async(
            self.execute_command("bump", send_to_channel=True)
        )
        self.assert_command_success(result1)
        
        # Second bump immediately after
        result2 = self.run_async(
            self.execute_command("bump", send_to_channel=True)
        )
        
        # Should still succeed but with cooldown message
        self.assert_command_success(result2)
        
        responses = result2.get("responses", [])
        if responses:
            response = responses[0]
            content = response.get("content", "")
            # Check for cooldown indicators
            self.assertTrue(
                any(word in content.lower() for word in ["cooldown", "poczekaj", "wait"]),
                "Response should indicate cooldown"
            )
    
    def test_bump_streak(self):
        """Test bump streak tracking."""
        # This test would need mock data or database setup
        # For now, just test that command executes
        result = self.run_async(
            self.execute_command("bump", send_to_channel=True)
        )
        
        self.assert_command_success(result)
    
    def test_bump_rewards(self):
        """Test bump rewards are given."""
        # This test would need to verify database changes
        # For now, just test command execution
        result = self.run_async(
            self.execute_command("bump", send_to_channel=True)
        )
        
        self.assert_command_success(result)
        
        # In a full test, we would check:
        # - User received gold reward
        # - Bump count increased
        # - Streak was updated if applicable


class TestBumpInfoCommands(CommandTestCase):
    """Test bump info related commands."""
    
    def test_bump_check(self):
        """Test bump check command."""
        result = self.run_async(
            self.execute_command("bumpcheck")
        )
        
        self.assert_command_success(result)
        
        responses = result.get("responses", [])
        self.assertTrue(responses, "No responses received")
        
        # Should show cooldown status
        response = responses[0]
        if response.get("embeds"):
            embed = response["embeds"][0]
            self.assertIn("bump", embed.get("title", "").lower())
    
    def test_bump_top(self):
        """Test bump leaderboard command."""
        result = self.run_async(
            self.execute_command("bumptop")
        )
        
        self.assert_command_success(result)
        
        responses = result.get("responses", [])
        self.assertTrue(responses, "No responses received")
        
        # Should show leaderboard
        response = responses[0]
        if response.get("embeds"):
            embed = response["embeds"][0]
            self.assertIn("top", embed.get("title", "").lower())


if __name__ == "__main__":
    unittest.main()