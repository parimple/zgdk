"""Queries for the database"""
import datetime
import logging
from typing import Optional, Sequence

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from .models import HandledPayment, Member, MemberRole, Role

logger = logging.getLogger(__name__)


class MemberQueries:
    """Class for Member Queries"""

    @staticmethod
    async def get_or_add_member(  # pylint: disable=too-many-arguments
        session: AsyncSession,
        member_id: int,
        wallet_balance: int = 0,
        first_inviter_id: Optional[int] = None,
        current_inviter_id: Optional[int] = None,
        joined_at: Optional[datetime.datetime] = None,
        rejoined_at: Optional[datetime.datetime] = None,
    ) -> Member:
        """Get a Member by ID, or add a new one if it doesn't exist"""
        result = await session.execute(select(Member).where(Member.id == member_id))
        member = result.scalars().first()

        # If member does not exist, add them
        if member is None:
            member = Member(
                id=member_id,
                wallet_balance=wallet_balance,
                first_inviter_id=first_inviter_id,
                current_inviter_id=current_inviter_id,
                joined_at=joined_at,
                rejoined_at=rejoined_at,
            )
            session.add(member)

        return member

    @staticmethod
    async def add_to_wallet_balance(session: AsyncSession, member_id: int, amount: int) -> None:
        """Add to the wallet balance of a Member"""

        # Get or add member before modifying their balance
        logging.info("Getting or adding member")
        await MemberQueries.get_or_add_member(session, member_id)

        stmt = (
            update(Member)
            .where(Member.id == member_id)
            .values(wallet_balance=Member.wallet_balance + amount)
        )
        logging.info("Updating wallet balance")
        await session.execute(stmt)


class RoleQueries:
    """Class for Role Queries"""

    @staticmethod
    async def add_role_to_member(
        session: AsyncSession, member_id: int, role_id: int, duration: int = 30, unit: str = "days"
    ):
        """Add a role to a member with an expiration date"""
        if unit == "minutes":
            expiration_date = datetime.datetime.now() + datetime.timedelta(minutes=duration)
        elif unit == "hours":
            expiration_date = datetime.datetime.now() + datetime.timedelta(hours=duration)
        else:  # default to days if unit is not recognized
            expiration_date = datetime.datetime.now() + datetime.timedelta(days=duration)
        member_role = MemberRole(
            member_id=member_id, role_id=role_id, expiration_date=expiration_date
        )
        session.add(member_role)
        await session.commit()

    @staticmethod
    async def add_role(
        session: AsyncSession, role_id: int, role_name: str, role_type: str = "premium"
    ):
        """Add a role to the database"""
        role = Role(id=role_id, name=role_name, role_type=role_type)
        session.add(role)

    @staticmethod
    async def get_all_roles(session: AsyncSession):
        """Get all roles from the database"""
        result = await session.execute(select(Role))
        return result.scalars().all()

    @staticmethod
    async def get_role_by_name(session: AsyncSession, name: str):
        """Get role by name"""
        result = await session.execute(select(Role).where(Role.name == name))
        return result.scalars().first()

    @staticmethod
    async def get_member_roles(session: AsyncSession, member_id: int):
        """Get all roles of a member"""
        result = await session.execute(
            select(MemberRole).join(Role).where(MemberRole.member_id == member_id)
        )
        return result.scalars().all()

    @staticmethod
    async def get_member_premium_roles(session: AsyncSession, member_id: int):
        """Get all premium roles of a member"""
        result = await session.execute(
            select(MemberRole)
            .join(Role)
            .where((MemberRole.member_id == member_id) & (Role.role_type == "premium"))
        )
        return result.scalars().all()

    @staticmethod
    async def delete_member_role(session: AsyncSession, member_id: int, role_id: int):
        """Delete a role of a member"""
        await session.execute(
            delete(MemberRole).where(
                (MemberRole.member_id == member_id) & (MemberRole.role_id == role_id)
            )
        )
        await session.commit()

    @staticmethod
    async def get_premium_role(session: AsyncSession, member_id: int):
        """Get the active premium role of a member"""
        result = await session.execute(
            select(MemberRole)
            .join(Role)
            .where(
                (MemberRole.member_id == member_id)
                & (Role.role_type == "premium")
                & (MemberRole.expiration_date >= datetime.datetime.now())
            )
        )
        return result.scalars().first()


class HandledPaymentQueries:
    """Class for Handled Payment Queries"""

    @staticmethod
    async def add_payment(  # pylint: disable=too-many-arguments
        session: AsyncSession,
        member_id: Optional[int],
        name: str,
        amount: int,
        paid_at: datetime.datetime,
        payment_type: str,
    ) -> HandledPayment:
        """Add Payment"""
        logger.info("add_payment")
        payment = HandledPayment(
            member_id=member_id,
            name=name,
            amount=amount,
            paid_at=paid_at,
            payment_type=payment_type,
        )

        session.add(payment)
        return payment

    @staticmethod
    async def get_last_payments(
        session: AsyncSession, limit: int = 10, payment_type: Optional[str] = None
    ) -> Sequence[HandledPayment]:
        """Get last 'limit' payments of specific type. If payment_type is None, return all types"""
        logger.info("get_last_payments")
        query = select(HandledPayment)
        if payment_type is not None:
            query = query.where(HandledPayment.payment_type == payment_type)
        query = query.order_by(HandledPayment.id.desc()).limit(limit)
        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def add_member_id_to_payment(
        session: AsyncSession, payment_id: int, member_id: int
    ) -> None:
        """Add member_id to an existing payment"""
        logger.info("add_member_id_to_payment")
        payment = await session.get(HandledPayment, payment_id)
        if payment is not None:
            payment.member_id = member_id
        else:
            logger.error("Payment with id %s not found", payment_id)
