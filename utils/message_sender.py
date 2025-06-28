"""Message sender utility for sending formatted messages.

This module has been refactored into smaller, specialized modules.
This file now serves as a compatibility layer.
"""

# Import the refactored MessageSender
from .message_sender_refactored import MessageSender

# Export for backward compatibility
__all__ = ["MessageSender"]
