"""Models for the zaGadka bot database"""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Member(Base):  # pylint: disable=too-few-public-methods
    """Member Model"""

    __tablename__ = "members"
    id = Column(BigInteger, primary_key=True)
    inviter_legacy_id = Column(BigInteger, ForeignKey("member.id"), nullable=True)
    inviter_id = Column(BigInteger, ForeignKey("member.id"), nullable=True)
    joined_at = Column(DateTime, nullable=True)
    joined_rec_at = Column(DateTime, nullable=True)
    wallet = Column(Integer, nullable=False, default=0)

    inviter_legacy = relationship("Member", remote_side=[id], backref="invited_legacy")
    inviter = relationship("Member", remote_side=[id], backref="invited")

    def __repr__(self):
        return f"<Member(id={self.id})>"


class MemberMember(Base):  # pylint: disable=too-few-public-methods
    """Member_Member Model"""

    __tablename__ = "member_member"
    id = Column(BigInteger, primary_key=True)
    member_id = Column(BigInteger, ForeignKey("member.id"), nullable=False)
    member = relationship("Member", backref="members")
    member_member_id = Column(BigInteger, ForeignKey("member.id"), nullable=False)
    member_member = relationship("Member", backref="members_members")

    def __repr__(self):
        return f"<MemberMember(id={self.id})>"


class Permission(Base):  # pylint: disable=too-few-public-methods
    """Permission Model"""

    __tablename__ = "permissions"
    id = Column(BigInteger, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(255), nullable=False)

    def __repr__(self):
        return f"<Permission(id={self.id})>"
