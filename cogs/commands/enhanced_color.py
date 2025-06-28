"""
Enhanced color command with PydanticAI integration.
"""

import logging
from typing import Optional

import discord
from discord.ext import commands

from core.ai.color_parser import ColorParser
from core.interfaces.premium_interfaces import IPremiumService
from core.models.command import ColorInput
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class EnhancedColorCommands(commands.Cog):
    """Enhanced color commands with AI support."""

    def __init__(self, bot):
        """Initialize enhanced color commands."""
        self.bot = bot
        self.message_sender = MessageSender(bot)
        self.color_parser = ColorParser(use_ai=True)

        # Color configuration
        color_config = self.bot.config.get("color", {})
        self.color_role_name = color_config.get("role_name", "✎")
        self.base_role_id = color_config.get("base_role_id", 960665311772803184)

    @commands.hybrid_command(
        name="kolor_ai", description="Ustaw swój kolor z pomocą AI (Premium)", aliases=["color_ai", "colour_ai"]
    )
    @commands.guild_only()
    async def color_ai(self, ctx: commands.Context, *, color: str):
        """
        Ustaw własny kolor roli z parsowaniem AI.

        Przykłady:
        - /kolor_ai ciemny fiolet jak twitch
        - /kolor_ai morski ale jaśniejszy
        - /kolor_ai #FF00FF
        - /kolor_ai rgb(255, 0, 128)
        - /kolor_ai pomarańczowy zachód słońca
        """
        await ctx.defer()

        try:
            # Check premium status
            async with self.bot.get_db() as session:
                premium_service = await self.bot.get_service(IPremiumService, session)
                has_premium = await premium_service.has_any_premium_role(ctx.author.id)

                if not has_premium:
                    embed = discord.Embed(
                        title="❌ Wymagane Premium",
                        description="Własne kolory to funkcja premium.\nZdobądź premium używając `/sklep`",
                        color=discord.Color.red(),
                    )
                    await ctx.send(embed=embed)
                    return

            # Parse color with AI
            try:
                enhanced_color = await self.color_parser.parse(color)
            except ValueError as e:
                embed = discord.Embed(title="❌ Nieprawidłowy Kolor", description=str(e), color=discord.Color.red())
                embed.add_field(
                    name="Przykłady",
                    value="• Hex: `#FF00FF`\n• RGB: `rgb(255, 0, 255)`\n• Nazwa: `fioletowy`\n• Opis: `ciemny niebieski jak discord`",
                    inline=False,
                )
                await ctx.send(embed=embed)
                return

            # Create color preview embed
            preview_embed = discord.Embed(
                title="🎨 Podgląd Koloru",
                description=f"Ustawiam twój kolor na **{enhanced_color.hex_color}**",
                color=enhanced_color.discord_color,
            )

            # Add interpretation info
            if enhanced_color.confidence < 1.0:
                preview_embed.add_field(name="Interpretacja AI", value=enhanced_color.interpretation, inline=False)

            if enhanced_color.closest_named_color:
                preview_embed.add_field(
                    name="Najbliższy Nazwany Kolor", value=enhanced_color.closest_named_color.title(), inline=True
                )

            preview_embed.add_field(
                name="Wartości RGB",
                value=f"R: {enhanced_color.rgb[0]}, G: {enhanced_color.rgb[1]}, B: {enhanced_color.rgb[2]}",
                inline=True,
            )

            # Show preview
            await ctx.send(embed=preview_embed)

            # Apply the color role
            color_role = await self._create_or_update_color_role(ctx.author, enhanced_color.discord_color)

            if color_role:
                success_embed = discord.Embed(
                    title="✅ Kolor Zastosowany",
                    description=f"Twój kolor został ustawiony na {enhanced_color.hex_color}",
                    color=enhanced_color.discord_color,
                )
                if enhanced_color.confidence < 0.9:
                    success_embed.set_footer(text=f"Pewność AI: {enhanced_color.confidence:.0%}")
                await ctx.send(embed=success_embed)
            else:
                await ctx.send("❌ Nie udało się utworzyć roli koloru. Spróbuj ponownie.")

        except Exception as e:
            logger.error(f"Error in color_ai command: {e}")
            await ctx.send(f"❌ Wystąpił błąd: {str(e)}")

    async def _create_or_update_color_role(self, member: discord.Member, color_int: int) -> Optional[discord.Role]:
        """Create or update member's color role."""
        guild = member.guild
        role_name = f"{self.color_role_name} {member.display_name}"

        # Find existing color role
        color_role = None
        for role in member.roles:
            if role.name.startswith(self.color_role_name):
                color_role = role
                break

        try:
            if color_role:
                # Update existing role
                await color_role.edit(color=discord.Color(color_int), reason=f"Color update requested by {member}")
            else:
                # Create new role
                base_role = guild.get_role(self.base_role_id)
                position = base_role.position + 1 if base_role else 1

                color_role = await guild.create_role(
                    name=role_name, color=discord.Color(color_int), reason=f"Color role for {member}"
                )

                # Move to correct position
                await color_role.edit(position=position)

                # Add role to member
                await member.add_roles(color_role)

            return color_role

        except discord.HTTPException as e:
            logger.error(f"Failed to manage color role: {e}")
            return None

    @commands.hybrid_command(name="test_koloru", description="Testuj parsowanie kolorów AI bez aplikowania")
    @commands.guild_only()
    async def color_test(self, ctx: commands.Context, *, color: str):
        """Testuj parsowanie kolorów z AI."""
        await ctx.defer()

        try:
            # Try both parsers
            embed = discord.Embed(
                title="🎨 Test Parsowania Koloru", description=f"Wejście: `{color}`", color=discord.Color.blue()
            )

            # Traditional parsing
            try:
                basic_color = ColorInput.parse(color)
                embed.add_field(
                    name="✅ Tradycyjny Parser",
                    value=f"Hex: {basic_color.hex_color}\nRGB: {basic_color.rgb}",
                    inline=False,
                )
            except Exception as e:
                embed.add_field(name="❌ Tradycyjny Parser", value=f"Błąd: {str(e)}", inline=False)

            # AI parsing
            try:
                ai_color = await self.color_parser.parse(color)
                ai_text = f"Hex: {ai_color.hex_color}\nRGB: {ai_color.rgb}\n"
                ai_text += f"Pewność: {ai_color.confidence:.0%}\n"
                ai_text += f"Interpretacja: {ai_color.interpretation}"

                if ai_color.closest_named_color:
                    ai_text += f"\nNajbliższy: {ai_color.closest_named_color}"

                embed.add_field(name="🤖 Parser AI", value=ai_text, inline=False)

                # Update embed color to parsed color
                embed.color = ai_color.discord_color

            except Exception as e:
                embed.add_field(name="❌ Parser AI", value=f"Błąd: {str(e)}", inline=False)

            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Test nieudany: {str(e)}")


async def setup(bot):
    """Setup enhanced color commands."""
    await bot.add_cog(EnhancedColorCommands(bot))
