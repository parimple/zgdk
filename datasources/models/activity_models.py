"""
Activity models for the database.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import MEMBER_ID, Base

if TYPE_CHECKING:
    from .member_models import Member


class Activity(Base):
    """Activity Model"""

    __tablename__ = "activity"
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, primary_key=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activity_type: Mapped[str] = mapped_column(String, nullable=False, primary_key=True)  # 'text', 'voice', 'bonus'

    member: Mapped["Member"] = relationship("Member", backref="activities")

    def __repr__(self) -> str:
        return f"<Activity(member_id={self.member_id}, date={self.date}, type={self.activity_type})>"
