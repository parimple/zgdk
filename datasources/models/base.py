"""
Base configuration and constants for SQLAlchemy models.
"""

from datetime import datetime, timezone

from sqlalchemy.orm import declarative_base

# SQLAlchemy Base
Base = declarative_base()

# Foreign Key constants
MEMBER_ID = "members.id"
ROLE_ID = "roles.id"

# Utility function for default datetime


def utc_now() -> datetime:
    """Return current UTC datetime"""
    return datetime.now(timezone.utc)
