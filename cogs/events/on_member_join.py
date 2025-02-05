"""On Member Join Event"""

import asyncio
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
        self.guild = None
        self.invites = {}
        self.welcome_channel = None
        self.rules_channel = None
        self.setup_channels.start()  # pylint: disable=no-member
        self.setup_guild.start()  # pylint: disable=no-member
        # clean_invites will be started after guild is set up

    @tasks.loop(count=1)
    async def setup_guild(self):
        """Setup guild and invites after bot is ready"""
        logger.info("Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

        # Wait for guild to be set
        while self.bot.guild is None:
            logger.info("Waiting for guild to be set...")
            await asyncio.sleep(1)

        logger.info("Bot is ready and guild is set, setting up guild and invites")

        self.guild = self.bot.guild
        self.invites = {invite.id: invite for invite in await self.guild.invites()}

        # Start clean_invites task only after guild is set up
        self.clean_invites.start()  # pylint: disable=no-member

    async def cog_unload(self):
        """Clean up tasks when cog is unloaded"""
        self.setup_channels.cancel()
        self.setup_guild.cancel()
        self.clean_invites.cancel()

    @tasks.loop(count=1)
    async def setup_channels(self):
        """Setup channels after bot is ready"""
        logger.info("Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

        # Wait for guild to be set
        while self.bot.guild is None:
            logger.info("Waiting for guild to be set...")
            await asyncio.sleep(1)

        logger.info("Bot is ready and guild is set, setting up channels")

        # Now we can safely get channels
        welcome_channel_id = self.bot.channels.get("on_join")
        rules_channel_id = self.bot.channels.get("rules")

        logger.info(f"Getting welcome channel with ID: {welcome_channel_id}")
        logger.info(f"Getting rules channel with ID: {rules_channel_id}")

        self.welcome_channel = self.bot.get_channel(welcome_channel_id)
        self.rules_channel = self.bot.get_channel(rules_channel_id)

        logger.info(f"Welcome channel set: {self.welcome_channel}")
        logger.info(f"Rules channel set: {self.rules_channel}")

        if not self.welcome_channel:
            logger.error(f"Failed to get welcome channel with ID {welcome_channel_id}")
        if not self.rules_channel:
            logger.error(f"Failed to get rules channel with ID {rules_channel_id}")

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
        logger.info(f"Member join event triggered for {member} ({member.id})")

        if member.guild.id != self.bot.guild_id:
            logger.info(
                f"Member joined different guild: {member.guild.id} (expected {self.bot.guild_id})"
            )
            return

        # Check if we have invites dictionary initialized
        if not self.invites:
            logger.warning("Invites dictionary is empty, initializing...")
            self.invites = {invite.id: invite for invite in await member.guild.invites()}

        # Log current state
        logger.info(f"Current invites count: {len(self.invites)}")

        try:
            # Fetch the current invites
            new_invites = await member.guild.invites()
            logger.info(f"New invites count: {len(new_invites)}")

            # Convert the new invites to a dictionary
            new_invites_dict = {invite.id: invite for invite in new_invites}

            # Find the used invite
            used_invite = None
            for invite_id, new_invite in new_invites_dict.items():
                old_invite = self.invites.get(invite_id)
                if old_invite:
                    logger.debug(
                        f"Comparing invite {invite_id}: old uses={old_invite.uses}, new uses={new_invite.uses}"
                    )
                    if old_invite.uses < new_invite.uses:
                        used_invite = new_invite
                        logger.info(
                            f"Found used invite: {invite_id} (uses: {new_invite.uses}, inviter: {new_invite.inviter})"
                        )
                        await self.process_invite(member, new_invite)
                        break
                else:
                    logger.debug(f"New invite found: {invite_id} (uses: {new_invite.uses})")

            # Handle the case when no invite was identified
            if used_invite is None:
                logger.info(f"No invite identified for member {member}, processing as unknown")
                await self.process_unknown_invite(member)

            # Update the invites dictionary
            self.invites = new_invites_dict

        except Exception as e:
            logger.error(f"Error processing member join for {member}: {str(e)}", exc_info=True)
            # Still try to process as unknown invite if something went wrong
            await self.process_unknown_invite(member)

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

        # Check if welcome_channel is None and try to get it again
        if self.welcome_channel is None:
            self.welcome_channel = self.bot.get_channel(self.bot.channels.get("on_join"))
            logger.info(f"Re-fetched welcome channel: {self.welcome_channel}")

        if self.welcome_channel:
            await self.welcome_channel.send(
                f"{member.mention} {member.display_name} zaproszony przez {invite.inviter.mention} "
                f"Kod: {invite.code}, Użycia: {invite.uses}",
                allowed_mentions=AllowedMentions(users=False),
            )
        else:
            logger.error(
                f"Welcome channel is still None, could not send welcome message for {member}"
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

        # Check if welcome_channel is None and try to get it again
        if self.welcome_channel is None:
            self.welcome_channel = self.bot.get_channel(self.bot.channels.get("on_join"))
            logger.info(f"Re-fetched welcome channel: {self.welcome_channel}")

        if self.welcome_channel:
            await self.welcome_channel.send(
                f"{member.mention} {member.display_name} zaproszony przez {self.bot.user.mention} "
                f"Kod: {self.guild.vanity_url_code}",
                allowed_mentions=AllowedMentions(users=False),
            )
        else:
            logger.error(
                f"Welcome channel is still None, could not send welcome message for {member}"
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
                # logger.info(
                #     f"Invite {invite.code} (ID: {invite.id}) created and added to database."
                # )
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
                # logger.info(
                #     f"Invite {invite.code} (ID: {invite.id}) deleted from Discord and database."
                # )
            except Exception as e:
                logger.error(f"Error deleting invite {invite.id} from database: {str(e)}")
                await session.rollback()

    async def sync_invites(self):
        guild_invites = await self.guild.invites()
        async with self.bot.get_db() as session:
            # Pobierz wszystkie zaproszenia z bazy danych
            db_invites = await InviteQueries.get_all_invites(session)

            # Utwórz zbiór ID zaproszeń z Discord
            discord_invite_ids = {invite.id for invite in guild_invites}

            # Usuń zaproszenia z bazy danych, których nie ma na Discord
            for db_invite in db_invites:
                if db_invite.id not in discord_invite_ids:
                    await InviteQueries.delete_invite(session, db_invite.id)
                    # logger.info(f"Deleted invite from database: {db_invite.id}")

            # Dodaj lub zaktualizuj zaproszenia z Discord w bazie danych
            for invite in guild_invites:
                creator_id = invite.inviter.id if invite.inviter else None
                try:
                    await InviteQueries.add_or_update_invite(
                        session,
                        invite.id,
                        creator_id,
                        invite.uses,
                        invite.created_at,
                        None,  # Nie aktualizujemy last_used_at podczas synchronizacji
                    )
                except Exception as e:
                    logger.error(f"Error syncing invite {invite.id}: {str(e)}")

            await session.commit()

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

            logger.info(
                f"Discord invites: {len(guild_invites)}, Database invites: {db_invite_count}"
            )

            if (
                abs(len(guild_invites) - db_invite_count) > 10
                or len(guild_invites) < db_invite_count
            ):
                logger.warning("Significant discrepancy in invite counts. Syncing invites...")
                await self.sync_invites()
                db_invite_count = await InviteQueries.get_invite_count(session)
                logger.info(
                    f"After sync - Discord invites: {len(guild_invites)}, Database invites: {db_invite_count}"
                )

            if len(guild_invites) < db_invite_count * 0.5:
                logger.error("Suspicious drop in invite count. Aborting cleanup.")
                return

            deleted_count = 0
            expired_count = 0
            not_found_count = 0
            max_deletions = min(100, max(0, len(guild_invites) - 900))

            if len(guild_invites) > 900:
                logger.info(f"Number of invites ({len(guild_invites)}) exceeds 900. Cleaning up...")

                inactive_threshold = timedelta(days=1)  # Konfigurowalny próg czasowy

                invites_to_check = await InviteQueries.get_invites_for_cleanup(
                    session, limit=max_deletions, inactive_threshold=inactive_threshold
                )

                for db_invite in invites_to_check:
                    if len(guild_invites) <= 900 or deleted_count >= max_deletions:
                        break

                    discord_invite = discord.utils.get(guild_invites, id=db_invite.id)
                    if discord_invite:
                        try:
                            await discord_invite.delete()
                            await InviteQueries.delete_invite(session, db_invite.id)
                            await self.notify_invite_deleted(
                                discord_invite.inviter.id, db_invite.id
                            )
                            deleted_count += 1
                            expired_count += 1
                            guild_invites.remove(discord_invite)
                            # logger.info(f"Deleted expired invite: {db_invite.id}")
                        except Exception as e:
                            logger.error(f"Error deleting invite {db_invite.id}: {str(e)}")
                    else:
                        await InviteQueries.delete_invite(session, db_invite.id)
                        deleted_count += 1
                        not_found_count += 1
                        # logger.info(
                        #     f"Deleted invite from database (not found on Discord): {db_invite.id}"
                        # )

            await session.commit()

            remaining_invites = len(guild_invites)
            donation_channel = self.bot.get_channel(self.bot.config["channels"]["donation"])
            if donation_channel:
                message = (
                    f"Podsumowanie czyszczenia zaproszeń:\n"
                    f"- Usunięto łącznie: {deleted_count} zaproszeń\n"
                    f"  • Wygasłe: {expired_count}\n"
                    f"  • Nieistniejące na Discord: {not_found_count}\n"
                    f"- Pozostało {remaining_invites} aktywnych zaproszeń na serwerze."
                )
                # await donation_channel.send(message)
            else:
                logger.warning("Donation channel not found. Could not send invite cleanup summary.")

            logger.info(
                f"Invite cleanup completed. Deleted {deleted_count} invites (Expired: {expired_count}, Not found: {not_found_count}). Remaining: {remaining_invites}"
            )

    @clean_invites.before_loop
    async def before_clean_invites(self):
        """Ensure guild is set before starting clean_invites task"""
        if not self.guild:
            logger.info("Waiting for guild to be set before starting clean_invites...")
            while not self.guild:
                await asyncio.sleep(1)

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
