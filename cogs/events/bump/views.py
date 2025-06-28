"""Views for bump module."""

import discord


class BumpStatusView(discord.ui.View):
    """View with buttons for bump services."""

    def __init__(self, bot=None):
        super().__init__(timeout=300)  # 5 minutes timeout

        # Get emojis from config or use defaults
        emojis = {}
        if bot and hasattr(bot, "config"):
            config_emojis = bot.config.get("emojis", {})
            emojis = {
                "discadia": config_emojis.get("discadia", "🌟"),
                "discordservers": config_emojis.get("discordservers", "📊"),
                "dsme": config_emojis.get("dsme", "📈"),
            }
        else:
            emojis = {
                "discadia": "🌟",
                "discordservers": "📊",
                "dsme": "📈",
            }

        # Add buttons for each voting service
        self.add_item(
            discord.ui.Button(
                label="Głosuj na Discadia",
                emoji=emojis["discadia"],
                style=discord.ButtonStyle.link,
                url="https://discadia.com/vote/polska/",
            )
        )

        self.add_item(
            discord.ui.Button(
                label="Głosuj na DiscordServers",
                emoji=emojis["discordservers"],
                style=discord.ButtonStyle.link,
                url="https://discordservers.com/server/960665311701528596/bump",
            )
        )

        self.add_item(
            discord.ui.Button(
                label="Głosuj na DSME",
                emoji=emojis["dsme"],
                style=discord.ButtonStyle.link,
                url="https://discords.com/servers/960665311701528596/upvote",
            )
        )

        # Add refresh button
        self.add_item(RefreshButton())


class RefreshButton(discord.ui.Button):
    """Button to refresh bump status."""

    def __init__(self):
        super().__init__(
            label="Odśwież status", emoji="🔄", style=discord.ButtonStyle.secondary, custom_id="bump_refresh"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle button click."""
        # Import here to avoid circular import
        from utils.message_sender import MessageSender

        from .status import BumpStatusHandler

        # Defer response
        await interaction.response.defer()

        # Get bot from interaction
        bot = interaction.client

        # Create status handler
        message_sender = MessageSender(bot)
        status_handler = BumpStatusHandler(bot, message_sender)

        # Show updated status
        await status_handler.show_status(interaction, interaction.user)
