"""Role manager for handling role operations and expiry checks."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

import discord
from discord import AllowedMentions

from datasources.queries import MemberQueries, NotificationLogQueries, RoleQueries
from utils.errors import ResourceNotFoundError, ZGDKError
from utils.managers import BaseManager

logger = logging.getLogger(__name__)


class RoleManager(BaseManager):
    """Manages temporary roles on the Discord server."""

    # Static variables to store last check results
    _last_check_results = {}
    _last_check_timestamp = None

    def __init__(self, bot):
        """Initialize the role manager with a bot instance."""
        super().__init__(bot)
        self.notification_channel_id = self.bot.config.get("channels", {}).get(
            "mute_notifications"
        )

    @property
    def force_channel_notifications(self):
        """Get the notification channel setting."""
        return getattr(self.bot, "force_channel_notifications", True)

    async def check_expired_roles(
        self,
        role_type: Optional[str] = None,
        role_ids: Optional[List[int]] = None,
        notification_handler: Optional[Callable] = None,
    ) -> int:
        """Check and remove expired roles of the specified type or IDs.

        Only removes roles that:
        1. Exist in the database with an expiration date
        2. Have expired according to the date in the database
        3. Are currently assigned to the user on the server

        Does not remove database entries for roles that are no longer assigned to users,
        allowing interoperability with other role management bots.

        Args:
            role_type: Optional role type to check (e.g. "premium", "mute")
            role_ids: Optional list of specific role IDs to check
            notification_handler: Optional function to handle notifications

        Returns:
            Number of removed roles
        """
        start_time = datetime.now()
        now = datetime.now(timezone.utc)
        removed_count = 0

        # Create a unique key for this specific check
        check_key = f"{role_type}_{str(role_ids)}"

        # Counters for statistics
        stats = {
            "non_existent_members": 0,
            "non_existent_roles": 0,
            "roles_not_assigned": 0,
            "skipped_member_ids": set(),  # Unique member IDs
            "skipped_role_ids": set(),  # Unique role IDs
            "expired_roles_count": 0,  # Number of expired roles found in the database
            "removed_count": 0,  # Number of removed roles
        }

        # Check if the guild is available
        if not hasattr(self.bot, "guild") or self.bot.guild is None:
            logger.error("Guild not available - skipping expired roles check")
            return 0

        # Change logging level from INFO to DEBUG
        logger.debug(
            f"Checking expired roles: type={role_type}, specific_ids={role_ids}"
        )

        try:
            # Remember the previous state of skipped members for this key
            previous_skipped_ids = RoleManager._last_check_results.get(
                check_key, {}
            ).get("skipped_member_ids", set())

            async with self.bot.get_db() as session:
                # Get expired roles from the database
                expired_roles = await RoleQueries.get_expired_roles(
                    session, now, role_type=role_type, role_ids=role_ids
                )

                if not expired_roles:
                    # Check if there was something to do previously
                    last_stats = RoleManager._last_check_results.get(check_key, {})
                    if last_stats.get("expired_roles_count", 0) > 0:
                        logger.info(
                            "No expired roles found (changed from previous check)"
                        )
                        RoleManager._last_check_results[check_key] = stats.copy()
                    return 0

                # Save the number of expired roles
                stats["expired_roles_count"] = len(expired_roles)

                # Check if the number of expired roles has changed
                last_expired_count = RoleManager._last_check_results.get(
                    check_key, {}
                ).get("expired_roles_count", -1)
                if last_expired_count != stats["expired_roles_count"]:
                    logger.info(
                        f"Found {stats['expired_roles_count']} expired roles to process (changed from {last_expired_count})"
                    )

                # Identify the mutenick role (role with index 2 in the configuration)
                nick_mute_role_id = None
                for role_config in self.config["mute_roles"]:
                    if role_config["description"] == "attach_files_off":
                        nick_mute_role_id = role_config["id"]
                        break

                if not nick_mute_role_id:
                    logger.warning("Couldn't find mutenick role ID in config")

                # Group roles by users for optimized processing
                # Dictionary: {member_id: {"member": discord.Member, "roles": [(member_role, role_obj)]}}
                member_data_map: Dict[int, Dict[str, Any]] = {}

                for member_role in expired_roles:
                    member: Optional[discord.Member] = None
                    # Check if we've already fetched this user
                    if member_role.member_id in member_data_map:
                        member = member_data_map[member_role.member_id]["member"]
                    else:
                        try:
                            member = await self.bot.guild.fetch_member(
                                member_role.member_id
                            )
                            # Save the fetched user to avoid multiple fetches
                            member_data_map[member_role.member_id] = {
                                "member": member,
                                "roles": [],
                            }
                        except discord.NotFound:
                            logger.info(
                                f"Member with ID {member_role.member_id} not found (left server?), skipping role {member_role.role_id} and cleaning DB."
                            )
                            stats["non_existent_members"] += 1
                            stats["skipped_member_ids"].add(member_role.member_id)
                            await RoleQueries.delete_member_role(
                                session, member_role.member_id, member_role.role_id
                            )
                            removed_count += 1  # Count DB removal as an action
                            stats["removed_count"] += 1
                            continue
                        except Exception as e:
                            logger.error(
                                f"Error fetching member {member_role.member_id}: {e}"
                            )
                            stats["non_existent_members"] += 1
                            stats["skipped_member_ids"].add(member_role.member_id)
                            # Don't delete from DB on unknown error, might be temporary
                            continue

                    if (
                        not member
                    ):  # Should be handled by exceptions above, but as an additional safeguard
                        stats["non_existent_members"] += 1
                        stats["skipped_member_ids"].add(member_role.member_id)
                        logger.warning(
                            f"Member object is None for ID {member_role.member_id} despite fetch attempt, skipping role."
                        )
                        # Consider if DB cleanup is needed here too
                        continue

                    role = self.bot.guild.get_role(member_role.role_id)
                    if not role:
                        logger.info(
                            f"Role ID {member_role.role_id} not found on server for member {member_role.member_id}. Cleaning DB."
                        )
                        stats["non_existent_roles"] += 1
                        stats["skipped_role_ids"].add(member_role.role_id)
                        await RoleQueries.delete_member_role(
                            session, member_role.member_id, member_role.role_id
                        )
                        removed_count += 1  # Count DB removal
                        stats["removed_count"] += 1
                        continue

                    if role not in member.roles:
                        logger.info(
                            f"Role {role.name} (ID: {role.id}) was in DB for member {member.display_name} (ID: {member.id}) but not assigned on Discord. Cleaning DB."
                        )
                        stats["roles_not_assigned"] += 1
                        await RoleQueries.delete_member_role(
                            session, member_role.member_id, member_role.role_id
                        )
                        removed_count += 1  # Count DB removal
                        stats["removed_count"] += 1
                        continue

                    # Add the (member_role, role) pair to the user's role list
                    # This part is reached only if member exists, role exists, and member has the role.
                    member_data_map[member_role.member_id]["roles"].append(
                        (member_role, role)
                    )

                # Process roles grouped by users
                for member_id, data in member_data_map.items():
                    member = data["member"]
                    role_pairs = data["roles"]

                    if not member or not role_pairs:
                        logger.warning(
                            f"Skipping member_id {member_id} due to missing member object or roles list in map."
                        )
                        continue

                    # Prepare a list of discord.Role objects to remove
                    discord_roles_to_remove_on_discord: List[discord.Role] = [
                        rp[1] for rp in role_pairs
                    ]

                    # Check if the user has mutenick and if they have a default nick before removing roles
                    default_nick = self.config.get("default_mute_nickname", "random")

                    if (
                        not discord_roles_to_remove_on_discord
                    ):  # If the list is empty, continue
                        logger.debug(
                            f"No Discord roles to remove for member {member.display_name} ({member.id}), skipping Discord interaction."
                        )
                        continue

                    try:
                        # Step 1: Try to remove roles on Discord
                        await member.remove_roles(
                            *discord_roles_to_remove_on_discord, reason="Roles expired"
                        )
                        logger.info(
                            f"Successfully removed {len(discord_roles_to_remove_on_discord)} roles from {member.display_name} ({member.id}) on Discord."
                        )

                        # Step 2: If the removal on Discord was successful, remove from the database and send notifications
                        for member_role_db_entry, role_obj in role_pairs:
                            try:
                                await RoleQueries.delete_member_role(
                                    session,
                                    member_role_db_entry.member_id,
                                    member_role_db_entry.role_id,
                                )
                                removed_count += 1
                                stats["removed_count"] += 1
                                logger.debug(
                                    f"Successfully deleted role ID {member_role_db_entry.role_id} for member {member_role_db_entry.member_id} from DB."
                                )

                                notification_tag = f"{role_type or 'role'}_expired"
                                await NotificationLogQueries.add_or_update_notification_log(
                                    session,
                                    member_role_db_entry.member_id,
                                    notification_tag,
                                )

                                if notification_handler:
                                    await notification_handler(
                                        member, member_role_db_entry, role_obj
                                    )
                                else:
                                    # Logic for default notification, if needed and no handler is provided
                                    # (assuming we send a notification for each successful removal)
                                    # await self.send_default_notification(member, role_obj) # Uncomment/adapt as needed
                                    pass  # Currently handler is passed from OnTaskEvent

                            except Exception as e_db_notify:
                                logger.error(
                                    f"Error during DB delete or notification for role {role_obj.name} (member {member.id}): {e_db_notify}",
                                    exc_info=True,
                                )
                                # Continue with the next role, but log the error.
                                # We don't want an error with one role to stop processing others.

                        # Logic related to mutenick after successful role removal
                        if nick_mute_role_id:  # Check only if mutenick is configured
                            await asyncio.sleep(
                                0.5
                            )  # Give Discord a moment to process the role removal
                            # Get a fresh member object to be sure about current roles and nick
                            try:
                                updated_member = await self.bot.guild.fetch_member(
                                    member.id
                                )
                                if (
                                    not updated_member
                                ):  # In case fetch_member returns None
                                    logger.warning(
                                        f"Could not fetch updated member {member.id} after role removal, skipping nick logic."
                                    )
                                    continue  # Go to the next member in the member_data_map loop
                            except discord.NotFound:
                                logger.info(
                                    f"Member {member.id} not found after role removal, likely left. Skipping nick logic."
                                )
                                continue
                            except Exception as e_fetch:
                                logger.error(
                                    f"Error fetching updated member {member.id}: {e_fetch}, skipping nick logic."
                                )
                                continue

                            current_nick = updated_member.nick
                            member_roles_after_removal = updated_member.roles

                            has_nick_mute_role_after_removal = (
                                discord.utils.get(
                                    member_roles_after_removal, id=nick_mute_role_id
                                )
                                is not None
                            )
                            was_nick_mute_role_removed = any(
                                role.id == nick_mute_role_id
                                for role in discord_roles_to_remove_on_discord
                            )

                            # Scenario 1: The mutenick role was just removed
                            if was_nick_mute_role_removed:
                                if current_nick == default_nick:
                                    try:
                                        await updated_member.edit(
                                            nick=None,
                                            reason="Mute nick expired, resetting nick",
                                        )
                                        logger.info(
                                            f"Reset nickname for {updated_member.display_name} ({updated_member.id}) as their mute nick role expired."
                                        )
                                    except Exception as e_nick_reset:
                                        logger.error(
                                            f"Failed to reset nick for {updated_member.display_name} after mute nick expiry: {e_nick_reset}"
                                        )
                                # If the nick wasn't the default mute nick, we don't do anything - the user might have changed it.

                            # Scenario 2: Another role expired, but the user still has mutenick and had the default nick
                            elif (
                                has_nick_mute_role_after_removal
                                and current_nick == default_nick
                            ):
                                # This condition is more precise - we check if they *still* have mutenick
                                # and if they *still* have the default nick. If so, we make sure the nick is preserved.
                                try:
                                    await updated_member.edit(
                                        nick=default_nick,
                                        reason="Preserving default nick after other role expiry (still has mutenick)",
                                    )
                                    logger.info(
                                        f"Ensured default nickname '{default_nick}' for {updated_member.display_name} ({updated_member.id}) as they still have a mute nick role."
                                    )
                                except Exception as e_nick:
                                    logger.error(
                                        f"Failed to ensure default nick for {updated_member.display_name}: {e_nick}"
                                    )

                    except discord.Forbidden:
                        logger.error(
                            f"PERMISSION ERROR removing roles from {member.display_name} ({member.id}). Roles NOT deleted from DB. Audit should catch this."
                        )
                        # IMPORTANT: We don't remove from the DB if the removal from Discord failed due to lack of permissions.
                    except discord.HTTPException as e_http:
                        logger.error(
                            f"HTTP ERROR {e_http.status} (code: {e_http.code}) removing roles from {member.display_name} ({member.id}): {e_http.text}. Roles NOT deleted from DB. Audit should catch this."
                        )
                        # IMPORTANT: We don't remove from the DB if the removal from Discord failed due to an HTTP error.
                    except Exception as e_main_remove:
                        logger.error(
                            f"GENERAL ERROR removing roles from {member.display_name} ({member.id}): {e_main_remove}. Roles NOT deleted from DB. Audit should catch this.",
                            exc_info=True,
                        )
                        # IMPORTANT: We don't remove from the DB with other errors.

                await session.commit()

                # Get previous statistics and compare
                last_stats = RoleManager._last_check_results.get(check_key, {})

                # Log skip statistics only if something changed
                stats_changed = False

                # Check if the number of skipped roles for non-existent users changed
                if stats["non_existent_members"] != last_stats.get(
                    "non_existent_members", -1
                ):
                    stats_changed = True
                    if stats["non_existent_members"] > 0:
                        logger.info(
                            f"Skipped {stats['non_existent_members']} roles for {len(stats['skipped_member_ids'])} non-existent members"
                        )

                # Check if the number of skipped non-existent roles changed
                if stats["non_existent_roles"] != last_stats.get(
                    "non_existent_roles", -1
                ):
                    stats_changed = True
                    if stats["non_existent_roles"] > 0:
                        logger.info(
                            f"Skipped {stats['non_existent_roles']} non-existent roles for {len(stats['skipped_role_ids'])} unique IDs"
                        )

                # Check if the number of skipped unassigned roles changed
                if stats["roles_not_assigned"] != last_stats.get(
                    "roles_not_assigned", -1
                ):
                    stats_changed = True
                    if stats["roles_not_assigned"] > 0:
                        logger.info(
                            f"Skipped {stats['roles_not_assigned']} roles not actually assigned to members"
                        )

                # Check if any roles were removed or if the number of removed roles changed
                if removed_count > 0 or stats["removed_count"] != last_stats.get(
                    "removed_count", -1
                ):
                    stats_changed = True

                # Record performance metrics only if something changed or if something was removed
                if stats_changed or removed_count > 0:
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    logger.info(
                        f"Role expiry check completed in {duration:.2f}s - Processed {len(expired_roles)} roles, removed {removed_count}, skipped {stats['non_existent_members'] + stats['non_existent_roles'] + stats['roles_not_assigned']}"
                    )

                # Save current statistics as last
                RoleManager._last_check_results[check_key] = stats.copy()
                RoleManager._last_check_timestamp = now

                # Log aggregated information about skipped members only if the list changed
                current_skipped_ids = stats["skipped_member_ids"]
                if current_skipped_ids and current_skipped_ids != previous_skipped_ids:
                    logger.info(
                        f"RoleManager: Skipped processing for {stats['non_existent_members']} members not found in guild cache. IDs: {list(current_skipped_ids)}"
                    )

                return removed_count

        except Exception as e:
            logger.error(f"Error in check_expired_roles: {e}", exc_info=True)
            return 0

    async def send_default_notification(
        self, member: discord.Member, role: discord.Role
    ):
        """Send a default notification about role expiry.

        Args:
            member: The user whose role expired
            role: The role that expired
        """
        try:
            # Check if it's a mute role
            is_mute_role = any(
                role.id == mute_role["id"]
                for mute_role in self.config.get("mute_roles", [])
            )

            if is_mute_role:
                message = f"Your mute ({role.name}) has expired and has been automatically removed."
            else:
                message = f"Your role {role.name} has expired and has been automatically removed."

            await self.send_notification(member, message)

        except Exception as e:
            logger.error(f"Error sending default notification: {e}")

    async def send_notification(self, member: discord.Member, message: str):
        """Send a notification to the user via DM or channel.

        Args:
            member: The user to send the notification to
            message: The notification content
        """
        try:
            if not self.force_channel_notifications:
                # Send DM
                await member.send(message)
                logger.info(
                    f"Sent DM notification to {member.display_name} ({member.id})"
                )
            else:
                # Send to channel
                channel = self.bot.get_channel(self.notification_channel_id)
                if channel:
                    await channel.send(
                        f"[Channel] {member.mention}, {message}",
                        allowed_mentions=AllowedMentions(users=False),
                    )
                    logger.info(
                        f"Sent channel notification to {member.display_name} ({member.id})"
                    )
                else:
                    logger.error(
                        f"Notification channel {self.notification_channel_id} not found"
                    )
        except discord.Forbidden:
            logger.warning(f"Could not send DM to {member.display_name} ({member.id})")
            # Fallback to channel notification
            if not self.force_channel_notifications:
                channel = self.bot.get_channel(self.notification_channel_id)
                if channel:
                    await channel.send(
                        f"[DM not working] {member.mention}, {message}",
                        allowed_mentions=AllowedMentions(users=False),
                    )
        except Exception as e:
            logger.error(f"Error sending notification: {e}")

    async def add_role_with_expiry(
        self, member_id: int, role_id: int, expiry_hours: int
    ) -> bool:
        """Add a role with an expiration time to a member.

        Args:
            member_id: The Discord ID of the member
            role_id: The Discord ID of the role to add
            expiry_hours: Hours until the role expires

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get Discord objects
            member = self.bot.guild.get_member(member_id)
            if not member:
                try:
                    member = await self.bot.guild.fetch_member(member_id)
                except discord.NotFound:
                    logger.error(f"Member with ID {member_id} not found")
                    raise ResourceNotFoundError(f"Member with ID {member_id} not found")

            role = self.bot.guild.get_role(role_id)
            if not role:
                logger.error(f"Role with ID {role_id} not found")
                raise ResourceNotFoundError(f"Role with ID {role_id} not found")

            # Add role to member on Discord
            await member.add_roles(
                role, reason=f"Role added with {expiry_hours}h expiry"
            )

            # Update database
            async with self.bot.get_db() as session:
                # Add or update the role in the database
                await RoleQueries.add_or_update_role_to_member(
                    session, member_id, role_id, duration=timedelta(hours=expiry_hours)
                )
                await session.commit()

            logger.info(
                f"Added role {role.name} to {member.display_name} with {expiry_hours}h expiry"
            )
            return True

        except Exception as e:
            logger.error(f"Error adding role with expiry: {e}", exc_info=True)
            if isinstance(e, ZGDKError):
                raise
            return False

    async def remove_role(self, member_id: int, role_id: int) -> bool:
        """Remove a role from a member and from the database.

        Args:
            member_id: The Discord ID of the member
            role_id: The Discord ID of the role to remove

        Returns:
            True if successful, False otherwise
        """
        try:
            # Get Discord objects
            member = self.bot.guild.get_member(member_id)
            if not member:
                try:
                    member = await self.bot.guild.fetch_member(member_id)
                except discord.NotFound:
                    logger.error(f"Member with ID {member_id} not found")
                    # Still try to remove from DB even if member is not found
                    pass

            role = self.bot.guild.get_role(role_id)
            if not role:
                logger.error(f"Role with ID {role_id} not found")
                # Still try to remove from DB even if role is not found
                pass

            # Remove role from member on Discord if both objects exist
            if member and role and role in member.roles:
                await member.remove_roles(role, reason="Role manually removed")
                logger.info(f"Removed role {role.name} from {member.display_name}")

            # Update database
            async with self.bot.get_db() as session:
                # Remove the role from the database
                await RoleQueries.delete_member_role(session, member_id, role_id)
                await session.commit()

            return True

        except Exception as e:
            logger.error(f"Error removing role: {e}", exc_info=True)
            return False

    async def get_role_info(
        self, member_id: int, role_id: Optional[int] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """Get information about a member's roles.

        Args:
            member_id: The Discord ID of the member
            role_id: Optional specific role ID to get info about

        Returns:
            Tuple of (success, info_dict)
        """
        try:
            async with self.bot.get_db() as session:
                if role_id:
                    # Get specific role
                    member_role = await RoleQueries.get_member_role(
                        session, member_id, role_id
                    )
                    if not member_role:
                        return False, {"error": "Role not found for this member"}

                    role = await RoleQueries.get_role_by_id(session, role_id)
                    if not role:
                        return False, {"error": "Role not found in database"}

                    discord_role = self.bot.guild.get_role(role_id)
                    role_name = discord_role.name if discord_role else "Unknown Role"

                    return True, {
                        "id": role.id,
                        "name": role_name,
                        "type": role.role_type,
                        "expiry_date": member_role.expiration_date,
                        "has_role_on_discord": discord_role
                        in self.bot.guild.get_member(member_id).roles
                        if discord_role and self.bot.guild.get_member(member_id)
                        else False,
                    }
                else:
                    # Get all roles
                    member_roles = await RoleQueries.get_member_roles(
                        session, member_id
                    )
                    if not member_roles:
                        return False, {"error": "No roles found for this member"}

                    roles_info = []
                    for member_role in member_roles:
                        role = await RoleQueries.get_role_by_id(
                            session, member_role.role_id
                        )
                        if not role:
                            continue

                        discord_role = self.bot.guild.get_role(role.id)
                        role_name = (
                            discord_role.name if discord_role else "Unknown Role"
                        )

                        roles_info.append(
                            {
                                "id": role.id,
                                "name": role_name,
                                "type": role.role_type,
                                "expiry_date": member_role.expiration_date,
                                "has_role_on_discord": discord_role
                                in self.bot.guild.get_member(member_id).roles
                                if discord_role and self.bot.guild.get_member(member_id)
                                else False,
                            }
                        )

                    return True, {"roles": roles_info}

        except Exception as e:
            logger.error(f"Error getting role info: {e}", exc_info=True)
            return False, {"error": str(e)}
