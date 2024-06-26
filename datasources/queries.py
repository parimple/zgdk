"""
Queries for the database.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from .models import (
    ChannelPermission,
    HandledPayment,
    Member,
    MemberRole,
    Message,
    NotificationLog,
    Role,
)

logger = logging.getLogger(__name__)


class MemberQueries:
    """Class for Member Queries"""

    @staticmethod
    async def get_or_add_member(
        session: AsyncSession,
        member_id: int,
        wallet_balance: int = 0,
        first_inviter_id: Optional[int] = None,
        current_inviter_id: Optional[int] = None,
        joined_at: Optional[datetime] = None,
        rejoined_at: Optional[datetime] = None,
    ) -> Member:
        """Get a Member by ID, or add a new one if it doesn't exist"""
        member = await session.get(Member, member_id)

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
            await session.flush()

        return member

    @staticmethod
    async def add_to_wallet_balance(session: AsyncSession, member_id: int, amount: int) -> None:
        """Add to the wallet balance of a Member"""
        await session.execute(
            update(Member)
            .where(Member.id == member_id)
            .values(wallet_balance=Member.wallet_balance + amount)
        )


class RoleQueries:
    """Class for Role Queries"""

    @staticmethod
    async def add_role_to_member(
        session: AsyncSession,
        member_id: int,
        role_id: int,
        duration: timedelta = timedelta(days=30),
    ):
        """Add a role to a member with an expiration date"""
        expiration_date = datetime.now(timezone.utc) + duration
        member_role = MemberRole(
            member_id=member_id, role_id=role_id, expiration_date=expiration_date
        )
        session.add(member_role)

    @staticmethod
    async def add_role(
        session: AsyncSession, role_id: int, role_name: str, role_type: str = "premium"
    ):
        """Add a role to the database"""
        role = Role(id=role_id, name=role_name, role_type=role_type)
        session.add(role)

    @staticmethod
    async def get_all_roles(session: AsyncSession) -> List[Role]:
        """Get all roles from the database"""
        result = await session.execute(select(Role))
        return result.scalars().all()

    @staticmethod
    async def get_role_by_name(session: AsyncSession, name: str) -> Optional[Role]:
        """Get role by name"""
        result = await session.execute(select(Role).where(Role.name == name))
        return result.scalars().first()

    @staticmethod
    async def get_role_by_id(session: AsyncSession, role_id: int) -> Optional[Role]:
        """Get role by ID"""
        return await session.get(Role, role_id)

    @staticmethod
    async def get_member_roles(session: AsyncSession, member_id: int) -> list[MemberRole]:
        """Get all roles of a member"""
        result = await session.execute(
            select(MemberRole)
            .options(joinedload(MemberRole.role))
            .where(MemberRole.member_id == member_id)
        )
        return result.scalars().all()

    @staticmethod
    async def get_member_premium_roles(
        session: AsyncSession, member_id: Optional[int] = None
    ) -> list[tuple[MemberRole, Role]]:
        """Get all active premium roles of a member or all members if member_id is None"""
        now = datetime.now(timezone.utc)
        query = (
            select(MemberRole, Role)
            .join(Role, MemberRole.role_id == Role.id)
            .where((Role.role_type == "premium") & (MemberRole.expiration_date > now))
            .options(joinedload(MemberRole.role))
        )

        if member_id is not None:
            query = query.where(MemberRole.member_id == member_id)

        result = await session.execute(query)
        return result.unique().all()

    @staticmethod
    async def get_expiring_roles(
        session: AsyncSession, reminder_time: datetime, role_type: Optional[str] = None
    ) -> List[MemberRole]:
        """Get roles expiring within the next 24 hours"""
        query = (
            select(MemberRole)
            .options(joinedload(MemberRole.role))
            .where(MemberRole.expiration_date <= reminder_time)
        )
        if role_type:
            query = query.join(Role).where(Role.role_type == role_type)
        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_expired_roles(
        session: AsyncSession, current_time: datetime, role_type: Optional[str] = None
    ) -> List[MemberRole]:
        """Get roles that have already expired"""
        query = (
            select(MemberRole)
            .options(joinedload(MemberRole.role))
            .where(MemberRole.expiration_date <= current_time)
        )
        if role_type:
            query = query.join(Role).where(Role.role_type == role_type)
        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def delete_member_role(session: AsyncSession, member_id: int, role_id: int):
        """Delete a role of a member"""
        await session.execute(
            delete(MemberRole).where(
                (MemberRole.member_id == member_id) & (MemberRole.role_id == role_id)
            )
        )

    @staticmethod
    async def get_premium_role(session: AsyncSession, member_id: int) -> Optional[MemberRole]:
        """Get the active premium role of a member"""
        result = await session.execute(
            select(MemberRole)
            .join(Role, MemberRole.role_id == Role.id)
            .where(
                (MemberRole.member_id == member_id)
                & (Role.role_type == "premium")
                & (MemberRole.expiration_date >= datetime.now(timezone.utc))
            )
        )
        return result.scalars().first()

    @staticmethod
    async def get_role_for_member(
        session: AsyncSession, member_id: int, role_id: int
    ) -> Optional[MemberRole]:
        """Check if a member already has the role."""
        return await session.get(MemberRole, (member_id, role_id))

    @staticmethod
    async def update_role_expiration_date(
        session: AsyncSession, member_id: int, role_id: int, duration: timedelta
    ):
        """Update the expiration date of the role for the member."""
        member_role = await session.get(MemberRole, (member_id, role_id))
        if member_role:
            member_role.expiration_date += duration

    @staticmethod
    async def get_all_premium_roles(session: AsyncSession) -> List[MemberRole]:
        query = (
            select(MemberRole)
            .options(joinedload(MemberRole.role))
            .join(Role, MemberRole.role_id == Role.id)
            .where(Role.role_type == "premium")
        )
        result = await session.execute(query)
        return result.scalars().all()


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
        session: AsyncSession, offset: int = 0, limit: int = 10, payment_type: Optional[str] = None
    ) -> List[HandledPayment]:
        """Get last 'limit' payments of specific type. If payment_type is None, return all types"""
        query = (
            select(HandledPayment).order_by(HandledPayment.id.desc()).offset(offset).limit(limit)
        )
        if payment_type is not None:
            query = query.where(HandledPayment.payment_type == payment_type)
        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def add_member_id_to_payment(
        session: AsyncSession, payment_id: int, member_id: int
    ) -> None:
        """Add member_id to an existing payment"""
        payment = await session.get(HandledPayment, payment_id)
        if payment is not None:
            payment.member_id = member_id
        else:
            logger.error("Payment with id %s not found", payment_id)

    @staticmethod
    async def get_payment_by_id(session: AsyncSession, payment_id: int) -> Optional[HandledPayment]:
        """Fetch a payment by its ID."""
        return await session.get(HandledPayment, payment_id)


