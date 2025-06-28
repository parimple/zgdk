"""Role restoration functionality for returning members."""

import logging
from datetime import datetime, timezone
from typing import List, Set

import discord
from discord.ext import commands

from core.interfaces.member_interfaces import IMemberService, IModerationService
from core.interfaces.role_interfaces import IRoleService

logger = logging.getLogger(__name__)


class RoleRestorer:
    """Handles restoration of roles for returning members."""

    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        # Metryki
        self.voice_permissions_restored = 0

    async def restore_all_roles(self, member: discord.Member) -> List[discord.Role]:
        """Restore all roles that a member had before leaving."""
        restored_roles = []

        async with self.bot.get_db() as session:
            try:
                role_service = await self.bot.get_service(IRoleService, session)
                member_service = await self.bot.get_service(IMemberService, session)

                # Get member's previous roles
                db_member = await member_service.get_or_create_member(member)
                member_roles = await role_service.get_member_roles(member.id)

                if not member_roles:
                    logger.info(f"No previous roles found for {member}")
                    return restored_roles

                # Get special role names from config
                mute_role_names = {role["name"] for role in self.bot.config.get("mute_roles", [])}
                gender_role_names = {"♂", "♀"}

                # Process roles
                roles_to_restore = []
                special_roles_info = []

                for member_role in member_roles:
                    role = self.guild.get_role(member_role.role_id)
                    if not role:
                        logger.warning(f"Role {member_role.role_id} not found in guild")
                        continue

                    # Check role type
                    if role.name in mute_role_names:
                        # Check if mute is still active
                        active_mutes = await self._get_active_mutes(member, session)
                        mute_type = next(
                            (r["description"] for r in self.bot.config.get("mute_roles", []) if r["name"] == role.name),
                            "unknown",
                        )

                        if mute_type in active_mutes:
                            special_roles_info.append(f"wyciszenie [{mute_type}]")
                            roles_to_restore.append(role)

                    elif role.name in gender_role_names:
                        special_roles_info.append(f"płeć [{role.name}]")
                        roles_to_restore.append(role)

                    elif member_role.role_type == "premium":
                        # Check if premium role is still valid
                        if member_role.expiration_date and member_role.expiration_date > datetime.now(timezone.utc):
                            time_left = member_role.expiration_date - datetime.now(timezone.utc)
                            days_left = time_left.days
                            special_roles_info.append(f"premium [{role.name}] (zostało {days_left} dni)")
                            roles_to_restore.append(role)
                        else:
                            logger.info(f"Premium role {role.name} expired for {member}")

                    elif member_role.role_type == "team":
                        special_roles_info.append(f"drużyna [{role.name}]")
                        roles_to_restore.append(role)

                    else:
                        # Other roles
                        roles_to_restore.append(role)

                # Restore roles
                if roles_to_restore:
                    try:
                        await member.add_roles(*roles_to_restore, reason="Przywracanie ról po powrocie")
                        restored_roles = roles_to_restore

                        # Log special roles
                        if special_roles_info:
                            logger.info(f"Przywrócono role specjalne dla {member}: {', '.join(special_roles_info)}")

                        # Send notification about restored roles
                        await self._notify_restored_roles(member, restored_roles, special_roles_info)

                    except discord.Forbidden:
                        logger.error(f"No permission to restore roles for {member}")
                    except discord.HTTPException as e:
                        logger.error(f"Failed to restore roles for {member}: {e}")

            except Exception as e:
                logger.error(f"Error restoring roles for {member}: {e}")

        return restored_roles

    async def _get_active_mutes(self, member: discord.Member, session) -> Set[str]:
        """Get active mute types for a member."""
        active_mutes = set()

        try:
            moderation_service = await self.bot.get_service(IModerationService, session)
            mutes = await moderation_service.get_active_mutes(member.id)

            for mute in mutes:
                active_mutes.add(mute.mute_type)

        except Exception as e:
            logger.error(f"Error getting active mutes: {e}")

        return active_mutes

    async def _notify_restored_roles(
        self, member: discord.Member, restored_roles: List[discord.Role], special_info: List[str]
    ) -> None:
        """Send notification about restored roles."""
        if not restored_roles:
            return

        # Send DM to member
        try:
            embed = discord.Embed(
                title="🔄 Role przywrócone!",
                description=(
                    f"Witaj ponownie na serwerze **{self.guild.name}**!\n" f"Twoje poprzednie role zostały przywrócone."
                ),
                color=discord.Color.green(),
                timestamp=datetime.now(timezone.utc),
            )

            # Add role list
            role_names = [role.mention for role in restored_roles[:10]]  # Limit to 10
            if len(restored_roles) > 10:
                role_names.append(f"... i {len(restored_roles) - 10} więcej")

            embed.add_field(name="Przywrócone role", value="\n".join(role_names), inline=False)

            # Add special info if any
            if special_info:
                embed.add_field(
                    name="Informacje specjalne", value="\n".join(special_info[:5]), inline=False  # Limit to 5
                )

            embed.set_footer(text=f"ID: {member.id}")

            await member.send(embed=embed)
            logger.info(f"Sent role restoration notification to {member}")

        except discord.Forbidden:
            logger.info(f"Cannot send DM to {member} about restored roles")
        except Exception as e:
            logger.error(f"Error sending role restoration notification: {e}")

    async def restore_voice_permissions(self, member: discord.Member) -> int:
        """Restore voice channel permissions for a member."""
        restored_count = 0

        try:
            from datasources.queries import ChannelPermissionQueries

            async with self.bot.get_db() as session:
                # Get member's voice channel permissions
                permissions = await ChannelPermissionQueries.get_member_permissions(session, member.id)

                for perm in permissions:
                    channel = self.guild.get_channel(perm.channel_id)
                    if not channel or not isinstance(channel, discord.VoiceChannel):
                        continue

                    try:
                        # Create permission overwrite
                        overwrites = channel.overwrites
                        overwrites[member] = discord.PermissionOverwrite(
                            view_channel=perm.view_channel,
                            connect=perm.connect,
                            speak=perm.speak,
                            stream=perm.stream,
                            use_voice_activation=perm.use_voice_activation,
                        )

                        await channel.edit(overwrites=overwrites, reason=f"Przywracanie uprawnień dla {member}")

                        restored_count += 1
                        logger.info(f"Restored voice permissions for {member} in channel {channel.name}")

                    except discord.Forbidden:
                        logger.error(f"No permission to restore voice permissions in {channel.name}")
                    except discord.HTTPException as e:
                        logger.error(f"Failed to restore voice permissions in {channel.name}: {e}")

                # Update metrics
                if restored_count > 0:
                    self.voice_permissions_restored += restored_count
                    logger.info(f"Total voice permissions restored: {self.voice_permissions_restored}")

        except Exception as e:
            logger.error(f"Error restoring voice permissions for {member}: {e}")

        return restored_count
