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

from datasources.queries import (
    ChannelPermissionQueries,
    InviteQueries,
    MemberQueries,
    NotificationLogQueries,
    RoleQueries,
)

logger = logging.getLogger(__name__)


class OnMemberJoinEvent(commands.Cog):
    """Class for handling the event when a member joins the Discord server."""

    def __init__(self, bot):
        self.bot = bot
        self.guild = None
        self.invites = {}
        self.welcome_channel = None
        # Dodaj flagę - domyślnie True dla powiadomień na kanał (tymczasowo)
        self.bot.force_channel_notifications = (
            True  # Jeśli True - wysyła na kanał, False - wysyła na DM
        )
        # Metryki dla przywracania uprawnień głosowych
        self.voice_permissions_restored = 0
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

        logger.info(f"Getting welcome channel with ID: {welcome_channel_id}")

        self.welcome_channel = self.bot.get_channel(welcome_channel_id)

        logger.info(f"Welcome channel set: {self.welcome_channel}")

        if not self.welcome_channel:
            logger.error(f"Failed to get welcome channel with ID {welcome_channel_id}")

    async def restore_mute_roles(self, member):
        """
        Przywraca role wyciszenia użytkownikowi, który wrócił na serwer.

        Ta funkcja sprawdza w bazie danych, czy użytkownik miał przypisane role wyciszenia
        przed wyjściem z serwera, i jeśli tak, przywraca te role.

        :param member: Członek serwera, któremu trzeba przywrócić role
        :type member: discord.Member
        """
        logger.info(
            f"Sprawdzanie i przywracanie ról wyciszenia dla {member} ({member.id})"
        )

        try:
            # Pobierz konfigurację ról wyciszenia
            mute_roles_config = self.bot.config["mute_roles"]
            mute_role_ids = [role["id"] for role in mute_roles_config]

            # Pobierz ID kanału do powiadomień (używany gdy force_channel_notifications=True)
            notification_channel_id = self.bot.config["channels"]["mute_notifications"]
            notification_channel = self.bot.get_channel(notification_channel_id)

            # Flaga do sprawdzenia, czy użytkownik ma NICK mute
            has_nick_mute = False

            async with self.bot.get_db() as session:
                # Sprawdź, czy użytkownik ma jakiekolwiek role wyciszenia w bazie danych
                member_roles = await RoleQueries.get_member_roles(session, member.id)

                # Filtruj tylko role wyciszenia
                mute_member_roles = [
                    role for role in member_roles if role.role_id in mute_role_ids
                ]

                if not mute_member_roles:
                    logger.info(
                        f"Użytkownik {member.id} nie ma żadnych ról wyciszenia do przywrócenia"
                    )
                    return

                # Znajdź ID roli dla mutenick (usuń stary kod identyfikujący przez attach_files_off)
                nick_mute_role_ids = []
                for role_config in mute_roles_config:
                    if role_config["description"] == "attach_files_off":
                        nick_mute_role_ids.append(role_config["id"])

                roles_restored = 0

                # Przywróć każdą rolę wyciszenia
                for member_role in mute_member_roles:
                    role_id = member_role.role_id
                    mute_role = discord.Object(id=role_id)

                    # Znajdź opis roli do logowania
                    role_desc = next(
                        (
                            role["description"]
                            for role in mute_roles_config
                            if role["id"] == role_id
                        ),
                        "unknown",
                    )

                    # Sprawdź, czy to NICK mute
                    if role_id in nick_mute_role_ids:
                        has_nick_mute = True

                    # Sprawdź, czy rola jest nadal ważna (jeśli ma datę wygaśnięcia)
                    if (
                        member_role.expiration_date
                        and member_role.expiration_date < datetime.now(timezone.utc)
                    ):
                        logger.info(
                            f"Rola wyciszenia {role_id} ({role_desc}) dla {member.id} wygasła, nie przywracam"
                        )
                        # Usuń wygasłą rolę z bazy danych
                        await RoleQueries.delete_member_role(
                            session, member.id, role_id
                        )
                        continue

                    # Przywróć rolę
                    try:
                        await member.add_roles(
                            mute_role,
                            reason="Przywrócenie wyciszenia po powrocie na serwer",
                        )
                        roles_restored += 1
                        logger.info(
                            f"Przywrócono rolę wyciszenia {role_id} ({role_desc}) dla {member.id}"
                        )

                        # Znajdź właściwą nazwę roli
                        role_name = next(
                            (
                                role["name"]
                                for role in mute_roles_config
                                if role["id"] == role_id
                            ),
                            "⚠️",
                        )

                        # Przygotuj treść wiadomości
                        message_content = f"Przywrócono wyciszenie {role_name} dla {member.mention} po powrocie na serwer."

                        # Wybierz tryb powiadomienia w zależności od flagi
                        if self.bot.force_channel_notifications:
                            # Tryb powiadomienia na kanał
                            if notification_channel:
                                try:
                                    await notification_channel.send(
                                        message_content,
                                        allowed_mentions=AllowedMentions(users=False),
                                    )
                                except discord.HTTPException as e:
                                    logger.error(
                                        f"Błąd podczas wysyłania powiadomienia na kanał {notification_channel_id}: {e}"
                                    )
                        else:
                            # Tryb powiadomienia na DM
                            try:
                                await member.send(
                                    f"Twoje wyciszenie {role_name} zostało przywrócone po ponownym dołączeniu do serwera."
                                )
                                logger.info(
                                    f"Wysłano DM do {member.id} o przywróceniu wyciszenia {role_id}"
                                )
                            except discord.Forbidden:
                                logger.error(
                                    f"Nie można wysłać DM do {member.id}, użytkownik ma zablokowane wiadomości"
                                )
                                # Jeśli nie można wysłać DM, spróbuj wysłać na kanał
                                if notification_channel:
                                    await notification_channel.send(
                                        f"[Nie udało się wysłać DM] {message_content}",
                                        allowed_mentions=AllowedMentions(users=False),
                                    )
                            except discord.HTTPException as e:
                                logger.error(
                                    f"Błąd podczas wysyłania DM do {member.id}: {e}"
                                )
                    except discord.Forbidden:
                        logger.error(
                            f"Brak uprawnień do przywrócenia roli {role_id} dla {member.id}"
                        )
                    except discord.HTTPException as e:
                        logger.error(
                            f"Błąd Discord API podczas przywracania roli {role_id} dla {member.id}: {e}"
                        )

                await session.commit()

                # Jeśli przywrócono role i ma mutenick, zmień nazwę użytkownika
                if roles_restored > 0 and has_nick_mute:
                    try:
                        # Pobierz domyślny nickname z konfiguracji
                        default_nick = self.bot.config.get(
                            "default_mute_nickname", "random"
                        )
                        await member.edit(
                            nick=default_nick,
                            reason="Przywrócenie mutenick po powrocie na serwer",
                        )
                        logger.info(
                            f"Zmieniono nick użytkownika {member.id} na {default_nick} po przywróceniu mutenick"
                        )
                    except discord.Forbidden:
                        logger.warning(
                            f"Nie mogę zmienić nicku użytkownika {member.id} po przywróceniu mutenick"
                        )
                    except Exception as e:
                        logger.error(
                            f"Błąd podczas zmiany nicku użytkownika {member.id} po przywróceniu mutenick: {e}"
                        )

                if roles_restored > 0:
                    logger.info(
                        f"Przywrócono {roles_restored} ról wyciszenia dla {member.id}"
                    )

        except Exception as e:
            logger.error(
                f"Błąd podczas przywracania ról wyciszenia dla {member.id}: {e}",
                exc_info=True,
            )

    @commands.command()
    @commands.is_owner()
    async def toggle_mute_notifications(self, ctx, mode: str = None):
        """
        Przełącza tryb powiadomień o przywróconych wyciszeniach.

        :param ctx: Kontekst komendy
        :param mode: Tryb powiadomień: 'channel' lub 'dm'. Jeśli nie podano, przełącza między trybami.
        """
        if mode:
            if mode.lower() in ["channel", "kanał", "kanal"]:
                self.bot.force_channel_notifications = True
                status = "kanał"
            elif mode.lower() in ["dm", "pm", "private"]:
                self.bot.force_channel_notifications = False
                status = "DM"
            else:
                await ctx.send(
                    "Nieprawidłowy tryb. Dostępne opcje: 'channel' lub 'dm'."
                )
                return
        else:
            # Przełącz między trybami
            self.bot.force_channel_notifications = (
                not self.bot.force_channel_notifications
            )
            status = "kanał" if self.bot.force_channel_notifications else "DM"

        await ctx.send(
            f"Powiadomienia o przywróconych wyciszeniach będą teraz wysyłane na {status}."
        )
        logger.info(f"Zmieniono tryb powiadomień o wyciszeniach na: {status}")

    @property
    def force_channel_notifications(self):
        """Get global notification setting from bot"""
        return self.bot.force_channel_notifications

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

        # Przywróć role wyciszenia, jeśli były przypisane wcześniej
        await self.restore_mute_roles(member)

        # Przywróć uprawnienia głosowe, jeśli były przypisane wcześniej
        await self.restore_voice_permissions(member)

        # Check if we have invites dictionary initialized
        if not self.invites:
            logger.warning("Invites dictionary is empty, initializing...")
            self.invites = {
                invite.id: invite for invite in await member.guild.invites()
            }

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
                    logger.debug(
                        f"New invite found: {invite_id} (uses: {new_invite.uses})"
                    )

            # Handle the case when no invite was identified
            if used_invite is None:
                logger.info(
                    f"No invite identified for member {member}, processing as unknown"
                )
                await self.process_unknown_invite(member)

            # Update the invites dictionary
            self.invites = new_invites_dict

        except Exception as e:
            logger.error(
                f"Error processing member join for {member}: {str(e)}", exc_info=True
            )
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
                logger.error(
                    f"Error processing invite for member {member.id}: {str(e)}"
                )
                await session.rollback()

        # Check if welcome_channel is None and try to get it again
        if self.welcome_channel is None:
            self.welcome_channel = self.bot.get_channel(
                self.bot.channels.get("on_join")
            )
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

    async def process_unknown_invite(self, member: discord.Member):
        """Process member join when invite is unknown"""
        logger.info(
            f"No invite identified for member {member.display_name}, processing as unknown"
        )

        # Bezpieczne sprawdzenie self.guild i self.guild.vanity_url_code
        vanity_code = "nieznany"
        if (
            self.guild
            and hasattr(self.guild, "vanity_url_code")
            and self.guild.vanity_url_code
        ):
            vanity_code = self.guild.vanity_url_code
        elif not self.guild:
            logger.warning(
                "process_unknown_invite: self.guild is None, cannot get vanity URL."
            )
        elif not hasattr(self.guild, "vanity_url_code"):
            logger.warning(
                "process_unknown_invite: self.guild has no attribute 'vanity_url_code'."
            )

        embed_data = {
            "title": "Dołączenie bez zaproszenia (lub nieznane)",
            "description": f"Użytkownik {member.mention} ({member.id}) dołączył do serwera.",
            "color": discord.Color.orange(),
            "fields": [
                (
                    "Czas dołączenia",
                    discord.utils.format_dt(datetime.now(timezone.utc), "F"),
                    False,
                ),
                (
                    "Prawdopodobny powód",
                    "Użyto linku vanity lub bezpośredniego dołączenia",
                    False,
                ),
                ("Vanity URL", f"Kod: {vanity_code}", False),
            ],
            "thumbnail_url": member.display_avatar.url,
        }

        async with self.bot.get_db() as session:
            try:
                # First ensure guild exists in members table
                guild_id = self.bot.guild_id
                await MemberQueries.get_or_add_member(session, guild_id)
                await session.flush()

                # Then add the new member
                await MemberQueries.get_or_add_member(
                    session,
                    member.id,
                    first_inviter_id=guild_id,  # Use guild_id as inviter for unknown invites
                    joined_at=member.joined_at,
                )
                await session.commit()

                # Check if welcome_channel is None and try to get it again
                if self.welcome_channel is None:
                    self.welcome_channel = self.bot.get_channel(
                        self.bot.channels.get("on_join")
                    )
                    logger.info(f"Re-fetched welcome channel: {self.welcome_channel}")

                if self.welcome_channel:
                    await self.welcome_channel.send(
                        f"{member.mention} {member.display_name} zaproszony przez {self.bot.user.mention} "
                        f"Kod: {self.guild.vanity_url_code or 'nieznany'}",
                        allowed_mentions=AllowedMentions(users=False),
                    )
                else:
                    logger.error(
                        f"Welcome channel is still None, could not send welcome message for {member}"
                    )

            except Exception as e:
                logger.error(
                    "Error processing member join for %s: %s",
                    member.display_name,
                    str(e),
                )
                await session.rollback()
                raise

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
                logger.error(
                    f"Error deleting invite {invite.id} from database: {str(e)}"
                )
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
            logger.warning(
                "Received empty list of guild invites. Skipping cleanup process."
            )
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
                logger.warning(
                    "Significant discrepancy in invite counts. Syncing invites..."
                )
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
                logger.info(
                    f"Number of invites ({len(guild_invites)}) exceeds 900. Cleaning up..."
                )

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
                            logger.error(
                                f"Error deleting invite {db_invite.id}: {str(e)}"
                            )
                    else:
                        await InviteQueries.delete_invite(session, db_invite.id)
                        deleted_count += 1
                        not_found_count += 1
                        # logger.info(
                        #     f"Deleted invite from database (not found on Discord): {db_invite.id}"
                        # )

            await session.commit()

            remaining_invites = len(guild_invites)
            donation_channel = self.bot.get_channel(
                self.bot.config["channels"]["donation"]
            )
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
                logger.warning(
                    "Donation channel not found. Could not send invite cleanup summary."
                )

            logger.info(
                f"Invite cleanup completed. Deleted {deleted_count} invites (Expired: {expired_count}, Not found: {not_found_count}). Remaining: {remaining_invites}"
            )

    @clean_invites.before_loop
    async def before_clean_invites(self):
        """Ensure the cog is ready before starting the clean_invites task"""
        logger.info("Waiting for on_member_join cog to be ready...")
        while self.guild is None:
            logger.info("Guild not set yet, waiting...")
            await asyncio.sleep(1)
        logger.info("On_member_join cog is ready, starting clean_invites task")

    async def notify_invite_deleted(self, user_id: int, invite_id: str):
        """
        Notify user that their invite was deleted

        :param user_id: User ID who created the invite
        :param invite_id: Invite ID that was deleted
        """
        try:
            # Get the member
            member = self.guild.get_member(user_id)
            if not member:
                logger.warning(
                    f"Member {user_id} not found, cannot notify about deleted invite"
                )
                return

            # Send notification
            await member.send(
                f"Twoje zaproszenie `{invite_id}` zostało usunięte z powodu braku użycia przez ponad 30 dni."
            )
            logger.info(f"Notified {member} about deleted invite {invite_id}")

        except Exception as e:
            logger.error(
                f"Error notifying user {user_id} about deleted invite {invite_id}: {e}"
            )

    async def restore_voice_permissions(self, member):
        """
        Przywraca uprawnienia głosowe użytkownikowi, który wrócił na serwer.

        Sprawdza w bazie danych wszystkie uprawnienia gdzie użytkownik jest targetem,
        a następnie aplikuje je na kanałach gdzie właściciele są aktualnie obecni.
        """
        logger.info(
            f"Sprawdzanie uprawnień głosowych dla {member.display_name} ({member.id})"
        )

        try:
            async with self.bot.get_db() as session:
                # Pobierz wszystkie uprawnienia gdzie ten użytkownik jest targetem
                target_permissions = (
                    await ChannelPermissionQueries.get_permissions_for_target(
                        session, member.id
                    )
                )

                if not target_permissions:
                    logger.info(
                        f"Brak zapisanych uprawnień głosowych dla {member.display_name}"
                    )
                    return

                logger.info(
                    f"Znaleziono {len(target_permissions)} zapisanych uprawnień głosowych dla {member.display_name}"
                )

                permissions_applied = 0

                # Dla każdego uprawnienia sprawdź czy właściciel jest w kanale głosowym
                for permission in target_permissions:
                    owner = self.guild.get_member(permission.member_id)
                    if not owner:
                        continue  # Właściciel już nie jest na serwerze

                    # Sprawdź czy właściciel jest w jakimś kanale głosowym i ma priority_speaker
                    if not owner.voice or not owner.voice.channel:
                        continue  # Właściciel nie jest w kanale głosowym

                    channel = owner.voice.channel

                    # Sprawdź czy właściciel ma uprawnienia priority_speaker w tym kanale
                    owner_perms = channel.overwrites_for(owner)
                    if not (owner_perms and owner_perms.priority_speaker):
                        continue  # Właściciel nie jest właścicielem tego kanału

                    # Konwertuj uprawnienia z bazy na Discord PermissionOverwrite
                    allow_perms = discord.Permissions(
                        permission.allow_permissions_value
                    )
                    deny_perms = discord.Permissions(permission.deny_permissions_value)
                    overwrite = discord.PermissionOverwrite.from_pair(
                        allow_perms, deny_perms
                    )

                    # Pobierz aktualne uprawnienia użytkownika w kanale
                    current_member_perms = channel.overwrites_for(member)
                    if current_member_perms:
                        # Scal z istniejącymi uprawnieniami
                        for perm_name, value in overwrite._values.items():
                            if value is not None:
                                setattr(current_member_perms, perm_name, value)
                        await channel.set_permissions(
                            member, overwrite=current_member_perms
                        )
                    else:
                        # Ustaw nowe uprawnienia
                        await channel.set_permissions(member, overwrite=overwrite)

                    permissions_applied += 1
                    self.voice_permissions_restored += 1
                    logger.info(
                        f"Przywrócono uprawnienia głosowe dla {member.display_name} w kanale {channel.name} "
                        f"(właściciel: {owner.display_name}, allow: {permission.allow_permissions_value}, "
                        f"deny: {permission.deny_permissions_value})"
                    )

                if permissions_applied > 0:
                    logger.info(
                        f"Przywrócono łącznie {permissions_applied} uprawnień głosowych dla {member.display_name}"
                    )

        except Exception as e:
            logger.error(
                f"Błąd podczas przywracania uprawnień głosowych dla {member.id}: {str(e)}"
            )


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnMemberJoinEvent(bot))
