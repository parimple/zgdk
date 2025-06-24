"""
Manager classes for the ZGDK application.

This layer contains the core business logic of the application,
independent of the presentation and data access layers.
"""


class BaseManager:
    """Base class for all manager classes."""

    def __init__(self, bot):
        """Initialize the manager with a bot instance."""
        self.bot = bot
        self.config = bot.config
