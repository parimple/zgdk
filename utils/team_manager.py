"""
Team management utilities for handling team operations.
"""

import logging

from sqlalchemy import select, text

from datasources.models import Role as DBRole

logger = logging.getLogger(__name__)


class TeamManager:
    """Manages team operations"""

    @staticmethod
    async def delete_user_teams(session, bot, member_id: int) -> int:
        """
        Delete all teams owned by a specific user.

        :param session: Database session
        :param bot: Bot instance
        :param member_id: ID of the user whose teams should be deleted
        :return: Number of deleted teams
        """
        # Szukamy teamów, których użytkownik jest właścicielem
        query_result = await session.execute(
            select(DBRole).where((DBRole.role_type == "team") & (DBRole.name == str(member_id)))
        )

        # Pobierz wyniki z zapytania - w testach możemy otrzymać obiekty
        # asynchroniczne, dlatego obsługujemy obie możliwości
        scalars_result = query_result.scalars()
        if hasattr(scalars_result, "__await__"):
            scalars_result = await scalars_result

        team_roles = scalars_result.all()
        if hasattr(team_roles, "__await__"):
            team_roles = await team_roles

        teams_deleted = 0
        if team_roles:
            guild = bot.guild
            for team_role_db in team_roles:
                try:
                    # Znajdź rolę teamu na serwerze
                    team_role = guild.get_role(team_role_db.id)
                    if team_role:
                        # Znajdź kanał teamu (nowy format topicu: "id_właściciela id_roli")
                        team_channel = None
                        for channel in guild.channels:
                            if hasattr(channel, "topic") and channel.topic:
                                topic_parts = channel.topic.split()
                                # Sprawdź czy topic ma format id_właściciela id_roli
                                if (
                                    len(topic_parts) >= 2
                                    and topic_parts[0] == str(member_id)
                                    and topic_parts[1] == str(team_role_db.id)
                                ):
                                    team_channel = channel
                                    break
                                # Dla kompatybilności ze starym formatem
                                elif (
                                    "Team Channel" in channel.topic
                                    and str(member_id) in channel.topic
                                ):
                                    team_channel = channel
                                    break

                        # Usuń kanał teamu
                        if team_channel:
                            await team_channel.delete(
                                reason=f"Team deletion after premium role loss for user {member_id}"
                            )
                            logger.info(
                                f"Deleted team channel {team_channel.id} for team {team_role_db.id}"
                            )

                        # Usuń rolę teamu
                        await team_role.delete(
                            reason=f"Team deletion after premium role loss for user {member_id}"
                        )
                        logger.info(f"Deleted team role {team_role_db.id}")

                    # Usuń team z bazy danych
                    await session.delete(team_role_db)
                    teams_deleted += 1

                    logger.info(
                        f"Team {team_role_db.id} owned by {member_id} deleted after premium role loss"
                    )
                except Exception as e:
                    logger.error(
                        f"Error deleting team {team_role_db.id} for user {member_id}: {str(e)}"
                    )

        return teams_deleted

    @staticmethod
    async def delete_user_teams_by_sql(session, bot, member_id: int) -> int:
        """
        Delete all teams owned by a specific user using direct SQL queries.

        This method is safer to use when deleting teams during role selling process
        as it avoids ORM dependencies issues. It first deletes the Discord roles/channels
        and then removes the database records using raw SQL.

        :param session: Database session
        :param bot: Bot instance
        :param member_id: ID of the user whose teams should be deleted
        :return: Number of deleted teams
        """
        # Najpierw znajdujemy wszystkie teamy, których użytkownik jest właścicielem
        query_result = await session.execute(
            select(DBRole).where((DBRole.role_type == "team") & (DBRole.name == str(member_id)))
        )

        # Pobierz wyniki z zapytania bez używania ORM
        teams_to_delete = []
        team_ids = []
        for row in query_result:
            team_role_db = row[0]
            teams_to_delete.append(team_role_db)
            team_ids.append(team_role_db.id)

        teams_deleted = 0
        if teams_to_delete:
            guild = bot.guild
            for team_role_db in teams_to_delete:
                try:
                    # Znajdź rolę teamu na serwerze
                    team_role = guild.get_role(team_role_db.id)
                    if team_role:
                        # Znajdź kanał teamu
                        team_channel = None
                        for channel in guild.channels:
                            if hasattr(channel, "topic") and channel.topic:
                                topic_parts = channel.topic.split()
                                # Sprawdź czy topic ma format id_właściciela id_roli
                                if (
                                    len(topic_parts) >= 2
                                    and topic_parts[0] == str(member_id)
                                    and topic_parts[1] == str(team_role_db.id)
                                ):
                                    team_channel = channel
                                    break
                                # Dla kompatybilności ze starym formatem
                                elif (
                                    "Team Channel" in channel.topic
                                    and str(member_id) in channel.topic
                                ):
                                    team_channel = channel
                                    break

                        # Usuń kanał teamu
                        if team_channel:
                            await team_channel.delete(
                                reason=f"Team deletion after premium role loss for user {member_id}"
                            )
                            logger.info(
                                f"Deleted team channel {team_channel.id} for team {team_role_db.id}"
                            )

                        # Usuń rolę teamu
                        await team_role.delete(
                            reason=f"Team deletion after premium role loss for user {member_id}"
                        )
                        logger.info(f"Deleted team role {team_role_db.id}")

                    teams_deleted += 1
                    logger.info(
                        f"Team {team_role_db.id} owned by {member_id} deleted via SQL method (Discord cleanup)"
                    )
                except Exception as e:
                    logger.error(
                        f"Error deleting team {team_role_db.id} for user {member_id}: {str(e)}"
                    )

            # Teraz usuwamy wszystkie teamy z bazy danych za pomocą zapytania SQL
            if team_ids:
                try:
                    placeholders = ", ".join([f":id{i}" for i in range(len(team_ids))])
                    params = {f"id{i}": team_id for i, team_id in enumerate(team_ids)}

                    # Najpierw usuń powiązane rekordy z tabeli member_roles
                    member_roles_sql = text(
                        f"DELETE FROM member_roles WHERE role_id IN ({placeholders})"
                    )
                    member_result = await session.execute(member_roles_sql, params)
                    members_deleted = (
                        member_result.rowcount if hasattr(member_result, "rowcount") else 0
                    )
                    logger.info(
                        f"Deleted {members_deleted} member role records from database for teams owned by user {member_id}"
                    )

                    # Teraz możemy bezpiecznie usunąć rekordy z tabeli roles
                    sql = text(
                        f"DELETE FROM roles WHERE id IN ({placeholders}) AND role_type = 'team'"
                    )
                    result = await session.execute(sql, params)
                    num_deleted = result.rowcount if hasattr(result, "rowcount") else 0

                    logger.info(
                        f"Deleted {num_deleted} team records from database for user {member_id} via SQL"
                    )
                except Exception as e:
                    logger.error(f"Error during SQL deletion of team records: {str(e)}")

        return teams_deleted
