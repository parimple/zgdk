"""Event handler for member role updates."""

import logging

import discord
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
                            await member.remove_roles(
                                color_role,
                                reason="No premium role found during startup check",
                            )
                            self.logger.info(
                                f"Removed color role from {member.display_name} during startup check (no premium)"
                            )
                        except Exception as e:
                            self.logger.error(
                                f"Failed to remove color role from {member.display_name} during startup: {str(e)}"
                            )

            # Delete role if it should be deleted (no members with premium or no members at all)
            if should_delete:
                try:
                    await color_role.delete(reason="No valid members with premium during startup check")
                    self.logger.info(f"Deleted color role {color_role.id} during startup check")
                except Exception as e:
                    self.logger.error(f"Failed to delete color role {color_role.id} during startup: {str(e)}")

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Handle member updates including role changes and nickname changes for mutenick users."""
        # Check if roles have changed
        roles_changed = before.roles != after.roles

        # Check if nickname has changed
        nickname_changed = before.nick != after.nick

        # Handle role changes (existing logic)
        if roles_changed:
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

        # Handle nickname changes for mutenick users
        if nickname_changed:
            # Check if user has mutenick role
            nick_mute_role_id = self.bot.config["mute_roles"][2]["id"]  # ☢︎ role (attach_files_off)
            has_nick_mute = any(role.id == nick_mute_role_id for role in after.roles)

            if has_nick_mute:
                default_nick = self.bot.config.get("default_mute_nickname", "random")
                current_nick = after.nick or after.name

                # If nickname is not the default mutenick nickname, enforce it
                if current_nick != default_nick:
                    self.logger.warning(
                        f"User {after.id} ({after.display_name}) with mutenick tried to change nick from '{before.nick}' to '{after.nick}'. Enforcing default nick."
                    )

                    try:
                        await after.edit(
                            nick=default_nick,
                            reason="Automatyczne wymuszenie nicku mutenick",
                        )
                        self.logger.info(f"Successfully enforced nick '{default_nick}' for mutenick user {after.id}")

                        # Try to send DM to user about the enforcement
                        try:
                            await after.send(
                                f"⚠️ Twój nick został automatycznie zmieniony na `{default_nick}` z powodu aktywnej kary mutenick. "
                                f"Aby odzyskać możliwość zmiany nicku, udaj się na kanał premium i zakup dowolną rangę."
                            )
                        except discord.Forbidden:
                            # User has DMs disabled, that's fine
                            pass

                    except discord.Forbidden:
                        self.logger.error(f"Failed to enforce nick for mutenick user {after.id} - permission denied")
                    except Exception as e:
                        self.logger.error(f"Error enforcing nick for mutenick user {after.id}: {e}")
                else:
                    # Nick is already correct, just log it
                    self.logger.debug(
                        f"Nick change detected for mutenick user {after.id}, but nick is already correct: '{current_nick}'"
                    )


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(OnMemberRoleUpdateEvent(bot))
