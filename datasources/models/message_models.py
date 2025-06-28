"""
Message-related SQLAlchemy models.
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, MEMBER_ID


class Message(Base):
    """Message Model"""

    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Discord message ID
    author_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MEMBER_ID), nullable=False
    )
    content: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reply_to_message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id"), nullable=True
    )

    author: Mapped["Member"] = relationship("Member", backref="messages")
    reply_to_message: Mapped["Message"] = relationship(
        "Message", remote_side=[id], backref="replies"
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, author_id={self.author_id}, content={self.content})>"