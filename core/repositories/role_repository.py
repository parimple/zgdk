"""Role repository implementation."""

from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.base_repository import BaseRepository
from datasources.models import MemberRole, Role


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
                        "expiry_time": member_role.expiry_time,
                        "role_type": member_role.role_type,
                        "role_name": role.name,
                    }
                )

            self.logger.debug(f"Found {len(roles)} roles for member {member_id}")
            return roles

        except Exception as e:
            self.logger.error(f"Error getting roles for member {member_id}: {e}")
            raise

    async def get_expired_roles(self, current_time: datetime) -> list[dict]:
        """Get all roles that have expired."""
        try:
            stmt = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where(MemberRole.expiry_time <= current_time)
                .where(MemberRole.expiry_time.isnot(None))
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
                        "expiry_time": member_role.expiry_time,
                        "role_type": member_role.role_type,
                        "role_name": role.name,
                    }
                )

            self.logger.debug(f"Found {len(expired_roles)} expired roles")
            return expired_roles

        except Exception as e:
            self.logger.error(f"Error getting expired roles: {e}")
            raise

    async def get_role_by_member_and_type(
        self, member_id: int, role_type: str
    ) -> Optional[dict]:
        """Get specific role type for a member."""
        try:
            stmt = (
                select(MemberRole, Role)
                .join(Role, MemberRole.role_id == Role.id)
                .where(MemberRole.member_id == member_id)
                .where(MemberRole.role_type == role_type)
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
                    "expiry_time": member_role.expiry_time,
                    "role_type": member_role.role_type,
                    "role_name": role.name,
                }
                self.logger.debug(
                    f"Found {role_type} role for member {member_id}: {role.name}"
                )
                return role_data

            self.logger.debug(f"No {role_type} role found for member {member_id}")
            return None

        except Exception as e:
            self.logger.error(
                f"Error getting {role_type} role for member {member_id}: {e}"
            )
            raise

    async def extend_role_expiry(
        self, member_id: int, role_id: int, new_expiry: datetime
    ) -> bool:
        """Extend role expiry time."""
        try:
            stmt = select(MemberRole).where(
                MemberRole.member_id == member_id, MemberRole.role_id == role_id
            )
            result = await self.session.execute(stmt)
            member_role = result.scalar_one_or_none()

            if member_role:
                member_role.expiry_time = new_expiry
                await self.session.flush()
                self.logger.debug(
                    f"Extended role expiry for member {member_id}, role {role_id} to {new_expiry}"
                )
                return True

            self.logger.warning(
                f"Cannot extend expiry - role not found: member {member_id}, role {role_id}"
            )
            return False

        except Exception as e:
            self.logger.error(
                f"Error extending role expiry for member {member_id}, role {role_id}: {e}"
            )
            raise
