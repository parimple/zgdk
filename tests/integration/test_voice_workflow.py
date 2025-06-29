"""Integration tests for voice command workflows."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from tests.base.base_command_test import BaseCommandTest
from tests.config import TEST_USER_ID

pytest_plugins = ("pytest_asyncio",)
from tests.utils.assertions import VoiceAssertions
from tests.utils.client import TestClient

logger = logging.getLogger(__name__)


class TestVoiceWorkflow(BaseCommandTest):
    """Test complete voice command workflows."""

    @pytest.fixture(autouse=True)
    async def setup_voice_test(self):
        """Set up voice test environment."""
        # Create test voice channel
        self.voice_channel = MagicMock(spec=discord.VoiceChannel)
        self.voice_channel.id = 12345
        self.voice_channel.name = "Test Voice Channel"
        self.voice_channel.guild = self.guild
        self.voice_channel.overwrites = {}
        self.voice_channel.category = None
        self.voice_channel.members = []

        # Mock voice state
        self.voice_state = MagicMock()
        self.voice_state.channel = self.voice_channel

        # Mock author voice state
        self.author.voice = self.voice_state

        # Mock channel permission methods
        async def set_permissions(target, *, overwrite=None, **kwargs):
            self.voice_channel.overwrites[target] = overwrite
            return None

        async def overwrites_for(target):
            return self.voice_channel.overwrites.get(target, discord.PermissionOverwrite())

        self.voice_channel.set_permissions = AsyncMock(side_effect=set_permissions)
        self.voice_channel.overwrites_for = MagicMock(side_effect=overwrites_for)

        yield

        # Cleanup
        self.author.voice = None

    @pytest.mark.asyncio
    async def test_voice_permission_workflow(self):
        """Test complete voice permission management workflow."""
        client = TestClient(self.bot)

        # Step 1: Test speak command
        response = await client.run_command("speak", "@everyone -")
        VoiceAssertions.assert_permission_updated(response, "speak", False)

        # Step 2: Test view command
        response = await client.run_command("view", f"<@{TEST_USER_ID}> +")
        VoiceAssertions.assert_permission_updated(response, "view_channel", True)

        # Step 3: Test connect command
        response = await client.run_command("connect", f"<@{TEST_USER_ID}> -")
        VoiceAssertions.assert_permission_updated(response, "connect", False)

        # Step 4: Test text command
        response = await client.run_command("text", "@everyone +")
        VoiceAssertions.assert_permission_updated(response, "send_messages", True)

        # Step 5: Test live command (requires premium)
        with patch.object(self.bot, "get_service") as mock_get_service:
            # Mock premium service to allow access
            premium_service = AsyncMock()
            premium_service.check_command_access.return_value = (True, "Access granted")
            mock_get_service.return_value = premium_service

            response = await client.run_command("live", f"<@{TEST_USER_ID}> +")
            VoiceAssertions.assert_permission_updated(response, "stream", True)

    @pytest.mark.asyncio
    async def test_voice_mod_management_workflow(self):
        """Test voice channel moderator management workflow."""
        client = TestClient(self.bot)

        # Give author priority_speaker permission (owner)
        owner_perms = discord.PermissionOverwrite(priority_speaker=True)
        self.voice_channel.overwrites[self.author] = owner_perms

        # Mock premium role with mod limit
        premium_role = MagicMock()
        premium_role.name = "MVP"
        self.author.roles.append(premium_role)

        # Update bot config for the test
        self.bot.config["premium_roles"] = [{"name": "MVP", "moderator_count": 3}]

        # Step 1: Check current mod status
        response = await client.run_command("mod")
        assert "Aktualni moderatorzy" in response.content
        assert "brak" in response.content

        # Step 2: Add a moderator
        test_member = self.create_member(TEST_USER_ID, "TestMod")
        response = await client.run_command("mod", f"<@{TEST_USER_ID}> +")
        VoiceAssertions.assert_mod_updated(response, test_member, True)

        # Step 3: Remove moderator
        response = await client.run_command("mod", f"<@{TEST_USER_ID}> -")
        VoiceAssertions.assert_mod_updated(response, test_member, False)

    @pytest.mark.asyncio
    async def test_voice_channel_management_workflow(self):
        """Test voice channel management workflow."""
        client = TestClient(self.bot)

        # Give author manage_messages permission (mod)
        mod_perms = discord.PermissionOverwrite(manage_messages=True)
        self.voice_channel.overwrites[self.author] = mod_perms

        # Mock premium checker to allow access
        with patch.object(self.bot.cogs["VoiceCog"].premium_checker, "check_voice_access", return_value=(True, None)):
            # Step 1: Set channel limit
            self.voice_channel.edit = AsyncMock()
            response = await client.run_command("limit", "10")
            assert "Zmieniono limit" in response.content
            self.voice_channel.edit.assert_called_once_with(user_limit=10)

            # Step 2: Get channel info
            response = await client.run_command("voicechat")
            assert self.voice_channel.name in response.title
            assert "Właściciel" in response.fields[0]["name"]

    @pytest.mark.asyncio
    async def test_voice_autokick_workflow(self):
        """Test voice channel autokick workflow."""
        client = TestClient(self.bot)

        # Give author priority_speaker permission (owner)
        owner_perms = discord.PermissionOverwrite(priority_speaker=True)
        self.voice_channel.overwrites[self.author] = owner_perms

        # Mock premium tier check
        with patch.object(self.bot.cogs["VoiceCog"].premium_checker, "check_premium_tier", return_value=(True, None)):
            # Step 1: Check autokick list (empty)
            response = await client.run_command("autokick")
            assert "Lista autokick" in response.title
            assert "Brak użytkowników" in response.description

            # Step 2: Add user to autokick
            test_member = self.create_member(TEST_USER_ID, "TestUser")
            response = await client.run_command("autokick", f"<@{TEST_USER_ID}> +")
            assert "dodano do listy autokick" in response.content

            # Step 3: Check autokick list (has user)
            response = await client.run_command("autokick")
            assert "Lista autokick" in response.title
            assert test_member.mention in response.description

            # Step 4: Remove user from autokick
            response = await client.run_command("autokick", f"<@{TEST_USER_ID}> -")
            assert "usunięto z listy autokick" in response.content

    @pytest.mark.asyncio
    async def test_voice_reset_workflow(self):
        """Test voice channel reset workflow."""
        client = TestClient(self.bot)

        # Give author priority_speaker permission (owner)
        owner_perms = discord.PermissionOverwrite(priority_speaker=True)
        self.voice_channel.overwrites[self.author] = owner_perms

        # Add some test permissions
        test_member = self.create_member(TEST_USER_ID, "TestUser")
        test_perms = discord.PermissionOverwrite(speak=False, connect=False)
        self.voice_channel.overwrites[test_member] = test_perms

        # Mock premium access check
        with patch.object(self.bot.cogs["VoiceCog"].premium_checker, "check_voice_access", return_value=(True, None)):
            # Step 1: Reset specific user permissions
            response = await client.run_command("reset", f"<@{TEST_USER_ID}>")
            assert "Zresetowano uprawnienia" in response.content
            assert test_member.mention in response.content

            # Step 2: Reset all channel permissions
            response = await client.run_command("reset")
            assert "Zresetowano wszystkie uprawnienia" in response.content

    @pytest.mark.asyncio
    async def test_voice_permission_conflicts(self):
        """Test handling of permission conflicts and edge cases."""
        client = TestClient(self.bot)

        # Test 1: Try to use command without being in voice channel
        self.author.voice = None
        response = await client.run_command("speak", "@everyone -")
        assert "nie jesteś na kanale głosowym" in response.content

        # Restore voice state
        self.author.voice = self.voice_state

        # Test 2: Try to use owner command as non-owner
        response = await client.run_command("mod", f"<@{TEST_USER_ID}> +")
        assert "Nie masz uprawnień" in response.content

        # Test 3: Try to modify priority_speaker permission
        owner_perms = discord.PermissionOverwrite(priority_speaker=True)
        self.voice_channel.overwrites[self.author] = owner_perms

        # This should be blocked
        with patch.object(
            self.bot.cogs["VoiceCog"].permission_commands["speak"], "permission_name", "priority_speaker"
        ):
            response = await client.run_command("speak", "@everyone -")
            assert "priority_speaker" in response.content

    @pytest.mark.asyncio
    async def test_voice_premium_restrictions(self):
        """Test premium restrictions on voice commands."""
        client = TestClient(self.bot)

        # Test speak command without premium
        with patch.object(self.bot, "get_service") as mock_get_service:
            # Mock premium service to deny access
            premium_service = AsyncMock()
            premium_service.check_command_access.return_value = (
                False,
                "Komenda dostępna tylko dla użytkowników premium",
            )
            mock_get_service.return_value = premium_service

            response = await client.run_command("speak", "@everyone -")
            assert "dostępna tylko dla użytkowników premium" in response.content

        # Test autokick command without premium tier
        with patch.object(
            self.bot.cogs["VoiceCog"].premium_checker,
            "check_premium_tier",
            return_value=(False, "Funkcja dostępna od poziomu VIP"),
        ):
            response = await client.run_command("autokick")
            assert "dostępna od poziomu VIP" in response.content
