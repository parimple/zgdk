"""Interfaces for role management domain."""

from abc import abstractmethod
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

import discord

from core.interfaces.base import IRepository, IService
from datasources.models import MemberRole, Role


class IRoleRepository(IRepository):
    """Interface for role data access operations."""

    @abstractmethod
    async def get_roles_by_member_id(self, member_id: int) -> list[dict]:
        """Get all roles for a specific member."""
        pass

    @abstractmethod
    async def get_expired_roles(
        self, current_time: datetime, role_type: Optional[str] = None, role_ids: Optional[List[int]] = None
    ) -> list[dict]:
        """Get all roles that have expired."""
        pass

    @abstractmethod
    async def get_role_by_member_and_type(self, member_id: int, role_type: str) -> Optional[dict]:
        """Get specific role type for a member."""
        pass

    @abstractmethod
    async def extend_role_expiry(self, member_id: int, role_id: int, new_expiry: datetime) -> bool:
        """Extend role expiry time."""
        pass

    @abstractmethod
    async def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """Get role by ID."""
        pass

    @abstractmethod
    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """Get role by name."""
        pass

    @abstractmethod
    async def get_all_roles(self) -> List[Role]:
        """Get all roles from the database."""
        pass

    @abstractmethod
    async def create_role(self, role_id: int, role_name: str, role_type: str = "premium") -> Role:
        """Create a new role."""
        pass

    @abstractmethod
    async def add_or_update_role_to_member(
        self, member_id: int, role_id: int, duration: Optional[timedelta] = None
    ) -> bool:
        """Add a role to a member or update its expiration date if it already exists."""
        pass

    @abstractmethod
    async def get_member_role(self, member_id: int, role_id: int) -> Optional[MemberRole]:
        """Get a specific member role."""
        pass

    @abstractmethod
    async def delete_member_role(self, member_id: int, role_id: int) -> bool:
        """Delete a role from a member."""
        pass

    @abstractmethod
    async def get_member_premium_roles(self, member_id: int) -> List[Tuple[MemberRole, Role]]:
        """Get all premium roles of a member (active and expired)."""
        pass

    @abstractmethod
    async def get_premium_role(self, member_id: int) -> Optional[MemberRole]:
        """Get the active premium role of a member."""
        pass

    @abstractmethod
    async def get_expiring_roles(self, reminder_time: datetime, role_type: Optional[str] = None) -> List[MemberRole]:
        """Get roles expiring within the specified time."""
        pass

    @abstractmethod
    async def update_role_expiration_date(
        self, member_id: int, role_id: int, duration: timedelta
    ) -> Optional[MemberRole]:
        """Update the expiration date of the role for the member."""
        pass

    @abstractmethod
    async def update_role_expiration_date_direct(self, member_id: int, role_id: int, new_expiry: datetime) -> bool:
        """Update role expiration date directly to a specific datetime."""
        pass

    @abstractmethod
    async def get_all_premium_roles(self) -> List[MemberRole]:
        """Get all premium roles."""
        pass

    @abstractmethod
    async def get_role_members(self, role_id: int) -> List[MemberRole]:
        """Get all members that have a specific role."""
        pass

    @abstractmethod
    async def count_unique_premium_users(self) -> int:
        """Count unique members who have ever had any premium role."""
        pass


class IRoleService(IService):
    """Interface for role business logic operations."""

    @abstractmethod
    async def assign_role_to_member(
        self,
        member: discord.Member,
        role: discord.Role,
        expiration_date: Optional[datetime] = None,
        role_type: str = "temporary",
    ) -> bool:
        """Assign a role to a member with optional expiry."""
        pass

    @abstractmethod
    async def remove_role_from_member(self, member: discord.Member, role: discord.Role) -> bool:
        """Remove a role from a member."""
        pass

    @abstractmethod
    async def process_expired_roles(
        self, role_type: Optional[str] = None, role_ids: Optional[List[int]] = None
    ) -> list[dict]:
        """Process all expired roles and remove them."""
        pass

    @abstractmethod
    async def extend_role_duration(self, member_id: int, role_id: int, additional_time: int) -> bool:
        """Extend role duration by specified time in seconds."""
        pass

    @abstractmethod
    async def get_member_role_info(self, member_id: int) -> list[dict]:
        """Get detailed role information for a member."""
        pass

    @abstractmethod
    async def add_or_update_role_to_member(
        self, member_id: int, role_id: int, duration: Optional[timedelta] = None
    ) -> bool:
        """Add a role to a member or update its expiration date if it already exists."""
        pass

    @abstractmethod
    async def get_role_by_id(self, role_id: int) -> Optional[Role]:
        """Get role by ID."""
        pass

    @abstractmethod
    async def get_role_by_name(self, name: str) -> Optional[Role]:
        """Get role by name."""
        pass

    @abstractmethod
    async def create_role(self, role_id: int, role_name: str, role_type: str = "premium") -> Role:
        """Create a new role."""
        pass

    @abstractmethod
    async def get_member_premium_roles(self, member_id: int) -> List[Tuple[MemberRole, Role]]:
        """Get all premium roles of a member (active and expired)."""
        pass

    @abstractmethod
    async def get_premium_role(self, member_id: int) -> Optional[MemberRole]:
        """Get the active premium role of a member."""
        pass

    @abstractmethod
    async def get_expiring_roles(self, reminder_time: datetime, role_type: Optional[str] = None) -> List[MemberRole]:
        """Get roles expiring within the specified time."""
        pass

    @abstractmethod
    async def update_role_expiration_date(
        self, member_id: int, role_id: int, duration: timedelta
    ) -> Optional[MemberRole]:
        """Update the expiration date of the role for the member."""
        pass

    @abstractmethod
    async def update_role_expiration_date_direct(self, member_id: int, role_id: int, new_expiry: datetime) -> bool:
        """Update role expiration date directly to a specific datetime."""
        pass

    @abstractmethod
    async def get_role_members(self, role_id: int) -> List[MemberRole]:
        """Get all members that have a specific role."""
        pass

    @abstractmethod
    async def count_unique_premium_users(self) -> int:
        """Count unique members who have ever had any premium role."""
        pass

    @abstractmethod
    async def delete_member_role(self, member_id: int, role_id: int) -> bool:
        """Delete a role from a member."""
        pass

    @abstractmethod
    async def check_member_has_role(self, member_id: int, role_id: int) -> Optional[MemberRole]:
        """Check if a member has a specific role."""
        pass

    @abstractmethod
    async def get_member_roles(self, member_id: int) -> List[MemberRole]:
        """Get all roles for a specific member."""
        pass
