"""
Decorators for command permissions.
This file exists to maintain compatibility with existing code.
Actual implementations are in permissions.py.
"""

from utils.permissions import is_zagadka_owner as _is_zagadka_owner

# Re-export is_zagadka_owner with the same functionality
is_zagadka_owner = _is_zagadka_owner
