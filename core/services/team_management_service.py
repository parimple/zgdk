"""Team management service for handling team operations."""

import logging
from typing import Optional, List

import discord
from sqlalchemy import select, text

from core.interfaces.team_interfaces import ITeamManagementService
from core.services.base_service import BaseService
from datasources.models import Role as DBRole


class TeamManagementService(BaseService, ITeamManagementService):
    """Service for managing team operations."""

    def __init__(self, bot=None, **kwargs):
        super().__init__(**kwargs)
        self.bot = bot
        self.logger = logging.getLogger(self.__class__.__name__)

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate team management operation."""
        return self.bot is not None

    async def delete_user_teams(self, session, member_id: int) -> int:
        """
        Delete all teams owned by a specific user.

        Args:
            session: Database session
            member_id: ID of the user whose teams should be deleted

        Returns:
            Number of deleted teams
        """
        try:
            # Find teams owned by the user
            query_result = await session.execute(
                select(DBRole).where(
                    (DBRole.role_type == "team") & (DBRole.name == str(member_id))
                )
            )

            # Handle async result properly
            scalars_result = query_result.scalars()
            if hasattr(scalars_result, "__await__"):
                scalars_result = await scalars_result

            team_roles = scalars_result.all()
            if hasattr(team_roles, "__await__"):
                team_roles = await team_roles

            teams_deleted = 0
            if team_roles and self.bot and hasattr(self.bot, "guild"):
                guild = self.bot.guild
                for team_role_db in team_roles:
                    try:
                        # Find team role on server
                        team_role = guild.get_role(team_role_db.id)
                        if team_role:
                            # Find team channel
                            team_channel = await self._find_team_channel(
                                guild, member_id, team_role_db.id
                            )

                            # Delete team channel
                            if team_channel:
                                await team_channel.delete(
                                    reason=f"Team deletion after premium role loss for user {member_id}"
                                )
                                self._log_operation(
                                    "delete_team_channel",
                                    channel_id=team_channel.id,
                                    team_id=team_role_db.id,
                                    owner_id=member_id,
                                )

                            # Delete team role
                            await team_role.delete(
                                reason=f"Team deletion after premium role loss for user {member_id}"
                            )
                            self._log_operation(
                                "delete_team_role",
                                role_id=team_role_db.id,
                                owner_id=member_id,
                            )

                        # Delete team from database
                        await session.delete(team_role_db)
                        teams_deleted += 1

                        self._log_operation(
                            "delete_team",
                            team_id=team_role_db.id,
                            owner_id=member_id,
                            deleted_count=teams_deleted,
                        )

                    except Exception as e:
                        self._log_error(
                            "delete_user_teams_single",
                            e,
                            team_id=team_role_db.id,
                            owner_id=member_id,
                        )

            return teams_deleted

        except Exception as e:
            self._log_error("delete_user_teams", e, member_id=member_id)
            return 0

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
        try:
            # First find all teams owned by the user
            query_result = await session.execute(
                select(DBRole).where(
                    (DBRole.role_type == "team") & (DBRole.name == str(member_id))
                )
            )

            # Get results without using ORM
            teams_to_delete = []
            team_ids = []
            for row in query_result:
                team_role_db = row[0]
                teams_to_delete.append(team_role_db)
                team_ids.append(team_role_db.id)

            teams_deleted = 0
            if teams_to_delete and self.bot and hasattr(self.bot, "guild"):
                guild = self.bot.guild
                for team_role_db in teams_to_delete:
                    try:
                        # Find team role on server
                        team_role = guild.get_role(team_role_db.id)
                        if team_role:
                            # Find team channel
                            team_channel = await self._find_team_channel(
                                guild, member_id, team_role_db.id
                            )

                            # Delete team channel
                            if team_channel:
                                await team_channel.delete(
                                    reason=f"Team deletion after premium role loss for user {member_id}"
                                )
                                self._log_operation(
                                    "delete_team_channel_sql",
                                    channel_id=team_channel.id,
                                    team_id=team_role_db.id,
                                    owner_id=member_id,
                                )

                            # Delete team role
                            await team_role.delete(
                                reason=f"Team deletion after premium role loss for user {member_id}"
                            )
                            self._log_operation(
                                "delete_team_role_sql",
                                role_id=team_role_db.id,
                                owner_id=member_id,
                            )

                        teams_deleted += 1

                    except Exception as e:
                        self._log_error(
                            "delete_user_teams_by_sql_single",
                            e,
                            team_id=team_role_db.id,
                            owner_id=member_id,
                        )

                # Now delete all teams from database using SQL
                if team_ids:
                    try:
                        placeholders = ", ".join([f":id{i}" for i in range(len(team_ids))])
                        params = {f"id{i}": team_id for i, team_id in enumerate(team_ids)}

                        # First delete related records from member_roles table
                        member_roles_sql = text(
                            f"DELETE FROM member_roles WHERE role_id IN ({placeholders})"
                        )
                        member_result = await session.execute(member_roles_sql, params)
                        members_deleted = (
                            member_result.rowcount
                            if hasattr(member_result, "rowcount")
                            else 0
                        )

                        # Now delete records from roles table
                        sql = text(
                            f"DELETE FROM roles WHERE id IN ({placeholders}) AND role_type = 'team'"
                        )
                        result = await session.execute(sql, params)
                        num_deleted = result.rowcount if hasattr(result, "rowcount") else 0

                        self._log_operation(
                            "delete_teams_sql",
                            owner_id=member_id,
                            member_roles_deleted=members_deleted,
                            teams_deleted=num_deleted,
                        )

                    except Exception as e:
                        self._log_error(
                            "delete_user_teams_by_sql_database",
                            e,
                            owner_id=member_id,
                            team_ids=team_ids,
                        )

            return teams_deleted

        except Exception as e:
            self._log_error("delete_user_teams_by_sql", e, member_id=member_id)
            return 0

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
        try:
            if not self.bot or not hasattr(self.bot, "guild"):
                self._log_error("create_team", ValueError("Bot or guild not available"))
                return None

            guild = self.bot.guild

            # Create Discord role
            role_kwargs = {"name": team_name}
            if team_color is not None:
                role_kwargs["color"] = discord.Color(team_color)

            team_role = await guild.create_role(**role_kwargs)

            # Create database record
            team_record = DBRole(
                id=team_role.id,
                name=str(owner_id),  # Store owner ID as name for lookup
                role_type="team",
            )

            session.add(team_record)

            self._log_operation(
                "create_team",
                team_id=team_role.id,
                owner_id=owner_id,
                team_name=team_name,
                team_color=team_color,
            )

            return team_role.id

        except Exception as e:
            self._log_error(
                "create_team",
                e,
                owner_id=owner_id,
                team_name=team_name,
                team_color=team_color,
            )
            return None

    async def get_user_teams(self, session, owner_id: int) -> list:
        """
        Get all teams owned by a specific user.

        Args:
            session: Database session
            owner_id: ID of the team owner

        Returns:
            List of team records
        """
        try:
            query_result = await session.execute(
                select(DBRole).where(
                    (DBRole.role_type == "team") & (DBRole.name == str(owner_id))
                )
            )

            scalars_result = query_result.scalars()
            if hasattr(scalars_result, "__await__"):
                scalars_result = await scalars_result

            teams = scalars_result.all()
            if hasattr(teams, "__await__"):
                teams = await teams

            self._log_operation(
                "get_user_teams",
                owner_id=owner_id,
                team_count=len(teams),
            )

            return teams

        except Exception as e:
            self._log_error("get_user_teams", e, owner_id=owner_id)
            return []

    async def validate_team_ownership(
        self, session, team_id: int, owner_id: int
    ) -> bool:
        """
        Validate if a user owns a specific team.

        Args:
            session: Database session
            team_id: ID of the team
            owner_id: ID of the potential owner

        Returns:
            True if user owns the team
        """
        try:
            query_result = await session.execute(
                select(DBRole).where(
                    (DBRole.id == team_id)
                    & (DBRole.role_type == "team")
                    & (DBRole.name == str(owner_id))
                )
            )

            result = query_result.first()
            is_owner = result is not None

            self._log_operation(
                "validate_team_ownership",
                team_id=team_id,
                owner_id=owner_id,
                is_owner=is_owner,
            )

            return is_owner

        except Exception as e:
            self._log_error(
                "validate_team_ownership",
                e,
                team_id=team_id,
                owner_id=owner_id,
            )
            return False

    async def _find_team_channel(
        self, guild: discord.Guild, owner_id: int, team_id: int
    ) -> Optional[discord.TextChannel]:
        """Find team channel based on topic format."""
        try:
            for channel in guild.channels:
                if hasattr(channel, "topic") and channel.topic:
                    topic_parts = channel.topic.split()
                    # Check if topic has format owner_id team_id
                    if (
                        len(topic_parts) >= 2
                        and topic_parts[0] == str(owner_id)
                        and topic_parts[1] == str(team_id)
                    ):
                        return channel
                    # For compatibility with old format
                    elif (
                        "Team Channel" in channel.topic
                        and str(owner_id) in channel.topic
                    ):
                        return channel
            return None

        except Exception as e:
            self._log_error(
                "_find_team_channel",
                e,
                owner_id=owner_id,
                team_id=team_id,
            )
            return None

    @staticmethod
    def count_member_teams(guild: discord.Guild, member: discord.Member, team_symbol: str = "☫") -> int:
        """
        Count how many teams a member belongs to.
        
        Args:
            guild: Discord guild
            member: Discord member
            team_symbol: Team role prefix symbol
            
        Returns:
            Number of teams the member belongs to
        """
        count = 0
        for role in member.roles:
            if role.name.startswith(team_symbol):
                count += 1
        return count

    @staticmethod
    def get_owned_teams(guild: discord.Guild, member: discord.Member, team_symbol: str = "☫") -> List[str]:
        """
        Get list of teams owned by the member.
        
        Args:
            guild: Discord guild
            member: Discord member
            team_symbol: Team role prefix symbol
            
        Returns:
            List of team names owned by the member
        """
        owned_teams = []
        for role in guild.roles:
            if role.name.startswith(team_symbol):
                # Check if user is owner by checking channel topic
                for channel in guild.channels:
                    if hasattr(channel, "topic") and channel.topic:
                        topic_parts = channel.topic.split()
                        # Check if topic has format owner_id role_id
                        if (
                            len(topic_parts) >= 2
                            and topic_parts[0] == str(member.id)
                            and topic_parts[1] == str(role.id)
                        ):
                            owned_teams.append(role.name)
                            break
                        # For compatibility with old format
                        elif (
                            "Team Channel" in channel.topic
                            and str(member.id) in channel.topic
                            and str(role.id) in channel.topic
                        ):
                            owned_teams.append(role.name)
                            break
        return owned_teams