"""Base message sender with common functionality."""

from datetime import datetime, timezone
from typing import Optional, Union, List, Tuple

import discord
from discord import AllowedMentions
from discord.ext import commands


class BaseMessageSender:
    """Base class for message sending functionality."""

    # Kolory dla różnych typów wiadomości
    COLORS = {
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "info": discord.Color.blue(),
        "warning": discord.Color.orange(),
    }

    def __init__(self, bot=None):
        self.bot = bot

    @staticmethod
    def _create_embed(
        title: str = None,
        description: str = None,
        color: str = None,
        fields: list = None,
        footer: str = None,
        ctx=None,
        add_author: bool = False,
    ) -> discord.Embed:
        """
        Creates a consistent embed with the given parameters.
        Also sets embed author if 'ctx' is provided and add_author is True.
        """
        # Get user's color if available
        embed_color = None
        if ctx:
            if isinstance(ctx, discord.Member):
                embed_color = ctx.color if ctx.color.value != 0 else None
            elif isinstance(ctx, commands.Context) and ctx.author:
                embed_color = ctx.author.color if ctx.author.color.value != 0 else None
            elif isinstance(ctx, discord.Interaction) and ctx.user:
                # Handle interactions
                if isinstance(ctx.user, discord.Member):
                    embed_color = ctx.user.color if ctx.user.color.value != 0 else None

        # Use provided color or user's color
        if color and isinstance(color, str):
            # Only override user color if a specific color type is requested
            embed_color = BaseMessageSender.COLORS.get(color, embed_color)
        elif color and isinstance(color, discord.Color):
            embed_color = color

        # Default to blue if no color specified
        if not embed_color:
            embed_color = discord.Color.blue()

        embed = discord.Embed(
            title=title,
            description=description,
            color=embed_color,
        )

        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get("name", ""),
                    value=field.get("value", ""),
                    inline=field.get("inline", True),
                )

        if footer:
            embed.set_footer(text=footer)

        # Set author if requested
        if add_author and ctx:
            author = None
            if isinstance(ctx, discord.Member):
                author = ctx
            elif isinstance(ctx, commands.Context) and ctx.author:
                author = ctx.author

            if author:
                embed.set_author(
                    name=author.display_name,
                    icon_url=author.display_avatar.url if author.display_avatar else None,
                )

        return embed

    @staticmethod
    def build_description(base_text: str, ctx, channel=None) -> str:
        """
        Builds a description with premium text if the user doesn't have premium.
        """
        from utils.bump_checker import BumpChecker
        from datasources.queries import MemberQueries
        
        if ctx is None:
            return base_text

        # Extract bot and member from context
        bot = None
        member = None
        
        if hasattr(ctx, 'bot'):
            bot = ctx.bot
        if isinstance(ctx, discord.Member):
            member = ctx
        elif hasattr(ctx, 'author'):
            member = ctx.author

        if not bot or not member:
            return base_text

        # Check if user has premium
        has_premium = False
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            
            async def check_premium():
                async with bot.get_db() as session:
                    db_member = await MemberQueries.get_or_add_member(
                        session, member.id, wallet_balance=0, joined_at=member.joined_at
                    )
                    return await db_member.has_premium_role(member, bot.config.get("premium_roles", []))
            
            if loop.is_running():
                # We're in an async context, but can't await here
                # Return base text for now
                return base_text
            else:
                has_premium = loop.run_until_complete(check_premium())
        except:
            # If we can't check premium, just return base text
            return base_text

        if has_premium:
            return base_text

        # Add premium text
        premium_text, premium_info = BaseMessageSender._get_premium_text(ctx, channel)
        return f"{base_text}\n\n{premium_text}"

    def _get_premium_text(self, ctx, channel=None) -> tuple[str, str]:
        """
        Get premium text for embed description.
        """
        if not hasattr(ctx, "bot") or not hasattr(ctx.bot, "config"):
            return "", ""

        mastercard = ctx.bot.config.get("emojis", {}).get("mastercard", "💳")
        premium_channel_id = ctx.bot.config["channels"]["premium_info"]
        
        # Try to get guild from ctx
        guild = None
        if hasattr(ctx, 'guild'):
            guild = ctx.guild
        elif hasattr(ctx, 'bot') and hasattr(ctx.bot, 'guild_id'):
            guild = ctx.bot.get_guild(ctx.bot.guild_id)
            
        if guild:
            premium_channel = guild.get_channel(premium_channel_id)
            premium_text = (
                f"Wybierz swój {premium_channel.mention} {mastercard}"
                if premium_channel
                else f"Wybierz swój <#{premium_channel_id}> {mastercard}"
            )
        else:
            premium_text = f"Wybierz swój <#{premium_channel_id}> {mastercard}"

        if not channel:
            # For non-voice commands, return only plan selection text
            return "", premium_text

        # For voice commands, return channel info
        return (
            f"Kanał: {channel.mention}",
            f"Kanał: {channel.mention} • {premium_text}",
        )

    async def _send_embed(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        embed: discord.Embed,
        ephemeral: bool = True,
        view: discord.ui.View = None,
        allowed_mentions: AllowedMentions = None,
        reply: bool = False,
    ) -> Optional[discord.Message]:
        """
        Sends an embed to the appropriate context.
        """
        try:
            if isinstance(ctx, discord.Interaction):
                if ctx.response.is_done():
                    return await ctx.followup.send(
                        embed=embed,
                        ephemeral=ephemeral,
                        view=view,
                        allowed_mentions=allowed_mentions or AllowedMentions.none(),
                    )
                else:
                    return await ctx.response.send_message(
                        embed=embed,
                        ephemeral=ephemeral,
                        view=view,
                        allowed_mentions=allowed_mentions or AllowedMentions.none(),
                    )
            else:
                # For regular context, use reply if requested
                if reply and ctx.message:
                    return await ctx.message.reply(
                        embed=embed,
                        view=view,
                        allowed_mentions=allowed_mentions or AllowedMentions.none(),
                    )
                else:
                    return await ctx.send(
                        embed=embed,
                        view=view,
                        allowed_mentions=allowed_mentions or AllowedMentions.none(),
                    )
        except Exception as e:
            print(f"Error sending embed: {e}")
            return None

    async def build_and_send_embed(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        title: str = None,
        description: str = None,
        color: str = None,
        fields: list = None,
        footer: str = None,
        ephemeral: bool = True,
        view: discord.ui.View = None,
        add_author: bool = False,
        allowed_mentions: AllowedMentions = None,
    ) -> Optional[discord.Message]:
        """
        Builds and sends an embed with the given parameters.
        """
        embed = self._create_embed(
            title=title,
            description=description,
            color=color,
            fields=fields,
            footer=footer,
            ctx=ctx,
            add_author=add_author,
        )
        
        return await self._send_embed(
            ctx=ctx,
            embed=embed,
            ephemeral=ephemeral,
            view=view,
            allowed_mentions=allowed_mentions,
        )

    async def send_success(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        message: str,
        title: str = "✅ Sukces",
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send a success message."""
        return await self.build_and_send_embed(
            ctx=ctx,
            title=title,
            description=message,
            color="success",
            ephemeral=ephemeral,
        )

    async def send_error(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        message: str,
        title: str = "❌ Błąd",
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send an error message."""
        return await self.build_and_send_embed(
            ctx=ctx,
            title=title,
            description=message,
            color="error",
            ephemeral=ephemeral,
        )

    async def send_user_not_found(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send user not found message."""
        return await self.send_error(
            ctx=ctx,
            message="Nie znaleziono użytkownika.",
            title="❌ Użytkownik nie znaleziony",
            ephemeral=ephemeral,
        )