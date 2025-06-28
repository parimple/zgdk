"""Invite management functionality for member join events."""

import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

import discord
from discord.ext import commands

from core.interfaces.member_interfaces import IInviteService, IMemberService
from core.repositories import InviteRepository

logger = logging.getLogger(__name__)


class InviteManager:
    """Manages Discord invites and tracks their usage."""

    def __init__(self, bot: commands.Bot, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.invites: Dict[str, discord.Invite] = {}

    async def sync_invites(self) -> None:
        """Sync invites from Discord with the database."""
        if not self.guild:
            logger.warning("Guild not set, cannot sync invites")
            return

        try:
            invites = await self.guild.invites()
            new_invites = {invite.code: invite for invite in invites}
            self.invites = new_invites
            logger.info(f"Synced {len(invites)} invites")
        except discord.Forbidden:
            logger.error("Bot doesn't have permission to manage invites")
        except Exception as e:
            logger.error(f"Error syncing invites: {e}")

    async def find_used_invite(self, member: discord.Member) -> Optional[discord.Invite]:
        """Find which invite was used by comparing before and after states."""
        if not self.guild:
            return None

        try:
            # Get current invites
            current_invites = await self.guild.invites()

            # Find the invite that has increased uses
            for invite in current_invites:
                old_invite = self.invites.get(invite.code)
                if old_invite and invite.uses > old_invite.uses:
                    return invite

            # Check for new invites
            current_codes = {inv.code for inv in current_invites}
            old_codes = set(self.invites.keys())
            new_codes = current_codes - old_codes

            for code in new_codes:
                invite = next((inv for inv in current_invites if inv.code == code), None)
                if invite and invite.uses > 0:
                    return invite

        except Exception as e:
            logger.error(f"Error finding used invite: {e}")

        return None

    async def process_invite(self, member: discord.Member, invite: discord.Invite) -> Optional[int]:
        """Process the invite used by a member and return inviter ID."""
        async with self.bot.get_db() as session:
            invite_service = await self.bot.get_service(IInviteService, session)
            member_service = await self.bot.get_service(IMemberService, session)

            # Get or create the inviter
            inviter_id = None
            if invite.inviter:
                inviter = await member_service.get_or_create_member(invite.inviter)
                inviter_id = inviter.id if hasattr(inviter, "id") else inviter.discord_id

                logger.info(
                    f"Member {member} (ID: {member.id}) joined using invite "
                    f"{invite.code} from {invite.inviter} (ID: {invite.inviter.id})"
                )
            else:
                logger.info(
                    f"Member {member} (ID: {member.id}) joined using invite " f"{invite.code} with unknown inviter"
                )

            # Track the invite - interface expects invite object and creator member
            if invite.inviter:
                await invite_service.create_tracked_invite(invite=invite, creator=invite.inviter)

            # Update member's inviter information
            if inviter_id:
                db_member = await member_service.get_or_create_member(member)
                if not db_member.first_inviter_id:
                    # Set both first and current inviter
                    await member_service.update_member_info(db_member, current_inviter_id=inviter_id)
                    # Need to update first_inviter_id directly via repository
                    from core.repositories import MemberRepository

                    member_repo = MemberRepository(session)
                    # Update first_inviter_id
                    await member_repo.update_inviter(member.id, inviter_id, update_current=False)
                    # Also update current_inviter_id
                    await member_repo.update_inviter(member.id, inviter_id, update_current=True)
                else:
                    # Only update current inviter
                    await member_service.update_member_info(db_member, current_inviter_id=inviter_id)

            await session.commit()
            return inviter_id

    async def process_unknown_invite(self, member: discord.Member) -> None:
        """Process when we can't determine which invite was used."""
        logger.warning(f"Could not determine invite used by {member} (ID: {member.id})")

        async with self.bot.get_db() as session:
            member_service = await self.bot.get_service(IMemberService, session)

            # Get or create member
            db_member = await member_service.get_or_create_member(member)

            # Set unknown inviter (using guild ID as placeholder)
            if not db_member.first_inviter_id:
                await member_service.update_member_info(
                    db_member, current_inviter_id=self.guild.id  # Guild ID as "unknown" inviter
                )
                # Update first_inviter_id via repository
                from core.repositories import MemberRepository

                member_repo = MemberRepository(session)
                # Update first_inviter_id
                await member_repo.update_inviter(member.id, self.guild.id, update_current=False)
                # Also update current_inviter_id
                await member_repo.update_inviter(member.id, self.guild.id, update_current=True)

            await session.commit()

    async def clean_expired_invites(self) -> int:
        """Clean up expired invites from the database."""
        cleaned_count = 0

        async with self.bot.get_db() as session:
            try:
                # Get all tracked invites
                invite_repo = InviteRepository(session)
                all_invites = await invite_repo.get_all_invites()

                for db_invite in all_invites:
                    should_delete = False

                    # Check if invite has max age and is expired
                    if (
                        hasattr(db_invite, "max_age_seconds")
                        and db_invite.max_age_seconds
                        and db_invite.max_age_seconds > 0
                    ):
                        expiry_time = db_invite.created_at + timedelta(seconds=db_invite.max_age_seconds)
                        if datetime.now(timezone.utc) > expiry_time:
                            should_delete = True
                            logger.info(
                                f"Invite {db_invite.code} expired "
                                f"(created: {db_invite.created_at}, max_age: {db_invite.max_age_seconds}s)"
                            )

                    # Check if invite reached max uses
                    if (
                        hasattr(db_invite, "max_uses")
                        and db_invite.max_uses
                        and db_invite.max_uses > 0
                        and hasattr(db_invite, "uses")
                        and db_invite.uses >= db_invite.max_uses
                    ):
                        should_delete = True
                        logger.info(
                            f"Invite {db_invite.code} reached max uses " f"({db_invite.uses}/{db_invite.max_uses})"
                        )

                    # Delete if needed
                    if should_delete:
                        await invite_repo.delete_invite(db_invite.code)
                        cleaned_count += 1

                        # Notify if there was an inviter
                        if db_invite.inviter_id and db_invite.inviter_id != self.guild.id:
                            # This would be handled by the main event handler
                            pass

                await session.commit()

                if cleaned_count > 0:
                    logger.info(f"Cleaned {cleaned_count} expired invites")

            except Exception as e:
                logger.error(f"Error cleaning invites: {e}")
                await session.rollback()

        return cleaned_count

    async def handle_invite_create(self, invite: discord.Invite) -> None:
        """Handle when a new invite is created."""
        self.invites[invite.code] = invite
        logger.info(f"New invite created: {invite.code} by {invite.inviter}")

    async def handle_invite_delete(self, invite: discord.Invite) -> None:
        """Handle when an invite is deleted."""
        if invite.code in self.invites:
            del self.invites[invite.code]
            logger.info(f"Invite deleted: {invite.code}")
