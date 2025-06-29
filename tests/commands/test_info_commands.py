"""
Tests for info commands.
"""

import unittest

from tests.base.test_base import CommandTestCase


class TestInfoCommands(CommandTestCase):
    """Test info commands functionality."""

    def test_profile_command(self):
        """Test profile command."""
        result = self.run_async(self.execute_command("profile", ""))

        self.assert_command_success(result)

        # Should show author's profile
        response = result["responses"][0]
        embeds = response.get("embeds", [])
        self.assertTrue(embeds, "Profile should return embed")

        # Check embed structure
        embed = embeds[0]
        self.assertIn("Profil", embed.get("title", ""))

    def test_help_command(self):
        """Test help command."""
        result = self.run_async(self.execute_command("help", ""))

        self.assert_command_success(result)

        # Should return help information
        response = result["responses"][0]
        embeds = response.get("embeds", [])
        self.assertTrue(embeds, "Help should return embed")

    def test_games_command(self):
        """Test games command."""
        result = self.run_async(self.execute_command("games", ""))

        self.assert_command_success(result)

        # Should return games list
        response = result["responses"][0]
        embeds = response.get("embeds", [])
        self.assertTrue(embeds, "Games should return embed")

        embed = embeds[0]
        self.assertIn("Gry", embed.get("title", ""))

    def test_ping_command(self):
        """Test ping command."""
        result = self.run_async(self.execute_command("ping", ""))

        self.assert_command_success(result)

        # Should return ping info
        response = result["responses"][0]
        embeds = response.get("embeds", [])
        self.assertTrue(embeds, "Ping should return embed")

        embed = embeds[0]
        fields = embed.get("fields", [])

        # Should have latency fields
        field_names = [f.get("name") for f in fields]
        self.assertIn("Ping", field_names)

    def test_serverinfo_command(self):
        """Test serverinfo command."""
        result = self.run_async(self.execute_command("serverinfo", ""))

        self.assert_command_success(result)

        # Should return server information
        response = result["responses"][0]
        embeds = response.get("embeds", [])
        self.assertTrue(embeds, "Serverinfo should return embed")

        embed = embeds[0]
        self.assertIn("Informacje o serwerze", embed.get("title", ""))

    def test_roles_command(self):
        """Test roles command."""
        result = self.run_async(self.execute_command("roles", ""))

        self.assert_command_success(result)

        # Should return roles list
        response = result["responses"][0]
        embeds = response.get("embeds", [])
        self.assertTrue(embeds, "Roles should return embed")

        embed = embeds[0]
        self.assertIn("Role", embed.get("title", "").lower())

    def test_invites_command(self):
        """Test invites command."""
        result = self.run_async(self.execute_command("invites", ""))

        self.assert_command_success(result)

        # Should return invites information
        response = result["responses"][0]
        embeds = response.get("embeds", [])
        self.assertTrue(embeds, "Invites should return embed")


if __name__ == "__main__":
    unittest.main()
