"""On Member Join Event"""

import logging
from datetime import datetime, timedelta, timezone

import discord
import sqlalchemy.exc
from discord import AllowedMentions, utils
from discord.ext import commands, tasks
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from datasources.queries import InviteQueries, MemberQueries, NotificationLogQueries

logger = logging.getLogger(__name__)


class OnMemberJoinEvent(commands.Cog):
    """Class for handling the event when a member joins the Discord server."""

    def __init__(self, bot):
        self.bot = bot
        self.guild = bot.guild
        self.invites = bot.invites
        self.channel = bot.guild.get_channel(bot.channels.get("on_join"))
        self.clean_invites.start()

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Event triggered when a member joins the guild.

        This method retrieves the current invites and compares them with previous invites
        to identify which invite was used. If the invite is not identified, the member is
        still added to the database with a characteristic ID. A notification is sent to the
        specific text channel in either case.

        :param member: The member who joined the guild
        """
        # Fetch the current invites
        new_invites = await member.guild.invites()

        # Convert the new invites to a dictionary
        new_invites_dict = {invite.id: invite for invite in new_invites}

        # Find the used invite
        used_invite = None
        for invite_id, new_invite in new_invites_dict.items():
            old_invite = self.invites.get(invite_id)
            if old_invite and old_invite.uses < new_invite.uses:
                used_invite = new_invite
                await self.process_invite(member, new_invite)
                break

        # Handle the case when no invite was identified
        if used_invite is None:
            await self.process_unknown_invite(member)

        # Update the invites dictionary
        self.invites = new_invites_dict

    async def process_invite(self, member, invite):
        """
        Process the used invite.
        This method checks if the inviter exists in the database, adds them if they don't,
        and updates or adds the member's record in the database with details about
        the invite used. It also sends a message to a specific text channel about the new
        member and the invite used.
        :param member: The member who joined
        :param invite: The invite that was used
        """
        inviter_id = invite.inviter.id if invite.inviter else self.guild.id
        now = datetime.now(timezone.utc)

        async with self.bot.get_db() as session:
            try:
                # Check if the inviter exists in the members table, if not, add them
                await MemberQueries.get_or_add_member(session, inviter_id)

                # Update or add the member's record
                await MemberQueries.get_or_add_member(
                    session,
                    member.id,
                    first_inviter_id=inviter_id,
                    current_inviter_id=inviter_id,
                    joined_at=now,
                    rejoined_at=now,
                )

                # Update or add the invite record
                await InviteQueries.add_or_update_invite(
                    session, invite.id, inviter_id, invite.uses, invite.created_at, now
                )

                await session.commit()
            except Exception as e:
                logger.error(f"Error processing invite for member {member.id}: {str(e)}")
                await session.rollback()

        await self.channel.send(
            f"{member.mention} {member.display_name} zaproszony przez {invite.inviter.mention} "
            f"Kod: {invite.code}, Użycia: {invite.uses}",
            allowed_mentions=AllowedMentions(users=False),
        )

    async def process_unknown_invite(self, member):
        """
        Process an unknown invite. Adds the member to the database
        with a characteristic ID and sends a notification.
        """
        characteristic_id = self.guild.id

        async with self.bot.get_db() as session:
            # Add the member with the characteristic ID
            await MemberQueries.get_or_add_member(
                session, member.id, first_inviter_id=characteristic_id
            )
            await session.commit()

        await self.channel.send(
            f"{member.mention} {member.display_name} zaproszony przez {self.bot.user.mention} "
            f"Kod: {self.guild.vanity_url_code}",
            allowed_mentions=AllowedMentions(users=False),
        )

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """
        Event triggered when an invite is created.

        :param invite: The invite that was created.
        """
        # Add the new invite to the invites dictionary
        self.invites[invite.id] = invite

        # Add the invite to the database
        async with self.bot.get_db() as session:
            try:
                await InviteQueries.add_or_update_invite(
                    session,
                    invite.id,
                    invite.inviter.id if invite.inviter else self.guild.id,
                    invite.uses,
                    invite.created_at,
                    datetime.now(timezone.utc),
                )
                await session.commit()
                logger.info(
                    f"Invite {invite.code} (ID: {invite.id}) created and added to database."
                )
            except Exception as e:
                logger.error(f"Error adding invite {invite.id} to database: {str(e)}")
                await session.rollback()

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """
        Event triggered when an invite is deleted.

        :param invite: The invite that was deleted.
        """
        # Remove the deleted invite from the invites dictionary
        self.invites.pop(invite.id, None)

        # Remove the invite from the database
        async with self.bot.get_db() as session:
            try:
                await InviteQueries.delete_invite(session, invite.id)
                await session.commit()
                logger.info(
                    f"Invite {invite.code} (ID: {invite.id}) deleted from Discord and database."
                )
            except Exception as e:
                logger.error(f"Error deleting invite {invite.id} from database: {str(e)}")
                await session.rollback()

    async def sync_invites(self):
        guild_invites = await self.guild.invites()
        async with self.bot.get_db() as session:
            for invite in guild_invites:
                creator_id = invite.inviter.id if invite.inviter else None
                try:
                    await InviteQueries.add_or_update_invite(
                        session,
                        invite.id,
                        creator_id,
                        invite.uses,
                        invite.created_at,
                        datetime.now(timezone.utc),
                    )
                    await session.commit()
                except Exception as e:
                    logger.error(f"Error syncing invite {invite.id}: {str(e)}")
                    await session.rollback()

        logger.info(f"Synchronized {len(guild_invites)} invites with the database")

    @tasks.loop(hours=1)
    async def clean_invites(self):
        logger.info("Starting invite cleanup process")
        try:
            guild_invites = await self.guild.invites()
        except discord.HTTPException as e:
            logger.error(f"Failed to fetch guild invites: {e}")
            return

        if not guild_invites:
            logger.warning("Received empty list of guild invites. Skipping cleanup process.")
            return

        now = datetime.now(timezone.utc)

        async with self.bot.get_db() as session:
            db_invite_count = await InviteQueries.get_invite_count(session)

            if len(guild_invites) < db_invite_count * 0.5:
                logger.error("Suspicious drop in invite count. Aborting cleanup.")
                return

            if db_invite_count < len(guild_invites):
                logger.info(
                    f"Database has fewer invites ({db_invite_count}) than Discord ({len(guild_invites)}). Syncing..."
                )
                await self.sync_invites()

            deleted_count = 0
            max_deletions = min(50, len(guild_invites) - 900)

            async def delete_invite(invite, reason):
                nonlocal deleted_count
                try:
                    if isinstance(invite, discord.Invite):
                        await invite.delete()
                    await InviteQueries.delete_invite(session, invite.id)
                    if hasattr(invite, "inviter"):
                        await self.notify_invite_deleted(invite.inviter.id, invite.id)
                    deleted_count += 1
                    logger.info(f"Deleted invite {invite.id}: {reason}")
                except discord.errors.NotFound:
                    logger.warning(f"Invite {invite.id} not found, might have been deleted already")
                except Exception as e:
                    logger.error(f"Error deleting invite {invite.id}: {str(e)}")

            if len(guild_invites) > 950:
                logger.info(f"Number of invites ({len(guild_invites)}) exceeds 950. Cleaning up...")
                inactive_invites = await InviteQueries.get_inactive_invites(
                    session, days=1, max_uses=5, limit=100
                )
                timed_invites = [
                    (db_inv, discord.utils.get(guild_invites, id=db_inv.id))
                    for db_inv in inactive_invites
                    if discord.utils.get(guild_invites, id=db_inv.id)
                    and discord.utils.get(guild_invites, id=db_inv.id).max_age > 0
                ]

                timed_invites.sort(
                    key=lambda x: x[1].created_at + timedelta(seconds=x[1].max_age), reverse=True
                )

                for db_invite, discord_invite in timed_invites:
                    if len(guild_invites) <= 950 or deleted_count >= max_deletions:
                        break
                    await delete_invite(discord_invite, "950+ limit")
                    guild_invites.remove(discord_invite)

            for guild_invite in guild_invites:
                if guild_invite.max_age > 0:
                    expiry_time = guild_invite.created_at + timedelta(seconds=guild_invite.max_age)
                    if expiry_time <= now:
                        await delete_invite(guild_invite, "expired")

            db_invites = await InviteQueries.get_all_invites(session)
            discord_invite_ids = {invite.id for invite in guild_invites}
            db_invites_to_delete = [
                db_inv for db_inv in db_invites if db_inv.id not in discord_invite_ids
            ]

            if len(db_invites_to_delete) > len(db_invites) * 0.5:
                logger.error(
                    f"Attempting to delete too many invites ({len(db_invites_to_delete)} out of {len(db_invites)}). Aborting."
                )
                return

            for db_invite in db_invites_to_delete[:max_deletions]:
                await delete_invite(db_invite, "not found on Discord")

            await session.commit()

            remaining_invites = len(guild_invites)
            donation_channel = self.bot.get_channel(self.bot.config["channels"]["donation"])
            if donation_channel:
                await donation_channel.send(
                    f"Usunięto {deleted_count} zaproszeń (wygasłych lub z powodu limitu 950+). "
                    f"Pozostało {remaining_invites} aktywnych zaproszeń na serwerze."
                )
            else:
                logger.warning("Donation channel not found. Could not send invite cleanup summary.")

            logger.info(
                f"Invite cleanup completed. Deleted {deleted_count} invites. Remaining: {remaining_invites}"
            )

    @clean_invites.before_loop
    async def before_clean_invites(self):
        await self.bot.wait_until_ready()

    async def notify_invite_deleted(self, user_id: int, invite_id: str):
        user = self.guild.get_member(user_id)
        if user:
            async with self.bot.get_db() as session:
                notification_log = await NotificationLogQueries.get_notification_log(
                    session, user_id, "invite_deleted"
                )
                if not notification_log or (
                    datetime.now(timezone.utc) - notification_log.sent_at
                ) > timedelta(hours=24):
                    try:
                        # await user.send(
                        #     f"Twoje zaproszenie o kodzie {invite_id} zostało usunięte z powodu nieaktywności. Jeśli chcesz zaprosić kogoś na serwer, musisz stworzyć nowe zaproszenie."
                        # )
                        await NotificationLogQueries.add_or_update_notification_log(
                            session, user_id, "invite_deleted"
                        )
                    except discord.Forbidden:
                        logger.warning(f"Could not send DM to user {user_id}")
            await session.commit()


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnMemberJoinEvent(bot))
