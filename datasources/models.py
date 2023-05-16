"""Models for the datasources package"""
from sqlalchemy import BigInteger, Column, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

MEMBER_ID = "members.id"
ROLE_ID = "roles.id"


class Member(Base):
    """Member Model"""

    __tablename__ = "members"
    id = Column(BigInteger, primary_key=True)
    first_inviter_id = Column(BigInteger, ForeignKey(MEMBER_ID), nullable=True)
    current_inviter_id = Column(BigInteger, ForeignKey(MEMBER_ID), nullable=True)
    joined_at = Column(DateTime, nullable=True)
    rejoined_at = Column(DateTime, nullable=True)
    wallet_balance = Column(Integer, nullable=False, default=0)

    first_inviter = relationship("Member", remote_side=[id], backref="initial_invited_members")
    current_inviter = relationship("Member", remote_side=[id], backref="current_invited_members")

    def __repr__(self) -> str:
        return f"<Member(id={self.id})>"


class Role(Base):
    """Role Model"""

    __tablename__ = "roles"
    id = Column(BigInteger, primary_key=True)
    name = Column(String, nullable=False)
    role_type = Column(String, nullable=False)

    def __repr__(self) -> str:
        return f"<Role(id={self.id})>"


class MemberRole(Base):
    """MemberRole Model"""

    __tablename__ = "member_roles"
    member_id = Column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    member = relationship("Member", backref="assigned_roles")
    role_id = Column(BigInteger, ForeignKey(ROLE_ID), primary_key=True)
    role = relationship("Role", backref="assigned_to_members")
    expiration_date = Column(DateTime, nullable=True)


class ChannelPermission(Base):
    """ChannelPermission Model"""

    __tablename__ = "channel_permissions"
    member_id = Column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    member = relationship("Member", foreign_keys=[member_id], backref="channel_permissions")
    target_id = Column(BigInteger, nullable=False, primary_key=True)  # Role or Member ID
    permissions_value = Column(BigInteger, nullable=False, default=0)

    def __repr__(self) -> str:
        return (
            f"<ChannelPermission(member_id={self.member_id}, "
            f"target_id={self.target_id}, permissions_value={self.permissions_value})>"
        )


class Activity(Base):
    """Activity Model"""

    __tablename__ = "activity"
    member_id = Column(BigInteger, ForeignKey(MEMBER_ID), primary_key=True)
    member = relationship("Member", backref="activities")
    date = Column(Date, primary_key=True)
    points = Column(Integer, nullable=False, default=0)
    activity_type = Column(String, primary_key=True)  # 'text', 'voice', 'bonus'

    def __repr__(self) -> str:
        return (
            f"<Activity(member_id={self.member_id}, date={self.date}, "
            f"points={self.points}, activity_type={self.activity_type})>"
        )


class HandledPayment(Base):
    """HandledPayment Model"""

    __tablename__ = "handled_payments"

    id = Column(BigInteger, primary_key=True)
    member_id = Column(BigInteger, nullable=True)
    member = relationship("Member", backref="handled_payments")
    name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    paid_at = Column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<HandledPayment(id={self.id}, member_id={self.member_id}, "
            f"name={self.name}, amount={self.amount}, paid_at={self.paid_at})>"
        )
