"""Main member join event handler."""

import asyncio
import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands, tasks
from sqlalchemy import select

from datasources.models import HandledPayment
from .invite_manager import InviteManager
from .role_restorer import RoleRestorer
from .welcome_message import WelcomeMessageSender

logger = logging.getLogger(__name__)


class OnMemberJoinEvent(commands.Cog):
    """Class for handling the event when a member joins the Discord server."""

    def __init__(self, bot):
        self.bot = bot
        self.guild = None
        
        # Initialize managers (will be set up after guild is ready)
        self.invite_manager = None
        self.role_restorer = None
        self.welcome_sender = None
        
        # Start setup tasks
        self.setup_guild.start()
        self.setup_channels.start()
        # clean_invites will be started after guild is set up

    @tasks.loop(count=1)
    async def setup_guild(self):
        """Setup guild and invites after bot is ready."""
        logger.info("Waiting for bot to be ready...")
        await self.bot.wait_until_ready()

        # Wait for guild to be set
        while self.bot.guild is None:
            logger.info("Waiting for guild to be set...")
            await asyncio.sleep(1)

        self.guild = self.bot.guild
        logger.info(f"Guild set: {self.guild.name}")
        
        # Initialize managers
        self.invite_manager = InviteManager(self.bot, self.guild)
        self.role_restorer = RoleRestorer(self.bot, self.guild)
        self.welcome_sender = WelcomeMessageSender(self.bot, self.guild)
        
        # Sync invites
        await self.invite_manager.sync_invites()
        
        # Start the clean invites task
        self.clean_invites.start()

    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.setup_guild.cancel()
        self.setup_channels.cancel()
        if self.clean_invites.is_running():
            self.clean_invites.cancel()

    @tasks.loop(count=1)
    async def setup_channels(self):
        """Setup channels after bot is ready."""
        await self.bot.wait_until_ready()
        
        # Wait for guild
        while self.guild is None:
            await asyncio.sleep(1)
        
        # Setup welcome channel
        if self.welcome_sender:
            await self.welcome_sender.setup_welcome_channel()

    @commands.hybrid_command(
        name="mutenotifications",
        description="Przełącz powiadomienia o przywróconych wyciszeniach"
    )
    @commands.has_permissions(manage_guild=True)
    async def toggle_mute_notifications(self, ctx, mode: str = None):
        """Toggle mute restoration notifications between DM and channel."""
        if mode:
            mode = mode.lower()
            if mode not in ["dm", "channel"]:
                await ctx.send("❌ Nieprawidłowy tryb. Użyj 'dm' lub 'channel'.")
                return
            
            self.bot.force_channel_notifications = (mode == "channel")
            if self.welcome_sender:
                self.welcome_sender.force_channel_notifications = (mode == "channel")
        else:
            # Toggle
            self.bot.force_channel_notifications = not self.bot.force_channel_notifications
            if self.welcome_sender:
                self.welcome_sender.force_channel_notifications = self.bot.force_channel_notifications
        
        current_mode = "channel" if self.bot.force_channel_notifications else "dm"
        await ctx.send(f"✅ Powiadomienia o przywróconych wyciszeniach: **{current_mode}**")

    @property
    def force_channel_notifications(self):
        """Get the current notification mode."""
        return getattr(self.bot, 'force_channel_notifications', True)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle member join event."""
        if not self.guild or member.guild.id != self.guild.id:
            return

        logger.info(f"Member joined: {member} (ID: {member.id})")
        
        # Check if member is returning and get mute info
        is_returning = False
        mute_info = None
        async with self.bot.get_db() as session:
            from core.interfaces.member_interfaces import IMemberService
            from core.repositories import ModerationRepository, RoleRepository
            
            member_service = await self.bot.get_service(IMemberService, session)
            try:
                db_member = await member_service.get_member(member)
                is_returning = True
            except:
                is_returning = False
            
            # Get mute information
            moderation_repo = ModerationRepository(session)
            role_repo = RoleRepository(session)
            
            # Get mute history
            mute_history = await moderation_repo.get_user_mute_history(member.id, limit=50)
            total_mutes = len([m for m in mute_history if m.action_type == "mute"])
            
            # Check for active mutes
            mute_role_ids = [role["id"] for role in self.bot.config.get("mute_roles", [])]
            active_mutes = []
            
            for role_config in self.bot.config.get("mute_roles", []):
                role_id = role_config["id"]
                role_type = role_config.get("description", "unknown")
                
                # Check if member has this mute role
                if member.get_role(role_id):
                    active_mutes.append({
                        'type': role_type,
                        'role_id': role_id
                    })
            
            mute_info = {
                'total_mutes': total_mutes,
                'active_mutes': active_mutes,
                'history': mute_history[:5] if mute_history else []
            }
        
        # Process invite tracking
        inviter = None
        if self.invite_manager:
            invite = await self.invite_manager.find_used_invite(member)
            if invite:
                inviter_id = await self.invite_manager.process_invite(member, invite)
                if inviter_id and inviter_id != self.guild.id:
                    inviter = self.guild.get_member(inviter_id)
            else:
                await self.invite_manager.process_unknown_invite(member)
            
            # Sync invites for next join
            await self.invite_manager.sync_invites()
        
        # Restore roles for returning members
        restored_roles_count = 0
        if is_returning and self.role_restorer:
            restored_roles = await self.role_restorer.restore_all_roles(member)
            restored_roles_count = len(restored_roles)
            
            # Restore voice permissions
            voice_perms = await self.role_restorer.restore_voice_permissions(member)
            if voice_perms > 0:
                logger.info(f"Restored {voice_perms} voice permissions for {member}")
        
        # Check for pending payments if member was unbanned and rejoined
        if is_returning:
            await self._check_pending_payments(member)
        
        # Send join log
        if self.welcome_sender:
            await self.welcome_sender.send_welcome_message(
                member=member,
                inviter=inviter,
                restored_roles=restored_roles_count,
                is_returning=is_returning,
                mute_info=mute_info
            )

    @commands.Cog.listener()
    async def on_invite_create(self, invite: discord.Invite):
        """Handle invite creation."""
        if invite.guild.id != self.guild.id:
            return
        
        if self.invite_manager:
            await self.invite_manager.handle_invite_create(invite)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite: discord.Invite):
        """Handle invite deletion."""
        if invite.guild.id != self.guild.id:
            return
        
        if self.invite_manager:
            await self.invite_manager.handle_invite_delete(invite)

    async def sync_invites(self):
        """Sync current invites with the bot's cache."""
        if self.invite_manager:
            await self.invite_manager.sync_invites()

    @tasks.loop(hours=6)
    async def clean_invites(self):
        """Periodically clean expired invites."""
        if self.invite_manager:
            cleaned = await self.invite_manager.clean_expired_invites()
            if cleaned > 0:
                logger.info(f"Cleaned {cleaned} expired invites")

    @clean_invites.before_loop
    async def before_clean_invites(self):
        """Wait for bot to be ready before starting clean invites loop."""
        await self.bot.wait_until_ready()
        # Additional wait to ensure everything is set up
        await asyncio.sleep(60)
    
    async def _check_pending_payments(self, member: discord.Member):
        """Check if member has pending payments from when they were banned."""
        # Removed - payment for unban is the unban itself, not premium
        pass

    async def notify_invite_deleted(self, user_id: int, invite_id: str):
        """Notify user that their invite was deleted."""
        try:
            user = self.bot.get_user(user_id) or await self.bot.fetch_user(user_id)
            if user:
                embed = discord.Embed(
                    title="🗑️ Zaproszenie usunięte",
                    description=(
                        f"Twoje zaproszenie **{invite_id}** zostało usunięte, "
                        f"ponieważ wygasło lub osiągnęło limit użyć."
                    ),
                    color=discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc)
                )
                embed.set_footer(text=f"Serwer: {self.guild.name}")
                
                await user.send(embed=embed)
                logger.info(f"Notified {user} about deleted invite {invite_id}")
        except discord.Forbidden:
            logger.info(f"Cannot send DM to user {user_id} about deleted invite")
        except Exception as e:
            logger.error(f"Error notifying user about deleted invite: {e}")