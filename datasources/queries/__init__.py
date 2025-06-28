"""
Query classes package for the ZGDK Discord bot.

This module provides centralized imports for all query classes,
maintaining backward compatibility for existing imports.
"""

from .autokick_queries import AutoKickQueries
from .channel_queries import ChannelPermissionQueries
from .invite_queries import InviteQueries

# Use adapters for migrated queries
try:
    from core.adapters.query_to_repository_adapter import MemberQueriesAdapter as MemberQueries
    from core.adapters.query_to_repository_adapter import RoleQueriesAdapter as RoleQueries
    from core.adapters.query_to_repository_adapter import HandledPaymentQueriesAdapter as HandledPaymentQueries
    from core.adapters.query_to_repository_adapter import MessageQueriesAdapter as MessageQueries
    from core.adapters.query_to_repository_adapter import ModerationLogQueriesAdapter as ModerationLogQueries
except ImportError:
    # Fallback to original if adapter not available
    from .member_queries import MemberQueries
    from .role_queries import RoleQueries
    from .payment_queries import HandledPaymentQueries
    from .message_queries import MessageQueries
    from .moderation_queries import ModerationLogQueries

from .notification_queries import NotificationLogQueries

# Activity/ranking system functions
try:
    # Use adapters for migrated activity functions
    from core.adapters.query_to_repository_adapter import ActivityQueriesAdapter
    add_activity_points = ActivityQueriesAdapter.add_activity_points
    ensure_member_exists = ActivityQueriesAdapter.ensure_member_exists
    get_member_ranking_position = ActivityQueriesAdapter.get_member_ranking_position
    get_member_total_points = ActivityQueriesAdapter.get_member_total_points
    get_top_members_by_points = ActivityQueriesAdapter.get_top_members_by_points
    
    # Import remaining functions from original
    from .activity_queries import (
        cleanup_old_activity_data,
        get_activity_leaderboard_with_names,
        get_member_activity_breakdown,
        get_ranking_tier,
        reset_daily_activity_points,
    )
except ImportError:
    # Fallback to original if adapter not available
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