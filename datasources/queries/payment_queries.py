"""
Payment-related queries for the database.
"""

import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import HandledPayment

logger = logging.getLogger(__name__)


class HandledPaymentQueries:
    """Class for Handled Payment Queries"""

    @staticmethod
    async def add_payment(
        session: AsyncSession,
        member_id: Optional[int],
        name: str,
        amount: int,
        paid_at: datetime,
        payment_type: str,
    ) -> HandledPayment:
        """Add Payment"""
        payment = HandledPayment(
            member_id=member_id,
            name=name,
            amount=amount,
            paid_at=paid_at,
            payment_type=payment_type,
        )
        session.add(payment)
        await session.flush()
        return payment

    @staticmethod
    async def get_last_payments(
        session: AsyncSession,
        offset: int = 0,
        limit: int = 10,
        payment_type: Optional[str] = None,
    ) -> List[HandledPayment]:
        """Get last 'limit' payments of specific type. If payment_type is None, return all types"""
        query = select(HandledPayment).order_by(HandledPayment.id.desc()).offset(offset).limit(limit)
        if payment_type is not None:
            query = query.where(HandledPayment.payment_type == payment_type)
        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def add_member_id_to_payment(session: AsyncSession, payment_id: int, member_id: int) -> None:
        """Add member_id to an existing payment"""
        payment = await session.get(HandledPayment, payment_id)
        if payment is not None:
            payment.member_id = member_id
        else:
            logger.error("Payment with id %s not found", payment_id)

    @staticmethod
    async def get_payment_by_id(session: AsyncSession, payment_id: int) -> Optional[HandledPayment]:
        """Get a payment by its ID"""
        return await session.get(HandledPayment, payment_id)

    @staticmethod
    async def get_payment_by_name_and_amount(session: AsyncSession, name: str, amount: int) -> Optional[HandledPayment]:
        """Get the last payment by name and amount"""
        result = await session.execute(
            select(HandledPayment)
            .where(HandledPayment.name == name, HandledPayment.amount == amount)
            .order_by(HandledPayment.paid_at.desc())
        )
        return result.scalars().first()
