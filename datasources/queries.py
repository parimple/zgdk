"""
Queries for the database.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import asc, delete, desc, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.expression import and_, case, or_
from sqlalchemy.sql.functions import func

from datasources.models import (
    Activity,
    AutoKick,
    ChannelPermission,
    HandledPayment,
    Invite,
    Member,
    MemberRole,
    Message,
    ModerationLog,
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
            try:
                await session.flush()
            except IntegrityError:
                await session.rollback()
                member = await session.get(Member, member_id)
                if member is None:
                    logger.error(f"Failed to add or retrieve member with ID {member_id}")
                    raise

        # Update fields for existing members
        if current_inviter_id is not None:
            member.current_inviter_id = current_inviter_id
        if rejoined_at is not None:
            member.rejoined_at = rejoined_at

        return member

    @staticmethod
    async def add_to_wallet_balance(session: AsyncSession, member_id: int, amount: int) -> None:
        """Add to the wallet balance of a Member"""
        await session.execute(
            update(Member)
            .where(Member.id == member_id)
            .values(wallet_balance=Member.wallet_balance + amount)
        )

    @staticmethod
    async def extend_voice_bypass(
        session: AsyncSession, member_id: int, duration: timedelta
    ) -> Optional[datetime]:
        """
        Extend the voice bypass duration for a member.
        If member has no active bypass, starts from now.
        If member has active bypass, extends from current expiration.
        Returns the new expiration datetime or None if failed.
        """
        try:
            member = await MemberQueries.get_or_add_member(session, member_id)
            now = datetime.now(timezone.utc)

            if member.voice_bypass_until is None or member.voice_bypass_until < now:
                member.voice_bypass_until = now + duration
            else:
                member.voice_bypass_until += duration

            await session.flush()
            return member.voice_bypass_until
        except Exception as e:
            logger.error(f"Failed to extend voice bypass for member {member_id}: {str(e)}")
            return None

    @staticmethod
    async def get_voice_bypass_status(session: AsyncSession, member_id: int) -> Optional[datetime]:
        """
        Get the current voice bypass expiration datetime for a member.
        Returns None if member has no bypass or if it's expired.
        """
        member = await session.get(Member, member_id)
        if not member or not member.voice_bypass_until:
            return None

        now = datetime.now(timezone.utc)
        return member.voice_bypass_until if member.voice_bypass_until > now else None

    @staticmethod
    async def clear_voice_bypass(session: AsyncSession, member_id: int) -> bool:
        """
        Clear the voice bypass for a member.
        Returns True if successful, False otherwise.
        """
        try:
            member = await session.get(Member, member_id)
            if member:
                member.voice_bypass_until = None
                await session.flush()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to clear voice bypass for member {member_id}: {str(e)}")
            return False

    @staticmethod
    async def add_bypass_time(session: AsyncSession, user_id: int, hours: int) -> Optional[Member]:
        """Add bypass time to a member"""
        member = await session.get(Member, user_id)
        if not member:
            return None

        now = datetime.now(timezone.utc)
        if not member.voice_bypass_until or member.voice_bypass_until < now:
            member.voice_bypass_until = now + timedelta(hours=hours)
        else:
            member.voice_bypass_until += timedelta(hours=hours)

        return member

    @staticmethod
    async def set_voice_bypass_status(
        session: AsyncSession, member_id: int, expiration: datetime
    ) -> Optional[Member]:
        """
        Set the voice bypass status for a member.
        Args:
            session: The database session
            member_id: The ID of the member
            expiration: The expiration datetime for the bypass
        Returns:
            The updated Member object or None if failed
        """
        try:
            member = await MemberQueries.get_or_add_member(session, member_id)
            member.voice_bypass_until = expiration
            await session.flush()
            return member
        except Exception as e:
            logger.error(f"Failed to set voice bypass status for member {member_id}: {str(e)}")
            return None


class RoleQueries:
    """Class for Role Queries"""

    @staticmethod
    async def add_or_update_role_to_member(
        session: AsyncSession,
        member_id: int,
        role_id: int,
        duration: Optional[timedelta] = timedelta(days=30),
    ):
        """Add a role to a member or update its expiration date if it already exists"""
        try:
            member_role = await session.get(MemberRole, (member_id, role_id))

            # Calculate expiration date (if duration is None, set it to None for permanent)
            expiration_date = None if duration is None else datetime.now(timezone.utc) + duration

            if member_role:
                member_role.expiration_date = expiration_date
                logger.info(f"Updated expiration date for role {role_id} of member {member_id}")
            else:
                member_role = MemberRole(
                    member_id=member_id, role_id=role_id, expiration_date=expiration_date
                )
                session.add(member_role)
                logger.info(f"Added new role {role_id} to member {member_id}")
            await session.flush()
        except IntegrityError as e:
            await session.rollback()
            logger.error(
                f"IntegrityError occurred while adding/updating role {role_id} for member {member_id}: {str(e)}"
            )
        except Exception as e:
            await session.rollback()
            logger.error(
                f"Unexpected error occurred while adding/updating role {role_id} for member {member_id}: {str(e)}"
            )

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
        session: AsyncSession, member_id: int
    ) -> list[tuple[MemberRole, Role]]:
        """Pobiera wszystkie role premium użytkownika, aktywne i wygasłe."""
        try:
            # Poprawna logika zapytania: pobiera wszystkie role premium użytkownika (aktywne i wygasłe).
            query = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where((MemberRole.member_id == member_id) & (Role.role_type == "premium"))
            )
            logger.info(
                f"Executing query for member_id {member_id} in get_member_premium_roles: {query}"
            )
            result = await session.execute(query)

            # Logowanie .first() dla wglądu w pierwszy potencjalny wiersz
            # Musimy być ostrożni, .first() może skonsumować wynik, więc lepiej wykonać to na nowym zapytaniu lub na kopii
            # Dla uproszczenia, po prostu zalogujemy i zobaczymy, czy .all() nadal działa.
            # W idealnym świecie, jeśli .first() konsumuje, należałoby ponownie wykonać zapytanie dla .all().
            temp_result_for_first = await session.execute(
                query
            )  # Wykonaj zapytanie ponownie dla .first()
            first_row = temp_result_for_first.first()
            logger.info(f"Query result.first() for member_id {member_id}: {first_row}")

            fetched_roles = result.all()  # Użyj oryginalnego wyniku dla .all()
            logger.info(
                f"Fetched roles via result.all() for member_id {member_id} (count: {len(fetched_roles)}): {fetched_roles}"
            )
            return fetched_roles
        except Exception as e:
            logger.error(
                f"Błąd podczas pobierania ról premium użytkownika {member_id}: {e}", exc_info=True
            )
            return []

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
        session: AsyncSession,
        current_time: datetime,
        role_type: Optional[str] = None,
        role_ids: Optional[List[int]] = None,
    ) -> List[MemberRole]:
        """Get roles that have already expired

        :param session: Database session
        :param current_time: Current time to compare expiration dates against
        :param role_type: Optional filter by role type (e.g., "premium")
        :param role_ids: Optional list of specific role IDs to filter by
        :return: List of expired member roles
        """
        query = (
            select(MemberRole)
            .options(joinedload(MemberRole.role))
            .where(
                and_(
                    MemberRole.expiration_date.isnot(
                        None
                    ),  # Don't select roles with no expiration date
                    MemberRole.expiration_date <= current_time,
                )
            )
        )

        if role_type:
            query = query.join(Role).where(Role.role_type == role_type)

        if role_ids:
            query = query.where(MemberRole.role_id.in_(role_ids))

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def delete_member_role(session: AsyncSession, member_id: int, role_id: int):
        """Delete a role of a member"""
        try:
            # Bezpośrednie wykonanie SQL DELETE z użyciem text()
            sql = text(
                f"DELETE FROM member_roles WHERE member_id = :member_id AND role_id = :role_id"
            )
            await session.execute(sql, {"member_id": member_id, "role_id": role_id})
            logger.info(f"Deleted role {role_id} for member {member_id} using raw SQL")
        except Exception as e:
            logger.error(f"Error deleting role {role_id} for member {member_id}: {str(e)}")
            raise

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
    ) -> Optional[MemberRole]:
        """Update the expiration date of the role for the member."""
        try:
            # Get the current member role
            member_role = await session.get(MemberRole, (member_id, role_id))
            if member_role:
                old_expiry = member_role.expiration_date
                member_role.expiration_date = member_role.expiration_date + duration
                logger.info(
                    f"[ROLE_UPDATE] Extending role {role_id} for member {member_id}:"
                    f"\n - Old expiry: {old_expiry}"
                    f"\n - Duration to add: {duration}"
                    f"\n - New expiry: {member_role.expiration_date}"
                )

                # Return the updated role object without flushing
                return member_role
            return None
        except Exception as e:
            logger.error(f"Error updating role expiration date: {str(e)}")
            raise

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

    @staticmethod
    async def update_role_expiration_date_direct(
        session, member_id: int, role_id: int, new_expiry: datetime
    ):
        """Update role expiration date directly to a specific datetime."""
        member_role = (
            await session.execute(
                select(MemberRole).where(
                    MemberRole.member_id == member_id,
                    MemberRole.role_id == role_id,
                )
            )
        ).scalar_one_or_none()

        if member_role:
            member_role.expiration_date = new_expiry

    @staticmethod
    async def get_member_role(
        session: AsyncSession, member_id: int, role_id: int
    ) -> Optional[MemberRole]:
        """Get a specific member role"""
        result = await session.execute(
            select(MemberRole).where(
                and_(MemberRole.member_id == member_id, MemberRole.role_id == role_id)
            )
        )
        return result.scalars().first()

    @staticmethod
    async def safe_delete_member_role(session: AsyncSession, member_id: int, role_id: int):
        """
        Bezpieczna metoda usuwania roli użytkownika, która unika problemów z ORM.
        W przeciwieństwie do delete_member_role, ta metoda:
        1. Zamyka wcześniej sesję przed wykonaniem delete
        2. Nie używa relacji, tylko usuwanie według klucza głównego
        3. Jest bardziej odporna na błędy
        """
        try:
            # Pobierz obiekt z bazy bez używania relacji
            stmt = select(MemberRole).where(
                (MemberRole.member_id == member_id) & (MemberRole.role_id == role_id)
            )
            result = await session.execute(stmt)
            member_role = result.scalar_one_or_none()

            if member_role:
                # Zdetachuj obiekt od sesji
                session.expunge(member_role)

                # Wykonaj surowy SQL DELETE z użyciem text()
                sql = text(
                    f"DELETE FROM member_roles WHERE member_id = :member_id AND role_id = :role_id"
                )
                await session.execute(sql, {"member_id": member_id, "role_id": role_id})

                logger.info(f"Safely deleted role {role_id} for member {member_id}")
                return True
            else:
                logger.warning(f"No role {role_id} found for member {member_id} to delete (safe)")
                return False
        except Exception as e:
            logger.error(f"Error in safe_delete_member_role: {str(e)}")
            raise

    @staticmethod
    async def raw_delete_member_role(session: AsyncSession, member_id: int, role_id: int) -> bool:
        """
        Najprostsza i najbezpieczniejsza metoda usuwania roli członka, używająca wyłącznie surowego SQL.
        Ta metoda jest stworzona specjalnie do rozwiązania problemu z usuwaniem ról podczas sprzedaży.
        """
        try:
            # Użyj text() do deklaracji surowego SQL
            sql = text(
                f"DELETE FROM member_roles WHERE member_id = :member_id AND role_id = :role_id"
            )
            await session.execute(sql, {"member_id": member_id, "role_id": role_id})
            logger.info(f"Raw SQL deletion of role {role_id} for member {member_id} succeeded")
            return True
        except Exception as e:
            logger.error(f"Raw SQL deletion failed for role {role_id}, member {member_id}: {e}")
            return False

    @staticmethod
    async def orm_delete_member_role(session: AsyncSession, member_id: int, role_id: int) -> bool:
        """
        Metoda usuwania roli członka używająca ORM SQLAlchemy, ale w bezpieczny sposób.
        Ta metoda używa funkcji delete() zamiast surowego SQL.
        """
        try:
            # Użyj delete() zamiast surowego SQL
            stmt = delete(MemberRole).where(
                (MemberRole.member_id == member_id) & (MemberRole.role_id == role_id)
            )
            result = await session.execute(stmt)
            await session.flush()
            logger.info(f"ORM deletion of role {role_id} for member {member_id} succeeded")
            return True
        except Exception as e:
            logger.error(f"ORM deletion failed for role {role_id}, member {member_id}: {e}")
            return False

    @staticmethod
    async def get_role_members(session: AsyncSession, role_id: int) -> List[MemberRole]:
        """Get all members that have a specific role

        :param session: The database session
        :param role_id: The ID of the role to query
        :return: List of MemberRole objects for all members with this role
        """
        result = await session.execute(
            select(MemberRole)
            .options(joinedload(MemberRole.role))
            .where(MemberRole.role_id == role_id)
        )
        return result.scalars().all()

    @staticmethod
    async def count_unique_premium_users(session: AsyncSession) -> int:
        """Count unique members who have ever had any premium role (including expired)"""
        try:
            query = (
                select(func.count(func.distinct(MemberRole.member_id)))
                .select_from(MemberRole)
                .join(Role, MemberRole.role_id == Role.id)
                .where(Role.role_type == "premium")
            )
            result = await session.execute(query)
            count = result.scalar()
            return count if count is not None else 0
        except Exception as e:
            logger.error(f"Error counting unique premium users: {e}")
            return 200  # Fallback number


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
        """Get a payment by its ID"""
        return await session.get(HandledPayment, payment_id)

    @staticmethod
    async def get_payment_by_name_and_amount(
        session: AsyncSession, name: str, amount: int
    ) -> Optional[HandledPayment]:
        """Get the last payment by name and amount"""
        result = await session.execute(
            select(HandledPayment)
            .where(HandledPayment.name == name, HandledPayment.amount == amount)
            .order_by(HandledPayment.paid_at.desc())
        )
        return result.scalars().first()


class ChannelPermissionQueries:
    """Class for Channel Permission Queries"""

    @staticmethod
    async def add_or_update_permission(
        session: AsyncSession,
        member_id: int,
        target_id: int,
        allow_permissions_value: int,
        deny_permissions_value: int,
        guild_id: int,
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

        # Count permissions excluding default ones (which are not in database)
        permissions_count = await session.scalar(
            select(func.count())
            .select_from(ChannelPermission)
            .where(ChannelPermission.member_id == member_id)
        )

        # If we're about to exceed the limit
        if permissions_count > 95:
            # Find the oldest permission that:
            # 1. Belongs to this owner
            # 2. Is not a moderator permission (no manage_messages)
            # 3. Is not an @everyone permission
            oldest_permission = await session.execute(
                select(ChannelPermission)
                .where(
                    (ChannelPermission.member_id == member_id)
                    & (
                        ChannelPermission.allow_permissions_value.bitwise_and(0x00002000) == 0
                    )  # not manage_messages
                    & (ChannelPermission.target_id != guild_id)  # not @everyone
                )
                .order_by(ChannelPermission.last_updated_at.asc())
                .limit(1)
            )
            oldest_permission = oldest_permission.scalar_one_or_none()
            if oldest_permission:
                await session.delete(oldest_permission)
                logger.info(
                    f"Deleted oldest permission for member {member_id} (target: {oldest_permission.target_id})"
                )

    @staticmethod
    async def remove_permission(session: AsyncSession, member_id: int, target_id: int):
        """Remove channel permissions for a specific member or role."""
        permission = await session.get(ChannelPermission, (member_id, target_id))
        if permission:
            await session.delete(permission)
            logger.info(f"Removed permission for member {member_id} and target {target_id}")
        else:
            logger.warning(f"No permission found for member {member_id} and target {target_id}")

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
        session: AsyncSession, member_id: int, limit: int = 95
    ) -> List[ChannelPermission]:
        """Get channel permissions for a specific member, limited to the most recent ones."""
        result = await session.execute(
            select(ChannelPermission)
            .where(ChannelPermission.member_id == member_id)
            .order_by(
                case(
                    (
                        ChannelPermission.allow_permissions_value.bitwise_and(0x00002000) != 0,
                        0,
                    ),  # manage_messages
                    (ChannelPermission.target_id == member_id, 0),  # everyone permissions
                    else_=1,
                ),
                ChannelPermission.last_updated_at.desc(),
            )
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def remove_all_permissions(session: AsyncSession, owner_id: int):
        """Remove all permissions for a specific owner."""
        result = await session.execute(
            select(ChannelPermission).where(ChannelPermission.member_id == owner_id)
        )
        permissions = result.scalars().all()

        for permission in permissions:
            await session.delete(permission)

        logger.info(f"Removed all {len(permissions)} permissions for owner {owner_id}")

    @staticmethod
    async def remove_mod_permissions_granted_by_member(session: AsyncSession, owner_id: int):
        """
        Remove only moderator permissions granted by a specific member.

        This method finds and removes permissions where:
        1. The specified user is the owner (member_id)
        2. The permission includes manage_messages (moderator permission)

        This preserves all other permissions the user has granted.

        Args:
            session: The database session
            owner_id: The ID of the member who granted the permissions
        """
        # Znajdujemy wszystkie uprawnienia gdzie użytkownik jest właścicielem (member_id)
        permissions = await session.execute(
            select(ChannelPermission).where(ChannelPermission.member_id == owner_id)
        )
        permissions = permissions.scalars().all()

        # Sprawdzamy każde uprawnienie, czy zawiera manage_messages (bit 15 w Discord Permissions)
        mod_permissions_removed = 0
        for permission in permissions:
            # Sprawdź czy uprawnienie zawiera manage_messages (0x00002000)
            if permission.allow_permissions_value & 0x00002000:
                # Usuń uprawnienie, które zawiera manage_messages
                await session.delete(permission)
                mod_permissions_removed += 1
                logger.info(
                    f"Removed moderator permission granted by {owner_id} to target {permission.target_id}"
                )

        logger.info(
            f"Total moderator permissions removed for owner {owner_id}: {mod_permissions_removed}"
        )

    @staticmethod
    async def remove_mod_permissions_for_target(session: AsyncSession, target_id: int):
        """
        Remove all moderator permissions for a specific target.

        This method removes all permissions where the user (target_id) has been
        granted manage_messages permission (moderator permission) by any channel owner.

        Args:
            session: The database session
            target_id: The ID of the user whose moderator permissions should be removed
        """
        # Znajdujemy wszystkie uprawnienia gdzie użytkownik jest celem (target_id)
        permissions = await session.execute(
            select(ChannelPermission).where(ChannelPermission.target_id == target_id)
        )
        permissions = permissions.scalars().all()

        # Sprawdzamy każde uprawnienie, czy zawiera manage_messages (bit 15 w Discord Permissions)
        for permission in permissions:
            # Sprawdź czy uprawnienie zawiera manage_messages (0x00002000)
            if permission.allow_permissions_value & 0x00002000:
                # Usuń uprawnienie, które zawiera manage_messages
                await session.delete(permission)
                logger.info(
                    f"Removed moderator permission for target {target_id} from owner {permission.member_id}"
                )


class NotificationLogQueries:
    """Class for Notification Log Queries"""

    GLOBAL_SERVICES = ["disboard"]  # tylko Disboard jest globalny
    MAX_NOTIFICATION_COUNT = 3

    @staticmethod
    async def add_or_update_notification_log(
        session: AsyncSession,
        member_id: int,
        notification_tag: str,
        reset_notification_count: bool = False,
    ) -> NotificationLog:
        """
        Add or update a notification log entry.
        For global services (bumps), member_id should be guild_id.
        For user-specific services, member_id should be user_id.
        """
        notification_log = await session.get(NotificationLog, (member_id, notification_tag))

        if notification_log is None:
            notification_log = NotificationLog(
                member_id=member_id,
                notification_tag=notification_tag,
                sent_at=datetime.now(timezone.utc),
                notification_count=0,
                opted_out=False,
            )
            session.add(notification_log)
        else:
            notification_log.sent_at = datetime.now(timezone.utc)
            if reset_notification_count:
                notification_log.notification_count = 0

        return notification_log

    @staticmethod
    async def increment_notification_count(
        session: AsyncSession, member_id: int, notification_tag: str
    ) -> Tuple[NotificationLog, bool]:
        """
        Increment notification count and return if max count reached.
        Returns (notification_log, should_opt_out)
        """
        notification_log = await session.get(NotificationLog, (member_id, notification_tag))
        if not notification_log:
            return None, False

        notification_log.notification_count += 1
        should_opt_out = (
            notification_log.notification_count >= NotificationLogQueries.MAX_NOTIFICATION_COUNT
        )
        if should_opt_out:
            notification_log.opted_out = True

        return notification_log, should_opt_out

    @staticmethod
    async def get_notification_log(
        session: AsyncSession, member_id: int, notification_tag: str
    ) -> Optional[NotificationLog]:
        """Get a notification log for a specific member and tag"""
        return await session.get(NotificationLog, (member_id, notification_tag))

    @staticmethod
    async def get_service_notification_log(
        session: AsyncSession, service: str, guild_id: int, user_id: Optional[int] = None
    ) -> Optional[NotificationLog]:
        """Get notification log for a service, handling both global and user-specific services"""
        # For global services (bumps), use guild_id as member_id
        member_id = guild_id if service in NotificationLogQueries.GLOBAL_SERVICES else user_id
        if member_id is None:
            return None

        return await session.get(NotificationLog, (member_id, service))

    @staticmethod
    async def get_service_users(
        session: AsyncSession, service: str, guild_id: Optional[int] = None
    ) -> List[int]:
        """Get all users who have used a service"""
        query = (
            select(NotificationLog.member_id)
            .where(NotificationLog.notification_tag == service)
            .distinct()
        )

        if guild_id is not None:
            query = query.where(NotificationLog.member_id != guild_id)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def can_use_service(
        session: AsyncSession,
        service: str,
        guild_id: int,
        user_id: Optional[int] = None,
        cooldown_hours: int = 24,
    ) -> bool:
        """Check if service can be used based on cooldown"""
        # For global services (bumps), use guild_id as member_id
        member_id = guild_id if service in NotificationLogQueries.GLOBAL_SERVICES else user_id
        if member_id is None:
            return False

        log = await session.get(NotificationLog, (member_id, service))
        if not log:
            return True

        now = datetime.now(timezone.utc)
        return (now - log.sent_at) >= timedelta(hours=cooldown_hours)

    @staticmethod
    async def process_service_usage(
        session: AsyncSession,
        service: str,
        guild_id: int,
        user_id: int,
        cooldown_hours: int,
        dry_run: bool = False,
    ) -> Tuple[bool, Optional[NotificationLog]]:
        """
        Process service usage and update notification log.
        If dry_run is True, only check if service can be used without updating the log.
        """
        # Get current notification log
        log = await NotificationLogQueries.get_service_notification_log(
            session, service, guild_id, user_id
        )

        # If no log exists, service can be used
        if not log:
            if not dry_run:
                log = await NotificationLogQueries.add_or_update_notification_log(
                    session, user_id, service
                )
            return True, log

        # Check if cooldown has passed
        current_time = datetime.now(timezone.utc)
        if log.sent_at and log.sent_at + timedelta(hours=cooldown_hours) > current_time:
            return False, log

        # Service can be used - update log if not dry run
        if not dry_run:
            log = await NotificationLogQueries.add_or_update_notification_log(
                session, user_id, service
            )

        return True, log


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


class InviteQueries:
    """Class for Invite Queries"""

    @staticmethod
    async def add_or_update_invite(
        session: AsyncSession,
        invite_id: str,
        creator_id: Optional[int],
        uses: int,
        created_at: datetime,
        last_used_at: Optional[datetime] = None,
    ) -> Invite:
        try:
            if creator_id:
                await MemberQueries.get_or_add_member(session, creator_id)
            invite = await session.get(Invite, invite_id)
            if invite is None:
                invite = Invite(
                    id=invite_id,
                    creator_id=creator_id,
                    uses=uses,
                    created_at=created_at,
                    last_used_at=last_used_at,
                )
                session.add(invite)
            else:
                # Update existing invite
                if creator_id is not None:  # Only update if new creator_id is not None
                    invite.creator_id = creator_id
                invite.uses = uses
                if last_used_at is not None:
                    invite.last_used_at = last_used_at
            await session.flush()
            return invite
        except IntegrityError as e:
            logger.error(f"Error adding or updating invite {invite_id}: {str(e)}")
            await session.rollback()
            return None

    @staticmethod
    async def get_inactive_invites(
        session: AsyncSession,
        days: int = 30,
        max_uses: int = 5,
        limit: int = 100,
        sort_by: str = "uses",
        order: str = "asc",
    ) -> List[Invite]:
        now = datetime.now(timezone.utc)
        cutoff_date = now - timedelta(days=days)

        query = select(Invite).where(
            and_(Invite.last_used_at < cutoff_date, Invite.uses <= max_uses)
        )

        if sort_by == "uses":
            query = query.order_by(Invite.uses.asc() if order == "asc" else Invite.uses.desc())
        elif sort_by == "last_used_at":
            query = query.order_by(
                Invite.last_used_at.asc() if order == "asc" else Invite.last_used_at.desc()
            )
        else:
            query = query.order_by(Invite.uses.asc(), Invite.last_used_at.asc())

        query = query.limit(limit)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def delete_invite(session: AsyncSession, invite_id: str) -> None:
        invite = await session.get(Invite, invite_id)
        if invite:
            await session.delete(invite)
            await session.flush()

    @staticmethod
    async def get_invite_count(session: AsyncSession) -> int:
        result = await session.execute(select(func.count()).select_from(Invite))
        return result.scalar_one()

    @staticmethod
    async def get_sorted_invites(
        session: AsyncSession, sort_by: str = "uses", order: str = "desc"
    ) -> List[Invite]:
        query = select(Invite)
        if sort_by == "uses":
            query = query.order_by(desc(Invite.uses) if order == "desc" else asc(Invite.uses))
        elif sort_by == "created_at":
            query = query.order_by(
                desc(Invite.created_at) if order == "desc" else asc(Invite.created_at)
            )

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_all_invites(session: AsyncSession) -> List[Invite]:
        result = await session.execute(select(Invite))
        return result.scalars().all()

    @staticmethod
    async def get_invites_for_cleanup(
        session: AsyncSession, limit: int = 100, inactive_threshold: timedelta = timedelta(days=1)
    ) -> List[Invite]:
        now = datetime.now(timezone.utc)
        threshold_date = now - inactive_threshold

        query = (
            select(Invite)
            .where(
                or_(
                    and_(Invite.last_used_at.is_(None), Invite.created_at < threshold_date),
                    Invite.last_used_at.isnot(None),
                )
            )
            .order_by(
                case(
                    (and_(Invite.last_used_at.is_(None), Invite.created_at < threshold_date), 0),
                    else_=1,
                ),
                Invite.last_used_at.asc().nulls_first(),
                Invite.created_at.asc(),
            )
            .limit(limit)
        )

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_member_invite_count(session: AsyncSession, member_id: int) -> int:
        """Get total count of invites (uses) for a specific member."""
        try:
            query = select(func.sum(Invite.uses)).where(Invite.creator_id == member_id)
            result = await session.execute(query)
            count = result.scalar()
            return count if count is not None else 0
        except Exception as e:
            logger.error(f"Error getting invite count for member {member_id}: {e}")
            return 0

    @staticmethod
    async def get_member_valid_invite_count(
        session: AsyncSession, member_id: int, guild, min_days: int = 7
    ) -> int:
        """
        Get count of valid invites for a specific member (like in legacy system).
        Only counts users who:
        - Are still on the server
        - Have an avatar
        - Have joined_at timestamp
        - Account age difference (joined_at - created_at) > min_days

        :param session: Database session
        :param member_id: ID of the member whose invites to count
        :param guild: Discord guild object
        :param min_days: Minimum account age difference in days (default 7)
        :return: Count of valid invites
        """
        try:
            # Get all members invited by this user from database
            query = select(Member).where(Member.current_inviter_id == member_id)
            result = await session.execute(query)
            invited_members = result.scalars().all()

            valid_count = 0

            for db_member in invited_members:
                # Get Discord member object
                discord_member = guild.get_member(db_member.id)

                if not discord_member:
                    # User is no longer on the server
                    continue

                if not discord_member.avatar:
                    # User has no avatar
                    continue

                if not discord_member.joined_at:
                    # No joined_at timestamp
                    continue

                # Check account age difference
                account_age_diff = discord_member.joined_at - discord_member.created_at
                if account_age_diff <= timedelta(days=min_days):
                    # Account too new (potential bot/fake account)
                    continue

                valid_count += 1

            logger.debug(
                f"Valid invite count for member {member_id}: {valid_count} (from {len(invited_members)} total)"
            )
            return valid_count

        except Exception as e:
            logger.error(f"Error getting valid invite count for member {member_id}: {e}")
            return 0


class AutoKickQueries:
    """Class for AutoKick Queries"""

    @staticmethod
    async def ensure_members_exist(session: AsyncSession, owner_id: int, target_id: int) -> None:
        """Ensure both owner and target exist in members table"""
        # Check if owner exists
        owner_exists = await session.scalar(select(Member.id).where(Member.id == owner_id))
        if not owner_exists:
            await session.merge(Member(id=owner_id))

        # Check if target exists
        target_exists = await session.scalar(select(Member.id).where(Member.id == target_id))
        if not target_exists:
            await session.merge(Member(id=target_id))

        await session.commit()

    @staticmethod
    async def add_autokick(session: AsyncSession, owner_id: int, target_id: int) -> None:
        """Add an autokick entry"""
        # Ensure both members exist
        await AutoKickQueries.ensure_members_exist(session, owner_id, target_id)

        # Add autokick entry
        autokick = AutoKick(
            owner_id=owner_id, target_id=target_id, created_at=datetime.now(timezone.utc)
        )
        session.add(autokick)
        await session.commit()

    @staticmethod
    async def remove_autokick(session: AsyncSession, owner_id: int, target_id: int) -> None:
        """Remove an autokick entry"""
        await session.execute(
            delete(AutoKick).where(
                (AutoKick.owner_id == owner_id) & (AutoKick.target_id == target_id)
            )
        )
        await session.commit()

    @staticmethod
    async def get_all_autokicks(session: AsyncSession) -> List[AutoKick]:
        """Get all autokick entries"""
        result = await session.execute(select(AutoKick))
        return result.scalars().all()

    @staticmethod
    async def get_owner_autokicks(session: AsyncSession, owner_id: int) -> List[AutoKick]:
        """Get all autokicks for a specific owner"""
        result = await session.execute(select(AutoKick).where(AutoKick.owner_id == owner_id))
        return result.scalars().all()

    @staticmethod
    async def get_target_autokicks(session: AsyncSession, target_id: int) -> List[AutoKick]:
        """Get all autokicks targeting a specific member"""
        result = await session.execute(select(AutoKick).where(AutoKick.target_id == target_id))
        return result.scalars().all()


# ===============================
# ACTIVITY/RANKING SYSTEM QUERIES
# ===============================


async def ensure_member_exists(session: AsyncSession, member_id: int) -> None:
    """Ensure member exists in the database."""
    result = await session.execute(select(Member).where(Member.id == member_id))
    if not result.scalar():
        new_member = Member(id=member_id)
        session.add(new_member)


async def add_activity_points(
    session: AsyncSession, member_id: int, activity_type: str, points: int, date: datetime = None
) -> None:
    """Add points to member's activity for specific date and type."""
    if date is None:
        date = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    # Check if activity record exists for this member, date and type
    activity = await session.get(Activity, (member_id, date, activity_type))

    if activity:
        activity.points += points
    else:
        activity = Activity(
            member_id=member_id, date=date, activity_type=activity_type, points=points
        )
        session.add(activity)


