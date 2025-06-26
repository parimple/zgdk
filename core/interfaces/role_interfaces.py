"""Interfaces for role management domain."""

from abc import abstractmethod
from datetime import datetime
from typing import Optional

import discord

from core.interfaces.base import IRepository, IService


class IRoleRepository(IRepository):
    """Interface for role data access operations."""

    @abstractmethod
    async def get_roles_by_member_id(self, member_id: int) -> list[dict]:
        """Get all roles for a specific member."""
        pass

    @abstractmethod
    async def get_expired_roles(self, current_time: datetime) -> list[dict]:
        """Get all roles that have expired."""
        pass

    @abstractmethod
    async def get_role_by_member_and_type(
        self, member_id: int, role_type: str
    ) -> Optional[dict]:
        """Get specific role type for a member."""
        pass

    @abstractmethod
    async def extend_role_expiry(
        self, member_id: int, role_id: int, new_expiry: datetime
    ) -> bool:
        """Extend role expiry time."""
        pass


class IRoleService(IService):
    """Interface for role business logic operations."""

    @abstractmethod
    async def assign_role_to_member(
        self,
        member: discord.Member,
        role: discord.Role,
        expiry_time: Optional[datetime] = None,
        role_type: str = "temporary",
    ) -> bool:
        """Assign a role to a member with optional expiry."""
        pass

    @abstractmethod
    async def remove_role_from_member(
        self, member: discord.Member, role: discord.Role
    ) -> bool:
        """Remove a role from a member."""
        pass

    @abstractmethod
    async def process_expired_roles(self) -> list[dict]:
        """Process all expired roles and remove them."""
        pass

    @abstractmethod
    async def extend_role_duration(
        self, member_id: int, role_id: int, additional_time: int
    ) -> bool:
        """Extend role duration by specified time in seconds."""
        pass

    @abstractmethod
    async def get_member_role_info(self, member_id: int) -> list[dict]:
        """Get detailed role information for a member."""
        pass
