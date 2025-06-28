"""Message repository implementation for message tracking operations."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from core.repositories.base_repository import BaseRepository
from datasources.models import Message

logger = logging.getLogger(__name__)


class MessageRepository(BaseRepository):
    """Repository for message tracking operations."""

    def __init__(self, session: AsyncSession):
        super().__init__(Message, session)

    async def save_message(
        self,
        message_id: int,
        author_id: int,
        content: str,
        timestamp: datetime,
        channel_id: int,
        reply_to_message_id: Optional[int] = None,
    ) -> Message:
        """Save a message to the database."""
        try:
            message = Message(
                id=message_id,
                author_id=author_id,
                content=content,
                timestamp=timestamp,
                channel_id=channel_id,
                reply_to_message_id=reply_to_message_id,
            )
            self.session.add(message)
            await self.session.flush()

            self._log_operation(
                "save_message",
                message_id=message_id,
                author_id=author_id,
                channel_id=channel_id,
            )

            return message

        except Exception as e:
            self._log_error("save_message", e, message_id=message_id)
            raise

    async def get_message_by_id(self, message_id: int) -> Optional[Message]:
        """Get a message by its ID."""
        try:
            message = await self.session.get(Message, message_id)

            self._log_operation(
                "get_message_by_id",
                message_id=message_id,
                found=message is not None,
            )

            return message

        except Exception as e:
            self._log_error("get_message_by_id", e, message_id=message_id)
            return None

    async def get_messages_by_author(self, author_id: int, limit: int = 100) -> list[Message]:
        """Get messages by author ID."""
        try:
            from sqlalchemy import select

            result = await self.session.execute(
                select(Message).where(Message.author_id == author_id).order_by(Message.timestamp.desc()).limit(limit)
            )
            messages = list(result.scalars().all())

            self._log_operation(
                "get_messages_by_author",
                author_id=author_id,
                limit=limit,
                count=len(messages),
            )

            return messages

        except Exception as e:
            self._log_error("get_messages_by_author", e, author_id=author_id)
            return []

    async def get_messages_by_channel(
        self, channel_id: int, limit: int = 100, before: Optional[datetime] = None
    ) -> list[Message]:
        """Get messages from a specific channel."""
        try:
            from sqlalchemy import select

            query = select(Message).where(Message.channel_id == channel_id)

            if before:
                query = query.where(Message.timestamp < before)

            query = query.order_by(Message.timestamp.desc()).limit(limit)

            result = await self.session.execute(query)
            messages = list(result.scalars().all())

            self._log_operation(
                "get_messages_by_channel",
                channel_id=channel_id,
                limit=limit,
                count=len(messages),
            )

            return messages

        except Exception as e:
            self._log_error("get_messages_by_channel", e, channel_id=channel_id)
            return []

    async def count_messages_by_author(self, author_id: int, after: Optional[datetime] = None) -> int:
        """Count messages by author with optional date filter."""
        try:
            from sqlalchemy import func, select

            query = select(func.count(Message.id)).where(Message.author_id == author_id)

            if after:
                query = query.where(Message.timestamp > after)

            result = await self.session.execute(query)
            count = result.scalar() or 0

            self._log_operation(
                "count_messages_by_author",
                author_id=author_id,
                count=count,
            )

            return count

        except Exception as e:
            self._log_error("count_messages_by_author", e, author_id=author_id)
            return 0

    async def get_reply_chain(self, message_id: int, max_depth: int = 10) -> list[Message]:
        """Get the reply chain for a message."""
        try:
            messages = []
            current_id = message_id
            depth = 0

            while current_id and depth < max_depth:
                message = await self.get_message_by_id(current_id)
                if not message:
                    break

                messages.append(message)
                current_id = message.reply_to_message_id
                depth += 1

            self._log_operation(
                "get_reply_chain",
                message_id=message_id,
                chain_length=len(messages),
            )

            return messages

        except Exception as e:
            self._log_error("get_reply_chain", e, message_id=message_id)
            return []

    async def delete_message(self, message_id: int) -> bool:
        """Delete a message by ID."""
        try:
            message = await self.get_message_by_id(message_id)
            if not message:
                return False

            await self.session.delete(message)
            await self.session.flush()

            self._log_operation("delete_message", message_id=message_id, success=True)

            return True

        except Exception as e:
            self._log_error("delete_message", e, message_id=message_id)
            return False
