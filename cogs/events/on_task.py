"""
On Task Event
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands, tasks

from cogs.commands.info import remove_premium_role_mod_permissions
from datasources.queries import ChannelPermissionQueries, NotificationLogQueries, RoleQueries
from utils.currency import CURRENCY_UNIT, g_to_pln
from utils.role_manager import RoleManager

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
        logger.info("Starting check_roles_expiry task")

        # 1. Sprawdź wygasłe role wyciszenia (częściej sprawdzane, co minutę)
        mute_role_ids = [role["id"] for role in self.bot.config["mute_roles"]]
        mutes_removed = await self.role_manager.check_expired_roles(
            role_ids=mute_role_ids, notification_handler=self.notify_mute_removal
        )

        # 2. Co godzinę sprawdź również role premium
        now = datetime.now(timezone.utc)
        hour_mark = now.minute == 0

        if hour_mark:
            # Sprawdź wygasające w ciągu 24h role premium dla powiadomień
            expiration_threshold = now + timedelta(hours=24)
            async with self.bot.get_db() as session:
                expiring_roles = await RoleQueries.get_member_premium_roles(session)
                logger.info("Found %d premium roles", len(expiring_roles))
                for member_role, role in expiring_roles:
                    if now < member_role.expiration_date <= expiration_threshold:
                        member = self.bot.guild.get_member(member_role.member_id)
                        if member:
                            guild_role = self.bot.guild.get_role(role.id)
                            if guild_role and guild_role in member.roles:
                                notification_log = (
                                    await NotificationLogQueries.get_notification_log(
                                        session, member.id, "premium_role_expiry"
                                    )
                                )
                                if (
                                    not notification_log
                                    or now - notification_log.sent_at > timedelta(hours=24)
                                ):
                                    await self.notify_premium_expiry(member, member_role, role)
                                    await NotificationLogQueries.add_or_update_notification_log(
                                        session, member.id, "premium_role_expiry"
                                    )
                await session.commit()

            # Sprawdź i usuń wygasłe role premium
            premium_removed = await self.role_manager.check_expired_roles(
                role_type="premium", notification_handler=self.notify_premium_removal
            )

            logger.info(f"Removed {premium_removed} expired premium roles")

        logger.info(f"Removed {mutes_removed} expired mute roles")
        logger.info("Finished check_roles_expiry task")

    async def notify_premium_expiry(self, member, member_role, role):
        """Notify user about expiring premium membership"""
        try:
            expiration_date = member_role.expiration_date
            expiration_str = discord.utils.format_dt(expiration_date, "R")

            role_price = next(
                (r["price"] for r in self.bot.config["premium_roles"] if r["name"] == role.name),
                None,
            )

            if role_price is not None:
                price_pln = g_to_pln(role_price)
                price_message = f"Aby przedłużyć tę rangę, potrzebujesz {role_price}{CURRENCY_UNIT} ({price_pln} PLN)."
            else:
                price_message = (
                    "Skontaktuj się z administracją, aby uzyskać informacje o cenie odnowienia."
                )

            logger.info("Sending expiry notification to %s (%d)", member.display_name, member.id)

            message = (
                f"Twoja rola premium {role.name} wygaśnie {expiration_str}. \n"
                f"{price_message}\n"
                f"Zasil swoje konto, aby ją przedłużyć: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            id_message = f"```{member.id}```"

            # Użyj RoleManager do wysyłania powiadomień
            await self.role_manager.send_notification(member, message)

            # ID wysyłamy osobno
            if not self.force_channel_notifications:
                await member.send(id_message)
            else:
                channel = self.bot.get_channel(self.notification_channel_id)
                if channel:
                    await channel.send(id_message)

        except Exception as e:
            logger.error(f"Error sending premium expiry notification: {e}")

    async def notify_premium_removal(self, member, member_role, role):
        """Notify user about removed premium membership"""
        try:
            role_price = next(
                (r["price"] for r in self.bot.config["premium_roles"] if r["name"] == role.name),
                None,
            )

            if role_price is not None:
                price_pln = g_to_pln(role_price)
                price_message = f"Aby odnowić tę rangę, potrzebujesz {role_price}{CURRENCY_UNIT} ({price_pln} PLN)."
            else:
                price_message = (
                    "Skontaktuj się z administracją, aby uzyskać informacje o cenie odnowienia."
                )

            expiration_date = discord.utils.format_dt(member_role.expiration_date, "R")

            logger.info("Sending removal notification to %s (%d)", member.display_name, member.id)

            message = (
                f"Twoja rola premium {role.name} wygasła {expiration_date}. \n"
                f"{price_message}\n"
                f"Zasil swoje konto, aby ją odnowić: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            id_message = f"```{member.id}```"

            # Użyj RoleManager do wysyłania powiadomień
            await self.role_manager.send_notification(member, message)

            # ID wysyłamy osobno
            if not self.force_channel_notifications:
                await member.send(id_message)
            else:
                channel = self.bot.get_channel(self.notification_channel_id)
                if channel:
                    await channel.send(id_message)

            # Dodatkowo usuń uprawnienia moderatorów nadane przez tego użytkownika
            async with self.bot.get_db() as session:
                await remove_premium_role_mod_permissions(session, self.bot, member.id)
                await session.commit()
                logger.info(
                    "Removed premium role privileges (mod permissions and teams) for %s (%d)",
                    member.display_name,
                    member.id,
                )

        except Exception as e:
            logger.error(f"Error sending premium removal notification: {e}")

    async def notify_mute_removal(self, member, member_role, role):
        """Powiadomienie o automatycznym usunięciu wyciszenia."""
        try:
            # Znajdź opis roli dla powiadomienia
            role_desc = next(
                (r["description"] for r in self.bot.config["mute_roles"] if r["id"] == role.id), ""
            )
            if role_desc:
                message = (
                    f"Twoje wyciszenie ({role.name}) wygasło i zostało automatycznie usunięte."
                )
                await self.role_manager.send_notification(member, message)
        except Exception as e:
            logger.error(f"Error sending mute removal notification: {e}")

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
            expired_roles = await RoleQueries.get_expired_roles(session, now)
            if not expired_roles:
                await ctx.send("Nie znaleziono wygasłych ról.")
                return

            for role in expired_roles:
                await ctx.send(
                    f"Expired role: Member ID: {role.member_id}, Role ID: {role.role_id}, Expiration Date: {role.expiration_date}"
                )

    @commands.command()
    @commands.is_owner()
    async def check_premium_role(self, ctx, member: discord.Member):
        """Command to check premium roles for a specific member"""
        async with self.bot.get_db() as session:
            premium_roles = await RoleQueries.get_member_premium_roles(session, member.id)
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
                member_roles = await RoleQueries.get_member_roles(session, member.id)
                mute_roles = [role for role in member_roles if role.role_id in mute_role_ids]

                if not mute_roles:
                    await ctx.send(f"Użytkownik {member.display_name} nie ma żadnych wyciszeń.")
                    return

                for role in mute_roles:
                    expiry_status = "aktywne" if role.expiration_date > now else "wygasłe"
                    expiry_time = (
                        f"wygasa {discord.utils.format_dt(role.expiration_date, 'R')}"
                        if role.expiration_date
                        else "stałe"
                    )

                    await ctx.send(
                        f"Wyciszenie {self.bot.guild.get_role(role.role_id).name} dla {member.display_name}:\n"
                        f"Status: {expiry_status}\n"
                        f"Czas: {expiry_time}"
                    )
            else:
                # Sprawdź wszystkie wyciszenia
                all_mute_roles = []
                for role_id in mute_role_ids:
                    role_members = await RoleQueries.get_role_members(session, role_id)
                    all_mute_roles.extend(role_members)

                if not all_mute_roles:
                    await ctx.send("Nie znaleziono żadnych aktywnych wyciszeń.")
                    return

                await ctx.send(f"Znaleziono {len(all_mute_roles)} aktywnych wyciszeń:")

                for i, member_role in enumerate(all_mute_roles[:10], 1):
                    member_obj = self.bot.guild.get_member(member_role.member_id)
                    member_name = (
                        member_obj.display_name if member_obj else f"ID: {member_role.member_id}"
                    )
                    role_name = self.bot.guild.get_role(member_role.role_id).name
                    expiry_time = (
                        f"wygasa {discord.utils.format_dt(member_role.expiration_date, 'R')}"
                        if member_role.expiration_date
                        else "stałe"
                    )

                    await ctx.send(f"{i}. {member_name}: {role_name} ({expiry_time})")

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


async def setup(bot: commands.Bot):
    await bot.add_cog(OnTaskEvent(bot))
