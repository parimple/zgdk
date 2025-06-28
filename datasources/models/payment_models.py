"""
Payment-related SQLAlchemy models.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    DateTime,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class HandledPayment(Base):
    """HandledPayment Model"""

    __tablename__ = "handled_payments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    payment_type: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<HandledPayment(id={self.id})>"