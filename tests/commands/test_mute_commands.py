"""
Tests for mute/unmute commands.
"""

import unittest

from tests.base.test_base import CommandTestCase
from tests.config import TEST_MUTE_DURATIONS, TEST_USER_ID
from tests.utils.assertions import assert_has_timestamp, assert_mute_response_valid


class TestMuteCommands(CommandTestCase):
    """Test mute commands functionality."""

    def test_mute_txt_default_duration(self):
        """Test mute txt with default duration (2h)."""
        result = self.run_async(
            self.execute_command("mute txt", TEST_USER_ID)
        )

        self.assert_command_success(result)

        # Check response structure
        responses = result.get("responses", [])
        self.assertEqual(len(responses), 1)

        response = responses[0]

        # Verify mute response
        self.assertTrue(
            assert_mute_response_valid(response, TEST_USER_ID, "txt", is_unmute=False),
            "Invalid mute txt response"
        )

        # Should have timestamp (2h default)
        self.assertTrue(
            assert_has_timestamp(response),
            "Mute txt should include timestamp for duration"
        )

    def test_mute_txt_custom_duration(self):
        """Test mute txt with custom duration."""
        for duration in TEST_MUTE_DURATIONS[:2]:  # Test first 2 durations
            with self.subTest(duration=duration):
                result = self.run_async(
                    self.execute_command("mute txt", f"{TEST_USER_ID} {duration}")
                )

                self.assert_command_success(result)

                response = result["responses"][0]
                self.assertTrue(
                    assert_has_timestamp(response),
                    f"Mute txt with {duration} should include timestamp"
                )

    def test_mute_img_permanent(self):
        """Test mute img with permanent duration."""
        result = self.run_async(
            self.execute_command("mute img", TEST_USER_ID)
        )

        self.assert_command_success(result)

        response = result["responses"][0]
        self.assertTrue(
            assert_mute_response_valid(response, TEST_USER_ID, "img", is_unmute=False)
        )

        # Check for "stałe" (permanent) in description
        desc = response["embeds"][0]["description"]
        self.assertIn("stałe", desc, "Default img mute should be permanent")

    def test_mute_nick(self):
        """Test mute nick (always 30 days)."""
        result = self.run_async(
            self.execute_command("mute nick", TEST_USER_ID)
        )

        self.assert_command_success(result)

        response = result["responses"][0]
        self.assertTrue(
            assert_mute_response_valid(response, TEST_USER_ID, "nick", is_unmute=False)
        )

        # Should mention premium requirement
        desc = response["embeds"][0]["description"]
        self.assertIn("zakup dowolną rangę premium", desc)

    def test_mute_live(self):
        """Test mute live (always permanent)."""
        result = self.run_async(
            self.execute_command("mute live", TEST_USER_ID)
        )

        self.assert_command_success(result)

        response = result["responses"][0]
        self.assertTrue(
            assert_mute_response_valid(response, TEST_USER_ID, "live", is_unmute=False)
        )

        # Should be permanent
        desc = response["embeds"][0]["description"]
        self.assertIn("stałe", desc)

    def test_mute_rank(self):
        """Test mute rank (always permanent)."""
        result = self.run_async(
            self.execute_command("mute rank", TEST_USER_ID)
        )

        self.assert_command_success(result)

        response = result["responses"][0]
        self.assertTrue(
            assert_mute_response_valid(response, TEST_USER_ID, "rank", is_unmute=False)
        )

    def test_mute_without_args(self):
        """Test mute command without arguments shows help."""
        result = self.run_async(
            self.execute_command("mute", "")
        )

        self.assert_command_success(result)
        self.assert_command_success(result, "Użyj jednej z podkomend")

    def test_mute_with_user_only(self):
        """Test mute with user but no subcommand acts as mute txt."""
        result = self.run_async(
            self.execute_command("mute", TEST_USER_ID)
        )

        self.assert_command_success(result)

        response = result["responses"][0]
        self.assertTrue(
            assert_mute_response_valid(response, TEST_USER_ID, "txt", is_unmute=False)
        )


class TestUnmuteCommands(CommandTestCase):
    """Test unmute commands functionality."""

    def test_unmute_txt(self):
        """Test unmute txt."""
        result = self.run_async(
            self.execute_command("unmute txt", TEST_USER_ID)
        )

        self.assert_command_success(result)

        response = result["responses"][0]
        self.assertTrue(
            assert_mute_response_valid(response, TEST_USER_ID, "txt", is_unmute=True)
        )

    def test_unmute_img(self):
        """Test unmute img."""
        result = self.run_async(
            self.execute_command("unmute img", TEST_USER_ID)
        )

        self.assert_command_success(result)

        response = result["responses"][0]
        self.assertTrue(
            assert_mute_response_valid(response, TEST_USER_ID, "img", is_unmute=True)
        )

    def test_unmute_nick(self):
        """Test unmute nick."""
        result = self.run_async(
            self.execute_command("unmute nick", TEST_USER_ID)
        )

        self.assert_command_success(result)

        response = result["responses"][0]
        self.assertTrue(
            assert_mute_response_valid(response, TEST_USER_ID, "nick", is_unmute=True)
        )

    def test_unmute_all_types(self):
        """Test unmute for all mute types."""
        mute_types = ["txt", "img", "nick", "live", "rank"]

        for mute_type in mute_types:
            with self.subTest(mute_type=mute_type):
                result = self.run_async(
                    self.execute_command(f"unmute {mute_type}", TEST_USER_ID)
                )

                self.assert_command_success(result)

                response = result["responses"][0]
                self.assertTrue(
                    assert_mute_response_valid(response, TEST_USER_ID, mute_type, is_unmute=True),
                    f"Invalid unmute {mute_type} response"
                )


if __name__ == "__main__":
    unittest.main()
