#!/usr/bin/env python3
"""Check user's current roles in database."""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from datasources.queries import RoleQueries

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def check_user_roles():
    """Check user's roles."""
    # Use Docker database URL
    database_url = "postgresql+asyncpg://postgres:postgres@db:5432/postgres"
    engine = create_async_engine(database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            member_id = 956602391891947592

            # Get all roles
            member_roles = await RoleQueries.get_member_roles(session, member_id)
            logger.info(f"\nUser {member_id} has {len(member_roles)} roles:")

            now = datetime.now(timezone.utc)
            for mr in member_roles:
                role = await RoleQueries.get_role_by_id(session, mr.role_id)
                role_name = role.name if role else f"Unknown ({mr.role_id})"

                if mr.expiration_date and mr.expiration_date > now:
                    status = "ACTIVE"
                    time_left = mr.expiration_date - now
                    days_left = time_left.days
                else:
                    status = "EXPIRED"
                    days_left = 0

                logger.info(
                    f"  - {role_name} ({mr.role_id}): {status} - expires {mr.expiration_date} ({days_left} days left)"
                )

        except Exception as e:
            logger.error(f"Error: {e}", exc_info=True)
        finally:
            await engine.dispose()


if __name__ == "__main__":
    asyncio.run(check_user_roles())
