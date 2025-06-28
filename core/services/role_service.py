"""Role service implementation with business logic."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

import discord

from core.interfaces.role_interfaces import IRoleRepository, IRoleService
from datasources.models import MemberRole, Role


class RoleService(IRoleService):
    """Service for role business logic operations."""

    def __init__(self, role_repository: IRoleRepository, **kwargs) -> None:
        self.role_repository = role_repository
        self.logger = logging.getLogger(self.__class__.__name__)

    def _log_operation(self, operation_name: str, **context) -> None:
        """Log service operation with context."""
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        self.logger.info(f"{operation_name}: {context_str}")

    def _log_error(self, operation_name: str, error: Exception, **context) -> None:
        """Log service error with context."""
        context_str = ", ".join([f"{k}={v}" for k, v in context.items()])
        self.logger.error(f"{operation_name} failed: {error} | Context: {context_str}")

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate role operations."""
        # Add business rules validation here
        return True

    async def assign_role_to_member(
        self,
        member: discord.Member,
        role: discord.Role,
        expiration_date: Optional[datetime] = None,
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
            await member.add_roles(role, reason=f"Role assignment via service ({role_type})")

            # Calculate duration for repository method
            duration = None
            if expiration_date:
                duration = expiration_date - datetime.now(timezone.utc)

            # Add to database using repository
            success = await self.role_repository.add_or_update_role_to_member(member.id, role.id, duration)

            if success:
                self._log_operation(
                    "assign_role_to_member",
                    member_id=member.id,
                    role_id=role.id,
                    role_type=role_type,
                    expiration_date=expiration_date,
                )

            return success

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
            self._log_error("assign_role_to_member", e, member_id=member.id, role_id=role.id)
            return False

    async def remove_role_from_member(self, member: discord.Member, role: discord.Role) -> bool:
        """Remove a role from a member."""
        try:
            # Remove from Discord
            await member.remove_roles(role, reason="Role removal via service")

            # Remove from database
            success = await self.role_repository.delete_member_role(member.id, role.id)

            if success:
                self._log_operation("remove_role_from_member", member_id=member.id, role_id=role.id)

            return success

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
            self._log_error("remove_role_from_member", e, member_id=member.id, role_id=role.id)
            return False

    async def process_expired_roles(
        self, role_type: Optional[str] = None, role_ids: Optional[List[int]] = None
    ) -> list[dict]:
        """Process all expired roles and remove them."""
        try:
            current_time = datetime.now(timezone.utc)
            expired_roles = await self.role_repository.get_expired_roles(current_time, role_type, role_ids)

            processed_roles = []
            for role_data in expired_roles:
                try:
                    # Get guild and member objects (this would need to be injected)
                    # For now, we'll return the data for external processing
                    processed_roles.append(role_data)

                    # Remove from database
                    await self.role_repository.delete_member_role(role_data["member_id"], role_data["role_id"])

                except Exception as e:
                    self._log_error(
                        "process_expired_role",
                        e,
                        member_id=role_data["member_id"],
                        role_id=role_data["role_id"],
                    )

            self._log_operation("process_expired_roles", processed_count=len(processed_roles))
            return processed_roles

        except Exception as e:
            self._log_error("process_expired_roles", e)
            return []

    async def extend_role_duration(self, member_id: int, role_id: int, additional_time: int) -> bool:
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
            current_expiry = target_role["expiration_date"]
            if current_expiry:
                new_expiry = current_expiry + timedelta(seconds=additional_time)
            else:
                # If no expiry set, set from now
                new_expiry = datetime.now(timezone.utc) + timedelta(seconds=additional_time)

            # Update expiry
            success = await self.role_repository.extend_role_expiry(member_id, role_id, new_expiry)

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
            self._log_error("extend_role_duration", e, member_id=member_id, role_id=role_id)
            return False

    async def get_member_role_info(self, member_id: int) -> list[dict]:
        """Get detailed role information for a member."""
        try:
            roles = await self.role_repository.get_roles_by_member_id(member_id)
            self._log_operation("get_member_role_info", member_id=member_id, count=len(roles))
            return roles
        except Exception as e:
            self._log_error("get_member_role_info", e, member_id=member_id)
            return []

    async def add_or_update_role_to_member(
        self, member_id: int, role_id: int, duration: Optional[timedelta] = None
    ) -> bool:
        """Add a role to a member or update its expiration date if it already exists."""
        try:
            success = await self.role_repository.add_or_update_role_to_member(member_id, role_id, duration)

            if success:
                self._log_operation(
                    "add_or_update_role_to_member",
                    member_id=member_id,
                    role_id=role_id,
                    duration=duration,
                )

            return success
        except Exception as e:
            self._log_error("add_or_update_role_to_member", e, member_id=member_id, role_id=role_id)
            return False

    async def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """Get role by ID."""
        try:
            role = await self.role_repository.get_role_by_id(role_id)
            self._log_operation("get_role_by_id", role_id=role_id, found=role is not None)
            return role
        except Exception as e:
            self._log_error("get_role_by_id", e, role_id=role_id)
            return None

    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """Get role by name."""
        try:
            role = await self.role_repository.get_role_by_name(name)
            self._log_operation("get_role_by_name", name=name, found=role is not None)
            return role
        except Exception as e:
            self._log_error("get_role_by_name", e, name=name)
            return None

    async def create_role(self, role_id: int, role_name: str, role_type: str = "premium") -> Role:
        """Create a new role."""
        try:
            role = await self.role_repository.create_role(role_id, role_name, role_type)
            self._log_operation("create_role", role_id=role_id, name=role_name, role_type=role_type)
            return role
        except Exception as e:
            self._log_error("create_role", e, role_id=role_id, name=role_name)
            raise

    async def get_member_premium_roles(self, member_id: int) -> List[Tuple[MemberRole, Role]]:
        """Get all premium roles of a member (active and expired)."""
        try:
            roles = await self.role_repository.get_member_premium_roles(member_id)
            self._log_operation("get_member_premium_roles", member_id=member_id, count=len(roles))
            return roles
        except Exception as e:
            self._log_error("get_member_premium_roles", e, member_id=member_id)
            return []

    async def get_premium_role(self, member_id: int) -> Optional[MemberRole]:
        """Get the active premium role of a member."""
        try:
            role = await self.role_repository.get_premium_role(member_id)
            self._log_operation("get_premium_role", member_id=member_id, found=role is not None)
            return role
        except Exception as e:
            self._log_error("get_premium_role", e, member_id=member_id)
            return None

    async def get_expiring_roles(self, reminder_time: datetime, role_type: Optional[str] = None) -> List[MemberRole]:
        """Get roles expiring within the specified time."""
        try:
            roles = await self.role_repository.get_expiring_roles(reminder_time, role_type)
            self._log_operation(
                "get_expiring_roles", reminder_time=reminder_time, role_type=role_type, count=len(roles)
            )
            return roles
        except Exception as e:
            self._log_error("get_expiring_roles", e, reminder_time=reminder_time)
            return []

    async def update_role_expiration_date(
        self, member_id: int, role_id: int, duration: timedelta
    ) -> Optional[MemberRole]:
        """Update the expiration date of the role for the member."""
        try:
            role = await self.role_repository.update_role_expiration_date(member_id, role_id, duration)

            if role:
                self._log_operation(
                    "update_role_expiration_date",
                    member_id=member_id,
                    role_id=role_id,
                    duration=duration,
                    new_expiry=role.expiration_date,
                )

            return role
        except Exception as e:
            self._log_error("update_role_expiration_date", e, member_id=member_id, role_id=role_id)
            return None

    async def update_role_expiration_date_direct(self, member_id: int, role_id: int, new_expiry: datetime) -> bool:
        """Update role expiration date directly to a specific datetime."""
        try:
            success = await self.role_repository.update_role_expiration_date_direct(member_id, role_id, new_expiry)

            if success:
                self._log_operation(
                    "update_role_expiration_date_direct",
                    member_id=member_id,
                    role_id=role_id,
                    new_expiry=new_expiry,
                )

            return success
        except Exception as e:
            self._log_error("update_role_expiration_date_direct", e, member_id=member_id, role_id=role_id)
            return False

    async def get_role_members(self, role_id: int) -> List[MemberRole]:
        """Get all members that have a specific role."""
        try:
            members = await self.role_repository.get_role_members(role_id)
            self._log_operation("get_role_members", role_id=role_id, count=len(members))
            return members
        except Exception as e:
            self._log_error("get_role_members", e, role_id=role_id)
            return []

    async def count_unique_premium_users(self) -> int:
        """Count unique members who have ever had any premium role."""
        try:
            count = await self.role_repository.count_unique_premium_users()
            self._log_operation("count_unique_premium_users", count=count)
            return count
        except Exception as e:
            self._log_error("count_unique_premium_users", e)
            return 0

    async def delete_member_role(self, member_id: int, role_id: int) -> bool:
        """Delete a role from a member."""
        try:
            success = await self.role_repository.delete_member_role(member_id, role_id)

            if success:
                self._log_operation("delete_member_role", member_id=member_id, role_id=role_id)

            return success
        except Exception as e:
            self._log_error("delete_member_role", e, member_id=member_id, role_id=role_id)
            return False

    async def check_member_has_role(self, member_id: int, role_id: int) -> Optional[MemberRole]:
        """Check if a member has a specific role."""
        try:
            role = await self.role_repository.get_member_role(member_id, role_id)
            self._log_operation(
                "check_member_has_role", member_id=member_id, role_id=role_id, has_role=role is not None
            )
            return role
        except Exception as e:
            self._log_error("check_member_has_role", e, member_id=member_id, role_id=role_id)
            return None

    async def _can_assign_role(self, member: discord.Member, role: discord.Role, role_type: str) -> bool:
        """Business logic to validate if role can be assigned."""
        # Check if member already has this role
        if role in member.roles:
            self.logger.debug(f"Member {member.id} already has role {role.id}")
            return False

        # Check role hierarchy (bot must be higher than role)
        if member.guild.me.top_role.position <= role.position:
            self.logger.warning(f"Bot cannot assign role {role.id} - insufficient permissions")
            return False

        # Add more business rules as needed
        # For example, check if premium role and member has premium status
        if role_type == "premium":
            # Would integrate with premium service here
            pass

        return True

    async def get_member_roles(self, member_id: int) -> List[MemberRole]:
        """Get all roles for a specific member."""
        try:
            roles = await self.role_repository.get_roles_by_member_id(member_id)
            # Convert dict results to MemberRole objects if needed
            member_roles = []
            for role_data in roles:
                # Create MemberRole object from dict data
                member_role = MemberRole(
                    member_id=role_data.get("member_id", member_id),
                    role_id=role_data.get("role_id"),
                    expiration_date=role_data.get("expiration_date"),
                )
                member_roles.append(member_role)

            self._log_operation("get_member_roles", member_id=member_id, role_count=len(member_roles))
            return member_roles
        except Exception as e:
            self._log_error("get_member_roles", e, member_id=member_id)
            return []
