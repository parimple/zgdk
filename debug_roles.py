#!/usr/bin/env python3
"""Debug script to check roles in database."""

import asyncio
import logging

from datasources.queries import RoleQueries
from main import setup_database, setup_logging

logger = logging.getLogger(__name__)


async def check_roles():
    session_factory = await setup_database()
    async with session_factory() as session:
        roles = await RoleQueries.get_all_roles(session)
        logger.info("Roles in database:")
        for role in roles:
            logger.info(
                "  ID: %s, Name: %s, Type: %s", role.id, role.name, role.role_type
            )

        # Check specific gender roles
        male_role = await RoleQueries.get_role_by_id(session, 960665311701528599)
        female_role = await RoleQueries.get_role_by_id(session, 960665311701528600)

        logger.info("\nGender roles:")
        logger.info("  Male role (960665311701528599): %s", male_role)
        logger.info("  Female role (960665311701528600): %s", female_role)


if __name__ == "__main__":
    setup_logging()
    asyncio.run(check_roles())
