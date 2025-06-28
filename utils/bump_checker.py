"""Utility for checking bump service statuses."""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


class BumpChecker:
    """Class for checking bump service statuses."""

    GLOBAL_SERVICES = ["disboard"]  # tylko Disboard jest globalny

    def __init__(self, bot):
        self.bot = bot

    def get_service_emoji(self, service: str) -> str:
        """Get emoji for a service from config"""
        emojis = self.bot.config.get("emojis", {})
        
        # Fallback to unicode if custom emoji not found
        fallbacks = {
            "disboard": "🇩",
            "dzik": "🐗",
            "discadia": "🌟",
            "discordservers": "📊",
            "dsme": "📈",
        }
        
        return emojis.get(service, fallbacks.get(service, ""))

    @staticmethod
    def get_service_details(service: str) -> dict:
        """Get details for a service"""
        return {
            "disboard": {
                "name": "Disboard",
                "cooldown": "2h",
                "cooldown_type": "🌐",
                "reward": "3T",
                "command": "/bump",
            },
            "dzik": {
                "name": "Dzik",
                "cooldown": "3h",
                "cooldown_type": "👤",
                "reward": "3T",
                "command": "/bump",
            },
            "discadia": {
                "name": "Discadia",
                "cooldown": "24h",
                "cooldown_type": "👤",
                "reward": "6T",
                "url": "https://discadia.com/vote/polska/",
            },
            "discordservers": {
                "name": "DiscordServers",
                "cooldown": "12h",
                "cooldown_type": "👤",
                "reward": "6T",
                "url": "https://discordservers.com/server/960665311701528596/bump",
            },
            "dsme": {
                "name": "DSME",
                "cooldown": "6h",
                "cooldown_type": "👤",
                "reward": "3T",
                "url": "https://discords.com/servers/960665311701528596/upvote",
            },
        }[service]

    async def get_service_status(self, service: str, user_id: int) -> dict:
        """Get status of a bump service for a user"""
        now = datetime.now(timezone.utc)
        cooldown = self.bot.config["bypass"]["cooldown"].get(service, 24)
        duration = self.bot.config["bypass"]["duration"]["services"].get(service, 3)

        async with self.bot.get_db() as session:
            # For global services, use guild_id instead of user ID
            check_id = self.bot.guild_id if service in self.GLOBAL_SERVICES else user_id
            from core.repositories import NotificationRepository

            notification_repo = NotificationRepository(session)
            log = await notification_repo.get_notification_log(
                check_id, service
            )

            if not log or now - log.sent_at > timedelta(hours=cooldown):
                return {
                    "available": True,
                    "next_available": now,
                    "cooldown": cooldown,
                    "duration": duration,
                }
            else:
                next_available = log.sent_at + timedelta(hours=cooldown)
                return {
                    "available": False,
                    "next_available": next_available,
                    "cooldown": cooldown,
                    "duration": duration,
                }
