"""Payment repository implementation for payment-related operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.base_repository import BaseRepository
from datasources.models import HandledPayment

logger = logging.getLogger(__name__)


class PaymentRepository(BaseRepository):
    """Repository for payment-related operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(HandledPayment, session)

    async def add_payment(
        self,
        member_id: Optional[int],
        name: str,
        amount: int,
        paid_at: datetime,
        payment_type: str,
    ) -> HandledPayment:
        """Add a new payment record."""
        try:
            payment = HandledPayment(
                member_id=member_id,
                name=name,
                amount=amount,
                paid_at=paid_at,
                payment_type=payment_type,
            )
            self.session.add(payment)
            await self.session.flush()

            self._log_operation(
                "add_payment",
                name=name,
                amount=amount,
                payment_type=payment_type,
                member_id=member_id,
            )

            return payment

        except Exception as e:
            self._log_error("add_payment", e, name=name, amount=amount)
            raise

    async def get_payment_by_id(self, payment_id: int) -> Optional[HandledPayment]:
        """Get a payment by its ID."""
        try:
            payment = await self.session.get(HandledPayment, payment_id)

            self._log_operation(
                "get_payment_by_id",
                payment_id=payment_id,
                found=payment is not None,
            )

            return payment

        except Exception as e:
            self._log_error("get_payment_by_id", e, payment_id=payment_id)
            return None

    async def get_last_payments(
        self,
        offset: int = 0,
        limit: int = 10,
        payment_type: Optional[str] = None,
    ) -> list[HandledPayment]:
        """Get last 'limit' payments of specific type."""
        try:
            query = select(HandledPayment)
            
            if payment_type is not None:
                query = query.where(HandledPayment.payment_type == payment_type)
            
            query = query.order_by(HandledPayment.id.desc())
            query = query.offset(offset).limit(limit)

            result = await self.session.execute(query)
            payments = list(result.scalars().all())

            self._log_operation(
                "get_last_payments",
                offset=offset,
                limit=limit,
                payment_type=payment_type,
                count=len(payments),
            )

            return payments

        except Exception as e:
            self._log_error(
                "get_last_payments", e, offset=offset, limit=limit, payment_type=payment_type
            )
            return []

    async def add_member_id_to_payment(
        self, payment_id: int, member_id: int
    ) -> Optional[HandledPayment]:
        """Add member_id to an existing payment."""
        try:
            payment = await self.session.get(HandledPayment, payment_id)
            if payment is not None:
                payment.member_id = member_id
                await self.session.flush()

                self._log_operation(
                    "add_member_id_to_payment",
                    payment_id=payment_id,
                    member_id=member_id,
                    success=True,
                )
            else:
                self._log_operation(
                    "add_member_id_to_payment",
                    payment_id=payment_id,
                    member_id=member_id,
                    success=False,
                    error="Payment not found",
                )

            return payment

        except Exception as e:
            self._log_error(
                "add_member_id_to_payment", e, payment_id=payment_id, member_id=member_id
            )
            return None

    async def get_payment_by_name_and_amount(
        self, name: str, amount: int
    ) -> Optional[HandledPayment]:
        """Get the last payment by name and amount."""
        try:
            result = await self.session.execute(
                select(HandledPayment)
                .where(HandledPayment.name == name, HandledPayment.amount == amount)
                .order_by(HandledPayment.paid_at.desc())
            )
            payment = result.scalars().first()

            self._log_operation(
                "get_payment_by_name_and_amount",
                name=name,
                amount=amount,
                found=payment is not None,
            )

            return payment

        except Exception as e:
            self._log_error("get_payment_by_name_and_amount", e, name=name, amount=amount)
            return None

    async def get_payments_by_member(
        self, member_id: int, limit: int = 10
    ) -> list[HandledPayment]:
        """Get payments for a specific member."""
        try:
            result = await self.session.execute(
                select(HandledPayment)
                .where(HandledPayment.member_id == member_id)
                .order_by(HandledPayment.paid_at.desc())
                .limit(limit)
            )
            payments = list(result.scalars().all())

            self._log_operation(
                "get_payments_by_member",
                member_id=member_id,
                limit=limit,
                count=len(payments),
            )

            return payments

        except Exception as e:
            self._log_error("get_payments_by_member", e, member_id=member_id)
            return []

    async def get_total_payment_amount(
        self, payment_type: Optional[str] = None, member_id: Optional[int] = None
    ) -> int:
        """Get total payment amount with optional filters."""
        try:
            from sqlalchemy import func

            query = select(func.sum(HandledPayment.amount))

            if payment_type is not None:
                query = query.where(HandledPayment.payment_type == payment_type)

            if member_id is not None:
                query = query.where(HandledPayment.member_id == member_id)

            result = await self.session.execute(query)
            total = result.scalar() or 0

            self._log_operation(
                "get_total_payment_amount",
                payment_type=payment_type,
                member_id=member_id,
                total=total,
            )

            return total

        except Exception as e:
            self._log_error(
                "get_total_payment_amount", e, payment_type=payment_type, member_id=member_id
            )
            return 0