from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from datasources.models import Base, MemberRole
from datasources.queries import RoleQueries


@pytest.mark.asyncio
async def test_delete_role():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        member_role = MemberRole(member_id=123, role_id=456, expiration_date=datetime.now(timezone.utc))
        session.add(member_role)
        await session.commit()

        await RoleQueries.delete_member_role(session, 123, 456)
        await session.commit()

        result = await session.get(MemberRole, (123, 456))
        assert result is None
