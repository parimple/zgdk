"""
On Task Event
"""

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from datasources.queries import NotificationLogQueries, RoleQueries

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
            expiring_roles_with_notifications = (
                await NotificationLogQueries.get_member_roles_with_notifications(
                    session,
                    expiration_threshold=expiration_threshold,
                    notification_tag="premium_role_expiry",
                )
            )
            logger.info("Found %d expiring roles", len(expiring_roles_with_notifications))
            for role, notification_log in expiring_roles_with_notifications:
                member = self.bot.guild.get_member(role.member_id)
                if member:
                    logger.info("Processing member %d for role %d", member.id, role.role_id)
                    if not notification_log or now - notification_log.sent_at > timedelta(hours=24):
                        logger.info(
                            "Notifying member %d about expiring role %d", member.id, role.role_id
                        )
                        await self.notify_premium_expiry(member, role)
                        await NotificationLogQueries.add_or_update_notification_log(
                            session, member.id, "premium_role_expiry"
                        )
            await session.commit()
        logger.info("Finished check_premium_expiry task")

    async def notify_premium_expiry(self, member, role):
        """Notify user about expiring premium membership"""
        try:
            expiration_date = role.expiration_date
            expiration_str = discord.utils.format_dt(expiration_date, "R")
            logger.info("Sending expiry notification to %s (%d)", member.display_name, member.id)
            await member.send(
                f"Twoja rola premium {role.role.name} wygaśnie {expiration_str}. "
                f"Zasil swoje konto, aby ją przedłużyć: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            await member.send(f"```{member.id}```")
        except discord.Forbidden:
            logger.warning("Could not send DM to %s (%d).", member.display_name, member.id)
            await self.notify_in_channel(member, expiration_str)

    async def notify_in_channel(self, member, expiration_str):
        """Notify in the channel if DM cannot be sent"""
        channel_id = self.bot.config["channels"]["donation"]
        channel = self.bot.get_channel(channel_id)
        if channel:
            logger.info("Sending channel notification to %s (%d)", member.display_name, member.id)
            await channel.send(
                f"{member.mention}, Twoja rola premium wygaśnie {expiration_str}, "
                f"ale nie mogłem wysłać do Ciebie wiadomości prywatnej. "
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
            expired_roles_with_notifications = (
                await NotificationLogQueries.get_member_roles_with_notifications(
                    session, expiration_threshold=now, notification_tag="premium_role_expired"
                )
            )
            logger.info("Found %d expired roles", len(expired_roles_with_notifications))
            for role, notification_log in expired_roles_with_notifications:
                member = self.bot.guild.get_member(role.member_id)
                if member:
                    logger.info("Processing member %d for expired role %d", member.id, role.role_id)
                    await self.notify_premium_removal(member, role)
                    await self.remove_premium_role(session, member, role)
                    await NotificationLogQueries.add_or_update_notification_log(
                        session, member.id, "premium_role_expired"
                    )
            await session.commit()
        logger.info("Finished remove_expired_roles task")

    async def notify_premium_removal(self, member, role):
        """Notify user about removed premium membership"""
        try:
            logger.info("Sending removal notification to %s (%d)", member.display_name, member.id)
            await member.send(
                f"Twoja rola premium {role.role.name} wygasła. "
                f"Zasil swoje konto, aby ją odnowić: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            await member.send(f"```{member.id}```")
        except discord.Forbidden:
            logger.warning("Could not send DM to %s (%d).", member.display_name, member.id)
            await self.notify_in_channel(member, "już wygasła")

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


async def setup(bot: commands.Bot):
    await bot.add_cog(OnTaskEvent(bot))
