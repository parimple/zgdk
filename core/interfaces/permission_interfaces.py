"""Interfaces for permission management system."""

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import List, Union

import discord


class PermissionLevel(Enum):
    """Enum for permission levels."""

    OWNER = auto()  # Bot owner (ID from config)
    ADMIN = auto()  # Server admin (role from config)
    MOD = auto()  # Server mod (role from config)
    MOD_OR_ADMIN = auto()  # Either mod or admin role
    OWNER_OR_ADMIN = auto()  # Either owner or admin role
    PREMIUM = auto()  # Premium roles from config
    ALL = auto()  # All levels combined


class IPermissionService(ABC):
    """Interface for permission management and checking."""

    @abstractmethod
    def check_permission_level(
        self, member: discord.Member, level: PermissionLevel
    ) -> bool:
        """Check if a member has the required permission level."""
        pass

    @abstractmethod
    def is_owner(self, member: discord.Member) -> bool:
        """Check if member is the bot owner."""
        pass

    @abstractmethod
    def is_admin(self, member: discord.Member) -> bool:
        """Check if member has admin role."""
        pass

    @abstractmethod
    def is_mod(self, member: discord.Member) -> bool:
        """Check if member has mod role."""
        pass

    @abstractmethod
    def is_mod_or_admin(self, member: discord.Member) -> bool:
        """Check if member has mod or admin role."""
        pass

    @abstractmethod
    def is_owner_or_admin(self, member: discord.Member) -> bool:
        """Check if member is owner or has admin role."""
        pass

    @abstractmethod
    def is_premium(self, member: discord.Member) -> bool:
        """Check if member has any premium role."""
        pass

    @abstractmethod
    def has_permission_levels(
        self,
        member: discord.Member,
        levels: Union[PermissionLevel, List[PermissionLevel]],
        require_all: bool = False,
    ) -> bool:
        """Check if member has required permission level(s)."""
        pass

    @abstractmethod
    def create_permission_check(
        self,
        level: Union[PermissionLevel, List[PermissionLevel]],
        require_all: bool = False,
    ):
        """Create a permission check decorator for commands."""
        pass