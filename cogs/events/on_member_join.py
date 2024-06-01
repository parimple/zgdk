"""On Member Join Event"""

import logging
from datetime import datetime, timezone

from discord import AllowedMentions
from discord.ext import commands

from datasources.queries import MemberQueries

logger = logging.getLogger(__name__)


class OnMemberJoinEvent(commands.Cog):
    """Class for handling the event when a member joins the Discord server."""

    def __init__(self, bot):
        self.bot = bot
        self.guild = bot.guild
        self.session = bot.session
        self.invites = bot.invites
        self.channel = bot.guild.get_channel(bot.channels.get("on_join"))

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """
        Event triggered when a member joins the guild.

        This method retrieves the current invites and compares them with previous invites
        to identify which invite was used. If the invite is not identified, the member is
        still added to the database with a characteristic ID. A notification is sent to the
        specific text channel in either case.

        :param member: The member who joined the guild
        """
        # Fetch the current invites
        new_invites = await member.guild.invites()

        # Convert the new invites to a dictionary
        new_invites_dict = {invite.id: invite for invite in new_invites}

        # Find the used invite
        used_invite = None
        for invite_id, new_invite in new_invites_dict.items():
            old_invite = self.invites.get(invite_id)
            if old_invite and old_invite.uses < new_invite.uses:
                used_invite = new_invite
                await self.process_invite(member, new_invite)
                break

        # Handle the case when no invite was identified
        if used_invite is None:
            await self.process_unknown_invite(member)

        # Update the invites dictionary
        self.invites = new_invites_dict

    async def process_invite(self, member, invite):
        """
        Process the used invite.

        This method checks if the inviter exists in the database, adds them if they don't,
        and updates or adds the member's record in the database with details about
        the invite used. It also sends a message to a specific text channel about the new
        member and the invite used.

        :param member: The member who joined
        :param invite: The invite that was used
        """
        inviter_id = (
            invite.inviter.id if invite.inviter else self.guild.id
        )  # Use guild ID if inviter is unknown

        async with self.session() as session:
            # Check if the inviter exists in the members table, if not, add them
            await MemberQueries.get_or_add_member(session, inviter_id)

            # Check if the member already exists and set the inviter
            db_member = await MemberQueries.get_or_add_member(session, member.id)
            if db_member.first_inviter_id is None or db_member.first_inviter_id == self.guild.id:
                db_member.first_inviter_id = inviter_id
                db_member.joined_at = datetime.now(timezone.utc)

            # Update the current_inviter_id and rejoined_at fields
            db_member.current_inviter_id = inviter_id
            db_member.rejoined_at = datetime.now(timezone.utc)

            # Commit the changes to the database
            await session.commit()

        # logger.info("Member %s joined using invite %s from %s", member.id, invite.code, inviter_id
        await self.channel.send(
            f"{member.mention} {member.display_name} zaproszony przez {invite.inviter.mention} "
            f"Kod: {invite.code}, Użycia: {invite.uses}",
            allowed_mentions=AllowedMentions(users=False),
        )

    async def process_unknown_invite(self, member):
        """
        Process an unknown invite. Adds the member to the database
        with a characteristic ID and sends a notification.
        """
        characteristic_id = self.guild.id

        async with self.session() as session:
            # Add the member with the characteristic ID
            await MemberQueries.get_or_add_member(
                session, member.id, first_inviter_id=characteristic_id
            )
            await session.commit()

        await self.channel.send(
            f"{member.mention} {member.display_name} zaproszony przez {self.bot.user.mention} "
            f"Kod: {self.guild.vanity_url_code}",
            allowed_mentions=AllowedMentions(users=False),
        )

    @commands.Cog.listener()
    async def on_invite_create(self, invite):
        """
        Event triggered when an invite is created.

        :param invite: The invite that was created.
        """
        # Add the new invite to the invites dictionary
        self.invites[invite.id] = invite
        # logger.info("Invite %s created", invite.code)

    @commands.Cog.listener()
    async def on_invite_delete(self, invite):
        """
        Event triggered when an invite is deleted.

        :param invite: The invite that was deleted.
        """
        # Remove the deleted invite from the invites dictionary
        self.invites.pop(invite.id, None)
        logger.info("Invite %s deleted", invite.code)


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnMemberJoinEvent(bot))
