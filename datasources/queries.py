"""Queries for the database"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Member


async def create_member(session: AsyncSession, name: str):
    """Create a new member"""
    new_member = Member(name=name)
    session.add(new_member)
    await session.commit()
    await session.refresh(new_member)
    return new_member


async def get_all_members(session: AsyncSession):
    """Get all members"""
    result = await session.execute(select(Member))
    return result.scalars().all()
