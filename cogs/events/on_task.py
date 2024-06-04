"""
On Task Event
"""

import logging
from datetime import datetime, timedelta, timezone

import discord
from discord.ext import commands, tasks

from datasources.queries import RoleQueries

logger = logging.getLogger(__name__)


class OnTaskEvent(commands.Cog):
    """Cog to handle tasks that run periodically."""

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session
        self.last_notified = {}  # Store the last notification time for each member
        self.check_premium_expiry.start()  # pylint: disable=no-member
        self.remove_expired_roles.start()  # pylint: disable=no-member

    @tasks.loop(hours=1)
    async def check_premium_expiry(self):
        """Check for expiring premium memberships and notify users"""
        now = datetime.now(timezone.utc)
        reminder_time = now + timedelta(hours=24)
        async with self.session() as session:
            expiring_roles = await RoleQueries.get_expiring_roles(
                session, reminder_time, role_type="premium"
            )
            for role in expiring_roles:
                member = self.bot.guild.get_member(role.member_id)
                if member:
                    last_notified_time = self.last_notified.get((role.member_id, role.role_id))
                    if not last_notified_time or now - last_notified_time > timedelta(hours=24):
                        await self.notify_premium_expiry(member, role)
                        self.last_notified[(role.member_id, role.role_id)] = now

    async def notify_premium_expiry(self, member, role):
        """Notify user about expiring premium membership"""
        try:
            await member.send(
                f"Twoja rola premium {role.role.name} wygaśnie za 24 godziny. "
                f"Zasil swoje konto, aby ją przedłużyć: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            await member.send(f"```{member.id}```")
        except discord.Forbidden:
            logger.warning("Could not send DM to %s (%d).", member.display_name, member.id)
            await self.notify_in_channel(member)

    async def notify_in_channel(self, member):
        """Notify in the channel if DM cannot be sent"""
        channel_id = self.bot.config["channels"]["donation"]
        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.send(
                f"{member.mention}, Twoja rola premium wygaśnie za 24 godziny, "
                f"ale nie mogłem wysłać do Ciebie wiadomości prywatnej. "
                f"Zasil swoje konto, aby ją przedłużyć: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            await channel.send(f"```{member.id}```")

    @tasks.loop(hours=1)
    async def remove_expired_roles(self):
        """Remove expired premium memberships"""
        now = datetime.now(timezone.utc)
        async with self.session() as session:
            expired_roles = await RoleQueries.get_expired_roles(session, now, role_type="premium")
            for role in expired_roles:
                member = self.bot.guild.get_member(role.member_id)
                if member:
                    await self.notify_premium_removal(member, role)
                    await self.remove_premium_role(member, role)

    async def notify_premium_removal(self, member, role):
        """Notify user about removed premium membership"""
        try:
            await member.send(
                f"Twoja rola premium {role.role.name} wygasła. "
                f"Zasil swoje konto, aby ją odnowić: {self.bot.config['donate_url']}\n"
                "Wpisując **TYLKO** swoje id w polu - Twój nick."
            )
            await member.send(f"```{member.id}```")
        except discord.Forbidden:
            logger.warning("Could not send DM to %s (%d).", member.display_name, member.id)
            await self.notify_in_channel(member)

    async def remove_premium_role(self, member, role):
        """Remove the expired premium role from the user"""
        guild_role = self.bot.guild.get_role(role.role_id)
        if guild_role in member.roles:
            try:
                await member.remove_roles(guild_role)
                async with self.session() as session:
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
        await self.bot.wait_until_ready()


async def setup(bot: commands.Bot):
    await bot.add_cog(OnTaskEvent(bot))