async def get_member_total_points(session: AsyncSession, member_id: int, days_back: int = 7) -> int:
    """Get total points for a member from last N days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    result = await session.execute(
        select(func.sum(Activity.points))
        .where(Activity.member_id == member_id)
        .where(Activity.date >= cutoff_date)
    )
    total = result.scalar()
    return total or 0


async def get_top_members_by_points(
    session: AsyncSession, limit: int = 100, days_back: int = 7
) -> List[Tuple[int, int]]:
    """Get top members by total points from last N days."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    result = await session.execute(
        select(Activity.member_id, func.sum(Activity.points).label("total_points"))
        .where(Activity.date >= cutoff_date)
        .group_by(Activity.member_id)
        .order_by(func.sum(Activity.points).desc())
        .limit(limit)
    )
    return result.all()


async def get_member_ranking_position(
    session: AsyncSession, member_id: int, days_back: int = 7
) -> int:
    """Get member's ranking position (1-based)."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    # Get all members with their total points
    result = await session.execute(
        select(Activity.member_id, func.sum(Activity.points).label("total_points"))
        .where(Activity.date >= cutoff_date)
        .group_by(Activity.member_id)
        .order_by(func.sum(Activity.points).desc())
    )

    ranking = result.all()
    for position, (mid, points) in enumerate(ranking, 1):
        if mid == member_id:
            return position
    return 0  # Not found in ranking


async def reset_daily_activity_points(session: AsyncSession, activity_type: str = None) -> None:
    """Reset activity points for today. If activity_type is None, reset all types."""
    today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

    if activity_type:
        await session.execute(
            update(Activity)
            .where(Activity.date == today)
            .where(Activity.activity_type == activity_type)
            .values(points=0)
        )
    else:
        await session.execute(update(Activity).where(Activity.date == today).values(points=0))


async def get_member_activity_breakdown(
    session: AsyncSession, member_id: int, days_back: int = 7
) -> Dict[str, int]:
    """Get breakdown of points by activity type for a member."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    result = await session.execute(
        select(Activity.activity_type, func.sum(Activity.points).label("total_points"))
        .where(Activity.member_id == member_id)
        .where(Activity.date >= cutoff_date)
        .group_by(Activity.activity_type)
    )

    return {activity_type: total_points for activity_type, total_points in result.all()}


