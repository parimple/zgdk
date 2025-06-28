"""
Models package for the ZGDK Discord bot.

This module provides centralized imports for all SQLAlchemy models,
maintaining backward compatibility for existing imports.
"""

# Activity models
from .activity_models import Activity

# Base and constants
from .base import MEMBER_ID, ROLE_ID, Base, utc_now

# Channel models
from .channel_models import ChannelPermission

# Invite models
from .invite_models import Invite

# Member models
from .member_models import Member, MemberRole

# Message models
from .message_models import Message

# Moderation models
from .moderation_models import AutoKick, ModerationLog

# Notification models
from .notification_models import NotificationLog

# Payment models
from .payment_models import HandledPayment

# Role models
from .role_models import Role

__all__ = [
    # Base and constants
    "Base",
    "MEMBER_ID",
    "ROLE_ID",
    "utc_now",
    # Member models
    "Member",
    "MemberRole",
    # Activity models
    "Activity",
    # Role models
    "Role",
    # Channel models
    "ChannelPermission",
    # Payment models
    "HandledPayment",
    # Notification models
    "NotificationLog",
    # Message models
    "Message",
    # Invite models
    "Invite",
    # Moderation models
    "AutoKick",
    "ModerationLog",
]
