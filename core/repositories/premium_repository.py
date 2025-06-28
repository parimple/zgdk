"""Repository for premium-related data operations."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.base_repository import BaseRepository
from datasources.models import HandledPayment, MemberRole, Role


class PremiumRepository(BaseRepository):
    """Repository for premium data access operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MemberRole, session)

    async def get_member_premium_roles(self, member_id: int) -> list[dict]:
        """Get all premium roles for a member."""
        try:
            # Premium role names (based on config)
            premium_role_names = ["zG50", "zG100", "zG500", "zG1000"]

            stmt = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where(MemberRole.member_id == member_id)
                .where(Role.name.in_(premium_role_names))
            )
            result = await self.session.execute(stmt)
            rows = result.fetchall()

            premium_roles = []
            for member_role, role in rows:
                premium_roles.append(
                    {
                        "member_role": member_role,
                        "role": role,
                        "member_id": member_role.member_id,
                        "role_id": member_role.role_id,
                        "role_name": role.name,
                        "expiration_date": member_role.expiration_date,
                        "role_type": role.role_type,
                    }
                )

            self.logger.debug(
                f"Found {len(premium_roles)} premium roles for member {member_id}"
            )
            return premium_roles

        except Exception as e:
            self.logger.error(
                f"Error getting premium roles for member {member_id}: {e}"
            )
            raise

    async def get_expired_premium_roles(self, current_time: datetime) -> list[dict]:
        """Get all expired premium roles."""
        try:
            premium_role_names = ["zG50", "zG100", "zG500", "zG1000"]

            stmt = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where(MemberRole.expiration_date <= current_time)
                .where(MemberRole.expiration_date.isnot(None))
                .where(Role.name.in_(premium_role_names))
            )
            result = await self.session.execute(stmt)
            rows = result.fetchall()

            expired_roles = []
            for member_role, role in rows:
                expired_roles.append(
                    {
                        "member_role": member_role,
                        "role": role,
                        "member_id": member_role.member_id,
                        "role_id": member_role.role_id,
                        "role_name": role.name,
                        "expiration_date": member_role.expiration_date,
                        "role_type": role.role_type,
                    }
                )

            self.logger.debug(f"Found {len(expired_roles)} expired premium roles")
            return expired_roles

        except Exception as e:
            self.logger.error(f"Error getting expired premium roles: {e}")
            raise

    async def get_role_by_name(self, role_name: str) -> Optional[dict]:
        """Get role information by name."""
        try:
            stmt = select(Role).where(Role.name == role_name)
            result = await self.session.execute(stmt)
            role = result.scalar_one_or_none()

            if role:
                # Import the mapping
                from premium_role_mapping import get_premium_role_discord_id
                
                role_data = {
                    "role": role,
                    "id": role.id,
                    "name": role.name,
                    "discord_id": get_premium_role_discord_id(role.name),
                }
                self.logger.debug(f"Found role: {role_name}")
                return role_data

            self.logger.debug(f"Role not found: {role_name}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting role {role_name}: {e}")
            raise

    async def create_member_role(
        self,
        member_id: int,
        role_id: int,
        expiration_date: Optional[datetime] = None,
        role_type: str = "premium",
    ) -> bool:
        """Create a member role assignment."""
        try:
            member_role = MemberRole(
                member_id=member_id,
                role_id=role_id,
                expiration_date=expiration_date,
                role_type=role_type,
            )

            await self.create(member_role)
            self.logger.debug(
                f"Created member role: member={member_id}, role={role_id}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error creating member role: {e}")
            raise

    async def update_role_expiry(
        self, member_id: int, role_id: int, new_expiry: datetime
    ) -> bool:
        """Update role expiry time."""
        try:
            stmt = select(MemberRole).where(
                MemberRole.member_id == member_id, MemberRole.role_id == role_id
            )
            result = await self.session.execute(stmt)
            member_role = result.scalar_one_or_none()

            if member_role:
                member_role.expiration_date = new_expiry
                await self.session.flush()
                self.logger.debug(
                    f"Updated role expiry: member={member_id}, role={role_id}, new_expiry={new_expiry}"
                )
                return True

            self.logger.warning(
                f"Member role not found for expiry update: member={member_id}, role={role_id}"
            )
            return False

        except Exception as e:
            self.logger.error(f"Error updating role expiry: {e}")
            raise

    async def remove_member_role(self, member_id: int, role_id: int) -> bool:
        """Remove a member role assignment."""
        try:
            stmt = select(MemberRole).where(
                MemberRole.member_id == member_id, MemberRole.role_id == role_id
            )
            result = await self.session.execute(stmt)
            member_role = result.scalar_one_or_none()

            if member_role:
                await self.session.delete(member_role)
                await self.session.flush()
                self.logger.debug(
                    f"Removed member role: member={member_id}, role={role_id}"
                )
                return True

            self.logger.warning(
                f"Member role not found for removal: member={member_id}, role={role_id}"
            )
            return False

        except Exception as e:
            self.logger.error(f"Error removing member role: {e}")
            raise


class PaymentRepository(BaseRepository):
    """Repository for payment data operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(HandledPayment, session)

    async def is_payment_handled(
        self, payment_name: str, amount: int, paid_at: datetime
    ) -> bool:
        """Check if a payment has already been handled."""
        try:
            stmt = select(HandledPayment).where(
                HandledPayment.payment_name == payment_name,
                HandledPayment.amount == amount,
                HandledPayment.paid_at == paid_at,
            )
            result = await self.session.execute(stmt)
            payment = result.scalar_one_or_none()

            handled = payment is not None
            self.logger.debug(
                f"Payment handled check: {payment_name}, amount={amount}, handled={handled}"
            )
            return handled

        except Exception as e:
            self.logger.error(f"Error checking if payment is handled: {e}")
            raise

    async def mark_payment_as_handled(
        self,
        payment_name: str,
        amount: int,
        paid_at: datetime,
        member_id: Optional[int] = None,
        processing_result: str = "success",
    ) -> bool:
        """Mark a payment as handled."""
        try:
            handled_payment = HandledPayment(
                payment_name=payment_name,
                amount=amount,
                paid_at=paid_at,
                processed_at=datetime.now(),
                member_id=member_id,
                processing_result=processing_result,
            )

            await self.create(handled_payment)
            self.logger.debug(
                f"Marked payment as handled: {payment_name}, amount={amount}"
            )
            return True

        except Exception as e:
            self.logger.error(f"Error marking payment as handled: {e}")
            raise

    async def get_handled_payments_for_member(
        self, member_id: int, limit: int = 10
    ) -> list[dict]:
        """Get recent handled payments for a member."""
        try:
            stmt = (
                select(HandledPayment)
                .where(HandledPayment.member_id == member_id)
                .order_by(HandledPayment.processed_at.desc())
                .limit(limit)
            )
            result = await self.session.execute(stmt)
            payments = result.scalars().all()

            payment_list = []
            for payment in payments:
                payment_list.append(
                    {
                        "payment": payment,
                        "payment_name": payment.payment_name,
                        "amount": payment.amount,
                        "paid_at": payment.paid_at,
                        "processed_at": payment.processed_at,
                        "processing_result": payment.processing_result,
                    }
                )

            self.logger.debug(
                f"Found {len(payment_list)} handled payments for member {member_id}"
            )
            return payment_list

        except Exception as e:
            self.logger.error(
                f"Error getting handled payments for member {member_id}: {e}"
            )
            raise
