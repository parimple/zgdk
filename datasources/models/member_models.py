"""
Member-related SQLAlchemy models.
"""

from datetime import datetime
from sqlalchemy import (
    BigInteger,
    DateTime,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, MEMBER_ID, ROLE_ID


class Member(Base):
    """Member Model"""

    __tablename__ = "members"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    first_inviter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("members.id"), nullable=True
    )
    current_inviter_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("members.id"), nullable=True
    )
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    rejoined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    wallet_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    voice_bypass_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    first_inviter: Mapped["Member"] = relationship(
        "Member",
        backref="initial_invited_members",
        foreign_keys=[first_inviter_id],
        remote_side=[id],
    )
    current_inviter: Mapped["Member"] = relationship(
        "Member",
        backref="current_invited_members",
        foreign_keys=[current_inviter_id],
        remote_side=[id],
    )
    created_invites: Mapped[list["Invite"]] = relationship(
        "Invite", back_populates="creator", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Member(id={self.id})>"


class MemberRole(Base):
    """MemberRole Model"""

    __tablename__ = "member_roles"
    member_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(MEMBER_ID), primary_key=True
    )
    role_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(ROLE_ID), primary_key=True
    )
    expiration_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    member: Mapped[Member] = relationship("Member", backref="assigned_roles")
    role: Mapped["Role"] = relationship("Role", backref="assigned_to_members")

    def __repr__(self) -> str:
        return f"<MemberRole(member_id={self.member_id}, role_id={self.role_id})>"