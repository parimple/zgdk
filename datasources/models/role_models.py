"""
Role models for the database.
"""

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Role(Base):
    """Role Model"""

    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role_type: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<Role(id={self.id})>"