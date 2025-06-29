"""Category management commands for admins."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from core.exceptions import InvalidChannelType, ValidationException
from core.interfaces import IMemberService, IPremiumService
from utils.message_sender import MessageSender
from utils.permissions import is_admin, is_owner

logger = logging.getLogger(__name__)


class CategoryCommands(commands.Cog):
    """Commands for managing Discord categories."""

    def __init__(self, bot):
        """Initialize category commands."""
        self.bot = bot
        self.message_sender = MessageSender(bot)

    @commands.hybrid_command(
        name="createcategory",
        description="Tworzy nową kategorię z możliwością skopiowania uprawnień (płatna opcja)"
    )
    @is_admin()
    @discord.app_commands.describe(
        name="Nazwa nowej kategorii",
        copy_from="Kategoria z której skopiować uprawnienia (opcjonalne)",
        position="Pozycja kategorii (opcjonalne)",
    )
    async def create_category(
        self,
        ctx: commands.Context,
        name: str,
        copy_from: Optional[discord.CategoryChannel] = None,
        position: Optional[int] = None,
    ):
        """Create a new category with optional permission copying."""
        try:
            # Check if this is a paid feature
            async with ctx.bot.get_db() as session:
                member_service = await ctx.bot.get_service(IMemberService, session)
                premium_service = await ctx.bot.get_service(IPremiumService, session)
                
                # Check if member has premium for copying permissions
                has_premium = False
                if copy_from:
                    premium_roles = await premium_service.get_member_premium_roles(ctx.author.id)
                    # Check if member has zG500 or zG1000 (high tier premium)
                    high_tier_roles = ["zG500", "zG1000"]
                    has_premium = any(role["role_name"] in high_tier_roles for role in premium_roles)
                    
                    if not has_premium and not await ctx.bot.is_owner(ctx.author):
                        await self.message_sender.send(
                            ctx,
                            text="❌ Kopiowanie uprawnień wymaga rangi **zG500** lub wyższej!",
                            reply=True
                        )
                        return

            # Create category
            overwrites = {}
            if copy_from:
                # Copy permissions from source category
                overwrites = copy_from.overwrites.copy()
                logger.info(f"Copying permissions from category {copy_from.name}")

            new_category = await ctx.guild.create_category(
                name=name,
                overwrites=overwrites,
                position=position,
                reason=f"Created by {ctx.author} using createcategory command"
            )

            # Log the action
            logger.info(
                f"Category '{name}' created by {ctx.author} (ID: {ctx.author.id})"
                + (f" with permissions copied from '{copy_from.name}'" if copy_from else "")
            )

            # Send success message
            embed = discord.Embed(
                title="✅ Kategoria utworzona!",
                description=f"Utworzono kategorię **{new_category.name}**",
                color=discord.Color.green()
            )
            
            if copy_from:
                embed.add_field(
                    name="Skopiowane uprawnienia",
                    value=f"Z kategorii: **{copy_from.name}**",
                    inline=False
                )
                
            embed.add_field(
                name="ID kategorii",
                value=f"`{new_category.id}`",
                inline=True
            )
            
            if position is not None:
                embed.add_field(
                    name="Pozycja",
                    value=str(position),
                    inline=True
                )

            await self.message_sender._send_embed(ctx, embed, reply=True)

        except discord.Forbidden:
            await self.message_sender.send(
                ctx,
                text="❌ Bot nie ma uprawnień do tworzenia kategorii!",
                reply=True
            )
        except Exception as e:
            logger.error(f"Error creating category: {e}", exc_info=True)
            await self.message_sender.send(
                ctx,
                text=f"❌ Wystąpił błąd podczas tworzenia kategorii: {str(e)}",
                reply=True
            )

    @commands.hybrid_command(
        name="deletecategory",
        description="Usuwa kategorię (tylko właściciel)"
    )
    @is_owner()
    @discord.app_commands.describe(
        category="Kategoria do usunięcia",
        move_channels_to="Przenieś kanały do innej kategorii (opcjonalne)",
    )
    async def delete_category(
        self,
        ctx: commands.Context,
        category: discord.CategoryChannel,
        move_channels_to: Optional[discord.CategoryChannel] = None,
    ):
        """Delete a category with optional channel moving."""
        try:
            # Move channels if specified
            if move_channels_to and category.channels:
                for channel in category.channels:
                    await channel.edit(category=move_channels_to)
                    logger.info(f"Moved channel {channel.name} to {move_channels_to.name}")

            category_name = category.name
            category_id = category.id
            
            # Delete the category
            await category.delete(reason=f"Deleted by {ctx.author} using deletecategory command")
            
            logger.info(f"Category '{category_name}' (ID: {category_id}) deleted by {ctx.author}")

            embed = discord.Embed(
                title="🗑️ Kategoria usunięta",
                description=f"Usunięto kategorię **{category_name}**",
                color=discord.Color.red()
            )
            
            if move_channels_to:
                embed.add_field(
                    name="Przeniesione kanały",
                    value=f"Do kategorii: **{move_channels_to.name}**",
                    inline=False
                )

            await self.message_sender._send_embed(ctx, embed, reply=True)

        except discord.Forbidden:
            await self.message_sender.send(
                ctx,
                text="❌ Bot nie ma uprawnień do usuwania kategorii!",
                reply=True
            )
        except Exception as e:
            logger.error(f"Error deleting category: {e}", exc_info=True)
            await self.message_sender.send(
                ctx,
                text=f"❌ Wystąpił błąd podczas usuwania kategorii: {str(e)}",
                reply=True
            )


async def setup(bot):
    """Setup function for the cog."""
    await bot.add_cog(CategoryCommands(bot))