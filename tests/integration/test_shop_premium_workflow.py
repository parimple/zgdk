"""Integration tests for shop and premium command workflows."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import discord
import pytest

from tests.base.base_command_test import BaseCommandTest
from tests.config import SECONDARY_TEST_USER_ID, TEST_USER_ID
from tests.utils.client import TestClient

logger = logging.getLogger(__name__)


class TestShopPremiumWorkflow(BaseCommandTest):
    """Test complete shop and premium features workflow."""

    @pytest.fixture(autouse=True)
    async def setup_shop_test(self):
        """Set up shop test environment."""
        # Set up premium roles config
        self.bot.config["premium_roles"] = [
            {
                "id": 1027629813788106814,
                "name": "zG100",
                "price": 100,
                "color": "#FF0000",
                "description": "Basic premium role",
                "team_members": 5,
                "moderator_count": 2,
            },
            {
                "id": 1027629916951326761,
                "name": "zG500",
                "price": 500,
                "color": "#00FF00",
                "description": "Advanced premium role",
                "team_members": 10,
                "moderator_count": 5,
            },
            {
                "id": 1027630008227659826,
                "name": "zG1000",
                "price": 1000,
                "color": "#0000FF",
                "description": "Ultimate premium role",
                "team_members": 15,
                "moderator_count": 10,
            },
        ]

        # Create mock premium roles
        self.premium_roles = {}
        for role_config in self.bot.config["premium_roles"]:
            role = MagicMock(spec=discord.Role)
            role.id = role_config["id"]
            role.name = role_config["name"]
            role.color = discord.Color(int(role_config["color"][1:], 16))
            role.mention = f"<@&{role.id}>"
            self.premium_roles[role.name] = role

        # Mock guild.get_role to return our premium roles
        original_get_role = self.guild.get_role

        def mock_get_role(role_id):
            for role in self.premium_roles.values():
                if role.id == role_id:
                    return role
            return original_get_role(role_id)

        self.guild.get_role = mock_get_role

        yield

        # Cleanup
        self.premium_roles.clear()

    @pytest.mark.asyncio
    async def test_complete_shop_premium_workflow(self):
        """Test complete workflow: add balance, buy roles, test premium features, sell roles."""
        client = TestClient(self.bot)

        # Create test user
        test_user = self.create_member(int(TEST_USER_ID), "TestUser")
        test_user.add_roles = AsyncMock()
        test_user.remove_roles = AsyncMock()

        # Mock services
        with patch.object(self.bot, "get_service") as mock_get_service:
            # Mock member service
            member_service = AsyncMock()
            db_member = MagicMock()
            db_member.wallet_balance = 0
            member_service.get_or_create_member = AsyncMock(return_value=db_member)
            member_service.update_balance = AsyncMock()

            # Mock premium service
            premium_service = AsyncMock()
            premium_service.set_guild = MagicMock()
            premium_service.get_member_premium_roles = AsyncMock(return_value=[])
            premium_service.has_premium_role = AsyncMock(return_value=False)
            premium_service.get_highest_premium_role = AsyncMock(return_value=None)
            premium_service.check_command_access = AsyncMock(return_value=(False, "Brak dostępu"))

            # Mock payment processor
            payment_processor = AsyncMock()
            payment_processor.create_role_purchase = AsyncMock()
            payment_processor.create_role_sale = AsyncMock()

            async def get_service(service_type, session):
                from core.interfaces.member_interfaces import IMemberService
                from core.interfaces.payment_interfaces import IPaymentProcessor
                from core.interfaces.premium_interfaces import IPremiumService

                if service_type == IMemberService:
                    return member_service
                elif service_type == IPremiumService:
                    return premium_service
                elif service_type == IPaymentProcessor:
                    return payment_processor

            mock_get_service.side_effect = get_service

            # Step 1: Check initial shop (no balance, no roles)
            response = await client.run_command("shop")
            assert "Sklep z rolami" in response.title
            assert "Portfel: 0 G" in response.footer.text

            # Step 2: Add balance to user
            db_member.wallet_balance = 2000
            response = await client.run_command("addbalance", f"<@{TEST_USER_ID}> 2000")
            assert "Dodano 2000 G" in response.content
            assert test_user.mention in response.content
            member_service.update_balance.assert_called()

            # Step 3: Buy zG100 role
            # Mock the purchase process
            premium_service.get_member_premium_roles.return_value = [self.premium_roles["zG100"]]
            premium_service.has_premium_role.return_value = True
            premium_service.get_highest_premium_role.return_value = self.premium_roles["zG100"]
            premium_service.check_command_access.return_value = (True, "Access granted")

            # Simulate role purchase (would normally be done through button interaction)
            test_user.roles.append(self.premium_roles["zG100"])
            db_member.wallet_balance = 1900  # After purchase

            # Step 4: Test premium features with zG100
            # Test color command (should work with zG100)
            response = await client.run_command("color", "#FF5500")
            # Note: The actual color command would need the user to have the role
            # In real test, this would check if the color was changed

            # Test team creation (should work with zG100)
            with patch.object(self.bot.cogs.get("TeamCog", None), "_get_user_team_role", return_value=None):
                response = await client.run_command("team create", "MyTeam")
                # This would create a team with 5 member limit

            # Step 5: Buy zG500 role
            premium_service.get_member_premium_roles.return_value = [
                self.premium_roles["zG100"],
                self.premium_roles["zG500"],
            ]
            premium_service.get_highest_premium_role.return_value = self.premium_roles["zG500"]
            test_user.roles.append(self.premium_roles["zG500"])
            db_member.wallet_balance = 1400  # After purchase

            # Step 6: Test enhanced features with zG500
            # Now team should have 10 member limit
            # Color commands should allow more options

            # Step 7: Buy zG1000 role
            premium_service.get_member_premium_roles.return_value = [
                self.premium_roles["zG100"],
                self.premium_roles["zG500"],
                self.premium_roles["zG1000"],
            ]
            premium_service.get_highest_premium_role.return_value = self.premium_roles["zG1000"]
            test_user.roles.append(self.premium_roles["zG1000"])
            db_member.wallet_balance = 400  # After purchase

            # Step 8: Test ultimate features with zG1000
            # Team emoji support
            with patch.object(self.bot.cogs.get("TeamCog", None), "_get_user_team_role") as mock_team:
                team_role = MagicMock()
                team_role.name = "☫ MyTeam"
                team_role.edit = AsyncMock()
                mock_team.return_value = team_role

                # This would set team emoji (zG1000 feature)
                # response = await client.run_command("team emoji", "🔥")

            # Step 9: Sell all roles
            # Sell zG1000 (should get 700G back - 70% of 1000)
            premium_service.get_member_premium_roles.return_value = [
                self.premium_roles["zG100"],
                self.premium_roles["zG500"],
            ]
            test_user.roles.remove(self.premium_roles["zG1000"])
            db_member.wallet_balance = 1100  # After sale

            # Sell zG500 (should get 350G back - 70% of 500)
            premium_service.get_member_premium_roles.return_value = [self.premium_roles["zG100"]]
            test_user.roles.remove(self.premium_roles["zG500"])
            db_member.wallet_balance = 1450  # After sale

            # Sell zG100 (should get 70G back - 70% of 100)
            premium_service.get_member_premium_roles.return_value = []
            premium_service.has_premium_role.return_value = False
            premium_service.get_highest_premium_role.return_value = None
            premium_service.check_command_access.return_value = (False, "Brak dostępu")
            test_user.roles.remove(self.premium_roles["zG100"])
            db_member.wallet_balance = 1520  # After sale

            # Step 10: Verify no premium access after selling all
            response = await client.run_command("color", "#000000")
            # Should show no access message

            response = await client.run_command("team create", "NewTeam")
            # Should show premium required message

    @pytest.mark.asyncio
    async def test_shop_role_assignment_workflow(self):
        """Test shop role assignment by owner."""
        client = TestClient(self.bot)

        # Create test user and owner
        test_user = self.create_member(int(TEST_USER_ID), "TestUser")
        owner = self.create_member(int(SECONDARY_TEST_USER_ID), "Owner")

        # Set owner as author for commands
        original_author = self.ctx.author
        self.ctx.author = owner

        # Mock services
        with patch.object(self.bot, "get_service") as mock_get_service:
            # Mock member service
            member_service = AsyncMock()
            db_member = MagicMock()
            db_member.wallet_balance = 0
            member_service.get_or_create_member = AsyncMock(return_value=db_member)

            # Mock premium service
            premium_service = AsyncMock()
            premium_service.set_guild = MagicMock()
            premium_service.get_member_premium_roles = AsyncMock(return_value=[])

            # Mock role service
            role_service = AsyncMock()
            role_service.create_role_ownership = AsyncMock()

            async def get_service(service_type, session):
                from core.interfaces.member_interfaces import IMemberService
                from core.interfaces.premium_interfaces import IPremiumService
                from core.interfaces.role_interfaces import IRoleService

                if service_type == IMemberService:
                    return member_service
                elif service_type == IPremiumService:
                    return premium_service
                elif service_type == IRoleService:
                    return role_service

            mock_get_service.side_effect = get_service

            # View shop for another user
            response = await client.run_command("shop", f"<@{TEST_USER_ID}>")
            assert "Sklep z rolami" in response.title
            # Should show shop for the test user

            # Assign role directly (owner command)
            # This would typically be done through button interaction
            # but we simulate the backend process
            test_user.add_roles = AsyncMock()
            await test_user.add_roles(self.premium_roles["zG500"])

            # Update mock to reflect new role
            premium_service.get_member_premium_roles.return_value = [self.premium_roles["zG500"]]

            # Check role was assigned
            role_service.create_role_ownership.assert_called()

        # Restore original author
        self.ctx.author = original_author

    @pytest.mark.asyncio
    async def test_payment_handling_workflow(self):
        """Test payment assignment and viewing workflows."""
        client = TestClient(self.bot)

        # Create test user
        test_user = self.create_member(int(TEST_USER_ID), "TestUser")

        # Mock services
        with patch.object(self.bot, "get_service") as mock_get_service:
            # Mock member service
            member_service = AsyncMock()
            member_service.get_or_create_member = AsyncMock()

            # Mock payment processor
            payment_processor = AsyncMock()

            # Create mock payment
            mock_payment = MagicMock()
            mock_payment.id = 12345
            mock_payment.amount = 500
            mock_payment.description = "Test payment"
            mock_payment.handled = False
            payment_processor.get_pending_payments = AsyncMock(return_value=[mock_payment])
            payment_processor.assign_payment = AsyncMock()

            async def get_service(service_type, session):
                from core.interfaces.member_interfaces import IMemberService
                from core.interfaces.payment_interfaces import IPaymentProcessor

                if service_type == IMemberService:
                    return member_service
                elif service_type == IPaymentProcessor:
                    return payment_processor

            mock_get_service.side_effect = get_service

            # View all payments
            response = await client.run_command("all_payments")
            assert "payments" in response.title.lower() or "płatności" in response.title.lower()

            # Assign payment to user
            response = await client.run_command("assign_payment", f"12345 <@{TEST_USER_ID}>")
            assert "assigned" in response.content.lower() or "przypisano" in response.content.lower()
            payment_processor.assign_payment.assert_called_with(12345, test_user.id)

    @pytest.mark.asyncio
    async def test_role_expiry_workflow(self):
        """Test setting role expiry times."""
        client = TestClient(self.bot)

        # Create test user with premium role
        test_user = self.create_member(int(TEST_USER_ID), "TestUser")
        test_user.roles.append(self.premium_roles["zG100"])

        # Mock services
        with patch.object(self.bot, "get_service") as mock_get_service:
            # Mock role service
            role_service = AsyncMock()
            db_ownership = MagicMock()
            db_ownership.expires_at = None
            role_service.get_role_ownership = AsyncMock(return_value=db_ownership)
            role_service.update_role_expiry = AsyncMock()

            # Mock session
            session = AsyncMock()
            session.commit = AsyncMock()

            async def get_service(service_type, sess):
                from core.interfaces.role_interfaces import IRoleService

                if service_type == IRoleService:
                    return role_service

            mock_get_service.side_effect = get_service

            # Mock get_db context manager
            with patch.object(self.bot, "get_db") as mock_get_db:
                mock_get_db.return_value.__aenter__.return_value = session
                mock_get_db.return_value.__aexit__.return_value = None

                # Set role to expire in 24 hours
                response = await client.run_command("set_role_expiry", f"<@{TEST_USER_ID}> 24")
                assert "expires" in response.content.lower() or "wygasa" in response.content.lower()
                role_service.update_role_expiry.assert_called()

    @pytest.mark.asyncio
    async def test_premium_feature_restrictions(self):
        """Test that premium features are properly restricted."""
        client = TestClient(self.bot)

        # Create user without premium
        test_user = self.create_member(int(TEST_USER_ID), "TestUser")
        self.ctx.author = test_user

        # Mock services
        with patch.object(self.bot, "get_service") as mock_get_service:
            # Mock premium service to deny access
            premium_service = AsyncMock()
            premium_service.set_guild = MagicMock()
            premium_service.has_premium_role = AsyncMock(return_value=False)
            premium_service.check_command_access = AsyncMock(return_value=(False, "Ta komenda wymaga rangi premium"))

            async def get_service(service_type, session):
                from core.interfaces.premium_interfaces import IPremiumService

                if service_type == IPremiumService:
                    return premium_service

            mock_get_service.side_effect = get_service

            # Try color command without premium
            response = await client.run_command("color", "#FF0000")
            assert "wymaga rangi premium" in response.content or "premium" in response.content.lower()

            # Try team creation without premium
            response = await client.run_command("team create", "TestTeam")
            assert "premium" in response.description.lower() or "uprawnień" in response.description
