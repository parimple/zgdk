"""SQLAlchemy models for the database."""
from __future__ import annotations

import datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

Base = declarative_base()

MEMBER_ID = "members.id"
ROLE_ID = "roles.id"


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
    joined_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    rejoined_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)
    wallet_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    first_inviter: Mapped[Member] = relationship(
        "Member",
        backref=backref("initial_invited_members"),
        foreign_keys=[first_inviter_id],
        remote_side=[id],
    )
    current_inviter: Mapped[Member] = relationship(
        "Member",
        backref=backref("current_invited_members"),
        foreign_keys=[current_inviter_id],
        remote_side=[id],
    )

    def __repr__(self) -> str:
        return f"<Member(id={self.id})>"


class Role(Base):
    """Role Model"""

    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    role_type: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<Role(id={self.id})>"


class MemberRole(Base):
    """MemberRole Model"""

    __tablename__ = "member_roles"
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(ROLE_ID), primary_key=True)
    expiration_date: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=True)

    member: Mapped[Member] = relationship("Member", backref="assigned_roles")
    role: Mapped[Role] = relationship("Role", backref="assigned_to_members")

    def __repr__(self) -> str:
        return f"<MemberRole(member_id={self.member_id}, role_id={self.role_id})>"


class ChannelPermission(Base):
    """ChannelPermission Model"""

    __tablename__ = "channel_permissions"
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    target_id: Mapped[int] = mapped_column(
        BigInteger, nullable=False, primary_key=True
    )  # Role or Member ID
    permissions_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    member: Mapped[list[Member]] = relationship(
        "Member", foreign_keys=[member_id], backref="channel_permissions"
    )

    def __repr__(self) -> str:
        return f"<ChannelPermission(member_id={self.member_id}, target_id={self.target_id})>"


class Activity(Base):
    """Activity Model"""

    __tablename__ = "activity"
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    date: Mapped[datetime.date] = mapped_column(Date, nullable=False, primary_key=True)
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activity_type: Mapped[str] = mapped_column(
        String, nullable=False, primary_key=True
    )  # 'text', 'voice', 'bonus'

    member: Mapped[list[Member]] = relationship("Member", backref="activities")

    def __repr__(self) -> str:
        return (
            f"<Activity(member_id={self.member_id}, date={self.date}, type={self.activity_type})>"
        )


class HandledPayment(Base):
    """HandledPayment Model"""

    __tablename__ = "handled_payments"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    member_id: Mapped[int] = mapped_column(BigInteger, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    paid_at: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False)
    payment_type: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<HandledPayment(id={self.id})>"
