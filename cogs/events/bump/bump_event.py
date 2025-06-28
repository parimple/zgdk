"""Main bump event handler."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from datasources.queries import MemberQueries, NotificationLogQueries
from utils.message_sender import MessageSender

from .constants import (
    DISCADIA,
    DISBOARD,
    DISCORDSERVERS,
    DSME,
    DZIK,
    SERVICE_COOLDOWNS,
)
from .handlers import (
    DiscadiaHandler,
    DisboardHandler,
    DiscordServersHandler,
    DSMEHandler,
    DzikHandler,
)
from .status import BumpStatusHandler

logger = logging.getLogger(__name__)


class OnBumpEvent(commands.Cog):
    """Class for handling bump-related events."""

    def __init__(self, bot):
        self.bot = bot
        self.message_sender = MessageSender(bot)
        
        # Initialize handlers
        self.disboard_handler = DisboardHandler(bot, self.message_sender)
        self.dzik_handler = DzikHandler(bot, self.message_sender)
        self.discadia_handler = DiscadiaHandler(bot, self.message_sender)
        self.discordservers_handler = DiscordServersHandler(bot, self.message_sender)
        self.dsme_handler = DSMEHandler(bot, self.message_sender)
        self.status_handler = BumpStatusHandler(bot, self.message_sender)

    @commands.Cog.listener()
    async def on_ready(self):
        """Event listener for when the bot is ready."""
        logger.info("Cog: bump module Loaded")

    async def handle_slash_command(self, message: discord.Message) -> bool:
        """Handle slash command interactions."""
        if not message.interaction:
            return False

        user = message.interaction.user
        if not user:
            return False

        # Handle /bump command from Disboard
        if (
            message.author.id == DISBOARD["id"]
            and message.interaction.name == "bump"
        ):
            await self.disboard_handler.handle(message)
            return True

        # Handle /bump command from Dzik
        if message.author.id == DZIK["id"] and message.interaction.name == "bump":
            await self.dzik_handler.handle(message)
            return True

        # Handle DiscordServers interactions
        if message.author.id == DISCORDSERVERS["id"]:
            await self.discordservers_handler.handle(message)
            return True

        return False

    async def handle_webhook_message(self, message: discord.Message) -> bool:
        """Handle webhook messages."""
        if not message.webhook_id:
            return False

        # Discadia webhooks
        if message.author.id == DISCADIA["id"]:
            # Check if it's a vote notification
            if "voted" in message.content.lower():
                await self.discadia_handler.handle_vote(message)
                return True

        return False

    async def handle_regular_message(self, message: discord.Message) -> bool:
        """Handle regular bot messages."""
        # Disboard messages
        if message.author.id == DISBOARD["id"]:
            if message.embeds:
                await self.disboard_handler.handle(message)
                return True

        # DSME messages
        if message.author.id == DSME["id"]:
            await self.dsme_handler.handle(message)
            return True

        return False

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Handle message edits (for services that edit messages)."""
        if after.author.bot and after.embeds:
            # Some services edit their messages after sending
            await self.on_message(after)

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Handle all messages for bump detection."""
        # Skip if no guild
        if not message.guild:
            return
            
        # Log all bot messages on bump channel - check if channel exists
        if message.channel and hasattr(message.channel, 'id'):
            if message.channel.id == 1326322441383051385 and message.author.bot:
                logger.info(f"Bot message on bump channel from {message.author.name} ({message.author.id})")
                if message.content:
                    logger.info(f"Content preview: {message.content[:100]}")
                if message.embeds:
                    logger.info(f"Has {len(message.embeds)} embeds")
            
        # Ignore messages from non-bots
        if not message.author.bot:
            return

        # Log bump bot messages for debugging
        bump_bots = {
            DISBOARD["id"]: "DISBOARD",
            DZIK["id"]: "DZIK",
            DISCADIA["id"]: "DISCADIA",
            DISCORDSERVERS["id"]: "DISCORDSERVERS",
            DSME["id"]: "DSME"
        }
        
        if message.author.id in bump_bots:
            bot_name = bump_bots[message.author.id]
            logger.info(f"{bot_name} message detected! Embeds: {len(message.embeds)}, Content: {message.content[:100]}")
            if message.embeds:
                embed = message.embeds[0]
                logger.info(f"{bot_name} embed - Title: {embed.title}, Description: {embed.description[:200] if embed.description else 'None'}")
            if message.interaction:
                logger.info(f"{bot_name} interaction - Name: {message.interaction.name}, User: {message.interaction.user}")

        try:
            # Try different handlers based on message type
            if await self.handle_slash_command(message):
                return
            
            if await self.handle_webhook_message(message):
                return
                
            if await self.handle_regular_message(message):
                return

        except Exception as e:
            logger.error(f"Error handling bump message: {e}", exc_info=True)

    async def send_bump_marketing(
        self, channel: discord.TextChannel, service: str, user: discord.Member
    ) -> None:
        """Send marketing message after bump."""
        marketing_messages = {
            "disboard": (
                "💎 **Chcesz więcej nagród?**\n"
                "Zagłosuj również na:\n"
                "• [Discadia](https://discadia.com/vote/polska/) - **6T**\n"
                "• [DiscordServers](https://discordservers.com/server/960665311701528596/bump) - **6T**\n"
                "• [DSME](https://discords.com/servers/960665311701528596/upvote) - **3T**"
            ),
            "dzik": (
                "💎 **Zbieraj więcej T!**\n"
                "Podbij serwer również na:\n"
                "• `/bump` (Disboard) - **3T**\n"
                "• [Discadia](https://discadia.com/vote/polska/) - **6T**\n"
                "• [DiscordServers](https://discordservers.com/server/960665311701528596/bump) - **6T**"
            ),
            "discadia": (
                "💎 **Nie zapomnij o innych serwisach!**\n"
                "• `/bump` (Disboard) - **3T**\n"
                "• `/bump` (Dzik) - **3T**\n"
                "• [DSME](https://discords.com/servers/960665311701528596/upvote) - **3T**"
            ),
            "discordservers": (
                "💎 **Więcej głosów = więcej T!**\n"
                "• `/bump` dla Disboard i Dzik\n"
                "• [Discadia](https://discadia.com/vote/polska/) - **6T**\n"
                "• [DSME](https://discords.com/servers/960665311701528596/upvote) - **3T**"
            ),
            "dsme": (
                "💎 **Pamiętaj o innych serwisach!**\n"
                "• `/bump` (Disboard & Dzik) - **3T** każdy\n"
                "• [Discadia](https://discadia.com/vote/polska/) - **6T**\n"
                "• [DiscordServers](https://discordservers.com/server/960665311701528596/bump) - **6T**"
            ),
        }

        if service in marketing_messages:
            embed = self.message_sender._create_embed(
                color="info",
                description=marketing_messages[service],
            )
            embed.set_author(
                name=user.display_name,
                icon_url=user.display_avatar.url if user.display_avatar else None
            )
            embed.set_footer(text="Czas T pozwala korzystać z komend głosowych!")
            
            await channel.send(embed=embed)

    @commands.hybrid_command(name="bump", description="Sprawdź status swoich bumpów")
    async def bump_status(self, ctx: commands.Context):
        """Check bump status for all services (text command)."""
        # Create fake interaction for compatibility
        class FakeResponse:
            def __init__(self, ctx):
                self.ctx = ctx
                
            async def defer(self):
                pass
                
            async def send_message(self, **kwargs):
                return await self.ctx.send(**kwargs)
        
        class FakeInteraction:
            def __init__(self, ctx):
                self.user = ctx.author
                self.guild = ctx.guild
                self.channel = ctx.channel
                self.followup = self
                self.response = FakeResponse(ctx)
                self._ctx = ctx
                
            async def send(self, **kwargs):
                return await self._ctx.send(**kwargs)

        fake_interaction = FakeInteraction(ctx)
        await self.status_handler.show_status(fake_interaction, ctx.author)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Check for bypass role changes and send notifications."""
        # Get bypass role IDs from config
        nitro_role_name = "♵"  # nitro booster
        server_booster_name = "♼"  # server booster
        
        nitro_role = discord.utils.get(after.guild.roles, name=nitro_role_name)
        booster_role = discord.utils.get(after.guild.roles, name=server_booster_name)
        
        if not nitro_role and not booster_role:
            return

        # Check if user got a booster role
        before_roles = set(before.roles)
        after_roles = set(after.roles)
        new_roles = after_roles - before_roles
        
        for role in new_roles:
            if role == nitro_role:
                await self.send_booster_notification(after, "Nitro Booster", 12)
            elif role == booster_role:
                await self.send_booster_notification(after, "Server Booster", 6)

    async def send_booster_notification(
        self, member: discord.Member, booster_type: str, hours: int
    ) -> None:
        """Send notification when user becomes a booster."""
        # Add bypass time
        async with self.bot.get_db() as session:
            db_member = await MemberQueries.get_or_add_member(session, member.id)
            
            current_time = datetime.now(timezone.utc)
            if db_member.bypass_expiry and db_member.bypass_expiry > current_time:
                db_member.bypass_expiry = db_member.bypass_expiry + timedelta(hours=hours)
            else:
                db_member.bypass_expiry = current_time + timedelta(hours=hours)
            
            await session.commit()

        # Send notification
        embed = self.message_sender._create_embed(
            color="success",
            title=f"🎉 Dziękujemy za zostanie {booster_type}!",
            description=(
                f"Otrzymujesz **{hours}T** czasu bypass!\n"
                f"Możesz teraz korzystać z komend głosowych bez ograniczeń."
            ),
        )
        embed.set_author(
            name=member.display_name,
            icon_url=member.display_avatar.url if member.display_avatar else None
        )
        
        # Try to send in a suitable channel
        if hasattr(self.bot, "config"):
            channel_id = self.bot.config.get("channels", {}).get("lounge")
            if channel_id:
                channel = member.guild.get_channel(channel_id)
                if channel:
                    await channel.send(content=member.mention, embed=embed)


async def setup(bot: commands.Bot):
    """Setup function to add the cog to the bot."""
    await bot.add_cog(OnBumpEvent(bot))