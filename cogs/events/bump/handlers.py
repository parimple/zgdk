"""Handler classes for different bump services."""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord

from core.repositories import NotificationRepository
from datasources.models import Member
from datasources.queries import MemberQueries
from utils.message_sender import MessageSender

from .constants import BYPASS_DURATIONS, DISBOARD, DISCADIA, DISCORDSERVERS, DSME, DZIK, SERVICE_COOLDOWNS

logger = logging.getLogger(__name__)


class BumpHandler:
    """Base class for bump handlers."""

    def __init__(self, bot, message_sender: MessageSender):
        self.bot = bot
        self.message_sender = message_sender

    async def add_bypass_time(self, member: discord.Member, hours: int, service: str) -> None:
        """Add bypass time to a member."""
        try:
            async with self.bot.get_db() as session:
                db_member = await MemberQueries.get_or_add_member(session, member.id)

                # Calculate new bypass expiry
                current_time = datetime.now(timezone.utc)
                if db_member.bypass_expiry and db_member.bypass_expiry > current_time:
                    # Extend existing bypass
                    db_member.bypass_expiry = db_member.bypass_expiry + timedelta(hours=hours)
                else:
                    # Set new bypass
                    db_member.bypass_expiry = current_time + timedelta(hours=hours)

                await session.commit()
                logger.info(
                    f"Added {hours}h bypass time for {member.display_name} on {service}. "
                    f"New expiry: {db_member.bypass_expiry}"
                )
        except Exception as e:
            logger.error(f"Error adding bypass time: {e}", exc_info=True)

    async def check_cooldown(self, session, user_id: int, service: str, cooldown_hours: int) -> bool:
        """Check if user is on cooldown for a service."""
        # For global services like disboard, use guild_id
        guild_id = self.bot.guild_id if hasattr(self.bot, "guild_id") else None
        notification_repo = NotificationRepository(session)
        last_notification = await notification_repo.get_service_notification_log(service, guild_id, user_id)

        if last_notification:
            current_time = datetime.now(timezone.utc)
            cooldown_end = last_notification.sent_at + timedelta(hours=cooldown_hours)

            if current_time < cooldown_end:
                return True  # Still on cooldown

        return False  # Not on cooldown

    async def log_notification(self, session, user_id: int, service: str) -> None:
        """Log a notification for cooldown tracking."""
        guild_id = self.bot.guild_id if hasattr(self.bot, "guild_id") else None
        notification_repo = NotificationRepository(session)
        await notification_repo.add_or_update_notification_log(user_id, service)


