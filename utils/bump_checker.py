"""Utility for checking bump status and service availability."""

import logging
from datetime import datetime, timedelta, timezone

from datasources.queries import NotificationLogQueries

logger = logging.getLogger(__name__)


class BumpChecker:
    """Class for checking bump status and service availability."""

    def __init__(self, bot):
        self.bot = bot

    @staticmethod
    def get_service_emoji(service: str) -> str:
        """Get emoji for a service."""
        emojis = {
            "disboard": "<:botDisboard:1336275527241044069>",
            "dzik": "<:botDzik:1336275532991565824>",
            "discadia": "<:botDiscadia:1336275880703561758>",
            "discordservers": "<:botDiscordServers:1336322514170806383>",
            "dsme": "<:botDSME:1336311501765476352>",
        }
        return emojis.get(service, "")

    @staticmethod
    def get_service_details(service: str) -> dict:
        """Get details for a service."""
        details = {
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
        }
        return details.get(service, {})

    async def get_service_status(self, service: str, user_id: int) -> dict:
        """Get status for a service."""
        async with self.bot.get_db() as session:
            # For global services (like Disboard), use guild_id instead of user_id
            member_id = (
                self.bot.guild_id if service in NotificationLogQueries.GLOBAL_SERVICES else user_id
            )

            log = await NotificationLogQueries.get_service_notification_log(
                session, service, self.bot.guild_id, user_id
            )

            now = datetime.now(timezone.utc)
            details = self.get_service_details(service)
            cooldown_hours = int(details["cooldown"].rstrip("h"))

            if not log or not log.sent_at:
                return {"available": True, "next_available": now}

            next_available = log.sent_at + timedelta(hours=cooldown_hours)
            return {
                "available": next_available <= now,
                "next_available": next_available,
            }
