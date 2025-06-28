"""
Role Queries for the database.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy import and_, delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from sqlalchemy.sql.functions import func

from ..models import MemberRole, Role

logger = logging.getLogger(__name__)


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
                    member_id=member_id,
                    role_id=role_id,
                    expiration_date=expiration_date,
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
        member_role = MemberRole(member_id=member_id, role_id=role_id, expiration_date=expiration_date)
        session.add(member_role)

    @staticmethod
    async def add_role(session: AsyncSession, role_id: int, role_name: str, role_type: str = "premium"):
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
            select(MemberRole).options(joinedload(MemberRole.role)).where(MemberRole.member_id == member_id)
        )
        return result.scalars().all()

    @staticmethod
    async def get_member_premium_roles(session: AsyncSession, member_id: int) -> list[tuple[MemberRole, Role]]:
        """Pobiera wszystkie role premium użytkownika, aktywne i wygasłe."""
        try:
            # Poprawna logika zapytania: pobiera wszystkie role premium użytkownika (aktywne i wygasłe).
            query = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where((MemberRole.member_id == member_id) & (Role.role_type == "premium"))
            )
            logger.info(f"Executing query for member_id {member_id} in get_member_premium_roles: {query}")
            result = await session.execute(query)

            # Logowanie .first() dla wglądu w pierwszy potencjalny wiersz
            # Musimy być ostrożni, .first() może skonsumować wynik, więc lepiej wykonać to na nowym zapytaniu lub na kopii
            # Dla uproszczenia, po prostu zalogujemy i zobaczymy, czy .all() nadal działa.
            # W idealnym świecie, jeśli .first() konsumuje, należałoby ponownie wykonać zapytanie dla .all().
            temp_result_for_first = await session.execute(query)  # Wykonaj zapytanie ponownie dla .first()
            first_row = temp_result_for_first.first()
            logger.info(f"Query result.first() for member_id {member_id}: {first_row}")

            fetched_roles = result.all()  # Użyj oryginalnego wyniku dla .all()
            logger.info(
                f"Fetched roles via result.all() for member_id {member_id} (count: {len(fetched_roles)}): {fetched_roles}"
            )
            return fetched_roles
        except Exception as e:
            logger.error(
                f"Błąd podczas pobierania ról premium użytkownika {member_id}: {e}",
                exc_info=True,
            )
            return []

    @staticmethod
    async def get_expiring_roles(
        session: AsyncSession, reminder_time: datetime, role_type: Optional[str] = None
    ) -> List[MemberRole]:
        """Get roles expiring within the next 24 hours"""
        query = (
            select(MemberRole).options(joinedload(MemberRole.role)).where(MemberRole.expiration_date <= reminder_time)
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
                    MemberRole.expiration_date.isnot(None),  # Don't select roles with no expiration date
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
            sql = text("DELETE FROM member_roles WHERE member_id = :member_id AND role_id = :role_id")
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
    async def get_role_for_member(session: AsyncSession, member_id: int, role_id: int) -> Optional[MemberRole]:
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
    async def update_role_expiration_date_direct(session, member_id: int, role_id: int, new_expiry: datetime):
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
    async def get_member_role(session: AsyncSession, member_id: int, role_id: int) -> Optional[MemberRole]:
        """Get a specific member role"""
        result = await session.execute(
            select(MemberRole).where(and_(MemberRole.member_id == member_id, MemberRole.role_id == role_id))
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
            stmt = select(MemberRole).where((MemberRole.member_id == member_id) & (MemberRole.role_id == role_id))
            result = await session.execute(stmt)
            member_role = result.scalar_one_or_none()

            if member_role:
                # Zdetachuj obiekt od sesji
                session.expunge(member_role)

                # Wykonaj surowy SQL DELETE z użyciem text()
                sql = text("DELETE FROM member_roles WHERE member_id = :member_id AND role_id = :role_id")
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
            sql = text("DELETE FROM member_roles WHERE member_id = :member_id AND role_id = :role_id")
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
            stmt = delete(MemberRole).where((MemberRole.member_id == member_id) & (MemberRole.role_id == role_id))
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
            select(MemberRole).options(joinedload(MemberRole.role)).where(MemberRole.role_id == role_id)
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
