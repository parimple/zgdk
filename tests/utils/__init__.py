"""
Test utilities
"""
from .commands_stub import install_commands_stub
from .mock_helpers import (
    create_shop_cog_with_mocks,
    make_async_cm,
    make_mock_bot,
    make_mock_context,
    make_mock_member,
    make_mock_user,
    patch_shop_queries,
)

__all__ = [
    'make_async_cm',
    'make_mock_bot',
    'make_mock_context',
    'make_mock_user',
    'make_mock_member',
    'patch_shop_queries',
    'create_shop_cog_with_mocks',
    'install_commands_stub'
]

# New test utilities for command testing
try:
    pass

    __all__.extend([
        "TestClient",
        "assert_user_mentioned",
        "assert_has_timestamp",
        "assert_premium_info"
    ])
except ImportError:
    pass  # New utilities not yet created
