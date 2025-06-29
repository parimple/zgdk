"""
Debug interface name resolution
"""
import sys

# Mock interfaces before import
from unittest.mock import MagicMock

sys.modules["core.interfaces.member_interfaces"] = MagicMock()

# Now import
from core.interfaces.member_interfaces import IMemberService  # noqa: E402

print(f"IMemberService: {IMemberService}")
print(f"IMemberService type: {type(IMemberService)}")
print(f"IMemberService has __name__: {hasattr(IMemberService, '__name__')}")
if hasattr(IMemberService, "__name__"):
    print(f"IMemberService.__name__: {IMemberService.__name__}")
print(f"str(IMemberService): {str(IMemberService)}")
