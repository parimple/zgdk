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
    async def on_ready(self):
        """Check for invalid color roles when bot starts up."""
        if not hasattr(self.bot, "guild_id"):
            self.logger.error("Bot doesn't have guild_id attribute")
            return

        guild = self.bot.get_guild(self.bot.guild_id)
        if not guild:
            self.logger.error(f"Cannot find guild with ID {self.bot.guild_id}")
            return

        # Get the list of premium roles from config
        premium_roles = [role["name"] for role in self.bot.config["premium_roles"]]
        
        # Get all color roles
        color_roles = [role for role in guild.roles if role.name == self.color_role_name]
        
        for color_role in color_roles:
            should_delete = True
            
            # Check if role has any members
            if len(color_role.members) > 0:
                for member in color_role.members:
                    # Check if member has any premium role
                    has_premium = any(role.name in premium_roles for role in member.roles)
                    if has_premium:
                        # If at least one member with premium has this role, don't delete it
                        should_delete = False
                        continue
                    else:
                        # Remove role from member without premium
                        try:
                            await member.remove_roles(color_role, reason="No premium role found during startup check")
                            self.logger.info(f"Removed color role from {member.display_name} during startup check (no premium)")
                        except Exception as e:
                            self.logger.error(f"Failed to remove color role from {member.display_name} during startup: {str(e)}")
            
            # Delete role if it should be deleted (no members with premium or no members at all)
            if should_delete:
                try:
                    await color_role.delete(reason="No valid members with premium during startup check")
                    self.logger.info(f"Deleted color role {color_role.id} during startup check")
                except Exception as e:
                    self.logger.error(f"Failed to delete color role {color_role.id} during startup: {str(e)}")

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