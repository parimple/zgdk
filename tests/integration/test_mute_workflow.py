"""
Integration tests for complete mute/unmute workflows.
"""

import unittest
import asyncio
from tests.base.test_base import CommandTestCase
from tests.config import TEST_USER_ID
from tests.utils.assertions import assert_mute_response_valid


class TestMuteWorkflow(CommandTestCase):
    """Test complete mute/unmute workflows."""
    
    def test_txt_mute_unmute_cycle(self):
        """Test complete txt mute and unmute cycle."""
        # First mute the user
        mute_result = self.run_async(
            self.execute_command("mute txt", f"{TEST_USER_ID} 1h")
        )
        self.assert_command_success(mute_result)
        
        # Wait a bit
        self.run_async(asyncio.sleep(0.5))
        
        # Now unmute
        unmute_result = self.run_async(
            self.execute_command("unmute txt", TEST_USER_ID)
        )
        self.assert_command_success(unmute_result)
        
        # Verify responses
        mute_response = mute_result["responses"][0]
        unmute_response = unmute_result["responses"][0]
        
        self.assertTrue(
            assert_mute_response_valid(mute_response, TEST_USER_ID, "txt", is_unmute=False)
        )
        self.assertTrue(
            assert_mute_response_valid(unmute_response, TEST_USER_ID, "txt", is_unmute=True)
        )
    
    def test_multiple_mute_types(self):
        """Test applying multiple mute types to same user."""
        mute_types = ["txt", "img", "rank"]
        results = []
        
        # Apply multiple mutes
        for mute_type in mute_types:
            result = self.run_async(
                self.execute_command(f"mute {mute_type}", TEST_USER_ID)
            )
            self.assert_command_success(result)
            results.append((mute_type, result))
            
            # Small delay between commands
            self.run_async(asyncio.sleep(0.3))
        
        # Verify all mutes were applied
        for mute_type, result in results:
            response = result["responses"][0]
            self.assertTrue(
                assert_mute_response_valid(response, TEST_USER_ID, mute_type, is_unmute=False),
                f"Mute {mute_type} not properly applied"
            )
    
    def test_override_existing_mute(self):
        """Test that applying same mute type overrides existing one."""
        # First mute with 1h duration
        first_result = self.run_async(
            self.execute_command("mute img", f"{TEST_USER_ID} 1h")
        )
        self.assert_command_success(first_result)
        
        # Wait a bit
        self.run_async(asyncio.sleep(0.5))
        
        # Apply same mute with different duration
        second_result = self.run_async(
            self.execute_command("mute img", f"{TEST_USER_ID} 2h")
        )
        self.assert_command_success(second_result)
        
        # Second response should mention override
        response = second_result["responses"][0]
        desc = response["embeds"][0]["description"]
        
        # Should contain override information
        self.assertIn("Nadpisano", desc, "Should mention override of existing mute")
    
    def test_nick_mute_special_behavior(self):
        """Test nick mute special behaviors."""
        # Apply nick mute
        result = self.run_async(
            self.execute_command("mute nick", TEST_USER_ID)
        )
        self.assert_command_success(result)
        
        response = result["responses"][0]
        desc = response["embeds"][0]["description"]
        
        # Should mention premium requirement
        self.assertIn("zakup dowolną rangę premium", desc)
        
        # Nick mute doesn't support custom duration
        # Should always be 30 days
        self.assertIn("Nałożono karę", desc)


if __name__ == "__main__":
    unittest.main()