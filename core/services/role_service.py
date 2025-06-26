"""Role service implementation with business logic."""

from datetime import datetime, timedelta
from typing import Optional

import discord

from core.interfaces.role_interfaces import IRoleRepository, IRoleService
from core.services.base_service import BaseService


class RoleService(BaseService, IRoleService):
    """Service for role business logic operations."""

    def __init__(self, role_repository: IRoleRepository, **kwargs) -> None:
        super().__init__(**kwargs)
        self.role_repository = role_repository

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate role operations."""
        # Add business rules validation here
        return True

    async def assign_role_to_member(
        self,
        member: discord.Member,
        role: discord.Role,
        expiry_time: Optional[datetime] = None,
        role_type: str = "temporary",
    ) -> bool:
        """Assign a role to a member with optional expiry."""
        try:
            # Business logic validation
            if not await self._can_assign_role(member, role, role_type):
                self._log_error(
                    "assign_role_to_member",
                    ValueError("Cannot assign role"),
                    member_id=member.id,
                    role_id=role.id,
                    role_type=role_type,
                )
                return False

            # Add role to Discord
            await member.add_roles(
                role, reason=f"Role assignment via service ({role_type})"
            )

            # Create database record
            from datasources.models import MemberRole

            member_role = MemberRole(
                member_id=member.id,
                role_id=role.id,
                expiry_time=expiry_time,
                role_type=role_type,
            )

            await self.role_repository.create(member_role)

            self._log_operation(
                "assign_role_to_member",
                member_id=member.id,
                role_id=role.id,
                role_type=role_type,
                expiry_time=expiry_time,
            )
            return True

        except discord.HTTPException as e:
            self._log_error(
                "assign_role_to_member",
                e,
                member_id=member.id,
                role_id=role.id,
                error_type="discord_api",
            )
            return False
        except Exception as e:
            self._log_error(
                "assign_role_to_member", e, member_id=member.id, role_id=role.id
            )
            return False

    async def remove_role_from_member(
        self, member: discord.Member, role: discord.Role
    ) -> bool:
        """Remove a role from a member."""
        try:
            # Remove from Discord
            await member.remove_roles(role, reason="Role removal via service")

            # Remove from database
            roles = await self.role_repository.get_roles_by_member_id(member.id)
            for role_data in roles:
                if role_data["role_id"] == role.id:
                    await self.role_repository.delete(role_data["member_role"].id)
                    break

            self._log_operation(
                "remove_role_from_member", member_id=member.id, role_id=role.id
            )
            return True

        except discord.HTTPException as e:
            self._log_error(
                "remove_role_from_member",
                e,
                member_id=member.id,
                role_id=role.id,
                error_type="discord_api",
            )
            return False
        except Exception as e:
            self._log_error(
                "remove_role_from_member", e, member_id=member.id, role_id=role.id
            )
            return False

    async def process_expired_roles(self) -> list[dict]:
        """Process all expired roles and remove them."""
        try:
            current_time = datetime.utcnow()
            expired_roles = await self.role_repository.get_expired_roles(current_time)

            processed_roles = []
            for role_data in expired_roles:
                try:
                    # Get guild and member objects (this would need to be injected)
                    # For now, we'll return the data for external processing
                    processed_roles.append(role_data)

                    # Remove from database
                    await self.role_repository.delete(role_data["member_role"].id)

                except Exception as e:
                    self._log_error(
                        "process_expired_role",
                        e,
                        member_id=role_data["member_id"],
                        role_id=role_data["role_id"],
                    )

            self._log_operation(
                "process_expired_roles", processed_count=len(processed_roles)
            )
            return processed_roles

        except Exception as e:
            self._log_error("process_expired_roles", e)
            return []

    async def extend_role_duration(
        self, member_id: int, role_id: int, additional_time: int
    ) -> bool:
        """Extend role duration by specified time in seconds."""
        try:
            # Get current role
            roles = await self.role_repository.get_roles_by_member_id(member_id)
            target_role = None
            for role_data in roles:
                if role_data["role_id"] == role_id:
                    target_role = role_data
                    break

            if not target_role:
                self._log_error(
                    "extend_role_duration",
                    ValueError("Role not found"),
                    member_id=member_id,
                    role_id=role_id,
                )
                return False

            # Calculate new expiry time
            current_expiry = target_role["expiry_time"]
            if current_expiry:
                new_expiry = current_expiry + timedelta(seconds=additional_time)
            else:
                # If no expiry set, set from now
                new_expiry = datetime.utcnow() + timedelta(seconds=additional_time)

            # Update expiry
            success = await self.role_repository.extend_role_expiry(
                member_id, role_id, new_expiry
            )

            if success:
                self._log_operation(
                    "extend_role_duration",
                    member_id=member_id,
                    role_id=role_id,
                    additional_time=additional_time,
                    new_expiry=new_expiry,
                )

            return success

        except Exception as e:
            self._log_error(
                "extend_role_duration", e, member_id=member_id, role_id=role_id
            )
            return False

    async def get_member_role_info(self, member_id: int) -> list[dict]:
        """Get detailed role information for a member."""
        try:
            roles = await self.role_repository.get_roles_by_member_id(member_id)
            self._log_operation(
                "get_member_role_info", member_id=member_id, count=len(roles)
            )
            return roles
        except Exception as e:
            self._log_error("get_member_role_info", e, member_id=member_id)
            return []

    async def _can_assign_role(
        self, member: discord.Member, role: discord.Role, role_type: str
    ) -> bool:
        """Business logic to validate if role can be assigned."""
        # Check if member already has this role
        if role in member.roles:
            self.logger.debug(f"Member {member.id} already has role {role.id}")
            return False

        # Check role hierarchy (bot must be higher than role)
        if member.guild.me.top_role.position <= role.position:
            self.logger.warning(
                f"Bot cannot assign role {role.id} - insufficient permissions"
            )
            return False

        # Add more business rules as needed
        # For example, check if premium role and member has premium status
        if role_type == "premium":
            # Would integrate with premium service here
            pass

        return True