class DisboardHandler(BumpHandler):
    """Handler for Disboard bumps."""

    async def handle(self, message: discord.Message) -> None:
        """Handle Disboard bump message."""
        logger.info(f"DisboardHandler.handle called for message from {message.author}")

        embed = message.embeds[0] if message.embeds else None
        if not embed:
            logger.warning("No embed found in DISBOARD message")
            return

        logger.info(f"Processing DISBOARD embed: {embed.to_dict()}")

        # Extract the user who bumped
        user = None

        # First check if it's from interaction (slash command)
        if message.interaction and message.interaction.user:
            user = message.interaction.user
            logger.info(f"Found user from interaction: {user.name} ({user.id})")
        else:
            # Fallback to checking embed content
            user_id = None

            # Check description first
            if embed.description:
                user_match = re.search(r"<@(\d+)>", embed.description)
                if user_match:
                    user_id = int(user_match.group(1))
                    logger.info(f"Found user ID in description: {user_id}")

            # Check fields if not found in description
            if not user_id and embed.fields:
                for field in embed.fields:
                    if field.value:
                        user_match = re.search(r"<@(\d+)>", field.value)
                        if user_match:
                            user_id = int(user_match.group(1))
                            logger.info(f"Found user ID in field '{field.name}': {user_id}")
                            break

            if user_id:
                user = message.guild.get_member(user_id)

        if not user:
            logger.error("Could not extract user from DISBOARD message")
            return

        async with self.bot.get_db() as session:
            # Check if user is on cooldown
            if await self.check_cooldown(session, user.id, "disboard", SERVICE_COOLDOWNS["disboard"]):
                logger.info(f"User {user.name} is on cooldown for Disboard")
                return

            # Get or create member
            member = await MemberQueries.get_or_add_member(session, user.id)

            # Add bypass time
            await self.add_bypass_time(user, BYPASS_DURATIONS["disboard"], "disboard")

            # Log the notification
            await self.log_notification(session, user.id, "disboard")

            # Update bump count
            member.bump_count = (member.bump_count or 0) + 1

            await session.commit()

        # Send thank you message
        await self.send_thank_you(message.channel, user, "Disboard")

        # Send marketing message
        if hasattr(self.bot.get_cog("OnBumpEvent"), "send_bump_marketing"):
            await self.bot.get_cog("OnBumpEvent").send_bump_marketing(message.channel, "disboard", user)

    async def send_thank_you(self, channel: discord.TextChannel, user: discord.Member, service: str) -> None:
        """Send thank you message for bump."""
        embed = self.message_sender._create_embed(
            color="success",
            description=(
                f"Dziękujemy za podbicie serwera na {service}!\n"
                f"Otrzymujesz **{BYPASS_DURATIONS['disboard']}T** czasu bypass."
            ),
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url if user.display_avatar else None)

        await channel.send(embed=embed)

    async def send_marketing(self, channel: discord.TextChannel, service: str, user: discord.Member) -> None:
        """Send marketing message after bump."""
        # This will be implemented in the main class
        pass


class DzikHandler(BumpHandler):
    """Handler for Dzik bumps."""

    async def handle(self, message: discord.Message) -> None:
        """Handle Dzik bump message."""
        # Check if it's the correct bot
        if message.author.id != DZIK["id"]:
            return

        # Extract user from interaction
        if not message.interaction or not message.interaction.user:
            return

        user = message.interaction.user

        async with self.bot.get_db() as session:
            # Check if user is on cooldown
            if await self.check_cooldown(session, user.id, "dzik", SERVICE_COOLDOWNS["dzik"]):
                logger.info(f"User {user.name} is on cooldown for Dzik")
                return

            # Get or create member
            member = await MemberQueries.get_or_add_member(session, user.id)

            # Add bypass time
            await self.add_bypass_time(user, BYPASS_DURATIONS["dzik"], "dzik")

            # Log the notification
            await self.log_notification(session, user.id, "dzik")

            # Update bump count
            member.bump_count = (member.bump_count or 0) + 1

            await session.commit()

        # Send thank you message
        embed = self.message_sender._create_embed(
            color="success",
            description=(
                f"Dziękujemy za podbicie serwera na Dziku!\n"
                f"Otrzymujesz **{BYPASS_DURATIONS['dzik']}T** czasu bypass."
            ),
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url if user.display_avatar else None)

        await message.channel.send(embed=embed)

        # Send marketing message
        if hasattr(self.bot.get_cog("OnBumpEvent"), "send_bump_marketing"):
            await self.bot.get_cog("OnBumpEvent").send_bump_marketing(message.channel, "dzik", user)


