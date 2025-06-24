#!/usr/bin/env python
"""
Performance test for RoleManager.check_expired_roles
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

from datasources.queries import NotificationLogQueries, RoleQueries
from utils.role_manager import RoleManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger()

# Configuration for test
TEST_USER_COUNT = 10
ROLES_PER_USER = 3


async def test_role_manager_performance():
    """Test the performance of the role_manager's check_expired_roles method"""
    start_time = time.time()

    # Setup mock for bot
    bot = MagicMock()
    guild = MagicMock()
    bot.guild = guild
    bot.config = {"mute_roles": []}

    # Setup role manager
    role_manager = RoleManager(bot)
    role_manager.send_notification = AsyncMock()
    role_manager.send_default_notification = AsyncMock()

    # Mock session
    session = AsyncMock()
    db_context = AsyncMock()
    db_context.__aenter__.return_value = session
    bot.get_db.return_value = db_context

    # Mock notification log queries
    NotificationLogQueries.add_or_update_notification_log = AsyncMock()

    # Setup patch for RoleQueries
    RoleQueries.get_expired_roles = AsyncMock()
    RoleQueries.delete_member_role = AsyncMock()

    # Create lookup dictionaries
    members = {}
    roles = {}

    # Create test data - each user has multiple expired roles
    expired_roles = []

    for user_id in range(1, TEST_USER_COUNT + 1):
        # Create member
        member = MagicMock()
        member.id = user_id
        member.display_name = f"TestUser{user_id}"
        member.remove_roles = AsyncMock()
        member.roles = []  # Start with empty roles list
        members[user_id] = member

        # Create roles for this member
        for role_id in range(1, ROLES_PER_USER + 1):
            actual_role_id = user_id * 100 + role_id

            # Create role
            role = MagicMock()
            role.id = actual_role_id
            role.name = f"Role{actual_role_id}"
            roles[actual_role_id] = role

            # Add role to member
            member.roles.append(role)

            # Create member role record
            expired_role = MagicMock()
            expired_role.member_id = user_id
            expired_role.role_id = actual_role_id
            expired_role.expiration_date = datetime.now(timezone.utc) - timedelta(
                days=1
            )

            expired_roles.append(expired_role)

    # Setup proper side_effects for get_member and get_role
    guild.get_member = MagicMock(side_effect=lambda id: members.get(id))
    guild.get_role = MagicMock(side_effect=lambda id: roles.get(id))

    # Configure the mock to return our test data
    RoleQueries.get_expired_roles.return_value = expired_roles

    setup_time = time.time() - start_time
    logger.info(f"Setup completed in {setup_time:.2f} seconds")
    logger.info(
        f"Created {TEST_USER_COUNT} users with {ROLES_PER_USER} roles each ({len(expired_roles)} total roles)"
    )

    # Run the optimized method
    logger.info("Running check_expired_roles with optimized algorithm...")
    start_exec = time.time()
    removed_count = await role_manager.check_expired_roles()
    exec_time = time.time() - start_exec

    logger.info(f"Removed {removed_count} expired roles in {exec_time:.3f} seconds")

    # Safe calculation of average time
    if removed_count > 0:
        logger.info(f"Average time per role: {exec_time / removed_count * 1000:.3f} ms")
    else:
        logger.warning("No roles were removed. Check the test setup.")

    # Verify expected behavior
    expected_roles = TEST_USER_COUNT * ROLES_PER_USER
    assert removed_count == expected_roles
    assert RoleQueries.delete_member_role.call_count == expected_roles

    # Verify the remove_roles calls
    for user_id, member in members.items():
        logger.info(
            f"User {user_id}: remove_roles called {member.remove_roles.call_count} times"
        )

    # Calculate total remove_roles calls across all members
    total_remove_calls = sum(
        member.remove_roles.call_count for member in members.values()
    )
    logger.info(f"Total remove_roles calls: {total_remove_calls}")

    # Check the number of database calls
    logger.info(f"Database delete calls: {RoleQueries.delete_member_role.call_count}")

    # Check if the batch optimization is working (should be ~TEST_USER_COUNT calls, not ROLES_PER_USER * TEST_USER_COUNT)
    if total_remove_calls > 0 and total_remove_calls <= TEST_USER_COUNT:
        logger.info("✅ Batch optimization is working correctly!")
    elif total_remove_calls == 0:
        logger.warning("❌ No remove_roles calls made. Check the test setup.")
    else:
        logger.warning(
            f"❌ Batch optimization may not be optimal. Expected ≤{TEST_USER_COUNT} calls, got {total_remove_calls}"
        )

    # Summary
    logger.info(f"Total test time: {time.time() - start_time:.2f} seconds")
    if removed_count == expected_roles:
        logger.info(f"✅ Performance test passed! Removed all {removed_count} roles.")
    else:
        logger.warning(
            f"❌ Performance test incomplete. Expected {expected_roles} roles to be removed, but removed {removed_count}."
        )


if __name__ == "__main__":
    asyncio.run(test_role_manager_performance())
