import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from datasources.models import Member
from datasources.queries import MemberQueries, NotificationLogQueries
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)

# Bot IDs and configurations
DISBOARD = {
    "id": 302050872383242240,
    "description": [
        "!",
        ":thumbsup:",
        ":sob:",
        "👍",
        "DISBOARD에서 확인하십시오",
        "Schau es dir auf DISBOARD",
        "Allez vérifier ça sur DISBOARD",
        "Zobacz aktualizację na stronie DISBOARD",
        "Check it on DISBOARD",
        "Échale un vistazo en DISBOARD",
        "Podbito serwer",
        "Server bumped",
    ],
    "ping_id": 764443772108013578,
    "message_bot": "Można już zbumpować kanał ❤️ Wpisz /bump ",
    "message_bump": "Można już zbumpować kanał ❤️ Wpisz /bump ",
    "command": "!d bump",
}

DZIK = {
    "id": 1270093920256393248,
}

DISCADIA = {
    "id": 1222548162741538938,
    "cooldown_messages": [
        "already bumped recently",
        "try again in",
        ":warning:",
        "can only bump every",
        "you must wait",
        "⚠️",
    ],
}

DCSERVERS = {
    "id": 1336297961402929195,  # Webhook channel ID
    "success_messages": [
        "has bumped your server on DiscordServers",
        "More Gems!",
    ],
}

DISCADIA_WEBHOOK_CHANNEL = 1326322441383051385
DCSERVERS_WEBHOOK_CHANNEL = 1336297961402929195

# Global services that use guild_id for cooldown
GLOBAL_SERVICES = ["disboard"]  # tylko Disboard jest globalny

DSME_ROLE_ID = 960665311743447108