class ChannelPermissionQueries:
    """Class for Channel Permission Queries"""

    @staticmethod
    async def add_or_update_permission(
        session: AsyncSession,
        member_id: int,
        target_id: int,
        allow_permissions_value: int,
        deny_permissions_value: int,
    ):
        """Add or update channel permissions for a specific member or role."""
        permission = await session.get(ChannelPermission, (member_id, target_id))

        if permission is None:
            permission = ChannelPermission(
                member_id=member_id,
                target_id=target_id,
                allow_permissions_value=allow_permissions_value,
                deny_permissions_value=deny_permissions_value,
                last_updated_at=datetime.now(timezone.utc),
            )
            session.add(permission)
        else:
            permission.allow_permissions_value = (
                permission.allow_permissions_value | allow_permissions_value
            ) & ~deny_permissions_value
            permission.deny_permissions_value = (
                permission.deny_permissions_value | deny_permissions_value
            ) & ~allow_permissions_value
            permission.last_updated_at = datetime.now(timezone.utc)

    @staticmethod
    async def remove_permission(session: AsyncSession, member_id: int, target_id: int):
        """Remove channel permissions for a specific member or role."""
        await session.execute(
            delete(ChannelPermission).where(
                (ChannelPermission.member_id == member_id)
                & (ChannelPermission.target_id == target_id)
            )
        )

    @staticmethod
    async def get_permission(
        session: AsyncSession, member_id: int, target_id: int
    ) -> Optional[ChannelPermission]:
        """Get channel permissions for a specific member or role."""
        return await session.get(ChannelPermission, (member_id, target_id))

    @staticmethod
    async def get_permissions_for_target(
        session: AsyncSession, target_id: int
    ) -> List[ChannelPermission]:
        """Get all channel permissions for a specific target (member or role)."""
        result = await session.execute(
            select(ChannelPermission).where(ChannelPermission.target_id == target_id)
        )
        return result.scalars().all()

    @staticmethod
    async def get_permissions_for_member(
        session: AsyncSession, member_id: int
    ) -> List[ChannelPermission]:
        """Get all channel permissions across different channels for a specific member."""
        result = await session.execute(
            select(ChannelPermission).where(ChannelPermission.member_id == member_id)
        )
        return result.scalars().all()


