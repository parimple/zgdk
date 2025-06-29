"""Setup test category for zaGadka bot."""

import logging
from typing import Optional

import discord

logger = logging.getLogger(__name__)


class TestCategorySetup:
    """Handles creation of test category and channels."""

    def __init__(self, bot):
        """Initialize test category setup."""
        self.bot = bot
        self.config = bot.config.get("test_category", {})

    async def setup_test_category(self, guild: discord.Guild) -> Optional[discord.CategoryChannel]:
        """Create test category with channels if it doesn't exist."""
        try:
            category_name = self.config.get("name", "🧪 zaGadka Testing")
            
            # Check if category already exists
            existing_category = discord.utils.get(guild.categories, name=category_name)
            if existing_category:
                logger.info(f"Test category '{category_name}' already exists")
                return existing_category

            # Create category with restricted permissions
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(
                    view_channel=False,  # Hidden from @everyone
                    connect=False
                ),
                guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    manage_channels=True,
                    manage_permissions=True
                )
            }

            # Add owner permissions
            owner_id = self.bot.config.get("owner_id")
            if owner_id:
                owner = guild.get_member(owner_id)
                if owner:
                    overwrites[owner] = discord.PermissionOverwrite(
                        view_channel=True,
                        send_messages=True,
                        connect=True,
                        manage_channels=True,
                        manage_permissions=True
                    )

            # Create the category
            category = await guild.create_category(
                name=category_name,
                overwrites=overwrites,
                reason="zaGadka test category setup"
            )
            logger.info(f"Created test category: {category_name}")

            # Create text channels
            channels_config = self.config.get("channels", {})
            
            # Commands channel
            commands_channel = await guild.create_text_channel(
                name=channels_config.get("commands", "zagadka-commands"),
                category=category,
                topic="Testowanie komend zaGadka | Test zaGadka commands here",
                overwrites=overwrites
            )
            logger.info(f"Created commands channel: {commands_channel.name}")

            # Logs channel
            logs_channel = await guild.create_text_channel(
                name=channels_config.get("logs", "zagadka-logs"),
                category=category,
                topic="Logi działania bota | Bot activity logs",
                overwrites=overwrites
            )
            logger.info(f"Created logs channel: {logs_channel.name}")

            # Errors channel
            errors_channel = await guild.create_text_channel(
                name=channels_config.get("errors", "zagadka-errors"),
                category=category,
                topic="Błędy i wyjątki | Errors and exceptions",
                overwrites=overwrites
            )
            logger.info(f"Created errors channel: {errors_channel.name}")

            # Analytics channel
            analytics_channel = await guild.create_text_channel(
                name=channels_config.get("analytics", "zagadka-analytics"),
                category=category,
                topic="Statystyki użycia | Usage statistics",
                overwrites=overwrites
            )
            logger.info(f"Created analytics channel: {analytics_channel.name}")

            # Voice create channel
            voice_create = await guild.create_voice_channel(
                name=channels_config.get("voice_create", "➕ Stwórz kanał"),
                category=category,
                overwrites=overwrites,
                user_limit=1  # Only one person can join to create
            )
            logger.info(f"Created voice create channel: {voice_create.name}")

            # Add voice create channel to config
            if "channels_create" not in self.bot.config:
                self.bot.config["channels_create"] = []
            self.bot.config["channels_create"].append(voice_create.id)
            
            # Add category to voice categories
            if "vc_categories" not in self.bot.config:
                self.bot.config["vc_categories"] = []
            self.bot.config["vc_categories"].append(category.id)

            # Store channel IDs in config for later use
            self.bot.config["test_channels"] = {
                "commands": commands_channel.id,
                "logs": logs_channel.id,
                "errors": errors_channel.id,
                "analytics": analytics_channel.id,
                "voice_create": voice_create.id
            }

            # Send welcome message
            embed = discord.Embed(
                title="🧪 zaGadka Test Category Setup Complete!",
                description="Kategoria testowa została utworzona pomyślnie.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="Kanały tekstowe",
                value=(
                    f"• {commands_channel.mention} - Testowanie komend\n"
                    f"• {logs_channel.mention} - Logi bota\n"
                    f"• {errors_channel.mention} - Błędy i wyjątki\n"
                    f"• {analytics_channel.mention} - Statystyki"
                ),
                inline=False
            )
            embed.add_field(
                name="Kanał głosowy",
                value=f"• **{voice_create.name}** - Wejdź aby utworzyć własny kanał",
                inline=False
            )
            embed.set_footer(text="zaGadka Bot v1.0 | Ready for production!")
            
            await commands_channel.send(embed=embed)

            return category

        except Exception as e:
            logger.error(f"Error setting up test category: {e}", exc_info=True)
            return None