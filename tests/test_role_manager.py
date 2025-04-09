import asyncio
import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from datasources.queries import RoleQueries
from utils.role_manager import RoleManager


class TestRoleManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.bot.config = MagicMock()
        self.bot.config.get.return_value = {"mute_roles": []}

        # Setup mock session for database operations
        self.session = AsyncMock()
        db_context = AsyncMock()
        db_context.__aenter__.return_value = self.session
        self.bot.get_db.return_value = db_context

        self.role_manager = RoleManager(self.bot)

        # Ensure send_notification is mocked to avoid actual Discord API calls
        self.role_manager.send_notification = AsyncMock()
        self.role_manager.send_default_notification = AsyncMock()

    @patch("utils.role_manager.NotificationLogQueries")
    @patch("utils.role_manager.RoleQueries")
    @patch("utils.role_manager.logger")
    async def test_check_expired_roles_ignores_non_database_roles(
        self, mock_logger, mock_role_queries, mock_notif_queries
    ):
        # Setup mocks
        guild = MagicMock()
        guild.id = 123
        self.bot.guild = guild

        member = MagicMock()
        member.id = 456
        member.display_name = "TestUser"

        # Important: Configure get_member to return our member
        guild.get_member.return_value = member

        role1 = MagicMock()
        role1.id = 789
        role1.name = "ExpiredRole"
        role2 = MagicMock()
        role2.id = 101
        role2.name = "ActiveRole"

        # Member has both roles
        member.roles = [role1, role2]
        guild.get_role.side_effect = lambda id: role1 if id == 789 else role2 if id == 101 else None

        # Make remove_roles a coroutine mock
        member.remove_roles = AsyncMock()

        # Only role1 is in the database with expiration
        expired_role = MagicMock()
        expired_role.member_id = 456
        expired_role.role_id = 789
        expired_role.expiration_date = datetime.now() - timedelta(days=1)

        mock_role_queries.get_expired_roles.return_value = [expired_role]
        mock_role_queries.delete_member_role = AsyncMock()
        mock_notif_queries.add_or_update_notification_log = AsyncMock()

        # Call the method
        removed_count = await self.role_manager.check_expired_roles()

        # Verify only role1 was removed
        member.remove_roles.assert_called_once()
        self.assertEqual(member.remove_roles.call_count, 1)

        # Verify database operations
        mock_role_queries.delete_member_role.assert_called_with(self.session, member.id, role1.id)

        # Verify notification was sent
        self.role_manager.send_default_notification.assert_called_once()

        # Verify correct count was returned
        self.assertEqual(removed_count, 1)

    @patch("utils.role_manager.NotificationLogQueries")
    @patch("utils.role_manager.RoleQueries")
    @patch("utils.role_manager.logger")
    async def test_batch_processing_of_expired_roles(
        self, mock_logger, mock_role_queries, mock_notif_queries
    ):
        """Test that multiple roles for the same user are processed in batch"""
        # Setup mocks
        guild = MagicMock()
        guild.id = 123
        self.bot.guild = guild

        # Create a user with multiple expired roles
        member = MagicMock()
        member.id = 456
        member.display_name = "TestUser"

        # Ensure guild.get_member returns our mock member
        guild.get_member.return_value = member

        # Create three roles that have expired
        role1 = MagicMock()
        role1.id = 789
        role1.name = "ExpiredRole1"

        role2 = MagicMock()
        role2.id = 790
        role2.name = "ExpiredRole2"

        role3 = MagicMock()
        role3.id = 791
        role3.name = "ExpiredRole3"

        # Member has all three roles
        member.roles = [role1, role2, role3]
        guild.get_role.side_effect = lambda id: {789: role1, 790: role2, 791: role3}.get(id)

        # Make remove_roles a coroutine mock
        member.remove_roles = AsyncMock()

        # Create MemberRole objects for the database
        expired_role1 = MagicMock()
        expired_role1.member_id = 456
        expired_role1.role_id = 789
        expired_role1.expiration_date = datetime.now() - timedelta(days=1)

        expired_role2 = MagicMock()
        expired_role2.member_id = 456
        expired_role2.role_id = 790
        expired_role2.expiration_date = datetime.now() - timedelta(days=1)

        expired_role3 = MagicMock()
        expired_role3.member_id = 456
        expired_role3.role_id = 791
        expired_role3.expiration_date = datetime.now() - timedelta(days=1)

        mock_role_queries.get_expired_roles.return_value = [
            expired_role1,
            expired_role2,
            expired_role3,
        ]

        mock_role_queries.delete_member_role = AsyncMock()
        mock_notif_queries.add_or_update_notification_log = AsyncMock()

        # Call the method
        removed_count = await self.role_manager.check_expired_roles()

        # Verify roles were removed
        self.assertEqual(member.remove_roles.call_count, 1)

        # Verify database operations
        self.assertEqual(mock_role_queries.delete_member_role.call_count, 3)

        # Verify the correct count was returned
        self.assertEqual(removed_count, 3)


if __name__ == "__main__":
    unittest.main()