class OnBumpEvent(commands.Cog):
    """Handles vote and bump events from different services."""

    def __init__(self, bot):
        self.bot = bot
        self.notification_channel_id = 1336368306940018739
        self.system_user_id = bot.guild_id
        self.test_mode = True  # Flaga do kontrolowania trybu testowego

    def get_service_duration(self, service: str) -> int:
        """Get duration for a service"""
        if service == "discordservers":
            return 6  # 6h za DCServers
        elif service == "dsme":
            return 3  # 3h za DSME
        return self.bot.config["bypass"]["duration"]["services"].get(service, 3)

    def get_service_cooldown(self, service: str) -> int:
        """Get cooldown for a service"""
        if service == "discordservers":
            return 12  # 12h cooldown dla DCServers
        elif service == "dsme":
            return 6  # 6h cooldown dla DSME
        return self.bot.config["bypass"]["cooldown"].get(service, 24)

    def extract_message_text(self, message: discord.Message) -> str:
        """
        Extract all possible text content from a message, including:
        - Direct content
        - Clean content
        - Embed content (title, description, fields)
        - Interaction data

        Returns:
            str: Combined message text or empty string if no content found
        """
        parts = []

        # 1. Direct content
        if message.content:
            parts.append(message.content)
        elif message.clean_content:
            parts.append(message.clean_content)

        # 2. Embed content
        if message.embeds:
            first_embed = message.embeds[0]
            if first_embed.title:
                parts.append(first_embed.title)
            if first_embed.description:
                parts.append(first_embed.description)
            if first_embed.fields:
                fields_text = "\n".join(
                    f"{field.name}: {field.value}" for field in first_embed.fields
                )
                parts.append(fields_text)

        # 3. System content (if available)
        if hasattr(message, "system_content") and message.system_content:
            parts.append(message.system_content)

        # Combine all parts
        return "\n".join(p for p in parts if p)

    def extract_user_id(self, message: discord.Message) -> Optional[int]:
        """Extract user ID from message content or embeds."""
        logger.info(f"Extracting user ID from message: {message.id}")
        logger.info(f"Message type: {message.type}")
        logger.info(f"Message content: {message.content}")
        logger.info(f"Has embeds: {bool(message.embeds)}")
        logger.info(f"Has mentions: {bool(message.mentions)}")

        # For slash commands, use the interaction user
        if message.type == discord.MessageType.chat_input_command:
            if message.interaction and message.interaction.user:
                return message.interaction.user.id

        # Check embeds for user information
        if message.embeds:
            embed = message.embeds[0]
            logger.info(f"Embed title: {embed.title}")
            logger.info(f"Embed description: {embed.description}")
            logger.info(f"Embed fields: {len(embed.fields)}")

            # Check fields for "Głosujący" field
            if embed.fields:
                for field in embed.fields:
                    logger.info(f"Field name: {field.name}")
                    logger.info(f"Field value: {field.value}")
                    if field.name == "Głosujący":
                        # Extract username from field value (removes ** if present)
                        username = field.value.strip("*")
                        # Find member by username
                        member = discord.utils.find(
                            lambda m: m.name.lower() == username.lower(),
                            self.bot.guild.members,
                        )
                        if member:
                            return member.id

            # Check description for user mention or username
            if embed.description:
                # First try to get user from mentions in the embed description
                if message.mentions:
                    logger.info(
                        f"Found mentions in message: {[m.name for m in message.mentions]}"
                    )
                    return message.mentions[0].id

                # Try to extract user ID from mention in description
                mention_match = re.search(r"<@!?(\d+)>", embed.description)
                if mention_match:
                    user_id = int(mention_match.group(1))
                    logger.info(f"Found user ID in embed description: {user_id}")
                    return user_id

                # If no mention found, try to match username
                match = re.search(r"@(\w+) has bumped", embed.description)
                if match:
                    username = match.group(1)
                    logger.info(f"Found username in description: {username}")
                    member = discord.utils.find(
                        lambda m: m.name.lower() == username.lower(),
                        self.bot.guild.members,
                    )
                    if member:
                        logger.info(
                            f"Found member by username: {member.name} ({member.id})"
                        )
                        return member.id
                    logger.warning(
                        f"Could not find member with username {username} in guild members"
                    )
                else:
                    logger.warning(
                        f"No username match found in description: {embed.description}"
                    )

        # Check message mentions
        if message.mentions:
            logger.info(
                f"Using first mention: {message.mentions[0].name} ({message.mentions[0].id})"
            )
            return message.mentions[0].id

        # Check message content for user mention
        if message.content:
            mention_match = re.search(r"<@!?(\d+)>", message.content)
            if mention_match:
                user_id = int(mention_match.group(1))
                logger.info(f"Found user ID in content: {user_id}")
                return user_id

        logger.warning("Could not extract user ID using any method")
        return None

    async def handle_slash_command(self, message: discord.Message) -> bool:
        """
        Handle slash command responses from bots.

        Note: Discadia's message sequence:
        1. Initial empty message:
           - MessageType.chat_input_command
           - Flags: value=128 (ephemeral)
           - Empty content
           - State: thinking

        2. Message edit:
           - Same message ID
           - Adds actual content
           - Still ephemeral

        3. Final message:
           - Same message ID
           - Same content
           - Flags: value=0 (not ephemeral)
           - State: final

        We primarily process the final message (step 3) as it has the most reliable state.
        """
        if not message.type == discord.MessageType.chat_input_command:
            return False

        bot_id = message.author.id
        is_ephemeral = bool(message.flags.ephemeral)
        has_embeds = bool(message.embeds)

        # Get command details
        command_name = (
            getattr(message.interaction, "name", "unknown")
            if message.interaction
            else "no interaction"
        )
        command_user = (
            getattr(message.interaction, "user", None) if message.interaction else None
        )

        # Log initial state
        logger.info(
            f"Processing slash command response:\n"
            f"Bot: {message.author.name} ({bot_id})\n"
            f"Command: {command_name}\n"
            f"User: {command_user}\n"
            f"Is Ephemeral: {is_ephemeral}\n"
            f"Has Embeds: {has_embeds}\n"
            f"Message ID: {message.id}\n"
            f"Content: {message.content}\n"
            f"State: {'thinking' if not message.content and not has_embeds else 'final'}"
        )

        # Handle initial/thinking state (empty message)
        if not message.content and not has_embeds:
            logger.info(
                f"Detected initial slash command state:\n"
                f"Bot: {message.author.name}\n"
                f"Command: {command_name}\n"
                f"User: {command_user}\n"
                f"State: thinking\n"
                f"Message ID: {message.id}\n"
                f"Flags: {message.flags}"
            )

            # Note: on_message_edit will handle Dzik slash command updates

            return True

        # Extract message content
        message_content = self.extract_message_text(message).lower()

        # Handle bot-specific responses
        if bot_id == DISCADIA["id"]:
            if is_ephemeral:
                logger.info(
                    f"Discadia message marked as ephemeral but visible to all (Message ID: {message.id}). "
                    f"This is normal behavior - ignoring ephemeral flag."
                )

            # Check for cooldown first
            if any(msg in message_content for msg in DISCADIA["cooldown_messages"]):
                logger.info(
                    f"Detected Discadia cooldown:\n"
                    f"Content: {message_content}\n"
                    f"Command: {command_name}\n"
                    f"User: {command_user}\n"
                    f"Message ID: {message.id}\n"
                    f"State: final\n"
                    f"Flags: {message.flags}"
                )
                # Show marketing message even when on cooldown
                if command_user:
                    # Create a fake context with necessary attributes
                    class FakeContext:
                        def __init__(self, bot, guild):
                            self.bot = bot
                            self.guild = guild
                            self.channel = message.channel

                        async def send(self, *args, **kwargs):
                            return await self.channel.send(*args, **kwargs)

                    ctx = FakeContext(self.bot, message.guild)
                    await self.send_bump_marketing(ctx, "dsme", command_user)
                return True

            # Check for successful bump
            if "has been successfully bumped!" in message_content:
                logger.info(
                    f"Detected successful Discadia bump:\n"
                    f"Content: {message_content}\n"
                    f"Original Author: {message.author}\n"
                    f"Command User: {command_user}\n"
                    f"Message ID: {message.id}\n"
                    f"State: final"
                )
                # Override message.author with the actual user who used the slash command
                if command_user:
                    message.author = command_user
                    logger.info(f"Using interaction user as author: {message.author}")
                await self.handle_discadia_bump(message)
                return True

            # Unhandled Discadia message
            logger.debug(
                f"Unhandled Discadia message:\n"
                f"Content: {message_content}\n"
                f"Command: {command_name}\n"
                f"User: {command_user}\n"
                f"Message ID: {message.id}\n"
                f"State: final\n"
                f"Note: Message content not recognized - this may be normal for some Discadia responses"
            )
            return True

        elif bot_id == DISBOARD["id"]:
            if any(d.lower() in message_content for d in DISBOARD["description"]):
                await self.handle_disboard_bump(message)
                return True

        elif bot_id == DZIK["id"]:
            await self.handle_dzik_bump(message)
            return True

        # Unhandled slash command
        logger.debug(
            f"Unhandled slash command:\n"
            f"Bot: {message.author.name}\n"
            f"Content: {message_content}\n"
            f"Command: {command_name}\n"
            f"User: {command_user}\n"
            f"Message ID: {message.id}\n"
            f"State: final"
        )
        return False

    async def handle_webhook_message(self, message: discord.Message) -> bool:
        """Handle webhook messages from bots."""
        if not message.webhook_id:
            return False

        # Extract message content at the start
        message_content = self.extract_message_text(message)

        if message.channel.id == DISCADIA_WEBHOOK_CHANNEL:
            if "voted for" in message_content.lower():
                await self.handle_discadia_vote(message)
                return True
        elif message.channel.id == DCSERVERS_WEBHOOK_CHANNEL:
            if any(msg in message_content for msg in DCSERVERS["success_messages"]):
                await self.handle_discordservers_bump(message)
                return True

        logger.debug(f"Unhandled webhook message: {message_content}")
        return False

    async def handle_regular_message(self, message: discord.Message) -> bool:
        """Handle regular bot messages."""
        if not message.author.bot or message.webhook_id:
            return False

        message_content = self.extract_message_text(message).lower()
        bot_id = message.author.id

        if bot_id == DISBOARD["id"]:
            if any(d.lower() in message_content for d in DISBOARD["description"]):
                await self.handle_disboard_bump(message)
                return True

        elif bot_id == DZIK["id"]:
            await self.handle_dzik_bump(message)
            return True

        logger.debug(f"Unhandled bot message: {message_content}")
        return False

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Handle message edits from bump bots (especially Dzik slash responses)."""
        # Skip if not in bump channel or not from relevant bots
        if not after.guild or after.author.id not in [
            DISBOARD["id"],
            DZIK["id"],
            DISCADIA["id"],
        ]:
            return

        # Only process if the message changed significantly (content or embeds)
        if (
            before.content == after.content
            and len(before.embeds) == len(after.embeds)
            and all(
                e1.description == e2.description
                for e1, e2 in zip(before.embeds, after.embeds)
            )
        ):
            return

        # Special handling for Dzik slash response edits (thinking -> final)
        if (
            after.author.id == DZIK["id"]
            and after.type == discord.MessageType.chat_input_command
            and not before.embeds
            and after.embeds
        ):
            logger.info(
                f"Detected Dzik slash response edit: {before.id} -> final state with embeds"
            )
            await self.handle_dzik_bump(after)
            return

        # Process other edited messages as normal
        await self.on_message(after)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """
        Handle messages from different bots and webhooks.

        Note: Special handling for Discadia:
        - Uses ephemeral flag (128) even for public messages
        - Creates sequence: initial (empty) -> thinking -> final message
        - May use different message types for same content
        """
        if not message.guild or message.author == self.bot.user:
            return

        # Log messages from bump bots or webhook channel
        should_log = message.author.id in [
            DISBOARD["id"],
            DZIK["id"],
            DISCADIA["id"],
        ] or (message.webhook_id and message.channel.id == DISCADIA_WEBHOOK_CHANNEL)

        if should_log:
            log_message = (
                f"Message received in #{message.channel.name}:\n"
                f"Bot ID: {message.author.id}\n"
                f"Bot Name: {message.author.name}\n"
                f"Is Webhook: {bool(message.webhook_id)}\n"
                f"Message Type: {message.type}\n"
                f"Flags: {message.flags}\n"
                f"Content: {message.content}"
            )
            if message.embeds:
                log_message += "\nEmbeds:"
                for i, embed in enumerate(message.embeds):
                    log_message += f"\n  Embed {i + 1}:"
                    if embed.title:
                        log_message += f"\n    Title: {embed.title}"
                    if embed.description:
                        log_message += f"\n    Description: {embed.description}"
                    if embed.fields:
                        log_message += "\n    Fields:"
                        for field in embed.fields:
                            log_message += f"\n      {field.name}: {field.value}"
            logger.info(log_message)

        # Try to handle message in order of specificity
        if await self.handle_slash_command(message):
            return
        if await self.handle_webhook_message(message):
            return
        if await self.handle_regular_message(message):
            return

        # Handle Disboard text command
        if not message.author.bot and message.content.lower() == DISBOARD["command"]:
            logger.info(f"Storing Disboard bump command author: {message.author.id}")
            async with self.bot.get_db() as session:
                await NotificationLogQueries.add_or_update_notification_log(
                    session, self.bot.guild.id, "disboard"
                )
                await session.commit()

    async def handle_disboard_bump(self, message: discord.Message):
        """Handle bump confirmation from Disboard."""
        if not message.embeds or not message.embeds[0].description:
            return

        # Check if this is a successful bump message
        if not any(
            d in message.embeds[0].description.lower() for d in DISBOARD["description"]
        ):
            return

        # For slash commands, use the interaction user
        if message.type == discord.MessageType.chat_input_command:
            if not message.interaction or not message.interaction.user:
                logger.warning(
                    "No interaction user found in Disboard slash command. Aborting."
                )
                return

            user = message.interaction.user
            logger.info(f"Using interaction user as bumper: {user} ({user.id})")

            async with self.bot.get_db() as session:
                # First ensure member exists in database
                member = await MemberQueries.get_or_add_member(session, user.id)
                if not member:
                    logger.error(f"Failed to get or create member for user {user.id}")
                    return

                cooldown = self.get_service_cooldown("disboard")
                can_use, log = await NotificationLogQueries.process_service_usage(
                    session,
                    "disboard",
                    self.bot.guild.id,
                    self.bot.guild.id,  # Use guild_id for global services
                    cooldown,
                )

                if not can_use:
                    logger.info("Disboard bump attempted but cooldown not finished")
                    # Show marketing message even when on cooldown in the channel where command was used
                    await self.send_bump_marketing(message.channel, "disboard", user)
                    return

                # Add T time to the user who executed the command
                duration = self.get_service_duration("disboard")
                if await MemberQueries.add_bypass_time(session, user.id, duration):
                    logger.info(
                        f"Added {duration}h T to user {user.id} for Disboard bump"
                    )
                    await session.commit()

                    # Send marketing message in the channel where command was used
                    await self.send_bump_marketing(message.channel, "disboard", user)
            return

        # For non-slash messages (fallback)
        logger.warning(
            "Received non-slash command Disboard message - this should not happen"
        )
        logger.info(
            f"Message details:\n"
            f"Type: {message.type}\n"
            f"Content: {message.content}\n"
            f"Has Embeds: {bool(message.embeds)}"
        )

    async def handle_dzik_bump(self, message: discord.Message):
        """Handle bump confirmation from Dzik."""
        # For slash commands, use the interaction user directly
        if message.type == discord.MessageType.chat_input_command:
            if not message.interaction or not message.interaction.user:
                logger.warning(
                    "No interaction user found in Dzik slash command. Aborting."
                )
                return

            user = message.interaction.user
            logger.info(f"Using interaction user for Dzik bump: {user} ({user.id})")

        else:
            # For regular messages, try to extract user ID
            user_id = self.extract_user_id(message)
            if not user_id:
                logger.warning("Could not extract user ID from Dzik message")
                return

            user = self.bot.guild.get_member(user_id)
            if not user:
                logger.warning(f"Could not find user with ID {user_id}")
                return

        async with self.bot.get_db() as session:
            # First ensure member exists in database
            member = await MemberQueries.get_or_add_member(session, user.id)
            if not member:
                logger.error(f"Failed to get or create member for user {user.id}")
                return

            cooldown = self.get_service_cooldown("dzik")
            can_use, log = await NotificationLogQueries.process_service_usage(
                session, "dzik", self.bot.guild.id, user.id, cooldown
            )

            if not can_use:
                logger.info(
                    f"User {user.id} attempted Dzik bump but cooldown not finished"
                )
                await self.send_bump_marketing(message.channel, "dzik", user)
                return

            # Add T time
            duration = self.get_service_duration("dzik")
            if await MemberQueries.add_bypass_time(session, user.id, duration):
                logger.info(f"Added {duration}h T to user {user.id} for Dzik bump")
                await session.commit()

                # Send marketing message in the channel where command was used
                await self.send_bump_marketing(message.channel, "dzik", user)

    async def handle_discadia_bump(self, message: discord.Message):
        """
        Handle bump confirmation from Discadia.

        For slash commands, we use message.interaction.user as the bumper,
        as this is the most reliable way to identify who used the command.
        """
        logger.info("Processing Discadia bump")

        # For slash commands, use the interaction user
        if message.type == discord.MessageType.chat_input_command:
            if not message.interaction or not message.interaction.user:
                logger.warning(
                    "No interaction user found in Discadia slash command. Aborting."
                )
                return

            user = message.interaction.user
            logger.info(f"Using interaction user as bumper: {user} ({user.id})")

            async with self.bot.get_db() as session:
                # First ensure member exists in database
                member = await MemberQueries.get_or_add_member(session, user.id)
                if not member:
                    logger.error(f"Failed to get or create member for user {user.id}")
                    return

                cooldown = self.get_service_cooldown("dsme")
                can_use, log = await NotificationLogQueries.process_service_usage(
                    session,
                    "dsme",
                    self.bot.guild.id,
                    self.bot.guild.id,  # Use guild_id for global services
                    cooldown,
                )

                if not can_use:
                    logger.info("Discadia bump attempted but cooldown not finished")
                    # Show marketing message even when on cooldown
                    await self.send_bump_marketing(message.channel, "dsme", user)
                    return

                # Add T time to the user who executed the command
                duration = self.get_service_duration("dsme")
                if await MemberQueries.add_bypass_time(session, user.id, duration):
                    logger.info(
                        f"Added {duration}h T to user {user.id} for Discadia bump"
                    )
                    await session.commit()

                    # Send marketing message
                    await self.send_bump_marketing(message.channel, "dsme", user)
            return

        # For non-slash messages (fallback)
        logger.warning(
            "Received non-slash command Discadia message - this should not happen"
        )
        logger.info(
            f"Message details:\n"
            f"Type: {message.type}\n"
            f"Content: {message.content}\n"
            f"Has Embeds: {bool(message.embeds)}"
        )

    async def handle_discadia_vote(self, message: discord.Message):
        """Handle vote confirmation from Discadia webhook."""
        # Get message content from either direct content or embed description
        message_content = message.content
        if not message_content and message.embeds:
            message_content = message.embeds[0].description

        if not message_content:
            logger.warning("No content found in Discadia webhook message")
            return

        # Parse user mention from message
        match = re.match(r"<@!?(\d+)> voted for", message_content)
        if not match:
            logger.warning(
                f"Could not parse user mention from Discadia webhook message.\n"
                f"Content: {message_content}"
            )
            return

        user_id = int(match.group(1))
        logger.info(f"Processing Discadia vote from user {user_id}")

        # Get member and their voice state
        member = self.bot.guild.get_member(user_id)
        if not member:
            logger.warning(f"Could not find member {user_id} in guild")
            return

        async with self.bot.get_db() as session:
            # First ensure member exists in database
            db_member = await MemberQueries.get_or_add_member(session, user_id)
            if not db_member:
                logger.error(f"Failed to get or create member for user {user_id}")
                return

            cooldown = self.get_service_cooldown("discadia")
            can_use, log = await NotificationLogQueries.process_service_usage(
                session, "discadia", self.bot.guild.id, user_id, cooldown
            )

            if not can_use:
                logger.info(
                    f"User {user_id} attempted Discadia vote but cooldown not finished"
                )
                return

            # Add T time
            duration = self.get_service_duration("discadia")
            if await MemberQueries.add_bypass_time(session, user_id, duration):
                logger.info(f"Added {duration}h T to user {user_id} for Discadia vote")
                await session.commit()

                # Send marketing message to user's voice channel if they're in one
                if member.voice and member.voice.channel:
                    await self.send_bump_marketing(
                        member.voice.channel, "discadia", member
                    )
                else:
                    logger.info(
                        f"User {user_id} not in voice channel, skipping marketing message"
                    )

    async def handle_discordservers_bump(self, message: discord.Message):
        """Handle bump confirmation from DCServers."""
        if not message.embeds or not message.embeds[0].description:
            return

        # Extract user ID from the message
        user_id = self.extract_user_id(message)
        if not user_id:
            logger.warning("Could not extract user ID from DCServers bump message")
            return

        member = self.bot.guild.get_member(user_id)
        if not member:
            logger.warning(f"Could not find member with ID {user_id}")
            return

        async with self.bot.get_db() as session:
            # First ensure member exists in database
            db_member = await MemberQueries.get_or_add_member(session, user_id)
            if not db_member:
                logger.error(f"Failed to get or create member for user {user_id}")
                return

            cooldown = self.get_service_cooldown("discordservers")
            can_use, log = await NotificationLogQueries.process_service_usage(
                session, "discordservers", self.bot.guild.id, user_id, cooldown
            )

            if not can_use:
                logger.info(
                    f"User {user_id} attempted DCServers bump but cooldown not finished"
                )
                return

            # Add T time
            duration = self.get_service_duration("discordservers")
            if await MemberQueries.add_bypass_time(session, user_id, duration):
                logger.info(f"Added {duration}h T to user {user_id} for DCServers bump")
                await session.commit()

                # Send marketing message in the channel where command was used
                await self.send_bump_marketing(
                    message.channel, "discordservers", member
                )

    @property
    def force_channel_notifications(self):
        """Get global notification setting from bot"""
        return self.bot.force_channel_notifications

    async def send_bump_marketing(self, channel, service: str, user: discord.Member):
        """Send marketing message about service usage and show all bump statuses."""
        # Get target channel
        target_channel = None
        if user.voice and user.voice.channel:
            # If user is in a voice channel, send it there
            target_channel = user.voice.channel
        else:
            # If user is not in a voice channel, send to the bots channel
            target_channel = self.bot.get_channel(self.bot.config["channels"]["bots"])

        if not target_channel:
            logger.warning(f"Could not find target channel for user {user.id}")
            return

        # Create fake context for MessageSender
        class FakeContext:
            def __init__(self, bot, guild, channel):
                self.bot = bot
                self.guild = guild
                self.channel = channel
                self.author = user

            async def send(self, *args, **kwargs):
                return await self.channel.send(*args, **kwargs)

        ctx = FakeContext(self.bot, target_channel.guild, target_channel)

        # Get status of all services for the user
        services = ["disboard", "dzik", "discadia", "discordservers", "dsme"]
        available_services = []
        waiting_services = []

        for srv in services:
            status = await self.get_service_status(srv, user.id)
            if status["available"]:
                available_services.append((srv, status))
            else:
                waiting_services.append((srv, status))

        # Sort waiting services by remaining time (longest first)
        waiting_services.sort(key=lambda x: x[1]["next_available"], reverse=True)

        # Get user's current T time
        current_t = "0T"
        async with self.bot.get_db() as session:
            db_member = await session.get(Member, user.id)
            if db_member and db_member.voice_bypass_until:
                now = datetime.now(timezone.utc)
                if db_member.voice_bypass_until > now:
                    remaining = db_member.voice_bypass_until - now
                    current_t = f"{int(remaining.total_seconds() // 3600)}T"

        # Create embed
        embed = discord.Embed(title="Status Bumpów", color=user.color)

        # Set author with user avatar
        embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)

        # Get "Wybierz swój plan" text first but don't set it yet
        _, plan_text = MessageSender._get_premium_text(ctx, None)

        # Add waiting services first
        if waiting_services:
            waiting_text = []
            for service, status in waiting_services:
                emoji = self.get_service_emoji(service)
                details = self.get_service_details(service)
                next_time = discord.utils.format_dt(status["next_available"], "R")
                service_text = f"{emoji} **{details['name']}** • {details['cooldown']} {details['cooldown_type']} • {details['reward']}"
                if "command" in details:
                    service_text += f"\nDostępne: {next_time} • `{details['command']}`"
                elif "url" in details:
                    service_text += (
                        f"\nDostępne: {next_time} • [Zagłosuj]({details['url']})"
                    )
                waiting_text.append(service_text)

            if waiting_text:
                embed.add_field(
                    name="⏳ Oczekujące", value="\n".join(waiting_text), inline=False
                )

        # Add available services
        if available_services:
            available_text = []
            for service, status in available_services:
                emoji = self.get_service_emoji(service)
                details = self.get_service_details(service)
                service_text = f"{emoji} **{details['name']}** • {details['cooldown']} {details['cooldown_type']} • {details['reward']} • "
                if "command" in details:
                    service_text += f"`{details['command']}`"
                elif "url" in details:
                    service_text += f"[Zagłosuj]({details['url']})"
                available_text.append(service_text)

            if available_text:
                embed.add_field(
                    name="✅ Dostępne teraz",
                    value="\n".join(available_text),
                    inline=False,
                )

        # Create view with buttons for voting services
        view = None
        if available_services:
            view = discord.ui.View()
            for service, status in available_services:
                details = self.get_service_details(service)
                if "url" in details:
                    emoji = self.get_service_emoji(service)
                    button = discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        label=details["name"],
                        emoji=emoji,
                        url=details["url"],
                    )
                    view.add_item(button)

        # Set footer with T count
        embed.set_footer(text=f"Posiadasz {current_t}")

        # Add "Wybierz swój plan" text as the last element
        if plan_text:
            embed.add_field(name="\u200b", value=plan_text, inline=False)

        # Send the embed
        await target_channel.send(embed=embed, view=view)

    def get_service_emoji(self, service: str) -> str:
        """Get emoji for a service"""
        emojis = {
            "disboard": "<:botDisboard:1336275527241044069>",
            "dzik": "<:botDzik:1336275532991565824>",
            "discadia": "<:botDiscadia:1336275880703561758>",
            "discordservers": "<:botDiscordServers:1336322514170806383>",
            "dsme": "<:botDSME:1336311501765476352>",
        }
        return emojis.get(service, "")

    def get_service_details(self, service: str) -> dict:
        """Get details for a service"""
        return {
            "disboard": {
                "name": "Disboard",
                "cooldown": "2h",
                "cooldown_type": "🌐",
                "reward": "3T",
                "command": "/bump",
            },
            "dzik": {
                "name": "Dzik",
                "cooldown": "3h",
                "cooldown_type": "👤",
                "reward": "3T",
                "command": "/bump",
            },
            "discadia": {
                "name": "Discadia",
                "cooldown": "24h",
                "cooldown_type": "👤",
                "reward": "6T",
                "url": "https://discadia.com/vote/polska/",
            },
            "discordservers": {
                "name": "DiscordServers",
                "cooldown": "12h",
                "cooldown_type": "👤",
                "reward": "6T",
                "url": "https://discordservers.com/server/960665311701528596/bump",
            },
            "dsme": {
                "name": "DSME",
                "cooldown": "6h",
                "cooldown_type": "👤",
                "reward": "3T",
                "url": "https://discords.com/servers/960665311701528596/upvote",
            },
        }[service]

    @commands.hybrid_command(
        name="bump", description="Pokazuje status wszystkich dostępnych bumpów"
    )
    @commands.cooldown(1, 5, commands.BucketType.user)  # Prevent spam
    @app_commands.describe(
        member="Użytkownik, którego status chcesz sprawdzić (opcjonalne)"
    )
    async def show_bump_status(
        self, ctx: commands.Context, member: discord.Member = None
    ):
        """Show status of all available bump services."""
        # Defer the response since we'll be making database queries
        await ctx.defer()

        # Use provided member or command author
        target = member or ctx.author

        # Get member's current T time
        async with self.bot.get_db() as session:
            db_member = await session.get(Member, target.id)
            current_t = "0T"
            if db_member and db_member.voice_bypass_until:
                now = datetime.now(timezone.utc)
                if db_member.voice_bypass_until > now:
                    remaining = db_member.voice_bypass_until - now
                    current_t = f"{int(remaining.total_seconds() // 3600)}T"

        services = ["disboard", "dzik", "discadia", "discordservers", "dsme"]
        available_services = []
        waiting_services = []

        for service in services:
            status = await self.get_service_status(service, target.id)
            if status["available"]:
                available_services.append((service, status))
            else:
                waiting_services.append((service, status))

        # Sort waiting services by remaining time (longest first)
        waiting_services.sort(key=lambda x: x[1]["next_available"], reverse=True)

        embed = discord.Embed(title="Status Bumpów", color=ctx.author.color)

        # Set author with user avatar
        embed.set_author(name=target.display_name, icon_url=target.display_avatar.url)

        # Get "Wybierz swój plan" text first but don't set it yet
        _, plan_text = MessageSender._get_premium_text(ctx, None)

        # Add waiting services first
        if waiting_services:
            waiting_text = []
            for service, status in waiting_services:
                emoji = self.get_service_emoji(service)
                details = self.get_service_details(service)
                next_time = discord.utils.format_dt(status["next_available"], "R")
                service_text = f"{emoji} **{details['name']}** • {details['cooldown']} {details['cooldown_type']} • {details['reward']}"
                if "command" in details:
                    service_text += f"\nDostępne: {next_time} • `{details['command']}`"
                elif "url" in details:
                    service_text += (
                        f"\nDostępne: {next_time} • [Zagłosuj]({details['url']})"
                    )
                waiting_text.append(service_text)

            if waiting_text:
                embed.add_field(
                    name="⏳ Oczekujące", value="\n".join(waiting_text), inline=False
                )

        # Add available services
        if available_services:
            available_text = []
            for service, status in available_services:
                emoji = self.get_service_emoji(service)
                details = self.get_service_details(service)
                service_text = f"{emoji} **{details['name']}** • {details['cooldown']} {details['cooldown_type']} • {details['reward']} • "
                if "command" in details:
                    service_text += f"`{details['command']}`"
                elif "url" in details:
                    service_text += f"[Zagłosuj]({details['url']})"
                available_text.append(service_text)

            if available_text:
                embed.add_field(
                    name="✅ Dostępne teraz",
                    value="\n".join(available_text),
                    inline=False,
                )

        # Create view with buttons for voting services
        view = None
        if available_services:
            view = discord.ui.View()
            for service, status in available_services:
                details = self.get_service_details(service)
                if "url" in details:
                    emoji = self.get_service_emoji(service)
                    button = discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        label=details["name"],
                        emoji=emoji,
                        url=details["url"],
                    )
                    view.add_item(button)

        # Set footer with T count
        embed.set_footer(text=f"Posiadasz {current_t}")

        # Add "Wybierz swój plan" text as the last field
        if plan_text:
            embed.add_field(name="\u200b", value=plan_text, inline=False)

        # Send the embed in the channel where the command was used
        await ctx.send(embed=embed, view=view)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Handle DSME vote role changes"""
        if after.guild.id != self.bot.guild_id:
            return

        # Check if the member received the DSME vote role
        dsme_role = discord.utils.get(after.guild.roles, id=DSME_ROLE_ID)
        if dsme_role and dsme_role not in before.roles and dsme_role in after.roles:
            async with self.bot.get_db() as session:
                cooldown = self.get_service_cooldown("dsme")
                can_use, log = await NotificationLogQueries.process_service_usage(
                    session,
                    "dsme",
                    after.id,
                    after.id,
                    cooldown,  # Używamy after.id zamiast guild.id
                )

                if not can_use:
                    logger.info(
                        f"User {after.id} attempted DSME vote but cooldown not finished"
                    )
                    # Remove the role since they can't use it yet
                    try:
                        await after.remove_roles(dsme_role)
                        logger.info(
                            f"Removed DSME role from {after.id} due to cooldown"
                        )
                    except discord.HTTPException as e:
                        logger.error(f"Failed to remove DSME role from {after.id}: {e}")
                    return

                # Add T time
                duration = self.get_service_duration("dsme")
                if await MemberQueries.add_bypass_time(session, after.id, duration):
                    logger.info(f"Added {duration}h T to user {after.id} for DSME vote")
                    await session.commit()

                    # Get the channel to send the marketing message
                    channel = self.bot.get_channel(self.notification_channel_id)
                    if channel:
                        await self.send_bump_marketing(channel, "dsme", after)

                    # Remove the role after processing
                    try:
                        await after.remove_roles(dsme_role)
                        logger.info(
                            f"Removed DSME role from {after.id} after processing"
                        )
                    except discord.HTTPException as e:
                        logger.error(f"Failed to remove DSME role from {after.id}: {e}")

    async def get_service_status(self, service: str, user_id: int) -> dict:
        """Get status of a bump service for a user"""
        now = datetime.now(timezone.utc)
        cooldown = self.get_service_cooldown(service)
        duration = self.get_service_duration(service)

        async with self.bot.get_db() as session:
            # For global services, use guild_id instead of user ID
            check_id = self.bot.guild_id if service in GLOBAL_SERVICES else user_id
            log = await NotificationLogQueries.get_notification_log(
                session, check_id, service
            )

            if not log or now - log.sent_at > timedelta(hours=cooldown):
                return {
                    "available": True,
                    "next_available": now,
                    "cooldown": cooldown,
                    "duration": duration,
                }
            else:
                next_available = log.sent_at + timedelta(hours=cooldown)
                return {
                    "available": False,
                    "next_available": next_available,
                    "cooldown": cooldown,
                    "duration": duration,
                }

    async def send_notification(self, member, message):
        """Send notification based on test_mode setting"""
        # Format message with user mention
        formatted_message = message.format(mention=member.mention)

        if self.test_mode:
            # During testing, send all messages to test channel
            channel = self.bot.get_channel(self.notification_channel_id)
            if channel:
                try:
                    await channel.send(formatted_message)
                    logger.info(
                        f"[TEST MODE] Sent notification to test channel {channel.id}"
                    )
                    return True
                except discord.HTTPException as e:
                    logger.error(f"Failed to send to test channel: {e}")
                    return False

            logger.error(f"Could not find test channel {self.notification_channel_id}")
            return False

        # Normal mode - try voice channel first, then DM
        if member.voice and member.voice.channel:
            try:
                await member.voice.channel.send(formatted_message)
                logger.info(
                    f"Sent notification to voice channel {member.voice.channel.id}"
                )
                return True
            except discord.HTTPException as e:
                logger.error(f"Failed to send notification to voice channel: {e}")

        # If not in voice channel or voice channel send failed, try DM
        try:
            await member.send(formatted_message)
            logger.info(f"Sent notification to user DM {member.id}")
            return True
        except discord.Forbidden:
            logger.warning(f"Could not send DM to user {member.id}")
        except discord.HTTPException as e:
            logger.error(f"Failed to send DM: {e}")

        # If both voice and DM failed, send to test channel as last resort
        channel = self.bot.get_channel(self.notification_channel_id)
        if channel:
            try:
                await channel.send(f"[DM nie działa] {formatted_message}")
                logger.info(
                    f"Sent notification to test channel as fallback {channel.id}"
                )
                return True
            except discord.HTTPException as e:
                logger.error(f"Failed to send to test channel: {e}")

        return False


async def setup(bot):
    """Add the cog to the bot."""
    await bot.add_cog(OnBumpEvent(bot))
