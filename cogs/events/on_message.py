"""On Message Event"""

import logging
from datetime import datetime, timezone

from discord import Message
from discord.ext import commands

from core.repositories import MessageRepository

logger = logging.getLogger(__name__)


class OnMessageEvent(commands.Cog):
    """Class for handling the event when a message is sent in the Discord server."""

    def __init__(self, bot):
        self.bot = bot
        self.allowed_channels = [960665312200626196]

    @commands.Cog.listener()
    async def on_message(self, message: Message):
        """
        Event triggered when a message is sent in the guild.

        This method saves the message to the database with the user ID, message content,
        and whether it is a reply, but only if the message is from an allowed channel.

        :param message: The message that was sent
        """
        # Temporarily disabled - remove this return to enable message saving
        return

        if message.author.bot:
            return

        if message.channel.id not in self.allowed_channels:
            return

        reply_to_message_id = message.reference.message_id if message.reference else None

        async with self.bot.get_db() as session:
            message_repo = MessageRepository(session)
            await message_repo.save_message(
                message_id=message.id,
                author_id=message.author.id,
                content=message.content,
                timestamp=datetime.now(timezone.utc),
                channel_id=message.channel.id,
                reply_to_message_id=reply_to_message_id,
            )
            await session.commit()

        logger.info("Message from %s saved to database: %s", message.author.id, message.content)


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnMessageEvent(bot))
