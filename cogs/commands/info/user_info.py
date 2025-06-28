"""Import the refactored user info module."""

# Re-export everything from the modular structure
from .user import UserInfoCog, setup

__all__ = ["UserInfoCog", "setup"]