"""Profile-related commands."""

import logging
from typing import Optional

import discord
from discord.ext import commands

from .profile_helpers import get_profile_data, get_active_mutes
from .embed_builders import create_profile_embed
from .views import ProfileView, BuyRoleButton, SellRoleButton

logger = logging.getLogger(__name__)


class ProfileCommands(commands.Cog):
    """Commands for viewing user profiles."""
    
    def __init__(self, bot):
        self.bot = bot
        # Get team symbol from config
        team_config = self.bot.config.get("team", {})
        self.team_symbol = team_config.get("symbol", "☫")
    
    @commands.hybrid_command(
        name="profile", aliases=["p"], description="Wyświetla profil użytkownika."
    )
    async def profile(
        self, ctx: commands.Context, member: Optional[discord.Member] = None
    ):
        """Wyświetla profil użytkownika z informacjami o aktywności i zakupach."""
        # Handle interaction response for slash commands
        if ctx.interaction:
            await ctx.interaction.response.defer()
            
        if member is None:
            member = ctx.author

        logger.info(f"User {ctx.author} requested profile for {member}, interaction: {ctx.interaction is not None}")

        async with self.bot.get_db() as session:
            try:
                # Get all profile data
                profile_data = await get_profile_data(member, session, ctx, self.bot, self.team_symbol)
                
                # Get active mutes
                active_mutes, is_voice_muted = await get_active_mutes(member, ctx)
                
                # Create embed
                logger.info(f"Creating embed for {member}")
                embed = create_profile_embed(member, profile_data, active_mutes, is_voice_muted)
                logger.info(f"Embed created: {embed.title if embed else 'None'}")
                
                # Create view with buttons
                logger.info(f"Creating view for {member}")
                view = ProfileView(ctx, member, self.bot)
                
                # Show buy/sell buttons only for own profile
                if member == ctx.author:
                    view.add_item(BuyRoleButton())
                    
                    # Add sell button only if user has premium roles
                    if profile_data['premium_roles']:
                        view.add_item(SellRoleButton(self.bot))
                
                logger.info(f"Sending profile embed for {member}")
                try:
                    # For debugging, try sending without view first
                    if not ctx.guild:
                        logger.warning("No guild context - sending without view")
                        message = await ctx.send(embed=embed)
                    else:
                        message = await ctx.send(embed=embed, view=view)
                    logger.info(f"Profile embed sent successfully for {member}. Message ID: {message.id if message else 'None'}")
                except discord.Forbidden:
                    logger.error(f"Missing permissions to send embed in channel {ctx.channel.id}")
                    await ctx.send("❌ Nie mam uprawnień do wysyłania wiadomości z embedami w tym kanale.")
                except discord.HTTPException as e:
                    logger.error(f"HTTP exception when sending profile embed: {e}")
                    await ctx.send("❌ Wystąpił błąd podczas wysyłania profilu.")
                except Exception as e:
                    logger.error(f"Unexpected error sending profile embed: {e}")
                    raise
                
            except Exception as e:
                logger.error(f"Error getting profile for {member}: {e}")
                await ctx.send(
                    embed=discord.Embed(
                        title="❌ Błąd",
                        description="Wystąpił błąd podczas pobierania profilu.",
                        color=discord.Color.red()
                    )
                )