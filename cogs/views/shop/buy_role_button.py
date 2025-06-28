"""Buy role button for shop views."""
import discord

from utils.message_sender import MessageSender


class BuyRoleButton(discord.ui.Button):
    """Button for buying a role."""

    def __init__(self, bot=None, member=None, role_name=None, **kwargs):
        """Initialize the button.

        Args:
            bot: The bot instance (optional)
            member: The member to buy role for (optional)
            role_name: The name of the role to buy (optional)
            **kwargs: Additional button parameters (style, label, etc.)
        """
        kwargs.setdefault("style", discord.ButtonStyle.primary)
        kwargs.setdefault("label", "Kup rolę")
        kwargs.setdefault("emoji", bot.config.get("emojis", {}).get("mastercard", "💳") if bot else "💳")
        super().__init__(**kwargs)
        self.bot = bot
        self.member = member
        self.role_name = role_name
        # Initialize MessageSender with bot instance if available, otherwise without
        self.message_sender = MessageSender(bot) if bot else MessageSender()

    async def callback(self, interaction: discord.Interaction):
        """Handle the button click."""
        # If bot and member were provided (from payment view), use them
        if self.bot and self.member:
            ctx = await self.bot.get_context(interaction.message)
            ctx.author = self.member
            if self.role_name:
                await ctx.invoke(self.bot.get_command("shop"), role_name=self.role_name)
            else:
                await ctx.invoke(self.bot.get_command("shop"))
        # Otherwise use the standard shop command (from shop view)
        else:
            if self.role_name:
                await interaction.client.get_command("shop")(interaction, role_name=self.role_name)
            else:
                await interaction.client.get_command("shop")(interaction)
