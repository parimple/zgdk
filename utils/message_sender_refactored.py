"""Refactored MessageSender that combines all message sending functionality."""

from .message_senders.autokick import AutokickMessageSender
from .message_senders.base import BaseMessageSender
from .message_senders.general import GeneralMessageSender
from .message_senders.permissions import PermissionsMessageSender
from .message_senders.premium import PremiumMessageSender
from .message_senders.voice import VoiceMessageSender


class MessageSender(
    VoiceMessageSender,
    PermissionsMessageSender,
    AutokickMessageSender,
    PremiumMessageSender,
    GeneralMessageSender,
    BaseMessageSender,
):
    """
    Main MessageSender class that combines all message sending functionality.

    This class inherits from all specialized message sender classes to provide
    a unified interface for sending various types of messages in the bot.
    """

    def __init__(self, bot=None):
        """Initialize MessageSender with bot instance."""
        super().__init__(bot)

    # All methods are inherited from the specialized classes
    # This provides backward compatibility with existing code
