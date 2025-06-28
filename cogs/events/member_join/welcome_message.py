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
        self.force_channel_notifications = True  # Default to channel notifications
    
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
        is_returning: bool = False
    ) -> bool:
        """Send welcome message to new or returning member."""
        try:
            # Create welcome embed
            embed = self._create_welcome_embed(member, inviter, restored_roles, is_returning)
            
            # Try to send via DM first (unless forced to channel)
            if not self.force_channel_notifications:
                sent_dm = await self._send_welcome_dm(member, embed, inviter)
                if sent_dm:
                    return True
            
            # Send to welcome channel
            if self.welcome_channel:
                await self._send_welcome_channel(member, embed, inviter)
                return True
            else:
                logger.warning("No welcome channel configured")
                return False
                
        except Exception as e:
            logger.error(f"Error sending welcome message: {e}")
            return False
    
    def _create_welcome_embed(
        self,
        member: discord.Member,
        inviter: Optional[discord.User],
        restored_roles: int,
        is_returning: bool
    ) -> discord.Embed:
        """Create welcome embed based on member status."""
        if is_returning:
            title = f"🔄 Witaj ponownie, {member.display_name}!"
            description = f"Cieszymy się, że wróciłeś/aś na serwer **{self.guild.name}**!"
            color = discord.Color.green()
        else:
            title = f"👋 Witaj, {member.display_name}!"
            description = f"Witamy Cię na serwerze **{self.guild.name}**!"
            color = discord.Color.blue()
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc)
        )
        
        # Add member info
        embed.add_field(
            name="📊 Informacje",
            value=(
                f"**Członek #{member.guild.member_count}**\n"
                f"**Konto utworzone:** {discord.utils.format_dt(member.created_at, 'R')}"
            ),
            inline=True
        )
        
        # Add inviter info
        if inviter and inviter.id != self.guild.id:
            embed.add_field(
                name="🎟️ Zaproszony przez",
                value=f"{inviter.mention}\n({inviter})",
                inline=True
            )
        
        # Add restored roles info for returning members
        if is_returning and restored_roles > 0:
            embed.add_field(
                name="🔄 Przywrócone role",
                value=f"Przywrócono **{restored_roles}** ról",
                inline=True
            )
        
        # Add tips for new members
        if not is_returning:
            tips = [
                "📜 Przeczytaj regulamin w <#960665312624246864>",
                "🎭 Wybierz role w <#960665316109713421>",
                "💬 Przedstaw się na <#960665312624246865>",
                "❓ Potrzebujesz pomocy? Zapytaj na <#960665312624246866>"
            ]
            embed.add_field(
                name="💡 Pierwsze kroki",
                value="\n".join(tips),
                inline=False
            )
        
        # Set thumbnail and footer
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(
            text=f"ID: {member.id} | Serwer: {self.guild.name}",
            icon_url=self.guild.icon.url if self.guild.icon else None
        )
        
        return embed
    
    async def _send_welcome_dm(
        self,
        member: discord.Member,
        embed: discord.Embed,
        inviter: Optional[discord.User]
    ) -> bool:
        """Try to send welcome message via DM."""
        try:
            # Add server invite link to DM
            invite_link = "https://discord.gg/your-server"  # Replace with actual invite
            
            dm_embed = embed.copy()
            dm_embed.add_field(
                name="🔗 Link do serwera",
                value=f"[Kliknij tutaj]({invite_link})",
                inline=False
            )
            
            await member.send(embed=dm_embed)
            logger.info(f"Sent welcome DM to {member}")
            
            # Notify in welcome channel that DM was sent
            if self.welcome_channel:
                notify_msg = f"📨 Wysłano wiadomość powitalną do {member.mention}"
                if inviter and inviter.id != self.guild.id:
                    notify_msg += f" (zaproszony przez {inviter.mention})"
                
                await self.welcome_channel.send(
                    notify_msg,
                    allowed_mentions=AllowedMentions(users=[member])
                )
            
            return True
            
        except discord.Forbidden:
            logger.info(f"Cannot send DM to {member}, will use channel instead")
            return False
        except Exception as e:
            logger.error(f"Error sending welcome DM: {e}")
            return False
    
    async def _send_welcome_channel(
        self,
        member: discord.Member,
        embed: discord.Embed,
        inviter: Optional[discord.User]
    ) -> None:
        """Send welcome message to the welcome channel."""
        if not self.welcome_channel:
            return
        
        # Create mention message
        content = f"Witaj {member.mention}!"
        if inviter and inviter.id != self.guild.id:
            content += f" Dziękujemy {inviter.mention} za zaproszenie!"
        
        await self.welcome_channel.send(
            content=content,
            embed=embed,
            allowed_mentions=AllowedMentions(users=[member])
        )
        logger.info(f"Sent welcome message to channel for {member}")
    
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