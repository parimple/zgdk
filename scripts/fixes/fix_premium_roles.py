"""Fix premium role Discord IDs in the database."""

import asyncio
import logging
from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database URL - for running inside Docker container
DATABASE_URL = "postgresql+asyncpg://postgres:postgres@db:5432/postgres"

# Correct Discord role IDs from config.yml audit section
PREMIUM_ROLE_MAPPING = {
    "zG50": 1306588378829164565,
    "zG100": 1306588380141846528,
    "zG500": 1317129475271557221,
    "zG1000": 1321432424101576705,
}


async def fix_premium_roles():
    """Update premium role Discord IDs in the database."""
    # Create async engine
    engine = create_async_engine(DATABASE_URL, echo=True)

    # Create session
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        try:
            logger.info("Starting premium role fix...")

            # First, check what roles exist in the database
            result = await session.execute(
                text("SELECT id, name, discord_id, role_type FROM roles WHERE role_type = 'premium'")
            )
            existing_roles = result.fetchall()

            logger.info(f"Found {len(existing_roles)} existing premium roles:")
            for role in existing_roles:
                logger.info(f"  - {role.name}: discord_id={role.discord_id}")

            # Update or insert each premium role
            for role_name, discord_id in PREMIUM_ROLE_MAPPING.items():
                # Check if role exists
                result = await session.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": role_name})
                existing = result.fetchone()

                if existing:
                    # Update existing role
                    logger.info(f"Updating {role_name} with Discord ID {discord_id}")
                    await session.execute(
                        text(
                            """
                            UPDATE roles
                            SET discord_id = :discord_id,
                                role_type = 'premium',
                                updated_at = :updated_at
                            WHERE name = :name
                        """
                        ),
                        {"discord_id": discord_id, "name": role_name, "updated_at": datetime.utcnow()},
                    )
                else:
                    # Insert new role
                    logger.info(f"Inserting new role {role_name} with Discord ID {discord_id}")
                    await session.execute(
                        text(
                            """
                            INSERT INTO roles (name, discord_id, role_type, created_at, updated_at)
                            VALUES (:name, :discord_id, 'premium', :created_at, :updated_at)
                        """
                        ),
                        {
                            "name": role_name,
                            "discord_id": discord_id,
                            "created_at": datetime.utcnow(),
                            "updated_at": datetime.utcnow(),
                        },
                    )

            # Commit changes
            await session.commit()
            logger.info("✅ Premium roles updated successfully!")

            # Verify the changes
            result = await session.execute(
                text("SELECT name, discord_id FROM roles WHERE role_type = 'premium' ORDER BY name")
            )
            updated_roles = result.fetchall()

            logger.info("\nUpdated premium roles:")
            for role in updated_roles:
                logger.info(f"  - {role.name}: {role.discord_id}")

        except Exception as e:
            logger.error(f"Error updating premium roles: {e}")
            await session.rollback()
            raise
        finally:
            await engine.dispose()


if __name__ == "__main__":
    logger.info(f"Premium Role Fix Script - {datetime.now()}")
    asyncio.run(fix_premium_roles())
