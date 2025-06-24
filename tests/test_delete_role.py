"""Test script for testing role deletion"""
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from datasources.models import Base, MemberRole
from datasources.queries import RoleQueries

# Skonfiguruj logi, aby wyświetlały się na konsoli
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


import pytest


@pytest.mark.asyncio
async def test_delete_role():
    """Test the delete_member_role function"""
    logger.info("Starting test_delete_role")

    # Utwórz tymczasową bazę danych w pamięci
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    logger.info("Created in-memory database engine")

    # Stwórz schemat bazy danych
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database schema created")

    # Dodaj test role
    async with async_session() as session:
        member_role = MemberRole(
            member_id=123, role_id=456, expiration_date=datetime.now(timezone.utc)
        )
        session.add(member_role)
        await session.commit()
        logger.info("Test MemberRole created: %s", member_role)

        # Test usunięcia roli
        logger.info("Attempting to delete role")
        await RoleQueries.delete_member_role(session, 123, 456)
        await session.commit()
        logger.info("MemberRole deleted successfully")

        # Sprawdź, czy rola została usunięta
        result = await session.get(MemberRole, (123, 456))
        if result is None:
            logger.info("Verification successful - role no longer exists")
        else:
            logger.error("Verification failed - role still exists: %s", result)

    logger.info("Test completed successfully")
