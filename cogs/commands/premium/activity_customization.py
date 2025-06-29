"""Premium activity rank customization commands."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from core.interfaces import IPremiumService
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class ActivityCustomization(commands.Cog):
    """Premium commands for customizing activity ranks."""

    def __init__(self, bot):
        """Initialize activity customization commands."""
        self.bot = bot
        self.message_sender = MessageSender(bot)
        self.config = bot.config.get("activity_ranks", {})

    @commands.hybrid_group(
        name="myrank",
        description="Personalizuj swoje rangi aktywności (Premium)"
    )
    async def my_rank(self, ctx: commands.Context):
        """Personal rank customization group."""
        if ctx.invoked_subcommand is None:
            # Check premium status
            has_premium = await self._check_premium(ctx)
            
            embed = discord.Embed(
                title="🌟 Personalizacja rang aktywności",
                color=discord.Color.gold() if has_premium else discord.Color.greyple()
            )
            
            if has_premium:
                embed.description = "Możesz personalizować swoje rangi aktywności!"
                embed.add_field(
                    name="Dostępne komendy",
                    value=(
                        "`/myrank create <numer> <nazwa>` - Stwórz własną rangę\n"
                        "`/myrank rename <numer> <nazwa>` - Zmień nazwę swojej rangi\n"
                        "`/myrank color <numer> <kolor>` - Zmień kolor rangi\n"
                        "`/myrank emoji <numer> <emoji>` - Dodaj emoji do rangi\n"
                        "`/myrank list` - Pokaż swoje rangi"
                    ),
                    inline=False
                )
                embed.add_field(
                    name="Limity",
                    value=f"Możesz stworzyć do **{self.config.get('max_count', 99)}** rang!",
                    inline=False
                )
            else:
                embed.description = "❌ Ta funkcja wymaga premium!"
                required_role = self.config.get("premium_customization", {}).get("required_role", "zG500")
                embed.add_field(
                    name="Wymagania",
                    value=f"Potrzebujesz rangi **{required_role}** lub wyższej",
                    inline=False
                )
                embed.add_field(
                    name="Co otrzymasz?",
                    value="\n".join(self.config.get("premium_customization", {}).get("features", [])),
                    inline=False
                )
            
            await self.message_sender._send_embed(ctx, embed, reply=True)

    @my_rank.command(
        name="create",
        description="Stwórz własną rangę aktywności"
    )
    @discord.app_commands.describe(
        rank_number="Numer rangi (1-99)",
        name="Nazwa twojej rangi",
        color="Kolor rangi (hex, opcjonalnie)",
        points="Wymagane punkty (opcjonalnie)"
    )
    async def create_rank(
        self,
        ctx: commands.Context,
        rank_number: int,
        name: str,
        color: Optional[str] = None,
        points: Optional[int] = None
    ):
        """Create custom activity rank."""
        try:
            # Check premium
            if not await self._check_premium(ctx):
                await self._send_premium_required(ctx)
                return
            
            # Validate rank number
            if rank_number < 1 or rank_number > self.config.get("max_count", 99):
                await self.message_sender.send(
                    ctx,
                    text=f"❌ Numer rangi musi być między 1 a {self.config.get('max_count', 99)}!",
                    reply=True
                )
                return
            
            # Check if user already has this rank
            user_rank_role = discord.utils.get(
                ctx.author.roles,
                name=f"CustomRank_{ctx.author.id}_{rank_number}"
            )
            
            if user_rank_role:
                await self.message_sender.send(
                    ctx,
                    text=f"❌ Już masz rangę nr {rank_number}! Użyj `/myrank rename` aby zmienić nazwę.",
                    reply=True
                )
                return
            
            # Parse color if provided
            rank_color = discord.Color.default()
            if color:
                if not color.startswith("#"):
                    color = f"#{color}"
                try:
                    rank_color = discord.Color.from_str(color)
                except:
                    await self.message_sender.send(
                        ctx,
                        text="⚠️ Nieprawidłowy kolor, używam domyślnego",
                        reply=True
                    )
            
            # Create the role
            new_role = await ctx.guild.create_role(
                name=f"CustomRank_{ctx.author.id}_{rank_number}",
                color=rank_color,
                reason=f"Custom activity rank created by {ctx.author}"
            )
            
            # Store custom name in bot's memory (in production, use database)
            if not hasattr(self.bot, "custom_rank_names"):
                self.bot.custom_rank_names = {}
            
            self.bot.custom_rank_names[new_role.id] = {
                "display_name": name,
                "owner_id": ctx.author.id,
                "rank_number": rank_number,
                "points_required": points or (rank_number * 1000)  # Default scaling
            }
            
            embed = discord.Embed(
                title="✅ Ranga utworzona!",
                description=f"Twoja ranga **{rank_number}** została utworzona",
                color=rank_color
            )
            embed.add_field(name="Nazwa", value=name, inline=True)
            embed.add_field(name="Numer", value=str(rank_number), inline=True)
            embed.add_field(
                name="Punkty wymagane",
                value=f"{points or (rank_number * 1000):,}",
                inline=True
            )
            
            await self.message_sender._send_embed(ctx, embed, reply=True)
            logger.info(f"Custom rank {rank_number} '{name}' created by {ctx.author}")

        except discord.Forbidden:
            await self.message_sender.send(
                ctx,
                text="❌ Bot nie ma uprawnień do tworzenia ról!",
                reply=True
            )
        except Exception as e:
            logger.error(f"Error creating custom rank: {e}", exc_info=True)
            await self.message_sender.send(
                ctx,
                text=f"❌ Wystąpił błąd: {str(e)}",
                reply=True
            )

    @my_rank.command(
        name="list",
        description="Pokaż swoje niestandardowe rangi"
    )
    async def list_my_ranks(self, ctx: commands.Context):
        """List user's custom ranks."""
        try:
            # Find all custom ranks for this user
            custom_ranks = []
            for role in ctx.guild.roles:
                if role.name.startswith(f"CustomRank_{ctx.author.id}_"):
                    try:
                        rank_num = int(role.name.split("_")[2])
                        custom_ranks.append((rank_num, role))
                    except (IndexError, ValueError):
                        continue
            
            if not custom_ranks:
                embed = discord.Embed(
                    title="📋 Twoje rangi aktywności",
                    description="Nie masz jeszcze żadnych niestandardowych rang",
                    color=discord.Color.greyple()
                )
                
                if await self._check_premium(ctx):
                    embed.add_field(
                        name="Jak zacząć?",
                        value="Użyj `/myrank create <numer> <nazwa>` aby stworzyć swoją pierwszą rangę!",
                        inline=False
                    )
            else:
                custom_ranks.sort(key=lambda x: x[0])
                
                embed = discord.Embed(
                    title="📋 Twoje rangi aktywności",
                    description=f"Masz {len(custom_ranks)} niestandardowych rang",
                    color=discord.Color.gold()
                )
                
                for rank_num, role in custom_ranks[:25]:
                    # Get custom name from bot's memory
                    rank_info = getattr(self.bot, "custom_rank_names", {}).get(role.id, {})
                    display_name = rank_info.get("display_name", role.name)
                    points = rank_info.get("points_required", rank_num * 1000)
                    
                    embed.add_field(
                        name=f"Ranga {rank_num}: {display_name}",
                        value=f"Punkty: {points:,}\nKolor: {role.color}",
                        inline=True
                    )
            
            await self.message_sender._send_embed(ctx, embed, reply=False)

        except Exception as e:
            logger.error(f"Error listing custom ranks: {e}", exc_info=True)
            await self.message_sender.send(
                ctx,
                text=f"❌ Wystąpił błąd: {str(e)}",
                reply=True
            )

    async def _check_premium(self, ctx: commands.Context) -> bool:
        """Check if user has required premium role."""
        try:
            async with self.bot.get_db() as session:
                premium_service = await self.bot.get_service(IPremiumService, session)
                premium_roles = await premium_service.get_member_premium_roles(ctx.author.id)
                
                required_role = self.config.get("premium_customization", {}).get("required_role", "zG500")
                valid_roles = ["zG500", "zG1000"]  # Roles that have this feature
                
                if required_role == "zG500":
                    return any(role["role_name"] in valid_roles for role in premium_roles)
                
                return any(role["role_name"] == required_role for role in premium_roles)
                
        except Exception as e:
            logger.error(f"Error checking premium status: {e}")
            return False

    async def _send_premium_required(self, ctx: commands.Context):
        """Send premium required message."""
        required_role = self.config.get("premium_customization", {}).get("required_role", "zG500")
        
        embed = discord.Embed(
            title="❌ Premium wymagane!",
            description=f"Ta funkcja wymaga rangi **{required_role}** lub wyższej",
            color=discord.Color.red()
        )
        
        embed.add_field(
            name="Co otrzymasz z premium?",
            value="\n".join(self.config.get("premium_customization", {}).get("features", [])),
            inline=False
        )
        
        embed.add_field(
            name="Jak otrzymać?",
            value="Odwiedź `/shop` aby zobaczyć dostępne rangi premium!",
            inline=False
        )
        
        await self.message_sender._send_embed(ctx, embed, reply=True)


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(ActivityCustomization(bot))