class DiscadiaHandler(BumpHandler):
    """Handler for Discadia bumps and votes."""

    async def handle_bump(self, message: discord.Message) -> bool:
        """Handle Discadia bump message."""
        # Check for cooldown messages
        content_lower = message.content.lower()
        embed_content = ""

        if message.embeds:
            embed = message.embeds[0]
            embed_content = f"{embed.title or ''} {embed.description or ''}".lower()

        # Check for cooldown
        for cooldown_msg in DISCADIA["cooldown_messages"]:
            if cooldown_msg in content_lower or cooldown_msg in embed_content:
                return False  # User is on cooldown

        # Check for success
        for success_msg in DISCADIA["success_messages"]:
            if success_msg in content_lower or success_msg in embed_content:
                return True  # Successful bump

        return False

    async def handle_vote(self, message: discord.Message) -> None:
        """Handle Discadia vote message."""
        # Extract user from mentions
        if not message.mentions:
            return

        user = message.mentions[0]

        async with self.bot.get_db() as session:
            # Check if user is on cooldown
            if await self.check_cooldown(session, user.id, "discadia", SERVICE_COOLDOWNS["discadia"]):
                logger.info(f"User {user.name} is on cooldown for Discadia")
                return

            # Get or create member
            member = await MemberQueries.get_or_add_member(session, user.id)

            # Add bypass time
            await self.add_bypass_time(user, BYPASS_DURATIONS["discadia"], "discadia")

            # Log the notification
            await self.log_notification(session, user.id, "discadia")

            await session.commit()

        # Send thank you message
        embed = self.message_sender._create_embed(
            color="success",
            description=(
                f"Dziękujemy za głosowanie na Discadia!\n"
                f"Otrzymujesz **{BYPASS_DURATIONS['discadia']}T** czasu bypass."
            ),
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url if user.display_avatar else None)

        await message.channel.send(embed=embed)


class DiscordServersHandler(BumpHandler):
    """Handler for DiscordServers bumps."""

    async def handle(self, message: discord.Message) -> None:
        """Handle DiscordServers bump message."""
        # Check if message indicates success
        content_lower = message.content.lower()
        is_success = False

        for success_msg in DISCORDSERVERS["success_messages"]:
            if success_msg in content_lower:
                is_success = True
                break

        if not is_success:
            return

        # Extract user from interaction
        if not message.interaction or not message.interaction.user:
            return

        user = message.interaction.user

        async with self.bot.get_db() as session:
            # Check if user is on cooldown
            if await self.check_cooldown(session, user.id, "discordservers", SERVICE_COOLDOWNS["discordservers"]):
                logger.info(f"User {user.name} is on cooldown for DiscordServers")
                return

            # Get or create member
            member = await MemberQueries.get_or_add_member(session, user.id)

            # Add bypass time
            await self.add_bypass_time(user, BYPASS_DURATIONS["discordservers"], "discordservers")

            # Log the notification
            await self.log_notification(session, user.id, "discordservers")

            await session.commit()

        # Send thank you message
        embed = self.message_sender._create_embed(
            color="success",
            description=(
                f"Dziękujemy za głosowanie na DiscordServers!\n"
                f"Otrzymujesz **{BYPASS_DURATIONS['discordservers']}T** czasu bypass."
            ),
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url if user.display_avatar else None)

        await message.channel.send(embed=embed)


class DSMEHandler(BumpHandler):
    """Handler for DSME votes."""

    async def handle(self, message: discord.Message) -> None:
        """Handle DSME vote message."""
        # Check for success messages
        content_lower = message.content.lower()
        is_success = False

        for success_msg in DSME["success_messages"]:
            if success_msg in content_lower:
                is_success = True
                break

        if not is_success:
            return

        # Extract user from mentions or interaction
        user = None

        if message.mentions:
            user = message.mentions[0]
        elif message.interaction and message.interaction.user:
            user = message.interaction.user

        if not user:
            return

        async with self.bot.get_db() as session:
            # Check if user is on cooldown
            if await self.check_cooldown(session, user.id, "dsme", SERVICE_COOLDOWNS["dsme"]):
                logger.info(f"User {user.name} is on cooldown for DSME")
                return

            # Get or create member
            member = await MemberQueries.get_or_add_member(session, user.id)

            # Add bypass time
            await self.add_bypass_time(user, BYPASS_DURATIONS["dsme"], "dsme")

            # Log the notification
            await self.log_notification(session, user.id, "dsme")

            await session.commit()

        # Send thank you message
        embed = self.message_sender._create_embed(
            color="success",
            description=(
                f"Dziękujemy za głosowanie na DSME!\n" f"Otrzymujesz **{BYPASS_DURATIONS['dsme']}T** czasu bypass."
            ),
        )
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url if user.display_avatar else None)

        await message.channel.send(embed=embed)
