"""Import the refactored admin info module."""

# Re-export everything from the modular structure
from .admin import AdminInfoCog, setup

# Keep helper function for backward compatibility
from .admin.helpers import remove_premium_role_mod_permissions

__all__ = ["AdminInfoCog", "setup", "remove_premium_role_mod_permissions"]