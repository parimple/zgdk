"""Models for the datasources package"""
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Member(Base):  # pylint: disable=too-few-public-methods
    """Member Model"""

    __tablename__ = "members"
    id = Column(BigInteger, primary_key=True)
    inviter_legacy_id = Column(BigInteger, ForeignKey("members.id"), nullable=True)
    inviter_id = Column(BigInteger, ForeignKey("members.id"), nullable=True)
    joined_at = Column(DateTime, nullable=True)
    joined_rec_at = Column(DateTime, nullable=True)
    wallet = Column(Integer, nullable=False, default=0)

    inviter_legacy = relationship("Member", remote_side=[id], backref="legacy_invitees")
    inviter = relationship("Member", remote_side=[id], backref="direct_invitees")

    def __repr__(self) -> str:
        return f"<Member(id={self.id})>"


class MemberMember(Base):  # pylint: disable=too-few-public-methods
    """MemberMember Model"""

    __tablename__ = "member_connections"
    id = Column(BigInteger, primary_key=True)
    member_id = Column(BigInteger, ForeignKey("members.id"), nullable=False)
    member = relationship("Member", foreign_keys=[member_id], backref="connections")
    connected_member_id = Column(BigInteger, ForeignKey("members.id"), nullable=False)
    connected_member = relationship(
        "Member", foreign_keys=[connected_member_id], backref="connected_by"
    )

    def __repr__(self) -> str:
        return f"<MemberMember(id={self.id})>"


class Permission(Base):  # pylint: disable=too-few-public-methods
    """Permission Model"""

    __tablename__ = "permissions"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255), nullable=False)

    def __repr__(self) -> str:
        return f"<Permission(id={self.id})>"
