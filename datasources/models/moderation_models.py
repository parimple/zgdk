"""
Moderation-related SQLAlchemy models.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, MEMBER_ID


class AutoKick(Base):
    """AutoKick Model for storing automatic kick settings"""

    __tablename__ = "autokicks"
    owner_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MEMBER_ID), primary_key=True
    )
    target_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MEMBER_ID), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )

    owner: Mapped["Member"] = relationship(
        "Member", foreign_keys=[owner_id], backref="owned_autokicks"
    )
    target: Mapped["Member"] = relationship(
        "Member", foreign_keys=[target_id], backref="autokicks_targeting"
    )

    def __repr__(self) -> str:
        return f"<AutoKick(owner_id={self.owner_id}, target_id={self.target_id})>"


class ModerationLog(Base):
    """ModerationLog Model for storing moderation action history"""

    __tablename__ = "moderation_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    target_user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MEMBER_ID), nullable=False
    )
    moderator_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MEMBER_ID), nullable=False
    )
    action_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # 'mute', 'unmute', 'kick', 'ban'
    mute_type: Mapped[str] = mapped_column(
        String, nullable=True
    )  # 'nick', 'img', 'txt', 'live', 'rank'
    duration_seconds: Mapped[int] = mapped_column(
        Integer, nullable=True
    )  # NULL = permanentny
    reason: Mapped[str] = mapped_column(String, nullable=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    target_user: Mapped["Member"] = relationship(
        "Member", foreign_keys=[target_user_id], backref="moderation_logs_received"
    )
    moderator: Mapped["Member"] = relationship(
        "Member", foreign_keys=[moderator_id], backref="moderation_logs_given"
    )

    def __repr__(self) -> str:
        return f"<ModerationLog(id={self.id}, action={self.action_type}, target={self.target_user_id}, moderator={self.moderator_id})>"