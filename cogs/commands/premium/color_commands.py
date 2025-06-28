"""Color commands for premium users."""

import logging
from typing import Optional

import discord
from colour import Color
from discord.ext import commands

from core.interfaces.premium_interfaces import IPremiumService
from core.interfaces.role_interfaces import IRoleService
from utils.message_sender import MessageSender
from utils.permissions import is_zagadka_owner

logger = logging.getLogger(__name__)


class ColorCommands(commands.Cog):
    """Color-related commands for premium users."""

    def __init__(self, bot):
        """Initialize color commands."""
        self.bot = bot
        self.message_sender = MessageSender(bot)

        # Color configuration
        color_config = self.bot.config.get("color", {})
        self.color_role_name = color_config.get("role_name", "✎")
        self.base_role_id = color_config.get("base_role_id", 960665311772803184)

    async def parse_color(self, color_input: str) -> discord.Color:
        """
        Parse color from various formats (hex, rgb, color name).

        :param color_input: Color in hex (#RRGGBB), rgb(r,g,b), or color name
        :return: discord.Color object
        :raises ValueError: If color format is invalid
        """
        try:
            # Remove whitespace
            color_input = color_input.strip()

            # Try to parse as hex
            if color_input.startswith("#"):
                # Discord.py expects hex without #
                hex_color = color_input[1:]
                return discord.Color(int(hex_color, 16))

            # Try to parse as RGB
            if color_input.lower().startswith("rgb"):
                # Extract numbers from rgb(r, g, b) format
                import re

                numbers = re.findall(r"\d+", color_input)
                if len(numbers) == 3:
                    r, g, b = map(int, numbers)
                    if all(0 <= val <= 255 for val in (r, g, b)):
                        return discord.Color.from_rgb(r, g, b)
                    else:
                        raise ValueError("RGB values must be between 0 and 255")
                else:
                    raise ValueError("Invalid RGB format. Use: rgb(r, g, b)")

            # Try to parse as color name using colour library
            try:
                color_obj = Color(color_input)
                # Convert to RGB and then to discord.Color
                rgb = color_obj.rgb
                return discord.Color.from_rgb(int(rgb[0] * 255), int(rgb[1] * 255), int(rgb[2] * 255))
            except Exception:
                # If all else fails, try as hex without #
                try:
                    return discord.Color(int(color_input, 16))
                except Exception:
                    raise ValueError(
                        f"Invalid color format: '{color_input}'. "
                        "Use hex (#RRGGBB), rgb(r,g,b), or color name (e.g., 'red', 'blue')"
                    )

        except ValueError:
            # Re-raise ValueError with original message
            raise
        except Exception as e:
            # Convert any other exception to ValueError
            raise ValueError(f"Error parsing color '{color_input}': {str(e)}")

    async def _create_color_role(self, ctx, member: discord.Member, color: discord.Color) -> Optional[discord.Role]:
        """Create or update a color role for a member."""
        role_name = f"{self.color_role_name} {member.display_name}"

        # Check if user already has a color role
        color_role = None
        for role in member.roles:
            if role.name.startswith(self.color_role_name):
                color_role = role
                break

        try:
            if color_role:
                # Update existing role
                await color_role.edit(color=color)
                logger.info(f"Updated color role for {member.display_name} to {color}")
            else:
                # Create new role
                color_role = await ctx.guild.create_role(
                    name=role_name, color=color, mentionable=False, reason=f"Color role for {member.display_name}"
                )

                # Position the role
                base_role = ctx.guild.get_role(self.base_role_id)
                if base_role:
                    await ctx.guild.edit_role_positions({color_role: base_role.position + 1})

                # Assign role to member
                await member.add_roles(color_role)
                logger.info(f"Created color role for {member.display_name} with color {color}")

                # Save to database
                async with self.bot.get_db() as session:
                    role_service = await self.bot.get_service(IRoleService, session)
                    await role_service.create_role(discord_id=color_role.id, name=str(member.id), role_type="color")
                    await session.commit()

            return color_role

        except discord.HTTPException as e:
            logger.error(f"Failed to create/update color role: {e}")
            raise

    async def _send_premium_embed(self, ctx, description: str, color: int = 0x00FF00) -> Optional[discord.Message]:
        """Send an embed message with premium information if applicable."""
        embed = discord.Embed(title="🎨 Kolor Roli", description=description, color=color)

        # Add premium information if user doesn't have premium
        premium_text = ""
        async with self.bot.get_db() as session:
            premium_service = await self.bot.get_service(IPremiumService, session)
            if premium_service and ctx.guild:
                premium_service.set_guild(ctx.guild)
                has_premium = await premium_service.has_premium_role(ctx.author)

                if not has_premium:
                    premium_roles = await premium_service.get_available_premium_roles()
                    if premium_roles:
                        role_mentions = [
                            f"<@&{role['role_id']}>"
                            for role in premium_roles
                            if role.get("perks", {}).get("custom_role_color")
                        ]
                        if role_mentions:
                            premium_text = f"\n\n💎 **Funkcja Premium**\nDostępna dla: {', '.join(role_mentions)}"

        if premium_text:
            full_description = description + premium_text
            embed.description = full_description
            return await ctx.send(embed=embed)
        else:
            return await ctx.send(embed=embed)

    @commands.hybrid_command(aliases=["colour", "kolor"])
    @is_zagadka_owner()
    async def color(self, ctx, *, color: Optional[str] = None):
        """
        Set or remove custom role color (Premium feature).

        Usage:
        - /color #FF0000 - Set color using hex code
        - /color rgb(255, 0, 0) - Set color using RGB
        - /color red - Set color using name
        - /color - Remove custom color

        Premium feature available for zG100+ members.
        """
        # Check if user has permission
        async with self.bot.get_db() as session:
            premium_service = await self.bot.get_service(IPremiumService, session)
            premium_service.set_guild(ctx.guild)

            # Check if user has premium role with color permission
            has_color_permission = await premium_service.has_premium_role(ctx.author)

            # Additionally check if the user has specific color-enabled roles
            if has_color_permission:
                # Check if any of user's premium roles have color feature
                color_enabled_roles = ["zG100", "zG500", "zG1000"]  # All premium roles have color feature
                has_color_permission = any(role.name in color_enabled_roles for role in ctx.author.roles)

            if not has_color_permission:
                await self._send_premium_embed(
                    ctx, description="Nie masz uprawnień do używania kolorów ról.", color=0xFF0000
                )
                return

        # If no color specified, remove color role
        if color is None:
            # Find and remove color role
            color_role = None
            for role in ctx.author.roles:
                if role.name.startswith(self.color_role_name):
                    color_role = role
                    break

            if color_role:
                await color_role.delete(reason=f"Color role removed by {ctx.author.display_name}")
                await self._send_premium_embed(ctx, description="✅ Twój kolor roli został usunięty.", color=0x00FF00)

                # Remove from database
                async with self.bot.get_db() as session:
                    role_service = await self.bot.get_service(IRoleService, session)
                    await role_service.delete_role(color_role.id)
                    await session.commit()
            else:
                await self._send_premium_embed(ctx, description="Nie masz ustawionego koloru roli.", color=0xFF0000)
            return

        # Parse and set color
        try:
            discord_color = await self.parse_color(color)
            color_role = await self._create_color_role(ctx, ctx.author, discord_color)

            if color_role:
                embed = discord.Embed(
                    title="🎨 Kolor Roli Ustawiony",
                    description=f"Twój kolor roli został ustawiony na {color_role.mention}",
                    color=discord_color,
                )

                # Add color preview
                embed.add_field(
                    name="Podgląd koloru",
                    value=f"Hex: #{str(discord_color.value).upper():06X}\n"
                    f"RGB: {discord_color.r}, {discord_color.g}, {discord_color.b}",
                    inline=False,
                )

                await ctx.send(embed=embed)

        except ValueError as e:
            await self._send_premium_embed(ctx, description=f"❌ {str(e)}", color=0xFF0000)
        except discord.HTTPException as e:
            await self._send_premium_embed(
                ctx, description=f"❌ Błąd podczas ustawiania koloru: {str(e)}", color=0xFF0000
            )
        except Exception as e:
            logger.error(f"Unexpected error in color command: {e}")
            await self._send_premium_embed(
                ctx, description="❌ Wystąpił nieoczekiwany błąd podczas ustawiania koloru.", color=0xFF0000
            )
