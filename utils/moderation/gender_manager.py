"""Manager for gender role assignments.

Module for handling gender role assignments with database tracking,
embeds, and proper audit logging.
"""

import logging
from typing import Optional

import discord
from discord.ext import commands

from datasources.queries import MemberQueries, RoleQueries
from utils.message_sender import MessageSender
from .gender_type import GenderType

logger = logging.getLogger(__name__)


class GenderManager:
    """Manager for gender role assignments."""

    def __init__(self, bot):
        """Initialize the GenderManager.

        :param bot: Discord bot instance.
        """
        self.bot = bot
        self.config = bot.config

    async def assign_gender_role(self, ctx: commands.Context, user: discord.Member, gender_type_name: str):
        """Assign gender role to a user.

        :param ctx: Command context.
        :param user: Target user.
        :param gender_type_name: Type of gender role ('male' or 'female').
        """
        try:
            gender_type = GenderType.from_name(gender_type_name)
            await self._handle_gender_logic(ctx, user, gender_type)
        except ValueError as e:
            logger.error(f"Invalid gender type: {gender_type_name}, error: {e}")
            await ctx.send("❌ Nieprawidłowy typ roli płci.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in assign_gender_role: {e}", exc_info=True)
            await ctx.send("❌ Wystąpił błąd podczas przypisywania roli płci.", ephemeral=True)

    async def _handle_gender_logic(self, ctx: commands.Context, user: discord.Member, gender_type: GenderType):
        """Handle the core gender role assignment logic.

        :param ctx: Command context.
        :param user: Target user.
        :param gender_type: GenderType object.
        """
        try:
            # Get role IDs from config
            gender_roles = self.config.get("gender_roles", {})
            target_role_id = gender_roles.get(gender_type.role_id_field)
            opposite_role_id = gender_roles.get(
                GenderType.from_name(gender_type.opposite_type).role_id_field
            )

            if not target_role_id:
                await ctx.send("❌ Role płci nie są skonfigurowane.", ephemeral=True)
                return

            # Get Discord role objects
            target_role = ctx.guild.get_role(target_role_id)
            opposite_role = ctx.guild.get_role(opposite_role_id) if opposite_role_id else None

            if not target_role:
                await ctx.send(f"❌ Nie znaleziono roli {gender_type.display_name} na serwerze.", ephemeral=True)
                return

            # Check current state
            has_target_role = target_role in user.roles
            has_opposite_role = opposite_role and opposite_role in user.roles

            # Determine action type
            if has_target_role and not has_opposite_role:
                # User already has the target role and no opposite role
                message = gender_type.success_message_already_has.format(
                    user_mention=user.mention,
                    display_name=gender_type.display_name
                )
                action_type = "already_has"
            elif has_opposite_role:
                # User has opposite role, switch
                await user.remove_roles(opposite_role, reason=f"{GenderType.from_name(gender_type.opposite_type).reason_remove} - komenda przez {ctx.author}")
                await user.add_roles(target_role, reason=f"{gender_type.reason_add} - komenda przez {ctx.author}")
                
                message = gender_type.success_message_switch.format(
                    user_mention=user.mention,
                    role_symbol=gender_type.role_symbol
                )
                action_type = "switched"
            else:
                # User has no gender role, add new one
                await user.add_roles(target_role, reason=f"{gender_type.reason_add} - komenda przez {ctx.author}")
                
                message = gender_type.success_message_add.format(
                    user_mention=user.mention,
                    role_symbol=gender_type.role_symbol
                )
                action_type = "added"

            # Save to database if role was actually changed
            if action_type in ["switched", "added"]:
                async with self.bot.get_db() as session:
                    await MemberQueries.get_or_add_member(session, user.id)
                    
                    # Remove opposite role from database if it exists
                    if has_opposite_role and opposite_role_id:
                        await RoleQueries.remove_role_from_member(session, user.id, opposite_role_id)
                    
                    # Add new role to database
                    await RoleQueries.add_or_update_role_to_member(session, user.id, target_role_id)
                    await session.commit()

            # Send response with embed for consistency
            embed = discord.Embed(description=message, color=ctx.author.color)
            await ctx.reply(embed=embed)

            # Log the action
            if action_type != "already_has":
                await self._log_gender_action(ctx, user, gender_type, action_type)

            logger.info(f"Gender role {gender_type.type_name} assignment for user {user.id}: {action_type}")

        except discord.Forbidden as e:
            logger.error(f"Permission error during gender role assignment for user {user.id}: {e}", exc_info=True)
            await ctx.send("❌ Brak uprawnień do zarządzania rolami tego użytkownika.")
        except discord.HTTPException as e:
            logger.error(f"Discord API error during gender role assignment for user {user.id}: {e}", exc_info=True)
            await ctx.send("❌ Wystąpił błąd Discord API podczas przypisywania roli.")
        except Exception as e:
            logger.error(f"Error handling gender role assignment for user {user.id}: {e}", exc_info=True)
            await ctx.send("❌ Wystąpił błąd podczas przypisywania roli płci.")

    async def _log_gender_action(self, ctx: commands.Context, user: discord.Member, gender_type: GenderType, action_type: str):
        """Log gender role assignment to the moderation log channel.

        :param ctx: Command context.
        :param user: Target user.
        :param gender_type: GenderType object.
        :param action_type: Type of action performed.
        """
        try:
            # Get mod log channel
            mod_log_channel_id = self.config.get("channels", {}).get("mod_log")
            if not mod_log_channel_id:
                return

            mod_log_channel = ctx.guild.get_channel(mod_log_channel_id)
            if not mod_log_channel:
                return

            # Create log embed
            action_text = {
                "added": f"Nadano rolę {gender_type.role_symbol}",
                "switched": f"Zmieniono na rolę {gender_type.role_symbol}",
            }.get(action_type, f"Wykonano akcję: {action_type}")

            embed = discord.Embed(
                title="🏷️ Zmiana roli płci",
                color=discord.Color.blue(),
                timestamp=ctx.message.created_at
            )
            embed.add_field(name="👤 Użytkownik", value=f"{user.mention} (`{user.id}`)", inline=True)
            embed.add_field(name="👮 Moderator", value=f"{ctx.author.mention} (`{ctx.author.id}`)", inline=True)
            embed.add_field(name="🔄 Akcja", value=action_text, inline=True)
            embed.add_field(name="🏷️ Rola", value=f"{gender_type.role_symbol} {gender_type.display_name}", inline=True)
            embed.add_field(name="📝 Komenda", value=f"`{ctx.message.content}`", inline=False)

            await mod_log_channel.send(embed=embed)

        except Exception as e:
            logger.error(f"Error logging gender action: {e}", exc_info=True) 