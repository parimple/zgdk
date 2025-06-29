"""
Notification-related SQLAlchemy models.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import MEMBER_ID, Base

if TYPE_CHECKING:
    from .member_models import Member


class NotificationLog(Base):
    """NotificationLog Model"""

    __tablename__ = "notification_logs"
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    notification_tag: Mapped[str] = mapped_column(String, primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    notification_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    member: Mapped["Member"] = relationship("Member", backref="notification_logs")

    __table_args__ = (PrimaryKeyConstraint("member_id", "notification_tag", name="notification_log_pk"),)

    def __repr__(self) -> str:
        return f"<NotificationLog(member_id={self.member_id}, notification_tag={self.notification_tag}, sent_at={self.sent_at}, notification_count={self.notification_count}, opted_out={self.opted_out})>"
