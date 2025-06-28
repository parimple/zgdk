"""Welcome message functionality for new members."""

import logging
from typing import Optional
from datetime import datetime, timezone

import discord
from discord import AllowedMentions
from discord.ext import commands

logger = logging.getLogger(__name__)


class WelcomeMessageSender:
    """Handles sending welcome messages to new members."""
    
    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.welcome_channel: Optional[discord.TextChannel] = None
        self.force_channel_notifications = False  # Default to channel notifications (False = use channel)
    
    async def setup_welcome_channel(self) -> None:
        """Setup the welcome channel from config."""
        channel_id = self.bot.config.get("channels", {}).get("on_join")
        if channel_id:
            channel = self.guild.get_channel(channel_id)
            if channel and isinstance(channel, discord.TextChannel):
                self.welcome_channel = channel
                logger.info(f"Welcome channel set to: {channel.name}")
            else:
                logger.warning(f"Welcome channel {channel_id} not found or not a text channel")
    
    async def send_welcome_message(
        self, 
        member: discord.Member, 
        inviter: Optional[discord.User] = None,
        restored_roles: int = 0,
        is_returning: bool = False,
        mute_info: Optional[dict] = None
    ) -> bool:
        """Send member join log to the log channel."""
        try:
            # Create log embed
            embed = self._create_log_embed(member, inviter, restored_roles, is_returning, mute_info)
            
            # Always send to log channel
            if self.welcome_channel:
                await self._send_log_message(member, embed, inviter)
                return True
            else:
                logger.warning("No log channel configured")
                return False
                
        except Exception as e:
            logger.error(f"Error sending join log: {e}")
            return False
    
    def _create_log_embed(
        self,
        member: discord.Member,
        inviter: Optional[discord.User],
        restored_roles: int,
        is_returning: bool,
        mute_info: Optional[dict]
    ) -> discord.Embed:
        """Create technical log embed for member join."""
        # Determine join type and color
        if is_returning:
            title = f"[REJOIN] {member} ({member.id})"
            color = discord.Color.yellow()
        else:
            title = f"[JOIN] {member} ({member.id})"
            color = discord.Color.green()
        
        embed = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Basic account info
        account_age = (datetime.now(timezone.utc) - member.created_at.replace(tzinfo=timezone.utc)).days
        embed.add_field(
            name="Account Info",
            value=(
                f"**Created:** {discord.utils.format_dt(member.created_at, 'f')}\n"
                f"**Age:** {account_age} days\n"
                f"**Member #** {member.guild.member_count}"
            ),
            inline=True
        )
        
        # Inviter info
        if inviter:
            if inviter.id == self.guild.id:
                invite_info = "**Inviter:** Vanity URL"
            else:
                invite_info = f"**Inviter:** {inviter} ({inviter.id})"
        else:
            invite_info = "**Inviter:** Unknown"
        
        embed.add_field(
            name="Invite Info",
            value=invite_info,
            inline=True
        )
        
        # Status info
        status_info = []
        if is_returning:
            status_info.append("✅ Returning member")
            if restored_roles > 0:
                status_info.append(f"✅ Restored {restored_roles} roles")
        else:
            status_info.append("🆕 New member")
        
        # Mute info
        if mute_info:
            active_mutes = mute_info.get('active_mutes', [])
            mute_history = mute_info.get('total_mutes', 0)
            
            if active_mutes:
                mute_types = [m.get('type', 'unknown') for m in active_mutes]
                status_info.append(f"⚠️ Active mutes: {', '.join(mute_types)}")
            
            if mute_history > 0:
                status_info.append(f"📊 Mute history: {mute_history} total")
        
        embed.add_field(
            name="Status",
            value="\n".join(status_info) if status_info else "No special status",
            inline=True
        )
        
        # Risk assessment
        risk_factors = []
        if account_age < 7:
            risk_factors.append("🔴 Account < 7 days old")
        elif account_age < 30:
            risk_factors.append("🟡 Account < 30 days old")
        
        if mute_info and mute_info.get('total_mutes', 0) > 3:
            risk_factors.append("🔴 Multiple mute history")
        elif mute_info and mute_info.get('total_mutes', 0) > 0:
            risk_factors.append("🟡 Has mute history")
        
        if not member.avatar:
            risk_factors.append("🟡 No avatar")
        
        if risk_factors:
            embed.add_field(
                name="Risk Factors",
                value="\n".join(risk_factors),
                inline=False
            )
        
        # Set thumbnail
        embed.set_thumbnail(url=member.display_avatar.url)
        
        return embed
    
    
    async def _send_log_message(
        self,
        member: discord.Member,
        embed: discord.Embed,
        inviter: Optional[discord.User]
    ) -> None:
        """Send join log to the log channel."""
        if not self.welcome_channel:
            return
        
        # No mentions in log channel - just pure log
        await self.welcome_channel.send(
            embed=embed,
            allowed_mentions=AllowedMentions.none()
        )
        logger.info(f"Logged member join for {member}")
    
    async def send_error_notification(
        self,
        member: discord.Member,
        error_type: str,
        error_details: str
    ) -> None:
        """Send error notification to welcome channel."""
        if not self.welcome_channel:
            return
        
        embed = discord.Embed(
            title="⚠️ Błąd podczas dołączania członka",
            description=f"Wystąpił błąd podczas przetwarzania dołączenia {member.mention}",
            color=discord.Color.red(),
            timestamp=datetime.now(timezone.utc)
        )
        
        embed.add_field(
            name="Typ błędu",
            value=error_type,
            inline=True
        )
        
        embed.add_field(
            name="Szczegóły",
            value=error_details[:1024],  # Limit to 1024 chars
            inline=False
        )
        
        embed.set_footer(text=f"Member ID: {member.id}")
        
        await self.welcome_channel.send(
            embed=embed,
            allowed_mentions=AllowedMentions.none()
        )