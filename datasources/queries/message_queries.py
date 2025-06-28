"""
Message Queries for the database.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Message

logger = logging.getLogger(__name__)


class MessageQueries:
    """Class for Message Queries"""

    @staticmethod
    async def save_message(
        session: AsyncSession,
        message_id: int,
        author_id: int,
        content: str,
        timestamp: datetime,
        channel_id: int,
        reply_to_message_id: Optional[int] = None,
    ):
        """Save a message to the database"""
        message = Message(
            id=message_id,
            author_id=author_id,
            content=content,
            timestamp=timestamp,
            channel_id=channel_id,
            reply_to_message_id=reply_to_message_id,
        )
        session.add(message)
        await session.flush()
