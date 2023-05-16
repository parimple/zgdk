"""Queries for the database"""

import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from .models import HandledPayment, Member, MemberRole


class MemberQueries:
    """Class for Member Queries"""

    @staticmethod
    async def get_member_by_id(session: AsyncSession, member_id: int) -> Optional[Member]:
        """Get Member by ID"""
        result = await session.execute(select(Member).filter(Member.id == member_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_wallet_balance(
        session: AsyncSession, member_id: int, new_balance: int
    ) -> None:
        """Update Wallet Balance"""
        await session.execute(
            update(Member).where(Member.id == member_id).values(wallet_balance=new_balance)
        )
        await session.commit()


class RoleQueries:
    """Class for Role Queries"""

    @staticmethod
    async def assign_role(
        session: AsyncSession,
        member_id: int,
        role_id: int,
        expiration_date: Optional[datetime.datetime] = None,
    ) -> None:
        """Assign Role"""
        member_role = MemberRole(
            member_id=member_id, role_id=role_id, expiration_date=expiration_date
        )
        session.add(member_role)
        await session.commit()


class HandledPaymentQueries:
    """Class for Handled Payment Queries"""

    @staticmethod
    async def get_payment_by_id(session: AsyncSession, payment_id: int) -> Optional[HandledPayment]:
        """Get Payment by ID"""
        result = await session.execute(select(HandledPayment).filter_by(id=payment_id))
        return result.scalars().first()

    @staticmethod
    async def add_payment(
        session: AsyncSession,
        payment_id: int,
        member_id: int,
        name: str,
        amount: float,
        paid_at: datetime,
    ) -> HandledPayment:
        """Add Payment"""

        payment = HandledPayment(
            id=payment_id,
            member_id=member_id,
            name=name,
            amount=amount,
            paid_at=paid_at,
        )

        session.add(payment)
        return payment