class NotificationLogQueries:
    """Class for Notification Log Queries"""

    @staticmethod
    async def add_or_update_notification_log(
        session: AsyncSession,
        member_id: int,
        notification_tag: str,
        opted_out: Optional[bool] = None,
    ) -> NotificationLog:
        logger.info(
            f"Adding/updating notification log: Member ID: {member_id}, Tag: {notification_tag}"
        )
        notification_log = await session.get(NotificationLog, (member_id, notification_tag))

        if notification_log is None:
            logger.info("Creating new notification log")
            notification_log = NotificationLog(
                member_id=member_id,
                notification_tag=notification_tag,
                sent_at=datetime.now(timezone.utc),
                opted_out=False if opted_out is None else opted_out,
            )
            session.add(notification_log)
        else:
            logger.info(
                f"Updating existing notification log. Old sent_at: {notification_log.sent_at}"
            )
            notification_log.sent_at = datetime.now(timezone.utc)
            if opted_out is not None:
                notification_log.opted_out = opted_out

        logger.info(f"Notification log after update: {notification_log}")
        return notification_log

    @staticmethod
    async def get_notification_log(
        session: AsyncSession, member_id: int, notification_tag: str
    ) -> Optional[NotificationLog]:
        """Get a notification log for a specific member and tag"""
        return await session.get(NotificationLog, (member_id, notification_tag))

    @staticmethod
    async def get_notification_logs(
        session: AsyncSession, member_id: int, notification_tag: Optional[str] = None
    ) -> List[NotificationLog]:
        """Get all notification logs for a specific member"""
        query = select(NotificationLog).where(NotificationLog.member_id == member_id)
        if notification_tag:
            query = query.where(NotificationLog.notification_tag == notification_tag)
        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_member_roles_with_notifications(
        session: AsyncSession,
        expiration_threshold: datetime,
        role_ids: Optional[list[int]] = None,
        notification_tag: Optional[str] = None,
    ) -> list[tuple[MemberRole, Optional[NotificationLog]]]:
        query = (
            select(MemberRole, NotificationLog)
            .options(joinedload(MemberRole.role))
            .outerjoin(
                NotificationLog,
                (MemberRole.member_id == NotificationLog.member_id)
                & (NotificationLog.notification_tag == notification_tag),
            )
            .join(Role, MemberRole.role_id == Role.id)
            .where(
                (MemberRole.expiration_date <= expiration_threshold) & (Role.role_type == "premium")
            )
        )

        if role_ids:
            query = query.where(MemberRole.role_id.in_(role_ids))

        logger.info(f"SQL Query: {query.compile(compile_kwargs={'literal_binds': True})}")
        result = await session.execute(query)
        roles_with_notifications = result.all()
        for role, notification in roles_with_notifications:
            logger.info(
                f"Found role: Member ID: {role.member_id}, Role ID: {role.role_id}, "
                f"Expiration Date: {role.expiration_date}, "
                f"Notification: {notification.notification_tag if notification else 'None'}"
            )
        return roles_with_notifications


class MessageQueries:
    """Class for Message Queries"""

    @staticmethod
    async def save_message(
        session: AsyncSession,
        message_id: int,
        author_id: int,
        content: str,
        timestamp: datetime,
        channel_id: int,
        reply_to_message_id: Optional[int] = None,
    ):
        """Save a message to the database"""
        message = Message(
            id=message_id,
            author_id=author_id,
            content=content,
            timestamp=timestamp,
            channel_id=channel_id,
            reply_to_message_id=reply_to_message_id,
        )
        session.add(message)
        await session.flush()
