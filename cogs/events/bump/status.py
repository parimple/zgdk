"""Bump status handler."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import discord

from core.repositories import NotificationRepository
from utils.message_sender import MessageSender

from .constants import SERVICE_COOLDOWNS, SERVICE_NAMES
from .views import BumpStatusView

logger = logging.getLogger(__name__)


class BumpStatusHandler:
    """Handler for bump status commands."""

    def __init__(self, bot, message_sender: MessageSender):
        self.bot = bot
        self.message_sender = message_sender

    async def get_service_status(self, service: str, user_id: int) -> dict:
        """Get status for a specific bump service."""
        async with self.bot.get_db() as session:
            # For global services like disboard, use guild_id
            guild_id = self.bot.guild_id if hasattr(self.bot, "guild_id") else None
            notification_repo = NotificationRepository(session)
            last_notification = await notification_repo.get_service_notification_log(service, guild_id, user_id)

            if not last_notification:
                return {
                    "service": service,
                    "available": True,
                    "last_bump": None,
                    "next_available": None,
                    "cooldown_hours": SERVICE_COOLDOWNS.get(service, 0),
                }

            current_time = datetime.now(timezone.utc)
            cooldown_hours = SERVICE_COOLDOWNS.get(service, 0)
            cooldown_end = last_notification.sent_at + timedelta(hours=cooldown_hours)

            is_available = current_time >= cooldown_end

            return {
                "service": service,
                "available": is_available,
                "last_bump": last_notification.sent_at,
                "next_available": cooldown_end if not is_available else None,
                "cooldown_hours": cooldown_hours,
            }

    async def show_status(self, interaction: discord.Interaction, member: discord.Member) -> None:
        """Show bump status for all services."""
        await interaction.response.defer()

        # Get status for all services
        statuses = {}
        for service in SERVICE_NAMES.values():
            statuses[service] = await self.get_service_status(service, member.id)

        # Create status embed with user's color
        embed = self.message_sender._create_embed(
            title="📊 Status Twoich Bumpów",
            description="Sprawdź, które serwisy możesz już podbić!",
            ctx=member,  # Pass member as ctx to get their color
            add_author=True,  # This will add author automatically
        )

        # Service emojis from config or fallback to default
        config_emojis = self.bot.config.get("emojis", {})
        service_emojis = {
            "disboard": config_emojis.get("disboard", "🇩"),
            "dzik": config_emojis.get("dzik", "🐗"),
            "discadia": config_emojis.get("discadia", "🌟"),
            "discordservers": config_emojis.get("discordservers", "📊"),
            "dsme": config_emojis.get("dsme", "📈"),
        }

        # Debug log
        logger.info(f"Bump emojis loaded: disboard={service_emojis['disboard'][:20]}")

        # Service links
        service_links = {
            "disboard": "Użyj `/bump`",
            "dzik": "Użyj `/bump`",
            "discadia": "[Zagłosuj tutaj](https://discadia.com/vote/polska/)",
            "discordservers": "[Zagłosuj tutaj](https://discordservers.com/server/960665311701528596/bump)",
            "dsme": "[Zagłosuj tutaj](https://discords.com/servers/960665311701528596/upvote)",
        }

        # Service rewards
        service_rewards = {
            "disboard": "3T",
            "dzik": "3T",
            "discadia": "6T",
            "discordservers": "6T",
            "dsme": "3T",
        }

        # Add status for each service
        for service_name, status in statuses.items():
            emoji = service_emojis.get(service_name, "❓")
            link = service_links.get(service_name, "")
            reward = service_rewards.get(service_name, "?T")

            if status["available"]:
                # Service is available
                field_name = f"{emoji} {service_name.title()} - ✅ Dostępny"
                field_value = f"**Nagroda:** {reward}\n{link}"
            else:
                # Service is on cooldown
                field_name = f"{emoji} {service_name.title()} - ⏱️ Cooldown"

                # Calculate time remaining
                if status["next_available"]:
                    time_remaining = status["next_available"] - datetime.now(timezone.utc)
                    hours = int(time_remaining.total_seconds() // 3600)
                    minutes = int((time_remaining.total_seconds() % 3600) // 60)

                    if hours > 0:
                        time_str = f"{hours}h {minutes}m"
                    else:
                        time_str = f"{minutes}m"

                    field_value = f"**Dostępny za:** {time_str}\n**Nagroda:** {reward}"
                else:
                    field_value = f"**Nagroda:** {reward}"

            embed.add_field(name=field_name, value=field_value, inline=True)

        # Add summary
        available_count = sum(1 for s in statuses.values() if s["available"])
        total_count = len(statuses)

        embed.add_field(
            name="📈 Podsumowanie",
            value=(
                f"**Dostępne:** {available_count}/{total_count}\n"
                f"**Możliwy zysk:** {self.calculate_potential_rewards(statuses, service_rewards)}T"
            ),
            inline=False,
        )

        # Add tips
        if available_count > 0:
            embed.add_field(
                name="💡 Wskazówka",
                value="Wykorzystaj dostępne bumpy, aby zdobyć czas T!",
                inline=False,
            )

        embed.set_footer(text="Czas T pozwala korzystać z komend głosowych bez rang premium!")

        # Add premium channel info if available
        if hasattr(interaction, "_ctx"):
            # This is our fake interaction from bump_status command
            ctx = interaction._ctx
            if hasattr(ctx, "bot") and hasattr(ctx.bot, "config"):
                mastercard = ctx.bot.config.get("emojis", {}).get("mastercard", "💳")
                premium_channel_id = ctx.bot.config.get("channels", {}).get("premium_info")
                if premium_channel_id:
                    premium_channel = ctx.guild.get_channel(premium_channel_id)
                    if premium_channel:
                        embed.add_field(
                            name="\u200b", value=f"Wybierz swój {premium_channel.mention} {mastercard}", inline=False
                        )

        # Create view with buttons
        view = BumpStatusView(bot=self.bot)

        await interaction.followup.send(embed=embed, view=view)

    def calculate_potential_rewards(self, statuses: Dict[str, dict], rewards: Dict[str, str]) -> int:
        """Calculate total potential rewards from available services."""
        total = 0
        for service_name, status in statuses.items():
            if status["available"]:
                reward_str = rewards.get(service_name, "0T")
                reward_value = int(reward_str.replace("T", ""))
                total += reward_value
        return total
