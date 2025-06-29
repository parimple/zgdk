"""Team management commands."""

import logging
from typing import Any, Dict, Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.commands.premium.utils import emoji_to_icon, emoji_validator
from core.interfaces.premium_interfaces import IPremiumService
from core.interfaces.role_interfaces import IRoleService
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class TeamManagementCommands:
    """Team creation and management commands."""

    def __init__(self, bot):
        """Initialize team management commands."""
        self.bot = bot
        self.message_sender = MessageSender(bot)

        # Team configuration
        team_config = self.bot.config.get("team", {})
        self.team_symbol = team_config.get("symbol", "☫")
        self.team_base_role_id = team_config.get("base_role_id", 960665311730868240)
        self.team_category_id = team_config.get("category_id", 1344105013357842522)

        # Get prefix from bot
        self.prefix = self.bot.command_prefix[0] if self.bot.command_prefix else ","

    async def _get_user_team_role(self, member: discord.Member) -> Optional[discord.Role]:
        """Get user's team role if they have one."""
        for role in member.roles:
            if role.name.startswith(f"{self.team_symbol} "):
                return role
        return None

    async def _get_team_info(self, team_role: discord.Role) -> Dict[str, Any]:
        """Get information about a team."""
        guild = team_role.guild

        # Get owner from database
        owner = None
        max_members = 5  # Default

        async with self.bot.get_db() as session:
            role_service = await self.bot.get_service(IRoleService, session)
            db_role = await role_service.get_role_by_id(team_role.id)

            if db_role and db_role.name.isdigit():
                owner = guild.get_member(int(db_role.name))

                # Get max members based on owner's premium roles
                if owner:
                    premium_service = await self.bot.get_service(IPremiumService, session)
                    premium_service.set_guild(guild)
                    highest_premium = await premium_service.get_highest_premium_role(owner)

                    if highest_premium:
                        premium_config = next(
                            (r for r in self.bot.config["premium_roles"] if r["name"] == highest_premium.name), None
                        )
                        if premium_config:
                            max_members = premium_config.get("team_members", 5)

        # Get members
        members = [m for m in guild.members if team_role in m.roles]

        # Get channel
        channel = discord.utils.get(guild.channels, name=f"💬・{team_role.name[2:].lower().replace(' ', '-')}")

        return {"owner": owner, "members": members, "max_members": max_members, "channel": channel}

    def _get_team_commands_description(self) -> str:
        """Get description of available team commands."""
        return (
            f"`{self.prefix}team create <nazwa>` - Utworzenie nowego teamu\n"
            f"`{self.prefix}team invite <@user>` - Zaproszenie gracza do teamu\n"
            f"`{self.prefix}team kick <@user>` - Wyrzucenie gracza z teamu\n"
            f"`{self.prefix}team transfer <@user>` - Przekazanie własności teamu\n"
            f"`{self.prefix}team leave` - Opuszczenie teamu\n"
            f"`{self.prefix}team delete` - Usunięcie teamu (tylko właściciel)"
        )

    async def _send_premium_embed(
        self, ctx, description: str, color: int = 0x00FF00, title: str = "Team Management"
    ) -> Optional[discord.Message]:
        """Send an embed message with premium information if applicable."""
        embed = discord.Embed(title=f"{self.team_symbol} {title}", description=description, color=color)

        # Add premium information if user doesn't have premium
        premium_text = ""
        async with self.bot.get_db() as session:
            premium_service = await self.bot.get_service(IPremiumService, session)
            if premium_service and ctx.guild:
                premium_service.set_guild(ctx.guild)
                has_premium = await premium_service.has_premium_role(ctx.author)

                if not has_premium:
                    premium_text = "\n\n💎 **Funkcja Premium**\nDostępna dla: <@&1027629813788106814>, <@&1027629916951326761>, <@&1027630008227659826>"

        if premium_text:
            embed.description = description + premium_text

        return await ctx.send(embed=embed)

    @commands.group(invoke_without_command=True)
    async def team(self, ctx):
        """Team (clan) management."""
        # Get the owner's team role
        team_role = await self._get_user_team_role(ctx.author)

        # List available commands
        available_commands = f"**Dostępne komendy:**\n{self._get_team_commands_description()}"

        if not team_role:
            # Create description
            description = (
                "Nie masz teamu. Możesz go utworzyć za pomocą komendy:\n"
                f"`{self.prefix}team create <nazwa>`\n\n"
                "Minimalne wymagania: posiadanie rangi **zG100**.\n\n"
                f"{available_commands}"
            )

            await self._send_premium_embed(ctx, description=description, color=0xFF0000)
            return

        # Get team information
        team_info = await self._get_team_info(team_role)

        # Prepare description with team info
        description = (
            f"**Team**: {self.team_symbol} {team_role.name[2:]}\n\n"
            f"**Właściciel**: {team_info['owner'].mention if team_info['owner'] else 'Nieznany'}\n"
            f"**Liczba członków**: {len(team_info['members'])}/{team_info['max_members']}\n"
            f"**Kanał**: {team_info['channel'].mention if team_info['channel'] else 'Brak'}\n\n"
            f"**Członkowie**: {' '.join(m.mention for m in team_info['members'])}\n\n"
            f"{available_commands}"
        )

        await self._send_premium_embed(ctx, description=description)

    @team.command(name="create")
    @app_commands.describe(
        name="Nazwa teamu (klanu) - jeśli nie podano, użyta zostanie nazwa użytkownika",
        color="Kolor teamu (opcjonalne, wymaga rangi zG500+)",
        emoji="Emoji teamu (opcjonalne, wymaga rangi zG1000)",
    )
    async def team_create(
        self,
        ctx,
        name: Optional[str] = None,
        color: Optional[str] = None,
        emoji: Optional[str] = None,
    ):
        """
        Create a new team.

        :param ctx: Command context
        :param name: Team name (optional, defaults to username)
        :param color: Team color (optional)
        :param emoji: Team emoji (optional)
        """
        # If no name provided, use username
        if name is None:
            name = ctx.author.display_name

        # Check if user already owns a team
        async with self.bot.get_db() as session:
            role_service = await self.bot.get_service(IRoleService, session)
            premium_service = await self.bot.get_service(IPremiumService, session)

            # Set guild for premium service
            premium_service.set_guild(ctx.guild)

            # Check if user has premium role required for team creation
            has_premium = await premium_service.has_premium_role(ctx.author)
            if not has_premium:
                await self._send_premium_embed(
                    ctx,
                    description=(
                        "❌ **Brak wymaganych uprawnień**\n\n"
                        "Aby utworzyć team, musisz posiadać jedną z rang premium:\n"
                        "• <@&1027629813788106814> - 5 członków teamu\n"
                        "• <@&1027629916951326761> - 10 członków teamu\n"
                        "• <@&1027630008227659826> - 15 członków teamu\n\n"
                        "Rangi premium możesz zakupić w <#960665316109713421>"
                    ),
                    color=0xFF0000,
                )
                return

            # Check if user already has a team
            existing_team = await self._get_user_team_role(ctx.author)
            if existing_team:
                await self._send_premium_embed(
                    ctx,
                    description=f"❌ Już posiadasz team: {existing_team.mention}",
                    color=0xFF0000,
                )
                return

            # Validate team name
            if len(name) > 20:
                await self._send_premium_embed(
                    ctx, description="❌ Nazwa teamu nie może być dłuższa niż 20 znaków!", color=0xFF0000
                )
                return

            if not name.replace(" ", "").replace("-", "").replace("_", "").isalnum():
                await self._send_premium_embed(
                    ctx,
                    description="❌ Nazwa teamu może zawierać tylko litery, cyfry, spacje, myślniki i podkreślenia!",
                    color=0xFF0000,
                )
                return

            # Check if team name already exists
            team_role_name = f"{self.team_symbol} {name}"
            existing_role = discord.utils.get(ctx.guild.roles, name=team_role_name)
            if existing_role:
                await self._send_premium_embed(ctx, description="❌ Team o takiej nazwie już istnieje!", color=0xFF0000)
                return

            # Create team role
            try:
                # Get base role
                base_role = ctx.guild.get_role(self.team_base_role_id)
                if not base_role:
                    await self._send_premium_embed(
                        ctx, description="❌ Nie znaleziono roli bazowej teamu!", color=0xFF0000
                    )
                    return

                # Create role just above base role
                team_role = await ctx.guild.create_role(
                    name=team_role_name,
                    color=discord.Color.default(),
                    hoist=False,
                    mentionable=True,
                    reason=f"Team created by {ctx.author}",
                )

                # Move role position
                await team_role.edit(position=base_role.position + 1)

                # Assign role to creator
                await ctx.author.add_roles(team_role)

                # Save team info to database
                await role_service.create_role(discord_id=team_role.id, name=str(ctx.author.id), role_type="team")
                await session.commit()

                await self.message_sender.send_success(ctx, f"Pomyślnie utworzono team {team_role.mention}!")

            except Exception as e:
                logger.error(f"Error creating team: {str(e)}")
                await self.message_sender.send_error(ctx, f"Wystąpił błąd podczas tworzenia teamu: {str(e)}")
                return

        # Set color if provided and user has zG500+
        if color:
            has_color_permission = any(role.name in ["zG500", "zG1000"] for role in ctx.author.roles)
            if not has_color_permission:
                await self._send_premium_embed(
                    ctx,
                    description="Kolor teamu dostępny tylko dla rang zG500+. Kolor nie został ustawiony.",
                    color=0xFF0000,
                )
            else:
                try:
                    # Use ColorCommands parse_color method if available
                    if hasattr(self, "parse_color"):
                        discord_color = await self.parse_color(color)
                    else:
                        # Fallback to basic hex parsing
                        if color.startswith("#"):
                            color = color[1:]
                        discord_color = discord.Color(int(color, 16))

                    await team_role.edit(color=discord_color)
                except Exception as e:
                    await self._send_premium_embed(ctx, description=f"Błąd parsowania koloru: {str(e)}", color=0xFF0000)

        # Set emoji if provided and user has zG1000
        if emoji:
            has_emoji_permission = any(role.name == "zG1000" for role in ctx.author.roles)
            if not has_emoji_permission:
                await self._send_premium_embed(
                    ctx,
                    description="Emoji teamu dostępne tylko dla rangi zG1000. Emoji nie zostało ustawione.",
                    color=0xFF0000,
                )
            else:
                # Validate emoji
                is_valid, error_msg = emoji_validator(emoji)
                if not is_valid:
                    await self._send_premium_embed(ctx, description=f"❌ {error_msg}", color=0xFF0000)
                else:
                    try:
                        team_icon = await emoji_to_icon(self.bot, ctx.guild, emoji)
                        await team_role.edit(icon=team_icon)
                    except Exception as e:
                        await self._send_premium_embed(
                            ctx, description=f"Błąd ustawiania emoji: {str(e)}", color=0xFF0000
                        )

    @team.command(name="delete")
    async def team_delete(self, ctx):
        """Delete a team (owner only)."""
        # Get user's team role
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            await self._send_premium_embed(ctx, description="❌ Nie posiadasz teamu!", color=0xFF0000)
            return

        async with self.bot.get_db() as session:
            role_service = await self.bot.get_service(IRoleService, session)

            # Check if user owns the team
            db_role = await role_service.get_role_by_id(team_role.id)
            if not db_role or db_role.name != str(ctx.author.id):
                await self._send_premium_embed(
                    ctx,
                    description="❌ Nie jesteś właścicielem tego teamu!",
                    color=0xFF0000,
                )
                return

            # Confirm deletion
            confirm_msg = await self._send_premium_embed(
                ctx,
                description=(
                    f"⚠️ **Czy na pewno chcesz usunąć team {team_role.mention}?**\n\n"
                    "Ta operacja jest nieodwracalna!\n"
                    "Zareaguj ✅ aby potwierdzić lub ❌ aby anulować."
                ),
                color=0xFFFF00,
            )

            # Add reactions
            await confirm_msg.add_reaction("✅")
            await confirm_msg.add_reaction("❌")

            # Wait for reaction
            def check(reaction, user):
                return (
                    user == ctx.author and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == confirm_msg.id
                )

            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            except Exception:
                await confirm_msg.delete()
                await self._send_premium_embed(ctx, description="❌ Czas na potwierdzenie minął.", color=0xFF0000)
                return

            await confirm_msg.delete()

            if str(reaction.emoji) == "❌":
                await self._send_premium_embed(ctx, description="❌ Usuwanie teamu anulowane.", color=0xFF0000)
                return

            # Delete from database
            await role_service.delete_role(db_role.id)
            await session.commit()

            # Delete team channel if exists
            team_info = await self._get_team_info(team_role)
            if team_info["channel"]:
                try:
                    await team_info["channel"].delete(reason=f"Team deleted by {ctx.author}")
                except Exception:
                    pass

            # Delete role
            try:
                await team_role.delete(reason=f"Team deleted by {ctx.author}")
                await self.message_sender.send_success(ctx, "Team został pomyślnie usunięty!")
            except Exception as e:
                logger.error(f"Error deleting team role: {str(e)}")
                await self.message_sender.send_error(ctx, f"Wystąpił błąd podczas usuwania teamu: {str(e)}")
