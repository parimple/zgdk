"""
Query classes package for the ZGDK Discord bot.

This module provides centralized imports for all query classes,
maintaining backward compatibility for existing imports.
"""

from .autokick_queries import AutoKickQueries
from .channel_queries import ChannelPermissionQueries
from .invite_queries import InviteQueries
from .member_queries import MemberQueries
from .message_queries import MessageQueries
from .moderation_queries import ModerationLogQueries
from .notification_queries import NotificationLogQueries
from .payment_queries import HandledPaymentQueries
from .role_queries import RoleQueries

# Activity/ranking system functions
from .activity_queries import (
    add_activity_points,
    cleanup_old_activity_data,
    ensure_member_exists,
    get_activity_leaderboard_with_names,
    get_member_activity_breakdown,
    get_member_ranking_position,
    get_member_total_points,
    get_ranking_tier,
    get_top_members_by_points,
    reset_daily_activity_points,
)

__all__ = [
    # Query classes
    "AutoKickQueries",
    "ChannelPermissionQueries",
    "HandledPaymentQueries",
    "InviteQueries",
    "MemberQueries",
    "MessageQueries",
    "ModerationLogQueries",
    "NotificationLogQueries",
    "RoleQueries",
    
    # Activity/ranking functions
    "add_activity_points",
    "cleanup_old_activity_data",
    "ensure_member_exists",
    "get_activity_leaderboard_with_names",
    "get_member_activity_breakdown",
    "get_member_ranking_position",
    "get_member_total_points",
    "get_ranking_tier",
    "get_top_members_by_points",
    "reset_daily_activity_points",
]