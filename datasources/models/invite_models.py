"""
Invite-related SQLAlchemy models.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import MEMBER_ID, Base

if TYPE_CHECKING:
    from .member_models import Member


class Invite(Base):
    """Invite Model"""

    __tablename__ = "invites"
    id: Mapped[str] = mapped_column(String, primary_key=True)
    creator_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID))
    uses: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    creator: Mapped["Member"] = relationship("Member", back_populates="created_invites")

    def __repr__(self) -> str:
        return f"<Invite(id={self.id}, creator_id={self.creator_id}, uses={self.uses})>"
