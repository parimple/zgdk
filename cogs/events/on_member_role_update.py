"""Event handler for member role updates."""

import logging
from discord.ext import commands

logger = logging.getLogger(__name__)

class OnMemberRoleUpdateEvent(commands.Cog):
    """Class for handling member role updates."""

    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)
        # Nazwa roli kolorowej z config
        self.color_role_name = self.bot.config.get("color", {}).get("role_name", "✎")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Handle member role updates."""
        # Check if roles have changed
        if before.roles == after.roles:
            return

        # Get the premium roles from config
        premium_roles = [role["name"] for role in self.bot.config["premium_roles"]]

        # Check if user had any premium role before
        had_premium = any(role.name in premium_roles for role in before.roles)
        # Check if user has any premium role after
        has_premium = any(role.name in premium_roles for role in after.roles)

        # If user lost premium status (had premium before but doesn't have it now)
        if had_premium and not has_premium:
            # Find and remove the color role if it exists
            for role in after.roles:
                if role.name == self.color_role_name:
                    try:
                        await after.remove_roles(role, reason="Premium role expired")
                        self.logger.info(f"Removed color role from {after.display_name} due to premium expiration")
                        # Delete the role since it's no longer needed
                        await role.delete(reason="Premium role expired")
                        break
                    except Exception as e:
                        self.logger.error(f"Failed to remove color role from {after.display_name}: {str(e)}")

async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(OnMemberRoleUpdateEvent(bot)) 