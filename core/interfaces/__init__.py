"""Interface definitions for dependency injection."""

# Export all interfaces for easy importing
from .activity_interfaces import ActivityType, IActivityTrackingService
from .base import IService
from .currency_interfaces import ICurrencyService
from .member_interfaces import IMemberService, IModerationService
from .messaging_interfaces import IEmbedBuilder, IMessageFormatter, IMessageSender, INotificationService
from .permission_interfaces import IPermissionService, PermissionLevel
from .premium_interfaces import IPremiumService
from .role_interfaces import IRoleService
from .team_interfaces import ITeamManagementService
from .unit_of_work import IUnitOfWork

__all__ = [
    # Base interface
    "IService",
    # Activity tracking
    "IActivityTrackingService",
    "ActivityType",
    # Currency
    "ICurrencyService",
    # Member management
    "IMemberService",
    "IModerationService",
    # Messaging
    "IEmbedBuilder",
    "IMessageSender",
    "INotificationService",
    "IMessageFormatter",
    # Permissions
    "IPermissionService",
    "PermissionLevel",
    # Premium
    "IPremiumService",
    # Roles
    "IRoleService",
    # Team management
    "ITeamManagementService",
    # Unit of work
    "IUnitOfWork",
]
