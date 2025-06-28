"""Interfaces for team management system."""

from abc import ABC, abstractmethod
from typing import Optional


class ITeamManagementService(ABC):
    """Interface for team management operations."""

    @abstractmethod
    async def delete_user_teams(self, session, member_id: int) -> int:
        """
        Delete all teams owned by a specific user.

        Args:
            session: Database session
            member_id: ID of the user whose teams should be deleted

        Returns:
            Number of deleted teams
        """
        pass

    @abstractmethod
    async def delete_user_teams_by_sql(self, session, member_id: int) -> int:
        """
        Delete all teams owned by a specific user using direct SQL queries.

        This method is safer to use when deleting teams during role selling process
        as it avoids ORM dependencies issues.

        Args:
            session: Database session
            member_id: ID of the user whose teams should be deleted

        Returns:
            Number of deleted teams
        """
        pass

    @abstractmethod
    async def create_team(
        self,
        session,
        owner_id: int,
        team_name: str,
        team_color: Optional[int] = None,
    ) -> Optional[int]:
        """
        Create a new team for a user.

        Args:
            session: Database session
            owner_id: ID of the team owner
            team_name: Name of the team
            team_color: Color for the team role

        Returns:
            Team role ID if successful, None otherwise
        """
        pass

    @abstractmethod
    async def get_user_teams(self, session, owner_id: int) -> list:
        """
        Get all teams owned by a specific user.

        Args:
            session: Database session
            owner_id: ID of the team owner

        Returns:
            List of team records
        """
        pass

    @abstractmethod
    async def validate_team_ownership(self, session, team_id: int, owner_id: int) -> bool:
        """
        Validate if a user owns a specific team.

        Args:
            session: Database session
            team_id: ID of the team
            owner_id: ID of the potential owner

        Returns:
            True if user owns the team
        """
        pass
