import unittest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from utils.role_manager import RoleManager


class TestRoleManager(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = MagicMock()
        self.bot.config = {
            "mute_roles": [
                {"id": 1001, "description": "attach_files_off"},
                {"id": 1002, "description": "send_messages_off"},
            ],
            "default_mute_nickname": "random",
        }

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

        # Important: Configure fetch_member to return our member
        guild.fetch_member = AsyncMock(return_value=member)

        role1 = MagicMock()
        role1.id = 789
        role1.name = "ExpiredRole"
        role2 = MagicMock()
        role2.id = 101
        role2.name = "ActiveRole"

        # Member has both roles
        member.roles = [role1, role2]
        guild.get_role.side_effect = (
            lambda id: role1 if id == 789 else role2 if id == 101 else None
        )

        # Make remove_roles a coroutine mock
        member.remove_roles = AsyncMock()

        # Only role1 is in the database with expiration
        expired_role = MagicMock()
        expired_role.member_id = 456
        expired_role.role_id = 789
        expired_role.expiration_date = datetime.now() - timedelta(days=1)

        mock_role_queries.get_expired_roles = AsyncMock(return_value=[expired_role])
        mock_role_queries.delete_member_role = AsyncMock()
        mock_notif_queries.add_or_update_notification_log = AsyncMock()

        # Mock notification handler
        notification_handler = AsyncMock()

        # Call the method
        removed_count = await self.role_manager.check_expired_roles(
            notification_handler=notification_handler
        )

        # Verify only role1 was removed
        member.remove_roles.assert_called_once()
        self.assertEqual(member.remove_roles.call_count, 1)

        # Verify database operations
        mock_role_queries.delete_member_role.assert_called_with(
            self.session, member.id, role1.id
        )

        # Verify notification was sent
        notification_handler.assert_called_once()

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

        # Ensure guild.fetch_member returns our mock member
        guild.fetch_member = AsyncMock(return_value=member)

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
        guild.get_role.side_effect = lambda id: {
            789: role1,
            790: role2,
            791: role3,
        }.get(id)

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

        mock_role_queries.get_expired_roles = AsyncMock(
            return_value=[
                expired_role1,
                expired_role2,
                expired_role3,
            ]
        )

        mock_role_queries.delete_member_role = AsyncMock()
        mock_notif_queries.add_or_update_notification_log = AsyncMock()

        # Mock notification handler
        notification_handler = AsyncMock()

        # Call the method
        removed_count = await self.role_manager.check_expired_roles(
            notification_handler=notification_handler
        )

        # Verify roles were removed
        self.assertEqual(member.remove_roles.call_count, 1)

        # Verify database operations
        self.assertEqual(mock_role_queries.delete_member_role.call_count, 3)

        # Verify notifications were sent for all 3 roles
        self.assertEqual(notification_handler.call_count, 3)

        # Verify the correct count was returned
        self.assertEqual(removed_count, 3)

    @patch("utils.role_manager.NotificationLogQueries")
    @patch("utils.role_manager.RoleQueries")
    @patch("utils.role_manager.logger")
    async def test_notifications_sent_after_commit_success(
        self, mock_logger, mock_role_queries, mock_notif_queries
    ):
        """Test that notifications are sent only after successful database commit"""
        # Setup mocks
        guild = MagicMock()
        guild.id = 123
        self.bot.guild = guild

        member = MagicMock()
        member.id = 456
        member.display_name = "TestUser"
        member.remove_roles = AsyncMock()  # Successful role removal

        role = MagicMock()
        role.id = 789
        role.name = "ExpiredRole"
        member.roles = [role]

        guild.fetch_member = AsyncMock(return_value=member)
        guild.get_role.return_value = role

        # Create expired role
        expired_role = MagicMock()
        expired_role.member_id = 456
        expired_role.role_id = 789
        expired_role.expiration_date = datetime.now() - timedelta(days=1)

        mock_role_queries.get_expired_roles = AsyncMock(return_value=[expired_role])
        mock_role_queries.delete_member_role = AsyncMock()
        mock_notif_queries.add_or_update_notification_log = AsyncMock()

        # Track call order
        call_order = []

        # Mock session commit to track when it's called
        original_commit = self.session.commit

        async def mock_commit():
            call_order.append("commit")
            await original_commit()

        self.session.commit = mock_commit

        # Mock notification handler to track when it's called
        notification_handler = AsyncMock()

        async def track_notification(*args):
            call_order.append("notification")
            await notification_handler(*args)

        track_notification_mock = AsyncMock(side_effect=track_notification)

        # Call the method
        removed_count = await self.role_manager.check_expired_roles(
            notification_handler=track_notification_mock
        )

        # Debug: print what actually happened
        print(f"Debug: call_order = {call_order}")
        print(f"Debug: removed_count = {removed_count}")
        print(
            f"Debug: track_notification_mock.call_count = {track_notification_mock.call_count}"
        )

        # Verify notification was called after commit
        self.assertEqual(call_order, ["commit", "notification"])
        self.assertEqual(removed_count, 1)
        track_notification_mock.assert_called_once()

    @patch("utils.role_manager.NotificationLogQueries")
    @patch("utils.role_manager.RoleQueries")
    @patch("utils.role_manager.logger")
    async def test_no_notifications_sent_when_commit_fails(
        self, mock_logger, mock_role_queries, mock_notif_queries
    ):
        """Test that no notifications are sent when database commit fails"""
        # Setup mocks
        guild = MagicMock()
        guild.id = 123
        self.bot.guild = guild

        member = MagicMock()
        member.id = 456
        member.display_name = "TestUser"
        member.remove_roles = AsyncMock()  # Successful role removal

        role = MagicMock()
        role.id = 789
        role.name = "ExpiredRole"
        member.roles = [role]

        guild.fetch_member = AsyncMock(return_value=member)
        guild.get_role.return_value = role

        # Create expired role
        expired_role = MagicMock()
        expired_role.member_id = 456
        expired_role.role_id = 789
        expired_role.expiration_date = datetime.now() - timedelta(days=1)

        mock_role_queries.get_expired_roles = AsyncMock(return_value=[expired_role])
        mock_role_queries.delete_member_role = AsyncMock()
        mock_notif_queries.add_or_update_notification_log = AsyncMock()

        # Make session commit fail
        self.session.commit = AsyncMock(side_effect=Exception("Commit failed"))

        # Mock notification handler
        notification_handler = AsyncMock()

        # Call the method - should handle commit failure gracefully
        removed_count = await self.role_manager.check_expired_roles(
            notification_handler=notification_handler
        )

        # Verify no notification was sent due to commit failure
        notification_handler.assert_not_called()
        self.assertEqual(removed_count, 0)  # Nothing removed due to error

    @patch("utils.role_manager.NotificationLogQueries")
    @patch("utils.role_manager.RoleQueries")
    @patch("utils.role_manager.logger")
    async def test_role_in_db_but_not_on_discord_cleanup(
        self, mock_logger, mock_role_queries, mock_notif_queries
    ):
        """Test that roles in DB but not assigned on Discord are cleaned up WITH notification"""
        # Setup mocks
        guild = MagicMock()
        guild.id = 123
        self.bot.guild = guild

        member = MagicMock()
        member.id = 456
        member.display_name = "TestUser"
        member.remove_roles = AsyncMock()  # Mock this method

        role = MagicMock()
        role.id = 789
        role.name = "ExpiredRole"

        # KEY: Member does NOT have the role on Discord, but it exists in DB
        member.roles = []  # Empty roles list

        guild.fetch_member = AsyncMock(return_value=member)
        guild.get_role.return_value = role

        # Create expired role in DB
        expired_role = MagicMock()
        expired_role.member_id = 456
        expired_role.role_id = 789
        expired_role.expiration_date = datetime.now() - timedelta(days=1)

        print(
            f"Debug: Setting up expired_role with member_id={expired_role.member_id}, role_id={expired_role.role_id}"
        )
        mock_role_queries.get_expired_roles = AsyncMock(return_value=[expired_role])
        mock_role_queries.delete_member_role = AsyncMock()
        mock_notif_queries.add_or_update_notification_log = AsyncMock()

        # Mock notification handler
        notification_handler = AsyncMock()

        # Call the method
        removed_count = await self.role_manager.check_expired_roles(
            notification_handler=notification_handler
        )

        # Debug: print what actually happened
        print(f"Debug: removed_count = {removed_count}")
        print(
            f"Debug: delete_member_role call count = {mock_role_queries.delete_member_role.call_count}"
        )
        print(f"Debug: remove_roles call count = {member.remove_roles.call_count}")

        # Verify role was NOT removed from Discord (since user doesn't have it)
        member.remove_roles.assert_not_called()

        # Verify database cleanup happened
        mock_role_queries.delete_member_role.assert_called_once_with(
            self.session, member.id, role.id
        )

        # Verify notification WAS sent (new behavior)
        notification_handler.assert_called_once()

        # Verify correct count was returned (DB cleanup counts as removal)
        self.assertEqual(removed_count, 1)

    @patch("utils.role_manager.NotificationLogQueries")
    @patch("utils.role_manager.RoleQueries")
    @patch("utils.role_manager.logger")
    async def test_member_left_server_cleanup(
        self, mock_logger, mock_role_queries, mock_notif_queries
    ):
        """Test that expired roles for members who left the server are cleaned up without notification"""
        # Setup mocks
        guild = MagicMock()
        guild.id = 123
        self.bot.guild = guild

        # Member left server - fetch_member raises NotFound
        guild.fetch_member = AsyncMock(
            side_effect=discord.NotFound(MagicMock(), "Member not found")
        )

        # Create expired role in DB for missing member
        expired_role = MagicMock()
        expired_role.member_id = 456
        expired_role.role_id = 789
        expired_role.expiration_date = datetime.now() - timedelta(days=1)

        mock_role_queries.get_expired_roles = AsyncMock(return_value=[expired_role])
        mock_role_queries.delete_member_role = AsyncMock()
        mock_notif_queries.add_or_update_notification_log = AsyncMock()

        # Mock notification handler
        notification_handler = AsyncMock()

        # Call the method
        removed_count = await self.role_manager.check_expired_roles(
            notification_handler=notification_handler
        )

        # Verify database cleanup happened
        mock_role_queries.delete_member_role.assert_called_once_with(
            self.session, expired_role.member_id, expired_role.role_id
        )

        # Verify NO notification was sent (member left server)
        notification_handler.assert_not_called()

        # Verify correct count was returned (DB cleanup counts as removal)
        self.assertEqual(removed_count, 1)

        # Verify fetch_member was called and failed as expected
        guild.fetch_member.assert_called_once_with(456)


if __name__ == "__main__":
    unittest.main()
