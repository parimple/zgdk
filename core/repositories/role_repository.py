"""Role repository implementation."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy import and_, delete, func, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from core.repositories.base_repository import BaseRepository
from datasources.models import MemberRole, Role

logger = logging.getLogger(__name__)


class RoleRepository(BaseRepository):
    """Repository for role data access operations."""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(MemberRole, session)

    async def get_roles_by_member_id(self, member_id: int) -> list[dict]:
        """Get all roles for a specific member."""
        try:
            stmt = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where(MemberRole.member_id == member_id)
            )
            result = await self.session.execute(stmt)
            rows = result.fetchall()

            roles = []
            for member_role, role in rows:
                roles.append(
                    {
                        "member_role": member_role,
                        "role": role,
                        "member_id": member_role.member_id,
                        "role_id": member_role.role_id,
                        "expiration_date": member_role.expiration_date,
                        "role_type": role.role_type,
                        "role_name": role.name,
                    }
                )

            self.logger.debug(f"Found {len(roles)} roles for member {member_id}")
            return roles

        except Exception as e:
            self.logger.error(f"Error getting roles for member {member_id}: {e}")
            raise

    async def get_expired_roles(
        self, current_time: datetime, role_type: Optional[str] = None, role_ids: Optional[List[int]] = None
    ) -> list[dict]:
        """Get all roles that have expired."""
        try:
            stmt = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where(
                    and_(
                        MemberRole.expiration_date.isnot(None),
                        MemberRole.expiration_date <= current_time,
                    )
                )
            )

            if role_type:
                stmt = stmt.where(Role.role_type == role_type)

            if role_ids:
                stmt = stmt.where(MemberRole.role_id.in_(role_ids))

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
                        "expiration_date": member_role.expiration_date,
                        "role_type": role.role_type,
                        "role_name": role.name,
                    }
                )

            self.logger.debug(f"Found {len(expired_roles)} expired roles")
            return expired_roles

        except Exception as e:
            self.logger.error(f"Error getting expired roles: {e}")
            raise

    async def get_role_by_member_and_type(self, member_id: int, role_type: str) -> Optional[dict]:
        """Get specific role type for a member."""
        try:
            stmt = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where(MemberRole.member_id == member_id)
                .where(Role.role_type == role_type)
            )
            result = await self.session.execute(stmt)
            row = result.first()

            if row:
                member_role, role = row
                role_data = {
                    "member_role": member_role,
                    "role": role,
                    "member_id": member_role.member_id,
                    "role_id": member_role.role_id,
                    "expiration_date": member_role.expiration_date,
                    "role_type": role.role_type,
                    "role_name": role.name,
                }
                self.logger.debug(f"Found {role_type} role for member {member_id}: {role.name}")
                return role_data

            self.logger.debug(f"No {role_type} role found for member {member_id}")
            return None

        except Exception as e:
            self.logger.error(f"Error getting {role_type} role for member {member_id}: {e}")
            raise

    async def extend_role_expiry(self, member_id: int, role_id: int, new_expiry: datetime) -> bool:
        """Extend role expiry time."""
        try:
            stmt = select(MemberRole).where(MemberRole.member_id == member_id, MemberRole.role_id == role_id)
            result = await self.session.execute(stmt)
            member_role = result.scalar_one_or_none()

            if member_role:
                member_role.expiration_date = new_expiry
                await self.session.flush()
                self.logger.debug(f"Extended role expiry for member {member_id}, role {role_id} to {new_expiry}")
                return True

            self.logger.warning(f"Cannot extend expiry - role not found: member {member_id}, role {role_id}")
            return False

        except Exception as e:
            self.logger.error(f"Error extending role expiry for member {member_id}, role {role_id}: {e}")
            raise

    async def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """Get role by ID."""
        try:
            return await self.session.get(Role, role_id)
        except Exception as e:
            self.logger.error(f"Error getting role by id {role_id}: {e}")
            raise

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """Get role by name."""
        try:
            stmt = select(Role).where(Role.name == name)
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            self.logger.error(f"Error getting role by name {name}: {e}")
            raise

    async def get_all_roles(self) -> List[Role]:
        """Get all roles from the database."""
        try:
            stmt = select(Role)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Error getting all roles: {e}")
            raise

    async def add_member_role(
        self, member_id: int, role_id: int, expiration_date: Optional[datetime] = None, role_type: str = "temporary"
    ) -> MemberRole:
        """Add a role to a member."""
        try:
            member_role = MemberRole(member_id=member_id, role_id=role_id, expiration_date=expiration_date)
            self.session.add(member_role)
            await self.session.flush()
            return member_role
        except IntegrityError:
            await self.session.rollback()
            # Role already exists, return it
            return await self.get_member_role(member_id, role_id)
        except Exception as e:
            self.logger.error(f"Error adding role {role_id} to member {member_id}: {e}")
            raise

    async def get_member_role(self, member_id: int, role_id: int) -> Optional[MemberRole]:
        """Get a specific member role."""
        try:
            stmt = select(MemberRole).where(and_(MemberRole.member_id == member_id, MemberRole.role_id == role_id))
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            self.logger.error(f"Error getting member role: {e}")
            raise

    async def get_member_roles(self, member_id: int) -> list[MemberRole]:
        """Get all roles for a member."""
        try:
            stmt = select(MemberRole).where(MemberRole.member_id == member_id)
            result = await self.session.execute(stmt)
            return list(result.scalars().all())
        except Exception as e:
            self.logger.error(f"Error getting member roles: {e}")
            raise

    async def remove_member_role(self, member_id: int, role_id: int) -> bool:
        """Remove a role from a member."""
        try:
            stmt = delete(MemberRole).where(and_(MemberRole.member_id == member_id, MemberRole.role_id == role_id))
            result = await self.session.execute(stmt)
            await self.session.flush()
            return result.rowcount > 0
        except Exception as e:
            self.logger.error(f"Error removing role: {e}")
            raise

    async def update_role_expiry(self, member_id: int, role_id: int, new_expiry: datetime) -> Optional[MemberRole]:
        """Update role expiry time."""
        try:
            member_role = await self.get_member_role(member_id, role_id)
            if member_role:
                member_role.expiration_date = new_expiry
                await self.session.flush()
                return member_role
            return None
        except Exception as e:
            self.logger.error(f"Error updating role expiry: {e}")
            raise

    async def create_role(self, role_id: int, role_name: str, role_type: str = "premium") -> Role:
        """Create a new role."""
        try:
            role = Role(id=role_id, name=role_name, role_type=role_type)
            self.session.add(role)
            await self.session.flush()
            self.logger.debug(f"Created role {role_name} with id {role_id}")
            return role
        except Exception as e:
            self.logger.error(f"Error creating role {role_name}: {e}")
            raise

    async def add_or_update_role_to_member(
        self, member_id: int, role_id: int, duration: Optional[timedelta] = None
    ) -> bool:
        """Add a role to a member or update its expiration date if it already exists."""
        try:
            member_role = await self.session.get(MemberRole, (member_id, role_id))

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
                self.session.add(member_role)
                logger.info(f"Added new role {role_id} to member {member_id}")

            await self.session.flush()
            return True

        except IntegrityError as e:
            await self.session.rollback()
            logger.error(
                f"IntegrityError occurred while adding/updating role {role_id} for member {member_id}: {str(e)}"
            )
            return False
        except Exception as e:
            await self.session.rollback()
            logger.error(
                f"Unexpected error occurred while adding/updating role {role_id} for member {member_id}: {str(e)}"
            )
            return False

    async def get_member_role(self, member_id: int, role_id: int) -> Optional[MemberRole]:
        """Get a specific member role."""
        try:
            return await self.session.get(MemberRole, (member_id, role_id))
        except Exception as e:
            self.logger.error(f"Error getting member role for member {member_id}, role {role_id}: {e}")
            raise

    async def delete_member_role(self, member_id: int, role_id: int) -> bool:
        """Delete a role from a member using raw SQL for safety."""
        try:
            # Use raw SQL for safe deletion
            sql = text("DELETE FROM member_roles WHERE member_id = :member_id AND role_id = :role_id")
            await self.session.execute(sql, {"member_id": member_id, "role_id": role_id})
            logger.info(f"Deleted role {role_id} for member {member_id} using raw SQL")
            return True
        except Exception as e:
            logger.error(f"Error deleting role {role_id} for member {member_id}: {str(e)}")
            return False

    async def get_member_premium_roles(self, member_id: int) -> List[Tuple[MemberRole, Role]]:
        """Get all premium roles of a member (active and expired)."""
        try:
            stmt = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where((MemberRole.member_id == member_id) & (Role.role_type == "premium"))
            )
            result = await self.session.execute(stmt)
            fetched_roles = result.all()
            logger.info(
                f"Fetched premium roles for member_id {member_id} (count: {len(fetched_roles)}): {fetched_roles}"
            )
            return fetched_roles
        except Exception as e:
            logger.error(
                f"Error getting premium roles for member {member_id}: {e}",
                exc_info=True,
            )
            return []

    async def get_premium_role(self, member_id: int) -> Optional[MemberRole]:
        """Get the active premium role of a member."""
        try:
            stmt = (
                select(MemberRole)
                .join(Role, MemberRole.role_id == Role.id)
                .where(
                    (MemberRole.member_id == member_id)
                    & (Role.role_type == "premium")
                    & (MemberRole.expiration_date >= datetime.now(timezone.utc))
                )
            )
            result = await self.session.execute(stmt)
            return result.scalar_one_or_none()
        except Exception as e:
            self.logger.error(f"Error getting premium role for member {member_id}: {e}")
            raise

    async def get_expiring_roles(self, reminder_time: datetime, role_type: Optional[str] = None) -> List[MemberRole]:
        """Get roles expiring within the next 24 hours."""
        try:
            stmt = (
                select(MemberRole)
                .options(joinedload(MemberRole.role))
                .where(MemberRole.expiration_date <= reminder_time)
            )
            if role_type:
                stmt = stmt.join(Role).where(Role.role_type == role_type)

            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Error getting expiring roles: {e}")
            raise

    async def update_role_expiration_date(
        self, member_id: int, role_id: int, duration: timedelta
    ) -> Optional[MemberRole]:
        """Update the expiration date of the role for the member."""
        try:
            # Get the current member role
            member_role = await self.session.get(MemberRole, (member_id, role_id))
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

    async def update_role_expiration_date_direct(self, member_id: int, role_id: int, new_expiry: datetime) -> bool:
        """Update role expiration date directly to a specific datetime."""
        try:
            stmt = select(MemberRole).where(
                MemberRole.member_id == member_id,
                MemberRole.role_id == role_id,
            )
            result = await self.session.execute(stmt)
            member_role = result.scalar_one_or_none()

            if member_role:
                member_role.expiration_date = new_expiry
                await self.session.flush()
                return True
            return False
        except Exception as e:
            self.logger.error(f"Error updating role expiration date directly: {e}")
            raise

    async def get_all_premium_roles(self) -> List[MemberRole]:
        """Get all premium roles."""
        try:
            stmt = (
                select(MemberRole)
                .options(joinedload(MemberRole.role))
                .join(Role, MemberRole.role_id == Role.id)
                .where(Role.role_type == "premium")
            )
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Error getting all premium roles: {e}")
            raise

    async def get_role_members(self, role_id: int) -> List[MemberRole]:
        """Get all members that have a specific role."""
        try:
            stmt = select(MemberRole).options(joinedload(MemberRole.role)).where(MemberRole.role_id == role_id)
            result = await self.session.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            self.logger.error(f"Error getting members for role {role_id}: {e}")
            raise

    async def count_unique_premium_users(self) -> int:
        """Count unique members who have ever had any premium role (including expired)."""
        try:
            stmt = (
                select(func.count(func.distinct(MemberRole.member_id)))
                .select_from(MemberRole)
                .join(Role, MemberRole.role_id == Role.id)
                .where(Role.role_type == "premium")
            )
            result = await self.session.execute(stmt)
            count = result.scalar()
            return count if count is not None else 0
        except Exception as e:
            logger.error(f"Error counting unique premium users: {e}")
            return 200  # Fallback number