async def cleanup_old_activity_data(session: AsyncSession, days_to_keep: int = 30) -> int:
    """Remove activity data older than specified days. Returns number of deleted records."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

    result = await session.execute(delete(Activity).where(Activity.date < cutoff_date))
    return result.rowcount


async def get_activity_leaderboard_with_names(
    session: AsyncSession, limit: int = 100, days_back: int = 7
) -> List[Tuple[int, int, int]]:
    """Get leaderboard with member_id, points, and position."""
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

    result = await session.execute(
        select(
            Activity.member_id,
            func.sum(Activity.points).label("total_points"),
            func.row_number().over(order_by=func.sum(Activity.points).desc()).label("position"),
        )
        .where(Activity.date >= cutoff_date)
        .group_by(Activity.member_id)
        .order_by(func.sum(Activity.points).desc())
        .limit(limit)
    )
    return result.all()


async def get_ranking_tier(session: AsyncSession, member_id: int, days_back: int = 7) -> str:
    """Get ranking tier for member (100, 200, 300, or None)."""
    position = await get_member_ranking_position(session, member_id, days_back)

    if position == 0:
        return "Unranked"
    elif position <= 100:
        return "100"
    elif position <= 200:
        return "200"
    elif position <= 300:
        return "300"
    else:
        return "Unranked"


class ModerationLogQueries:
    """Class for Moderation Log Queries"""

    @staticmethod
    async def log_mute_action(
        session: AsyncSession,
        target_user_id: int,
        moderator_id: int,
        action_type: str,
        mute_type: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        reason: Optional[str] = None,
        channel_id: int = 0,
    ) -> ModerationLog:
        """Zapisuje akcję moderatorską do bazy danych"""
        # Oblicz datę wygaśnięcia jeśli podano czas trwania
        expires_at = None
        if duration_seconds is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=duration_seconds)

        # Stwórz wpis w logu
        moderation_log = ModerationLog(
            target_user_id=target_user_id,
            moderator_id=moderator_id,
            action_type=action_type,
            mute_type=mute_type,
            duration_seconds=duration_seconds,
            reason=reason,
            channel_id=channel_id,
            expires_at=expires_at,
        )

        session.add(moderation_log)
        await session.flush()
        return moderation_log

    @staticmethod
    async def get_user_mute_history(
        session: AsyncSession, user_id: int, limit: int = 50
    ) -> List[ModerationLog]:
        """Pobiera historię mute'ów użytkownika"""
        result = await session.execute(
            select(ModerationLog)
            .options(joinedload(ModerationLog.moderator))
            .where(ModerationLog.target_user_id == user_id)
            .where(ModerationLog.action_type.in_(["mute", "unmute"]))
            .order_by(ModerationLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()

    @staticmethod
    async def get_user_mute_count(session: AsyncSession, user_id: int, days_back: int = 30) -> int:
        """Zlicza ile razy użytkownik był mutowany w ostatnich X dniach"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        result = await session.execute(
            select(func.count(ModerationLog.id))
            .where(ModerationLog.target_user_id == user_id)
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
        )
        return result.scalar() or 0

    @staticmethod
    async def get_moderator_actions(
        session: AsyncSession,
        moderator_id: int,
        action_type: Optional[str] = None,
        days_back: int = 30,
        limit: int = 100,
    ) -> List[ModerationLog]:
        """Pobiera akcje wykonane przez moderatora"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        query = (
            select(ModerationLog)
            .options(joinedload(ModerationLog.target_user))
            .where(ModerationLog.moderator_id == moderator_id)
            .where(ModerationLog.created_at >= cutoff_date)
            .order_by(ModerationLog.created_at.desc())
            .limit(limit)
        )

        if action_type:
            query = query.where(ModerationLog.action_type == action_type)

        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def get_mute_statistics(session: AsyncSession, days_back: int = 30) -> Dict[str, any]:
        """Pobiera statystyki mute'ów z ostatnich X dni"""
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        # Wszystkie mute'y w okresie
        total_mutes_result = await session.execute(
            select(func.count(ModerationLog.id))
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
        )
        total_mutes = total_mutes_result.scalar() or 0

        # Statystyki według typu mute'a
        mute_types_result = await session.execute(
            select(ModerationLog.mute_type, func.count(ModerationLog.id))
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
            .where(ModerationLog.mute_type.isnot(None))
            .group_by(ModerationLog.mute_type)
            .order_by(func.count(ModerationLog.id).desc())
        )
        mute_types = dict(mute_types_result.all())

        # Top użytkownicy z największą liczbą mute'ów
        top_muted_users_result = await session.execute(
            select(ModerationLog.target_user_id, func.count(ModerationLog.id))
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
            .group_by(ModerationLog.target_user_id)
            .order_by(func.count(ModerationLog.id).desc())
            .limit(10)
        )
        top_muted_users = top_muted_users_result.all()

        # Top moderatorzy z największą aktywnością
        top_moderators_result = await session.execute(
            select(ModerationLog.moderator_id, func.count(ModerationLog.id))
            .where(ModerationLog.action_type == "mute")
            .where(ModerationLog.created_at >= cutoff_date)
            .group_by(ModerationLog.moderator_id)
            .order_by(func.count(ModerationLog.id).desc())
            .limit(10)
        )
        top_moderators = top_moderators_result.all()

        return {
            "total_mutes": total_mutes,
            "mute_types": mute_types,
            "top_muted_users": top_muted_users,
            "top_moderators": top_moderators,
            "period_days": days_back,
        }

    @staticmethod
    async def get_recent_actions(session: AsyncSession, limit: int = 20) -> List[ModerationLog]:
        """Pobiera ostatnie akcje moderatorskie"""
        result = await session.execute(
            select(ModerationLog)
            .options(joinedload(ModerationLog.target_user), joinedload(ModerationLog.moderator))
            .order_by(ModerationLog.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
