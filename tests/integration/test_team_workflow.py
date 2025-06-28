"""Integration tests for team command workflows."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from tests.base.base_command_test import BaseCommandTest
from tests.config import TEST_USER_ID
from tests.utils.client import TestClient

logger = logging.getLogger(__name__)


class TestTeamWorkflow(BaseCommandTest):
    """Test complete team command workflows."""

    @pytest.fixture(autouse=True)
    async def setup_team_test(self):
        """Set up team test environment."""
        # Add premium role to author
        premium_role = MagicMock()
        premium_role.id = 1027629813788106814
        premium_role.name = "zG100"
        self.author.roles.append(premium_role)

        # Set up team config
        self.bot.config["team"] = {
            "symbol": "☫",
            "base_role_id": 960665311730868240,
            "category_id": 1344105013357842522
        }

        # Set up premium roles config
        self.bot.config["premium_roles"] = [
            {"name": "zG100", "team_members": 5},
            {"name": "zG500", "team_members": 10},
            {"name": "zG1000", "team_members": 15}
        ]

        # Mock role creation
        self.created_roles = []
        async def create_role(**kwargs):
            role = MagicMock(spec=discord.Role)
            role.id = len(self.created_roles) + 1000
            role.name = kwargs.get("name", "")
            role.color = kwargs.get("color", discord.Color.default())
            role.mention = f"<@&{role.id}>"
            role.position = 10
            role.edit = AsyncMock()
            role.delete = AsyncMock()
            self.created_roles.append(role)
            return role

        self.guild.create_role = AsyncMock(side_effect=create_role)
        self.guild.get_role = lambda id: next((r for r in self.created_roles if r.id == id), None)

        # Mock base role
        self.base_role = MagicMock()
        self.base_role.id = 960665311730868240
        self.base_role.position = 5
        self.guild.get_role = lambda id: self.base_role if id == 960665311730868240 else None

        yield

        # Cleanup
        self.author.roles = self.author.roles[:-1]  # Remove premium role
        self.created_roles.clear()

    @pytest.mark.asyncio
    async def test_team_creation_workflow(self):
        """Test complete team creation workflow."""
        client = TestClient(self.bot)

        # Mock services
        with patch.object(self.bot, 'get_service') as mock_get_service:
            # Mock role service
            role_service = AsyncMock()
            role_service.create_role = AsyncMock()
            role_service.get_role_by_discord_id = AsyncMock(return_value=None)

            # Mock premium service
            premium_service = AsyncMock()
            premium_service.set_guild = MagicMock()
            premium_service.has_premium_role = AsyncMock(return_value=True)
            premium_service.get_highest_premium_role = AsyncMock(return_value=self.author.roles[-1])

            async def get_service(service_type, session):
                from core.interfaces.premium_interfaces import IPremiumService
                from core.interfaces.role_interfaces import IRoleService

                if service_type == IRoleService:
                    return role_service
                elif service_type == IPremiumService:
                    return premium_service

            mock_get_service.side_effect = get_service

            # Step 1: Check team status (no team)
            response = await client.run_command("team")
            assert "Nie masz teamu" in response.description
            assert "team create" in response.description

            # Step 2: Create team with default name
            response = await client.run_command("team create")
            assert "Pomyślnie utworzono team" in response.content
            assert len(self.created_roles) == 1
            assert self.created_roles[0].name == f"☫ {self.author.display_name}"

            # Check role was assigned to author
            self.author.add_roles.assert_called_once_with(self.created_roles[0])

            # Check database was updated
            role_service.create_role.assert_called_once_with(
                discord_id=self.created_roles[0].id,
                name=str(self.author.id),
                role_type="team"
            )

    @pytest.mark.asyncio
    async def test_team_creation_with_options(self):
        """Test team creation with color and emoji options."""
        client = TestClient(self.bot)

        # Add zG500 role for color permission
        color_role = MagicMock()
        color_role.name = "zG500"
        self.author.roles.append(color_role)

        # Add zG1000 role for emoji permission
        emoji_role = MagicMock()
        emoji_role.name = "zG1000"
        self.author.roles.append(emoji_role)

        # Mock services
        with patch.object(self.bot, 'get_service') as mock_get_service:
            # Mock services
            role_service = AsyncMock()
            role_service.create_role = AsyncMock()
            role_service.get_role_by_discord_id = AsyncMock(return_value=None)

            premium_service = AsyncMock()
            premium_service.set_guild = MagicMock()
            premium_service.has_premium_role = AsyncMock(return_value=True)

            async def get_service(service_type, session):
                from core.interfaces.premium_interfaces import IPremiumService
                from core.interfaces.role_interfaces import IRoleService

                if service_type == IRoleService:
                    return role_service
                elif service_type == IPremiumService:
                    return premium_service

            mock_get_service.side_effect = get_service

            # Create team with name, color, and emoji
            response = await client.run_command("team create", "TestTeam #FF0000 🔥")
            assert "Pomyślnie utworzono team" in response.content
            assert len(self.created_roles) == 1
            assert self.created_roles[0].name == "☫ TestTeam"

            # Check color was set
            self.created_roles[0].edit.assert_called()

        # Cleanup
        self.author.roles = self.author.roles[:-2]  # Remove color and emoji roles

    @pytest.mark.asyncio
    async def test_team_member_management_workflow(self):
        """Test team member invitation, kick, and leave workflow."""
        client = TestClient(self.bot)

        # Create a team first
        team_role = MagicMock(spec=discord.Role)
        team_role.id = 2000
        team_role.name = "☫ TestTeam"
        team_role.mention = f"<@&{team_role.id}>"
        self.author.roles.append(team_role)

        # Create test member to invite
        test_member = self.create_member(TEST_USER_ID, "TestMember")
        test_member.send = AsyncMock()
        test_member.add_roles = AsyncMock()
        test_member.remove_roles = AsyncMock()

        # Mock services
        with patch.object(self.bot, 'get_service') as mock_get_service:
            # Mock role service with ownership
            role_service = AsyncMock()
            db_role = MagicMock()
            db_role.name = str(self.author.id)  # Author owns the team
            role_service.get_role_by_discord_id = AsyncMock(return_value=db_role)

            # Mock premium service
            premium_service = AsyncMock()
            premium_service.set_guild = MagicMock()
            premium_service.get_highest_premium_role = AsyncMock(return_value=self.author.roles[0])

            async def get_service(service_type, session):
                from core.interfaces.premium_interfaces import IPremiumService
                from core.interfaces.role_interfaces import IRoleService

                if service_type == IRoleService:
                    return role_service
                elif service_type == IPremiumService:
                    return premium_service

            mock_get_service.side_effect = get_service

            # Mock bot.wait_for to simulate accepting invitation
            async def mock_wait_for(event, timeout, check):
                if event == "reaction_add":
                    # Simulate user accepting invitation
                    reaction = MagicMock()
                    reaction.emoji = "✅"
                    reaction.message.id = 12345
                    return reaction, test_member

            self.bot.wait_for = mock_wait_for

            # Step 1: Invite member
            response = await client.run_command("team_invite", f"<@{TEST_USER_ID}>")
            assert "Wysłano zaproszenie" in response.description

            # Check invitation was sent
            test_member.send.assert_called()
            invite_embed = test_member.send.call_args[1]["embed"]
            assert "Zaproszenie do teamu" in invite_embed.title

            # Check member was added to team
            test_member.add_roles.assert_called_with(team_role)

            # Step 2: Kick member
            # First add the role to simulate they're in the team
            test_member.roles.append(team_role)

            response = await client.run_command("team_kick", f"<@{TEST_USER_ID}>")
            assert f"{test_member.mention} został wyrzucony z teamu" in response.content

            # Check member was removed
            test_member.remove_roles.assert_called_with(team_role)

            # Step 3: Test leave command (as non-owner)
            # Create another member who's in the team but not owner
            other_member = self.create_member(999, "OtherMember")
            other_member.roles.append(team_role)

            # Change author to the other member temporarily
            original_author = self.ctx.author
            self.ctx.author = other_member

            response = await client.run_command("team_leave")
            assert "Opuściłeś team" in response.content

            # Restore original author
            self.ctx.author = original_author

        # Cleanup
        self.author.roles.remove(team_role)

    @pytest.mark.asyncio
    async def test_team_ownership_transfer(self):
        """Test transferring team ownership."""
        client = TestClient(self.bot)

        # Create a team
        team_role = MagicMock(spec=discord.Role)
        team_role.id = 2000
        team_role.name = "☫ TestTeam"
        team_role.mention = f"<@&{team_role.id}>"
        self.author.roles.append(team_role)

        # Create member to transfer to
        new_owner = self.create_member(TEST_USER_ID, "NewOwner")
        new_owner.roles.append(team_role)  # They're in the team

        # Add premium role to new owner
        premium_role = MagicMock()
        premium_role.name = "zG100"
        new_owner.roles.append(premium_role)

        # Mock services
        with patch.object(self.bot, 'get_service') as mock_get_service:
            # Mock role service
            role_service = AsyncMock()
            db_role = MagicMock()
            db_role.name = str(self.author.id)  # Current owner
            role_service.get_role_by_discord_id = AsyncMock(return_value=db_role)

            # Mock premium service
            premium_service = AsyncMock()
            premium_service.set_guild = MagicMock()
            premium_service.has_premium_role = AsyncMock(return_value=True)

            # Mock session for commit
            session = AsyncMock()
            session.commit = AsyncMock()

            async def get_service(service_type, sess):
                from core.interfaces.premium_interfaces import IPremiumService
                from core.interfaces.role_interfaces import IRoleService

                if service_type == IRoleService:
                    return role_service
                elif service_type == IPremiumService:
                    return premium_service

            mock_get_service.side_effect = get_service

            # Mock get_db context manager
            with patch.object(self.bot, 'get_db') as mock_get_db:
                mock_get_db.return_value.__aenter__.return_value = session
                mock_get_db.return_value.__aexit__.return_value = None

                # Transfer ownership
                response = await client.run_command("team_transfer", f"<@{TEST_USER_ID}>")
                assert "Przekazano własność teamu" in response.content
                assert new_owner.mention in response.content

                # Check database was updated
                assert db_role.name == str(new_owner.id)
                session.commit.assert_called_once()

        # Cleanup
        self.author.roles.remove(team_role)

    @pytest.mark.asyncio
    async def test_team_deletion(self):
        """Test team deletion workflow."""
        client = TestClient(self.bot)

        # Create a team
        team_role = MagicMock(spec=discord.Role)
        team_role.id = 2000
        team_role.name = "☫ TestTeam"
        team_role.mention = f"<@&{team_role.id}>"
        team_role.delete = AsyncMock()
        self.author.roles.append(team_role)

        # Mock services
        with patch.object(self.bot, 'get_service') as mock_get_service:
            # Mock role service
            role_service = AsyncMock()
            db_role = MagicMock()
            db_role.id = 1
            db_role.name = str(self.author.id)  # Author owns the team
            role_service.get_role_by_discord_id = AsyncMock(return_value=db_role)
            role_service.delete_role = AsyncMock()

            # Mock session
            session = AsyncMock()
            session.commit = AsyncMock()

            async def get_service(service_type, sess):
                from core.interfaces.role_interfaces import IRoleService

                if service_type == IRoleService:
                    return role_service

            mock_get_service.side_effect = get_service

            # Mock get_db context manager
            with patch.object(self.bot, 'get_db') as mock_get_db:
                mock_get_db.return_value.__aenter__.return_value = session
                mock_get_db.return_value.__aexit__.return_value = None

                # Mock bot.wait_for to simulate confirmation
                async def mock_wait_for(event, timeout, check):
                    if event == "reaction_add":
                        reaction = MagicMock()
                        reaction.emoji = "✅"
                        reaction.message.id = 12345
                        return reaction, self.author

                self.bot.wait_for = mock_wait_for

                # Delete team
                response = await client.run_command("team_delete")
                # Response is the confirmation message
                assert "Czy na pewno chcesz usunąć team" in response.description

                # Check team was deleted
                team_role.delete.assert_called_once()
                role_service.delete_role.assert_called_once_with(db_role.id)
                session.commit.assert_called_once()

        # Cleanup
        self.author.roles.remove(team_role)

    @pytest.mark.asyncio
    async def test_team_permission_checks(self):
        """Test various permission checks for team commands."""
        client = TestClient(self.bot)

        # Test without premium role
        self.author.roles = self.author.roles[:-1]  # Remove premium role

        # Mock services
        with patch.object(self.bot, 'get_service') as mock_get_service:
            # Mock premium service
            premium_service = AsyncMock()
            premium_service.set_guild = MagicMock()
            premium_service.has_premium_role = AsyncMock(return_value=False)

            async def get_service(service_type, session):
                from core.interfaces.premium_interfaces import IPremiumService

                if service_type == IPremiumService:
                    return premium_service

            mock_get_service.side_effect = get_service

            # Try to create team without premium
            response = await client.run_command("team create")
            assert "Brak wymaganych uprawnień" in response.description
            assert "musisz posiadać jedną z rang premium" in response.description

        # Test team name validation
        premium_role = MagicMock()
        premium_role.name = "zG100"
        self.author.roles.append(premium_role)

        with patch.object(self.bot, 'get_service') as mock_get_service:
            # Mock services to allow creation
            role_service = AsyncMock()
            role_service.get_role_by_discord_id = AsyncMock(return_value=None)

            premium_service = AsyncMock()
            premium_service.set_guild = MagicMock()
            premium_service.has_premium_role = AsyncMock(return_value=True)

            async def get_service(service_type, session):
                from core.interfaces.premium_interfaces import IPremiumService
                from core.interfaces.role_interfaces import IRoleService

                if service_type == IRoleService:
                    return role_service
                elif service_type == IPremiumService:
                    return premium_service

            mock_get_service.side_effect = get_service

            # Test name too long
            response = await client.run_command("team create", "ThisIsAVeryLongTeamNameThatExceedsTheLimit")
            assert "nie może być dłuższa niż 20 znaków" in response.description

            # Test invalid characters
            response = await client.run_command("team create", "Team@#$%")
            assert "może zawierać tylko litery, cyfry" in response.description
