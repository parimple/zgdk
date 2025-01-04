"""
SQLAlchemy models for the database.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    PrimaryKeyConstraint,
    String,
)
from sqlalchemy.orm import Mapped, declarative_base, mapped_column, relationship

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
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    rejoined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    wallet_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

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
    expiration_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

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
    allow_permissions_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    deny_permissions_value: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    last_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )

    member: Mapped[Member] = relationship(
        "Member", foreign_keys=[member_id], backref="channel_permissions"
    )

    def __repr__(self) -> str:
        return f"<ChannelPermission(member_id={self.member_id}, target_id={self.target_id}, last_updated_at={self.last_updated_at})>"


class Activity(Base):
    """Activity Model"""

    __tablename__ = "activity"
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, primary_key=True
    )
    points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    activity_type: Mapped[str] = mapped_column(
        String, nullable=False, primary_key=True
    )  # 'text', 'voice', 'bonus'

    member: Mapped[Member] = relationship("Member", backref="activities")

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
    paid_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    payment_type: Mapped[str] = mapped_column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<HandledPayment(id={self.id})>"


class NotificationLog(Base):
    """NotificationLog Model"""

    __tablename__ = "notification_logs"
    member_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    notification_tag: Mapped[str] = mapped_column(String, primary_key=True)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )
    opted_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    member: Mapped[Member] = relationship("Member", backref="notification_logs")

    __table_args__ = (
        PrimaryKeyConstraint("member_id", "notification_tag", name="notification_log_pk"),
    )

    def __repr__(self) -> str:
        return f"<NotificationLog(member_id={self.member_id}, notification_tag={self.notification_tag}, sent_at={self.sent_at}, opted_out={self.opted_out})>"


class Message(Base):
    """Message Model"""

    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # Discord message ID
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reply_to_message_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("messages.id"), nullable=True
    )

    author: Mapped[Member] = relationship("Member", backref="messages")
    reply_to_message: Mapped["Message"] = relationship(
        "Message", remote_side=[id], backref="replies"
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, author_id={self.author_id}, content={self.content})>"


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


class AutoKick(Base):
    """AutoKick Model for storing automatic kick settings"""

    __tablename__ = "autokicks"
    owner_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    target_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.now(timezone.utc)
    )

    owner: Mapped[Member] = relationship(
        "Member", foreign_keys=[owner_id], backref="owned_autokicks"
    )
    target: Mapped[Member] = relationship(
        "Member", foreign_keys=[target_id], backref="autokicks_targeting"
    )

    def __repr__(self) -> str:
        return f"<AutoKick(owner_id={self.owner_id}, target_id={self.target_id})>"
