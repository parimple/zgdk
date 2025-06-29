"""
On Task Event
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks

from cogs.commands.info.admin_info import remove_premium_role_mod_permissions
from core.interfaces.member_interfaces import IMemberService
from core.repositories import ModerationRepository, NotificationRepository, RoleRepository
from core.services.currency_service import CurrencyService
from utils.role_manager import RoleManager

# Currency constant
CURRENCY_UNIT = CurrencyService.CURRENCY_UNIT
logger = logging.getLogger(__name__)


class OnTaskEvent(commands.Cog):
    """Cog to handle tasks that run periodically."""

    def __init__(self, bot):
        self.bot = bot
        self.role_manager = RoleManager(bot)
        self.check_roles_expiry.start()  # pylint: disable=no-member
        self.notification_channel_id = 1336368306940018739
        # Set default channel notifications to True
        self.bot.force_channel_notifications = True

    @property
    def force_channel_notifications(self):
        """Get global notification setting from bot"""
        return self.bot.force_channel_notifications

    @tasks.loop(minutes=1)
    async def check_roles_expiry(self):
        """Check for expiring roles and remove them - both premium and mute roles"""
        # Informacja o rozpoczęciu będzie logowana tylko jeśli zadanie faktycznie coś zrobi
        log_start = False
        log_completed = False
        changes_made = False

        # 1. Sprawdź wygasłe role wyciszenia (częściej sprawdzane, co minutę)
        mute_role_ids = [role["id"] for role in self.bot.config["mute_roles"]]
        mutes_removed = await self.role_manager.check_expired_roles(
            role_ids=mute_role_ids, notification_handler=self.notify_mute_removal
        )

        # Jeśli usunięto jakieś role wyciszenia, zapisz tę informację i pokaż podsumowanie
        if mutes_removed > 0:
            log_start = True
            log_completed = True
            changes_made = True
            logger.info(f"Removed {mutes_removed} expired mute roles")

        # 2. Co godzinę sprawdź również role premium
        now = datetime.now(timezone.utc)
        hour_mark = now.minute == 0

        if hour_mark:
            premium_notifications_sent = 0
            # Sprawdź wygasające w ciągu 24h role premium dla powiadomień
            expiration_threshold = now + timedelta(hours=24)
            async with self.bot.get_db() as session:
                # Fetch all MemberRole entries that are premium
                role_repo = RoleRepository(session)
                all_premium_member_roles = await role_repo.get_all_premium_roles()

                # Logujemy tylko jeśli znaleziono role premium (i tylko przy godzinowym sprawdzeniu)
                if all_premium_member_roles:
                    log_start = True

                for member_role_db in all_premium_member_roles:
                    # Ensure expiration_date is not None before comparison
                    if member_role_db.expiration_date and now < member_role_db.expiration_date <= expiration_threshold:
                        member = self.bot.guild.get_member(member_role_db.member_id)
                        if not member:
                            logger.debug(
                                f"Member {member_role_db.member_id} not found in cache for premium expiry notification."
                            )
                            continue  # Skip if member not in cache

                        guild_role = self.bot.guild.get_role(member_role_db.role_id)
                        if not guild_role:
                            logger.warning(
                                f"Role ID {member_role_db.role_id} not found on server for premium expiry notification."
                            )
                            continue  # Skip if role not on server

                        if guild_role in member.roles:
                            notification_repo = NotificationRepository(session)
                            notification_log = await notification_repo.get_notification_log(
                                member.id, "premium_role_expiry"
                            )
                            if not notification_log or now - notification_log.sent_at > timedelta(hours=24):
                                # Pass the MemberRole and discord.Role objects to the notification handler
                                await self.notify_premium_expiry(member, member_role_db, guild_role)
                                await notification_repo.add_or_update_notification_log(member.id, "premium_role_expiry")
                                premium_notifications_sent += 1
                                changes_made = True
                await session.commit()

            # Loguj informacje o powiadomieniach tylko jeśli jakieś wysłano
            if premium_notifications_sent > 0:
                log_start = True
                log_completed = True
                logger.info(f"Sent {premium_notifications_sent} premium expiry notifications")

            # Sprawdź i usuń wygasłe role premium
            premium_removed = await self.role_manager.check_expired_roles(
                role_type="premium", notification_handler=self.notify_premium_removal
            )

            # Loguj informacje o usuniętych rolach premium tylko jeśli jakieś usunięto
            if premium_removed > 0:
                log_start = True
                log_completed = True
                changes_made = True
                logger.info(f"Removed {premium_removed} expired premium roles")

        # Logowanie tylko jeśli coś się działo
        if log_start:
            logger.info("Starting check_roles_expiry task")

        if log_completed or changes_made:
            logger.info("Finished check_roles_expiry task")

    async def _send_notification_template(
        self,
        member: discord.Member,
        role_name: str,
        title_prefix: str,
        reason_details: str,
        include_renewal_info: bool = False,
        log_prefix: str = "Notification",
        renewal_action_verb: str = "odnowić",
        renewal_payment_action_prefix: str = "",
    ):
        """Wysyła sformatowane powiadomienie do użytkownika."""
        try:
            if title_prefix:  # If title_prefix is provided, use the "prefix: role_name" structure
                full_message = f"{title_prefix}: {role_name}\n{reason_details}"
            else:  # Otherwise, assume reason_details contains the full main message
                full_message = reason_details

            if include_renewal_info:
                role_price_info = next(
                    (r for r in self.bot.config["premium_roles"] if r["name"] == role_name),
                    None,
                )
                if role_price_info and "price" in role_price_info:
                    price = role_price_info["price"]
                    price_pln = CurrencyService().g_to_pln(price)
                    full_message += (
                        f"\nAby ją {renewal_action_verb}, potrzebujesz {price}{CURRENCY_UNIT} ({price_pln} PLN)."
                    )
                    full_message += (
                        f"\nZasil swoje konto{renewal_payment_action_prefix}: {self.bot.config['donate_url']}"
                    )
                    full_message += "\nWpisując **TYLKO** swoje id w polu - Twój nick."
                else:
                    full_message += "\nSkontaktuj się z administracją w sprawie odnowienia."

            # Replace escaped newlines with actual newlines for sending
            full_message = full_message.replace("\\n", "\n")

            logger.info(
                f"{log_prefix}: Sending notification to {member.display_name} ({member.id}) for role {role_name}."
            )

            await self.role_manager.send_notification(member, full_message)

            id_message = f"```{member.id}```"
            if not self.force_channel_notifications:
                await member.send(id_message)
            else:
                channel = self.bot.get_channel(self.notification_channel_id)
                if channel:
                    await channel.send(id_message)

        except Exception as e:
            logger.error(
                f"{log_prefix}: Error sending notification for role {role_name}: {e}",
                exc_info=True,
            )

    async def notify_premium_expiry(self, member, member_role, role):
        """Notify user about expiring premium membership"""
        current_time = datetime.now(timezone.utc)
        # Check if the role is actually expiring in the future.
        # member_role.expiration_date should be > current_time for this notification.
        if not member_role.expiration_date or member_role.expiration_date <= current_time:
            logger.warning(
                f"notify_premium_expiry called for a role that is not in the future or already expired. Member: {member.id}, Role: {role.id}, Expiration: {member_role.expiration_date}. This should be handled by removal logic."
            )
            # Do not send a confusing "will expire X time ago" message.
            # The check_roles_expiry loop should ideally not call this function in this state.
            return

        expiration_str = discord.utils.format_dt(member_role.expiration_date, "R")
        main_message = f"Twoja rola premium {role.name} wygaśnie {expiration_str}."
        await self._send_notification_template(
            member,
            role.name,
            title_prefix="",  # Empty title_prefix to use main_message directly
            reason_details=main_message,
            include_renewal_info=True,
            log_prefix="Expiry",
            renewal_action_verb="przedłużyć",
            renewal_payment_action_prefix=", aby ją przedłużyć",
        )

    async def notify_premium_removal(self, member, member_role, role):
        """Notify user about removed premium membership"""
        expiration_str = discord.utils.format_dt(member_role.expiration_date, "R")
        main_message = f"Twoja rola premium {role.name} wygasła {expiration_str}."
        await self._send_notification_template(
            member,
            role.name,
            title_prefix="",  # Empty title_prefix to use main_message directly
            reason_details=main_message,
            include_renewal_info=True,
            log_prefix="Removal",
            renewal_action_verb="odnowić",
            renewal_payment_action_prefix=", aby ją odnowić",
        )
        try:
            async with self.bot.get_db() as session:
                await remove_premium_role_mod_permissions(session, self.bot, member.id)
                await session.commit()
                logger.info(
                    "Removed premium role privileges (mod permissions and teams) for %s (%d)",
                    member.display_name,
                    member.id,
                )
        except Exception as e:
            logger.error(f"Error in notify_premium_removal specific logic: {e}", exc_info=True)

    async def notify_mute_removal(self, member, member_role, role):
        """Powiadomienie o automatycznym usunięciu wyciszenia."""
        role_desc = next(
            (r["description"] for r in self.bot.config["mute_roles"] if r["id"] == role.id),
            "",
        )
        if role_desc:
            reason = f"Twoje wyciszenie ({role.name}) wygasło i zostało automatycznie usunięte."
            await self._send_notification_template(
                member,
                role.name,
                title_prefix="Usunięte wyciszenie",
                reason_details=reason,
                include_renewal_info=False,
                log_prefix="MuteRemoval",
            )

            # Log the automatic unmute action to database
            try:
                async with self.bot.get_db() as session:
                    # Mapuj opis roli na typ mute'a
                    mute_type_mapping = {
                        "stream_of": "live",
                        "send_messages_of": "txt",
                        "attach_files_of": "img",  # lub "nick" w zależności od kontekstu
                        "points_of": "rank",
                    }
                    mute_type = mute_type_mapping.get(role_desc, "unknown")

                    # Użyj ID bota jako moderatora dla automatycznych akcji
                    bot_id = self.bot.user.id

                    # Upewnij się, że użytkownicy istnieją w bazie
                    member_service = await self.bot.get_service(IMemberService, session)
                    await member_service.get_or_create_member(member)
                    bot_user = await self.bot.fetch_user(bot_id)
                    await member_service.get_or_create_member(bot_user)

                    # Zapisz automatyczne unmute do logu
                    moderation_repo = ModerationRepository(session)
                    await moderation_repo.log_mute_action(
                        target_user_id=member.id,
                        moderator_id=bot_id,  # Bot jako moderator dla automatycznych akcji
                        action_type="unmute",
                        mute_type=mute_type,
                        duration_seconds=None,
                        reason="Automatyczne usunięcie - wygaśnięcie czasu",
                        channel_id=0,  # Brak kanału dla automatycznych akcji
                    )
                    await session.commit()

                    logger.info(f"Saved automatic unmute to database: user {member.id}, type {mute_type}")
            except Exception as db_error:
                logger.error(
                    f"Error saving automatic unmute to database: {db_error}",
                    exc_info=True,
                )

            # Log the automatic unmute action to the log channel
            await self._log_automatic_unmute_action(member, member_role, role)

    async def notify_audit_role_removal(
        self,
        member: discord.Member,
        discord_role: discord.Role,
        db_expiration_date: Optional[datetime] = None,
        audit_reason_key: str = "niespójności systemowej",
    ):
        """Powiadamia użytkownika o usunięciu roli w wyniku audytu."""
        # Sprawdź czy powiadomienie zostało już wysłane
        async with self.bot.get_db() as session:
            # Sprawdź różne typy powiadomień - zarówno z normalnego systemu jak i audytu
            _recent_notifications = []
            notification_tags_to_check = [
                "premium_role_expiry",  # Powiadomienie o wygasaniu
                "premium_expired",  # Powiadomienie o usunięciu wygasłej roli
                f"audit_removal_{discord_role.name}",  # Powiadomienie z audytu dla tej konkretnej roli
            ]

            notification_repo = NotificationRepository(session)
            for tag in notification_tags_to_check:
                notification_log = await notification_repo.get_notification_log(member.id, tag)
                if notification_log:
                    # Sprawdź czy powiadomienie zostało wysłane w ciągu ostatnich 24 godzin
                    time_since_notification = datetime.now(timezone.utc) - notification_log.sent_at
                    if time_since_notification < timedelta(hours=24):
                        logger.info(
                            f"AuditRemoval: Skipping notification for {member.display_name} ({member.id}) "
                            f"- recent notification found: {tag} sent {time_since_notification} ago"
                        )
                        return

            role_name = discord_role.name
            main_message_body = ""
            include_renewal = False
            local_renewal_payment_action_prefix = ""  # Domyślnie pusty

            if db_expiration_date:
                expiration_str = discord.utils.format_dt(db_expiration_date, "R")
                main_message_body = f"Twoja rola premium {role_name} wygasła {expiration_str} i została usunięta w ramach korekty systemowej."
                include_renewal = True
                local_renewal_payment_action_prefix = ", aby ją odnowić"  # Ustawiamy dla spójności
            else:
                main_message_body = f"Twoja rola premium {role_name} została usunięta z powodu {audit_reason_key}."

            await self._send_notification_template(
                member,
                role_name,  # Nadal potrzebne dla wyszukania ceny w _send_notification_template
                title_prefix="",  # Kluczowa zmiana: używamy main_message_body jako głównej treści
                reason_details=main_message_body,
                include_renewal_info=include_renewal,
                log_prefix="AuditRemoval",
                # renewal_action_verb domyślnie jest "odnowić", co jest tutaj odpowiednie
                renewal_payment_action_prefix=local_renewal_payment_action_prefix,
            )

            # Zapisz że powiadomienie zostało wysłane, aby uniknąć duplikatów w przyszłości
            await notification_repo.add_or_update_notification_log(member.id, f"audit_removal_{role_name}")
            await session.commit()

    @check_roles_expiry.before_loop
    async def before_tasks(self):
        """Wait for bot to be ready and guild to be set before starting tasks"""
        logger.info("Waiting for bot to be ready before starting tasks")
        await self.bot.wait_until_ready()

        # Wait for guild to be set
        while self.bot.guild is None:
            logger.info("Waiting for guild to be set...")
            await asyncio.sleep(1)

        logger.info("Bot is ready and guild is set, starting tasks")

    @commands.command()
    @commands.is_owner()
    async def check_expired_roles(self, ctx):
        """Command to check and display expired roles"""
        now = datetime.now(timezone.utc)
        async with self.bot.get_db() as session:
            role_repo = RoleRepository(session)
            expired_roles = await role_repo.get_expired_roles(now)
            if not expired_roles:
                await ctx.send("No expired roles found.")
                return

            embed = discord.Embed(title="Expired Roles", color=discord.Color.orange())
            for mr in expired_roles:
                role_name = mr.role.name if mr.role else "Unknown Role"
                member = self.bot.guild.get_member(mr.member_id)
                member_name = member.display_name if member else f"Unknown Member (ID: {mr.member_id})"
                expiry_formatted = discord.utils.format_dt(mr.expiration_date, "F")
                embed.add_field(
                    name=f"Role: {role_name} for {member_name}",
                    value=f"Role ID: {mr.role_id}\\nMember ID: {mr.member_id}\\nExpired: {expiry_formatted}",
                    inline=False,
                )
                if len(embed.fields) == 25:
                    await ctx.send(embed=embed)
                    embed = discord.Embed(title="Expired Roles (Cont.)", color=discord.Color.orange())

            if embed.fields:
                await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def check_premium_role(self, ctx, member: discord.Member):
        """Command to check premium roles for a specific member"""
        async with self.bot.get_db() as session:
            role_repo = RoleRepository(session)
            premium_roles = await role_repo.get_member_premium_roles(member.id)
            current_time = datetime.now(timezone.utc)
            if not premium_roles:
                await ctx.send(f"Użytkownik {member.display_name} nie ma żadnych ról premium.")
                return

            for role in premium_roles:
                await ctx.send(
                    f"Role ID: {role.role_id}\n"
                    f"Expiration: {role.expiration_date}\n"
                    f"Current time: {current_time}\n"
                    f"Is expired: {role.expiration_date <= current_time}"
                )

    @commands.command()
    @commands.is_owner()
    async def check_mute_roles(self, ctx, member: Optional[discord.Member] = None):
        """Command to check mute roles for a specific member or all mute roles"""
        now = datetime.now(timezone.utc)
        mute_role_ids = [role["id"] for role in self.bot.config["mute_roles"]]

        async with self.bot.get_db() as session:
            if member:
                # Sprawdź tylko wyciszenia konkretnego użytkownika
                role_repo = RoleRepository(session)
                member_roles = await role_repo.get_member_roles(member.id)
                mute_roles = [role for role in member_roles if role.role_id in mute_role_ids]

                if not mute_roles:
                    await ctx.send(f"Użytkownik {member.display_name} nie ma żadnych wyciszeń.")
                    return

                for role in mute_roles:
                    expiry_status = "aktywne" if role.expiration_date > now else "wygasłe"
                    expiration_date = (
                        f"wygasa {discord.utils.format_dt(role.expiration_date, 'R')}"
                        if role.expiration_date
                        else "stałe"
                    )

                    await ctx.send(
                        f"Wyciszenie {self.bot.guild.get_role(role.role_id).name} dla {member.display_name}:\n"
                        f"Status: {expiry_status}\n"
                        f"Czas: {expiration_date}"
                    )
            else:
                # Sprawdź wszystkie wyciszenia
                all_mute_roles = []
                role_repo = RoleRepository(session)
                for role_id in mute_role_ids:
                    role_members = await role_repo.get_role_members(role_id)
                    all_mute_roles.extend(role_members)

                if not all_mute_roles:
                    await ctx.send("Nie znaleziono żadnych aktywnych wyciszeń.")
                    return

                await ctx.send(f"Znaleziono {len(all_mute_roles)} aktywnych wyciszeń:")

                for i, member_role in enumerate(all_mute_roles[:10], 1):
                    member_obj = self.bot.guild.get_member(member_role.member_id)
                    member_name = member_obj.display_name if member_obj else f"ID: {member_role.member_id}"
                    role_name = self.bot.guild.get_role(member_role.role_id).name
                    expiration_date = (
                        f"wygasa {discord.utils.format_dt(member_role.expiration_date, 'R')}"
                        if member_role.expiration_date
                        else "stałe"
                    )

                    await ctx.send(f"{i}. {member_name}: {role_name} ({expiration_date})")

                if len(all_mute_roles) > 10:
                    await ctx.send(f"... i {len(all_mute_roles) - 10} więcej.")

    @commands.command()
    @commands.is_owner()
    async def force_check_expired_roles(self, ctx):
        """Wymusza sprawdzenie i usunięcie wygasłych ról (premium i wyciszenia)"""
        # Sprawdź wygasłe role wyciszenia
        mute_role_ids = [role["id"] for role in self.bot.config["mute_roles"]]
        mutes_removed = await self.role_manager.check_expired_roles(
            role_ids=mute_role_ids, notification_handler=self.notify_mute_removal
        )

        # Sprawdź wygasłe role premium
        premium_removed = await self.role_manager.check_expired_roles(
            role_type="premium", notification_handler=self.notify_premium_removal
        )

        await ctx.send(
            f"Sprawdzono i usunięto wygasłe role:\n- Premium: {premium_removed}\n- Wyciszenia: {mutes_removed}"
        )

    @tasks.loop(hours=12)  # Uruchamiaj co 12 godzin
    async def audit_discord_premium_roles(self):
        """Audytuje role premium na Discord i porównuje z bazą danych."""
        logger.info("Starting premium roles audit...")
        guild = self.bot.guild
        if not guild:
            logger.error("Audit: Guild not found. Skipping audit.")
            return

        # Odczytaj ID ról premium z konfiguracji
        audit_config = self.bot.config.get("audit_settings", {})
        premium_role_ids = audit_config.get("premium_role_ids_for_audit", [])

        if not premium_role_ids:
            logger.warning("Audit: No premium_role_ids_for_audit defined in config. Skipping audit.")
            return

        actions_taken_summary = []

        for role_id in premium_role_ids:
            discord_role = guild.get_role(role_id)
            if not discord_role:
                logger.warning(f"Audit: Role ID {role_id} not found on server. Skipping.")
                continue

            logger.info(f"Audit: Checking role '{discord_role.name}' (ID: {discord_role.id})")
            members_with_role = discord_role.members

            if not members_with_role:
                logger.info(f"Audit: No members found with role '{discord_role.name}'.")
                continue

            for member in members_with_role:
                logger.debug(
                    f"Audit: Checking member {member.display_name} (ID: {member.id}) for role '{discord_role.name}'."
                )
                async with self.bot.get_db() as session:
                    try:
                        role_repo = RoleRepository(session)
                        db_member_role_entry = await role_repo.get_member_role(member.id, discord_role.id)

                        if db_member_role_entry is None:
                            logger.warning(
                                f"Audit: Member {member.display_name} (ID: {member.id}) has role '{discord_role.name}' on Discord, but no DB entry. Removing from Discord."
                            )
                            try:
                                await member.remove_roles(
                                    discord_role,
                                    reason="Audit: Brak wpisu w bazie danych",
                                )
                                # Powiadomienie użytkownika
                                await self.notify_audit_role_removal(
                                    member,
                                    discord_role,
                                    audit_reason_key="braku wpisu w bazie danych",
                                )
                                # Usuń też powiązane uprawnienia na wszelki wypadek
                                await remove_premium_role_mod_permissions(session, self.bot, member.id)
                                await session.commit()  # Commit po usunięciu uprawnień

                                actions_taken_summary.append(
                                    f"Usunięto rolę '{discord_role.name}' od {member.mention} (brak w DB)."
                                )
                                logger.info(
                                    f"Audit: Removed role '{discord_role.name}' from {member.display_name} (no DB entry)."
                                )
                            except discord.Forbidden:
                                logger.error(
                                    f"Audit: Forbidden to remove role '{discord_role.name}' from {member.display_name}."
                                )
                            except Exception as e_remove:
                                logger.error(
                                    f"Audit: Error removing role '{discord_role.name}' from {member.display_name}: {e_remove}"
                                )

                        elif (
                            db_member_role_entry.expiration_date
                            and db_member_role_entry.expiration_date <= datetime.now(timezone.utc)
                        ):
                            logger.warning(
                                f"Audit: Member {member.display_name} (ID: {member.id}) has role '{discord_role.name}' on Discord, but it's expired in DB (Exp: {db_member_role_entry.expiration_date}). Removing."
                            )
                            try:
                                await member.remove_roles(
                                    discord_role,
                                    reason="Audit: Rola wygasła wg bazy danych",
                                )
                                await remove_premium_role_mod_permissions(session, self.bot, member.id)
                                await role_repo.delete_member_role(member.id, discord_role.id)
                                await session.commit()
                                # Powiadomienie użytkownika
                                await self.notify_audit_role_removal(
                                    member,
                                    discord_role,
                                    db_expiration_date=db_member_role_entry.expiration_date,
                                    audit_reason_key="wygaśnięcia w bazie danych",
                                )

                                actions_taken_summary.append(
                                    f"Usunięto wygasłą rolę '{discord_role.name}' od {member.mention}."
                                )
                                logger.info(
                                    f"Audit: Corrected expired role '{discord_role.name}' for {member.display_name}."
                                )
                            except discord.Forbidden:
                                logger.error(
                                    f"Audit: Forbidden to remove role or manage permissions for {member.display_name} during expiry correction."
                                )
                            except Exception as e_correct:
                                logger.error(
                                    f"Audit: Error correcting expired role for {member.display_name}: {e_correct}"
                                )
                                await session.rollback()
                        # else: Role in DB is active or permanent, all good. No action needed.

                    except Exception as e_session:
                        logger.error(
                            f"Audit: Error processing member {member.display_name} for role '{discord_role.name}': {e_session}",
                            exc_info=True,
                        )
                        await session.rollback()

        if actions_taken_summary:
            summary_message = "Przeprowadzono audyt ról premium. Wykonane akcje:\n- " + "\n- ".join(
                actions_taken_summary
            )
            # Send summary to admin channel if configured
            admin_channel_id = self.bot.config.get("channels", {}).get("admin_logs")
            if admin_channel_id:
                admin_channel = self.bot.get_channel(admin_channel_id)
                if admin_channel:
                    embed = discord.Embed(
                        title="📊 Audit rang Premium",
                        description=summary_message[:4000],  # Discord limit
                        color=discord.Color.blue(),
                        timestamp=datetime.now(timezone.utc),
                    )
                    embed.set_footer(text=f"Akcje: {len(actions_taken_summary)}")
                    await admin_channel.send(embed=embed)

            logger.info(f"Premium roles audit completed. Actions taken: {len(actions_taken_summary)}")
            logger.info("Audit Summary:\n" + "\n".join(actions_taken_summary))

        else:
            logger.info("Premium roles audit completed. No inconsistencies found or actions taken.")

    @audit_discord_premium_roles.before_loop
    async def before_audit_premium_roles(self):
        """Wait for bot to be ready and guild to be set before starting audit task"""
        logger.info("Waiting for bot to be ready before starting premium roles audit task")
        await self.bot.wait_until_ready()
        while self.bot.guild is None:
            logger.info("Audit: Waiting for guild to be set...")
            await asyncio.sleep(5)  # Czekaj nieco dłużej, bo to rzadsze zadanie
        logger.info("Audit: Bot is ready and guild is set, audit task will start on schedule.")

    async def _log_automatic_unmute_action(self, member, member_role, role):
        """Loguje automatyczne odciszenie na kanale logów.

        :param member: Użytkownik, któremu wygasło wyciszenie
        :type member: discord.Member
        :param member_role: Obiekt roli z bazy danych
        :type member_role: MemberRole
        :param role: Rola Discord, która została usunięta
        :type role: discord.Role
        """
        try:
            # Pobierz kanał logów dla unmute'ów z konfiguracji
            log_channel_id = self.bot.config.get("channels", {}).get("unmute_logs")

            if not log_channel_id:
                logger.warning("Brak konfiguracji kanału logów odciszeń (unmute_logs) dla automatycznego unmute")
                return

            log_channel = self.bot.get_channel(log_channel_id)
            if not log_channel:
                logger.error(f"Nie można znaleźć kanału logów odciszeń o ID: {log_channel_id}")
                return

            # Znajdź typ wyciszenia na podstawie konfiguracji
            mute_type_info = next(
                (r for r in self.bot.config["mute_roles"] if r["id"] == role.id),
                {"description": "unknown", "name": "Nieznane"},
            )

            # Mapowanie opisów na czytelne nazwy
            mute_type_display_mapping = {
                "stream_of": "STREAM",
                "send_messages_of": "WIADOMOŚCI",
                "attach_files_of": "PLIKI/OBRAZY",
                "points_of": "RANKING",
            }

            mute_type_display = mute_type_display_mapping.get(
                mute_type_info["description"], mute_type_info["description"].upper()
            )

            # Stwórz embed z informacjami o automatycznym odciszeniu
            embed = discord.Embed(
                title=f"🔓 AUTOMATYCZNE ODCISZENIE - {mute_type_display}",
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )

            embed.add_field(
                name="👤 Użytkownik",
                value=f"{member.mention}\n`{member.name}` (`{member.id}`)",
                inline=True,
            )

            embed.add_field(
                name="🤖 Moderator",
                value="**System** (automatyczne)\n`Wygaśnięcie czasu`",
                inline=True,
            )

            # Informacja o wygaśnięciu
            if member_role.expiration_date:
                expiry_str = discord.utils.format_dt(member_role.expiration_date, "f")
                embed.add_field(name="⏰ Wygasło", value=expiry_str, inline=True)

            embed.add_field(
                name="📋 Typ wyciszenia",
                value=f"`{mute_type_info['description']}` - {mute_type_display}",
                inline=False,
            )

            embed.add_field(
                name="🔄 Sposób odciszenia",
                value="Automatyczne sprawdzenie systemu",
                inline=False,
            )

            # Dodaj thumbnail z avatarem użytkownika
            embed.set_thumbnail(url=member.display_avatar.url)

            # Wyślij log na kanał
            await log_channel.send(embed=embed)

            logger.info(
                f"Logged automatic unmute action for user {member.id} "
                f"({mute_type_info['description']}) to channel {log_channel_id}"
            )

        except Exception as e:
            logger.error(f"Error logging automatic unmute action: {e}", exc_info=True)


async def setup(bot: commands.Bot):
    """Setup function for OnTaskEvent cog."""
    cog = OnTaskEvent(bot)
    await bot.add_cog(cog)
    cog.audit_discord_premium_roles.start()  # Uruchomienie nowej pętli
