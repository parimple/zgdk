"""
Channel-related SQLAlchemy models.
"""

from datetime import datetime, timezone

from sqlalchemy import BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import MEMBER_ID, Base


class ChannelPermission(Base):
    """ChannelPermission Model"""

    __tablename__ = "channel_permissions"
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    target_id: Mapped[int] = mapped_column(BigInteger, nullable=False, primary_key=True)  # Role or Member ID
    allow_permissions_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    deny_permissions_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )

    member: Mapped["Member"] = relationship("Member", foreign_keys=[member_id], backref="channel_permissions")

    def __repr__(self) -> str:
        return f"<ChannelPermission(member_id={self.member_id}, target_id={self.target_id}, last_updated_at={self.last_updated_at})>"
