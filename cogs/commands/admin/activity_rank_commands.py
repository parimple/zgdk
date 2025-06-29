"""Activity rank management commands for admins."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from core.interfaces import IPremiumService
from utils.message_sender import MessageSender
from utils.permissions import is_admin

logger = logging.getLogger(__name__)


class ActivityRankCommands(commands.Cog):
    """Commands for managing activity ranks."""

    def __init__(self, bot):
        """Initialize activity rank commands."""
        self.bot = bot
        self.message_sender = MessageSender(bot)
        self.config = bot.config.get("activity_ranks", {})

    @commands.hybrid_group(
        name="activityrank",
        aliases=["arank"],
        description="Zarządzanie rangami aktywności"
    )
    @is_admin()
    async def activity_rank(self, ctx: commands.Context):
        """Activity rank management group."""
        if ctx.invoked_subcommand is None:
            embed = discord.Embed(
                title="🏆 Zarządzanie rangami aktywności",
                description="Dostępne komendy:",
                color=discord.Color.blue()
            )
            
            embed.add_field(
                name="Komendy administracyjne",
                value=(
                    "`/activityrank set <numer> <nazwa>` - Zmień nazwę rangi\n"
                    "`/activityrank setcolor <numer> <kolor>` - Zmień kolor rangi\n"
                    "`/activityrank setpoints <numer> <punkty>` - Zmień próg punktowy\n"
                    "`/activityrank list` - Pokaż wszystkie rangi"
                ),
                inline=False
            )
            
            # Check if user has premium for customization
            if ctx.author.guild_permissions.administrator:
                embed.add_field(
                    name="Informacje",
                    value=(
                        f"Domyślnie dostępne: **{self.config.get('default_count', 2)}** rangi\n"
                        f"Z premium ({self.config.get('premium_customization', {}).get('required_role', 'zG500')}): "
                        f"do **{self.config.get('max_count', 99)}** rang"
                    ),
                    inline=False
                )
            
            await self.message_sender._send_embed(ctx, embed, reply=True)

    @activity_rank.command(
        name="set",
        description="Zmień nazwę rangi aktywności"
    )
    @is_admin()
    @discord.app_commands.describe(
        rank_number="Numer rangi (1-99)",
        name="Nowa nazwa rangi"
    )
    async def set_rank_name(
        self,
        ctx: commands.Context,
        rank_number: int,
        *,
        name: str
    ):
        """Set activity rank name."""
        try:
            # Validate rank number
            max_ranks = await self._get_max_ranks(ctx.guild)
            if rank_number < 1 or rank_number > max_ranks:
                await self.message_sender.send(
                    ctx,
                    text=f"❌ Numer rangi musi być między 1 a {max_ranks}!",
                    reply=True
                )
                return

            # Get or create rank role
            rank_role = await self._get_or_create_rank_role(ctx.guild, rank_number, name)
            
            # Update role name if it exists
            if rank_role.name != name:
                await rank_role.edit(name=name, reason=f"Activity rank renamed by {ctx.author}")
            
            embed = discord.Embed(
                title="✅ Ranga zaktualizowana",
                description=f"Ranga **{rank_number}** została nazwana: **{name}**",
                color=discord.Color.green()
            )
            
            await self.message_sender._send_embed(ctx, embed, reply=True)
            logger.info(f"Activity rank {rank_number} renamed to '{name}' by {ctx.author}")

        except discord.Forbidden:
            await self.message_sender.send(
                ctx,
                text="❌ Bot nie ma uprawnień do zarządzania rolami!",
                reply=True
            )
        except Exception as e:
            logger.error(f"Error setting rank name: {e}", exc_info=True)
            await self.message_sender.send(
                ctx,
                text=f"❌ Wystąpił błąd: {str(e)}",
                reply=True
            )

    @activity_rank.command(
        name="setcolor",
        description="Zmień kolor rangi aktywności"
    )
    @is_admin()
    @discord.app_commands.describe(
        rank_number="Numer rangi (1-99)",
        color="Kolor w formacie hex (np. #FFD700)"
    )
    async def set_rank_color(
        self,
        ctx: commands.Context,
        rank_number: int,
        color: str
    ):
        """Set activity rank color."""
        try:
            # Parse color
            if not color.startswith("#"):
                color = f"#{color}"
            
            discord_color = discord.Color.from_str(color)
            
            # Validate rank number
            max_ranks = await self._get_max_ranks(ctx.guild)
            if rank_number < 1 or rank_number > max_ranks:
                await self.message_sender.send(
                    ctx,
                    text=f"❌ Numer rangi musi być między 1 a {max_ranks}!",
                    reply=True
                )
                return

            # Get rank role
            rank_role = await self._get_rank_role(ctx.guild, rank_number)
            if not rank_role:
                await self.message_sender.send(
                    ctx,
                    text=f"❌ Ranga {rank_number} nie istnieje! Użyj najpierw `/activityrank set {rank_number} <nazwa>`",
                    reply=True
                )
                return

            # Update color
            await rank_role.edit(color=discord_color, reason=f"Activity rank color changed by {ctx.author}")
            
            embed = discord.Embed(
                title="✅ Kolor zaktualizowany",
                description=f"Kolor rangi **{rank_number}** został zmieniony",
                color=discord_color
            )
            
            await self.message_sender._send_embed(ctx, embed, reply=True)
            logger.info(f"Activity rank {rank_number} color changed to {color} by {ctx.author}")

        except ValueError:
            await self.message_sender.send(
                ctx,
                text="❌ Nieprawidłowy format koloru! Użyj formatu hex, np. #FFD700",
                reply=True
            )
        except Exception as e:
            logger.error(f"Error setting rank color: {e}", exc_info=True)
            await self.message_sender.send(
                ctx,
                text=f"❌ Wystąpił błąd: {str(e)}",
                reply=True
            )

    @activity_rank.command(
        name="list",
        description="Pokaż wszystkie rangi aktywności"
    )
    async def list_ranks(self, ctx: commands.Context):
        """List all activity ranks."""
        try:
            # Get all activity rank roles
            rank_roles = []
            for role in ctx.guild.roles:
                if role.name.startswith("ActivityRank_"):
                    try:
                        rank_num = int(role.name.split("_")[1])
                        rank_roles.append((rank_num, role))
                    except (IndexError, ValueError):
                        continue
            
            # Sort by rank number
            rank_roles.sort(key=lambda x: x[0])
            
            if not rank_roles:
                # Show default ranks from config
                default_ranks = self.config.get("default_ranks", [])
                embed = discord.Embed(
                    title="🏆 Rangi aktywności (domyślne)",
                    description="Rangi nie zostały jeszcze utworzone na serwerze",
                    color=discord.Color.blue()
                )
                
                for i, rank_config in enumerate(default_ranks, 1):
                    embed.add_field(
                        name=f"Ranga {i}: {rank_config['name']}",
                        value=f"Punkty: {rank_config['points_required']:,}\nKolor: {rank_config['color']}",
                        inline=True
                    )
            else:
                embed = discord.Embed(
                    title="🏆 Rangi aktywności",
                    description=f"Aktywne rangi: {len(rank_roles)}",
                    color=discord.Color.blue()
                )
                
                for rank_num, role in rank_roles[:25]:  # Discord limit
                    # Get role info
                    member_count = len(role.members)
                    embed.add_field(
                        name=f"Ranga {rank_num}: {role.name}",
                        value=f"Użytkownicy: {member_count}\nKolor: {role.color}",
                        inline=True
                    )
                
                if len(rank_roles) > 25:
                    embed.set_footer(text=f"Pokazano 25 z {len(rank_roles)} rang")
            
            await self.message_sender._send_embed(ctx, embed, reply=False)

        except Exception as e:
            logger.error(f"Error listing ranks: {e}", exc_info=True)
            await self.message_sender.send(
                ctx,
                text=f"❌ Wystąpił błąd podczas pobierania listy rang: {str(e)}",
                reply=True
            )

    async def _get_max_ranks(self, guild: discord.Guild) -> int:
        """Get maximum number of ranks allowed."""
        # Check if any member has premium role
        premium_role_name = self.config.get("premium_customization", {}).get("required_role", "zG500")
        premium_role = discord.utils.get(guild.roles, name=premium_role_name)
        
        if premium_role and len(premium_role.members) > 0:
            return self.config.get("max_count", 99)
        
        return self.config.get("default_count", 2)

    async def _get_rank_role(self, guild: discord.Guild, rank_number: int) -> Optional[discord.Role]:
        """Get activity rank role by number."""
        role_name = f"ActivityRank_{rank_number}"
        return discord.utils.get(guild.roles, name=role_name)

    async def _get_or_create_rank_role(
        self,
        guild: discord.Guild,
        rank_number: int,
        name: str
    ) -> discord.Role:
        """Get or create activity rank role."""
        # Check if role exists
        existing_role = await self._get_rank_role(guild, rank_number)
        if existing_role:
            return existing_role
        
        # Get default color from config
        default_ranks = self.config.get("default_ranks", [])
        default_color = discord.Color.default()
        
        if rank_number <= len(default_ranks):
            color_str = default_ranks[rank_number - 1].get("color", "#000000")
            try:
                default_color = discord.Color.from_str(color_str)
            except:
                pass
        
        # Create new role
        new_role = await guild.create_role(
            name=f"ActivityRank_{rank_number}",
            color=default_color,
            reason=f"Activity rank {rank_number} created"
        )
        
        # Set display name
        await new_role.edit(name=name)
        
        return new_role


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(ActivityRankCommands(bot))