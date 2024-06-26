"""
On Task Event
"""

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from datasources.queries import NotificationLogQueries, RoleQueries
from utils.currency import CURRENCY_UNIT, g_to_pln

logger = logging.getLogger(__name__)


class OnTaskEvent(commands.Cog):
    """Cog to handle tasks that run periodically."""

    def __init__(self, bot):
        self.bot = bot
        self.check_premium_expiry.start()  # pylint: disable=no-member
        self.remove_expired_roles.start()  # pylint: disable=no-member

    @tasks.loop(hours=1)
    async def check_premium_expiry(self):
        """Check for expiring premium memberships and notify users"""
        logger.info("Starting check_premium_expiry task")
        now = datetime.now(timezone.utc)
        expiration_threshold = now + timedelta(hours=24)
        async with self.bot.get_db() as session:
            expiring_roles = await RoleQueries.get_member_premium_roles(session)
            logger.info("Found %d premium roles", len(expiring_roles))
            for member_role, role in expiring_roles:
                if member_role.expiration_date <= expiration_threshold:
                    member = self.bot.guild.get_member(member_role.member_id)
                    if member:
                        logger.info("Processing member %d for role %d", member.id, role.id)
                        notification_log = await NotificationLogQueries.get_notification_log(
                            session, member.id, "premium_role_expiry"
                        )
                        if not notification_log or now - notification_log.sent_at > timedelta(
                            hours=24
                        ):
                            logger.info(
                                "Notifying member %d about expiring role %d", member.id, role.id
                            )
                            await self.notify_premium_expiry(member, member_role, role)
                            await NotificationLogQueries.add_or_update_notification_log(
                                session, member.id, "premium_role_expiry"
                            )
        await session.commit()
        logger.info("Finished check_premium_expiry task")

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
                price_message = f"Aby przedłużyć tę rangę, potrzebujesz {role_price}{CURRENCY_UNIT} (około {price_pln:.2f} PLN)."
            else:
                price_message = (
                    "Skontaktuj się z administracją, aby uzyskać informacje o cenie odnowienia."
                )

            logger.info("Sending expiry notification to %s (%d)", member.display_name, member.id)
            await member.send(
                f"Twoja rola premium {role.name} wygaśnie {expiration_str}. \n"
                f"{price_message}\n"
                f"Zasil swoje konto, aby ją przedłużyć: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            await member.send(f"```{member.id}```")
        except discord.Forbidden:
            logger.warning("Could not send DM to %s (%d).", member.display_name, member.id)
            await self.notify_in_channel(member, expiration_str, price_message)

    async def notify_in_channel(self, member, expiration_str, price_message):
        """Notify in the channel if DM cannot be sent"""
        channel_id = self.bot.config["channels"]["donation"]
        channel = self.bot.get_channel(channel_id)
        if channel:
            logger.info("Sending channel notification to %s (%d)", member.display_name, member.id)
            await channel.send(
                f"{member.mention}, Twoja rola premium wygaśnie {expiration_str}, "
                f"ale nie mogłem wysłać do Ciebie wiadomości prywatnej. \n"
                f"{price_message}\n"
                f"Zasil swoje konto, aby ją przedłużyć: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            await channel.send(f"```{member.id}```")

    @tasks.loop(hours=1)
    async def remove_expired_roles(self):
        """Remove expired premium memberships"""
        logger.info("Starting remove_expired_roles task")
        now = datetime.now(timezone.utc)
        async with self.bot.get_db() as session:
            expired_roles = await RoleQueries.get_member_premium_roles(session)
            logger.info("Found %d premium roles", len(expired_roles))
            for member_role, role in expired_roles:
                if member_role.expiration_date <= now:
                    member = self.bot.guild.get_member(member_role.member_id)
                    if member:
                        logger.info("Processing member %d for expired role %d", member.id, role.id)
                        await self.notify_premium_removal(member, member_role, role)
                        await self.remove_premium_role(session, member, member_role, role)
                        await NotificationLogQueries.add_or_update_notification_log(
                            session, member.id, "premium_role_expired"
                        )
        await session.commit()
        logger.info("Finished remove_expired_roles task")

    async def notify_premium_removal(self, member, member_role, role):
        """Notify user about removed premium membership"""
        try:
            # Get the price of the role
            role_price = next(
                (r["price"] for r in self.bot.config["premium_roles"] if r["name"] == role.name),
                None,
            )

            if role_price is not None:
                price_pln = g_to_pln(role_price)
                price_message = f"Aby odnowić tę rangę, potrzebujesz {role_price}{CURRENCY_UNIT} (około {price_pln:.2f} PLN)."
            else:
                price_message = "Skontaktuj się z administracją, aby uzyskać informacje o cenie odnowienia."

            expiration_date = discord.utils.format_dt(member_role.expiration_date, "R")
            
            logger.info("Sending removal notification to %s (%d)", member.display_name, member.id)
            await member.send(
                f"Twoja rola premium {role.name} wygasła {expiration_date}. \n"
                f"{price_message}\n"
                f"Zasil swoje konto, aby ją odnowić: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            await member.send(f"```{member.id}```")
        except discord.Forbidden:
            logger.warning("Could not send DM to %s (%d).", member.display_name, member.id)
            await self.notify_in_channel(member, "już wygasła", price_message)

    async def remove_premium_role(self, session, member, role):
        """Remove the expired premium role from the user"""
        guild_role = self.bot.guild.get_role(role.role_id)
        if guild_role in member.roles:
            try:
                await member.remove_roles(guild_role)
                await RoleQueries.delete_member_role(session, member.id, role.role_id)
                logger.info(
                    "Removed expired role %s from %s (%d).",
                    guild_role.name,
                    member.display_name,
                    member.id,
                )
            except discord.Forbidden:
                logger.warning(
                    "Could not remove role %s from %s (%d).",
                    guild_role.name,
                    member.display_name,
                    member.id,
                )

    @check_premium_expiry.before_loop
    @remove_expired_roles.before_loop
    async def before_tasks(self):
        logger.info("Waiting for bot to be ready before starting tasks")
        await self.bot.wait_until_ready()
        logger.info("Bot is ready, starting tasks")

    @commands.command()
    @commands.is_owner()
    async def check_expired_roles(self, ctx):
        now = datetime.now(timezone.utc)
        async with self.bot.get_db() as session:
            expired_roles = await RoleQueries.get_expired_roles(session, now)
            for role in expired_roles:
                await ctx.send(
                    f"Expired role: Member ID: {role.member_id}, Role ID: {role.role_id}, Expiration Date: {role.expiration_date}"
                )

    @commands.command()
    @commands.is_owner()
    async def check_premium_role(self, ctx, member: discord.Member):
        async with self.bot.get_db() as session:
            premium_roles = await RoleQueries.get_member_premium_roles(session, member.id)
            current_time = datetime.now(timezone.utc)
            for role in premium_roles:
                await ctx.send(
                    f"Role ID: {role.role_id}\n"
                    f"Expiration: {role.expiration_date}\n"
                    f"Current time: {current_time}\n"
                    f"Is expired: {role.expiration_date <= current_time}"
                )

    @commands.command()
    @commands.is_owner()
    async def test_premium_expiry(self, ctx):
        """Command to test the premium expiry notifications"""
        logger.info("Starting test_premium_expiry command")
        now = datetime.now(timezone.utc)
        expiration_threshold = now + timedelta(hours=24)
        async with self.bot.get_db() as session:
            expiring_roles_with_notifications = (
                await NotificationLogQueries.get_member_roles_with_notifications(
                    session,
                    expiration_threshold=expiration_threshold,
                    notification_tag="premium_role_expiry",
                )
            )
            logger.info("Found %d expiring roles in test", len(expiring_roles_with_notifications))
            for role, notification_log in expiring_roles_with_notifications:
                member = self.bot.guild.get_member(role.member_id)
                if member:
                    await self.notify_premium_expiry(member, role)
                    await NotificationLogQueries.add_or_update_notification_log(
                        session, member.id, "premium_role_expiry"
                    )
            await session.commit()
        await ctx.send("Test premium expiry notifications sent.")

    @commands.command()
    @commands.is_owner()
    async def test_remove_expired_roles(self, ctx):
        """Command to test the removal of expired premium roles"""
        logger.info("Starting test_remove_expired_roles command")
        now = datetime.now(timezone.utc)
        async with self.bot.get_db() as session:
            expired_roles_with_notifications = (
                await NotificationLogQueries.get_member_roles_with_notifications(
                    session, expiration_threshold=now, notification_tag="premium_role_expired"
                )
            )
            logger.info("Found %d expired roles in test", len(expired_roles_with_notifications))
            for role, notification_log in expired_roles_with_notifications:
                member = self.bot.guild.get_member(role.member_id)
                if member:
                    await self.notify_premium_removal(member, role)
                    await self.remove_premium_role(session, member, role)
                    await NotificationLogQueries.add_or_update_notification_log(
                        session, member.id, "premium_role_expired"
                    )
            await session.commit()
        await ctx.send("Test remove expired roles executed.")

    @commands.command()
    @commands.is_owner()
    async def check_premium_roles_status(self, ctx):
        now = datetime.now(timezone.utc)
        async with self.bot.get_db() as session:
            all_premium_roles = await RoleQueries.get_all_premium_roles(session)
            for role in all_premium_roles:
                member = self.bot.guild.get_member(role.member_id)
                member_name = member.name if member else "Unknown"
                status = "Active" if role.expiration_date > now else "Expired"
                await ctx.send(
                    f"Member: {member_name} ({role.member_id}), "
                    f"Role: {role.role.name}, "
                    f"Expires: {role.expiration_date}, "
                    f"Status: {status}"
                )


async def setup(bot: commands.Bot):
    await bot.add_cog(OnTaskEvent(bot))
