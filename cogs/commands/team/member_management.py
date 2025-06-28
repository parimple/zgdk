"""Team member management commands."""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from core.interfaces.premium_interfaces import IPremiumService
from core.interfaces.role_interfaces import IRoleService
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class MemberManagementCommands:
    """Team member invitation, kicking, and transfer commands."""

    def __init__(self, bot):
        """Initialize member management commands."""
        self.bot = bot
        self.message_sender = MessageSender(bot)

        # Team configuration
        team_config = self.bot.config.get("team", {})
        self.team_symbol = team_config.get("symbol", "☫")
        self.team_category_id = team_config.get("category_id", 1344105013357842522)

    async def _get_user_team_role(self, member: discord.Member) -> Optional[discord.Role]:
        """Get user's team role if they have one."""
        for role in member.roles:
            if role.name.startswith(f"{self.team_symbol} "):
                return role
        return None

    async def _send_premium_embed(
        self, ctx, description: str, color: int = 0x00FF00, title: str = "Team Management"
    ) -> Optional[discord.Message]:
        """Send an embed message with premium information if applicable."""
        embed = discord.Embed(title=f"{self.team_symbol} {title}", description=description, color=color)

        # Add premium information if user doesn't have premium
        premium_text = ""
        async with self.bot.get_db() as session:
            premium_service = await self.bot.get_service(IPremiumService, session)
            if premium_service and ctx.guild:
                premium_service.set_guild(ctx.guild)
                has_premium = await premium_service.has_premium_role(ctx.author)

                if not has_premium:
                    premium_text = "\n\n💎 **Funkcja Premium**\nDostępna dla: <@&1027629813788106814>, <@&1027629916951326761>, <@&1027630008227659826>"

        if premium_text:
            embed.description = description + premium_text

        return await ctx.send(embed=embed)

    @commands.command(name="team_invite")
    @app_commands.describe(member="Użytkownik do zaproszenia")
    async def team_invite(self, ctx, member: discord.Member):
        """Invite a member to your team."""
        # Get invoker's team role
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            await self._send_premium_embed(ctx, description="❌ Nie posiadasz teamu!", color=0xFF0000)
            return

        # Check if user owns the team
        async with self.bot.get_db() as session:
            role_service = await self.bot.get_service(IRoleService, session)
            premium_service = await self.bot.get_service(IPremiumService, session)

            db_role = await role_service.get_role_by_id(team_role.id)
            if not db_role or db_role.name != str(ctx.author.id):
                await self._send_premium_embed(
                    ctx,
                    description="❌ Nie jesteś właścicielem tego teamu!",
                    color=0xFF0000,
                )
                return

            # Check if target already has a team
            target_team = await self._get_user_team_role(member)
            if target_team:
                await self._send_premium_embed(
                    ctx,
                    description=f"❌ {member.mention} już należy do teamu {target_team.mention}!",
                    color=0xFF0000,
                )
                return

            # Check team member limit
            premium_service.set_guild(ctx.guild)
            highest_premium = await premium_service.get_highest_premium_role(ctx.author)
            max_members = 5  # Default

            if highest_premium:
                premium_config = next(
                    (r for r in self.bot.config["premium_roles"] if r["name"] == highest_premium.name), None
                )
                if premium_config:
                    max_members = premium_config.get("team_members", 5)

            # Count current members
            current_members = len([m for m in ctx.guild.members if team_role in m.roles])
            if current_members >= max_members:
                await self._send_premium_embed(
                    ctx,
                    description=(
                        f"❌ Osiągnięto limit członków teamu ({current_members}/{max_members})!\n\n"
                        "Limity członków:\n"
                        "• <@&1027629813788106814> - 5 członków\n"
                        "• <@&1027629916951326761> - 10 członków\n"
                        "• <@&1027630008227659826> - 15 członków"
                    ),
                    color=0xFF0000,
                )
                return

            # Send invitation
            invite_msg = await member.send(
                embed=discord.Embed(
                    title=f"{self.team_symbol} Zaproszenie do teamu",
                    description=(
                        f"{ctx.author.mention} zaprasza Cię do teamu **{team_role.name[2:]}**!\n\n"
                        "Zareaguj ✅ aby dołączyć lub ❌ aby odrzucić zaproszenie."
                    ),
                    color=0x00FF00,
                )
            )

            await invite_msg.add_reaction("✅")
            await invite_msg.add_reaction("❌")

            await self._send_premium_embed(
                ctx,
                description=f"✅ Wysłano zaproszenie do {member.mention}!",
                color=0x00FF00,
            )

            # Wait for reaction
            def check(reaction, user):
                return user == member and str(reaction.emoji) in ["✅", "❌"] and reaction.message.id == invite_msg.id

            try:
                reaction, user = await self.bot.wait_for("reaction_add", timeout=300.0, check=check)
            except:
                await member.send("❌ Zaproszenie do teamu wygasło.")
                return

            if str(reaction.emoji) == "❌":
                await member.send("❌ Odrzuciłeś zaproszenie do teamu.")
                await ctx.author.send(f"❌ {member.mention} odrzucił zaproszenie do teamu.")
                return

            # Add member to team
            try:
                await member.add_roles(team_role)
                await member.send(f"✅ Dołączyłeś do teamu **{team_role.name[2:]}**!")
                await ctx.author.send(f"✅ {member.mention} dołączył do teamu **{team_role.name[2:]}**!")

                # Grant access to team channel if exists
                team_channel = discord.utils.get(
                    ctx.guild.channels, name=f"💬・{team_role.name[2:].lower().replace(' ', '-')}"
                )
                if team_channel:
                    await team_channel.set_permissions(member, read_messages=True, send_messages=True)

            except Exception as e:
                logger.error(f"Error adding member to team: {str(e)}")
                await member.send(f"❌ Wystąpił błąd podczas dodawania do teamu: {str(e)}")

    @commands.command(name="team_kick")
    @app_commands.describe(member="Użytkownik do wyrzucenia")
    async def team_kick(self, ctx, member: discord.Member):
        """Kick a member from your team."""
        # Get kicker's team role
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            await self._send_premium_embed(ctx, description="❌ Nie posiadasz teamu!", color=0xFF0000)
            return

        # Check if user owns the team
        async with self.bot.get_db() as session:
            role_service = await self.bot.get_service(IRoleService, session)

            db_role = await role_service.get_role_by_id(team_role.id)
            if not db_role or db_role.name != str(ctx.author.id):
                await self._send_premium_embed(
                    ctx,
                    description="❌ Nie jesteś właścicielem tego teamu!",
                    color=0xFF0000,
                )
                return

            # Check if target is in the team
            if team_role not in member.roles:
                await self._send_premium_embed(
                    ctx,
                    description=f"❌ {member.mention} nie należy do Twojego teamu!",
                    color=0xFF0000,
                )
                return

            # Can't kick yourself
            if member == ctx.author:
                await self._send_premium_embed(
                    ctx,
                    description="❌ Nie możesz wyrzucić samego siebie! Użyj `/team leave`.",
                    color=0xFF0000,
                )
                return

            # Remove from team
            try:
                await member.remove_roles(team_role)

                # Remove access to team channel if exists
                team_channel = discord.utils.get(
                    ctx.guild.channels, name=f"💬・{team_role.name[2:].lower().replace(' ', '-')}"
                )
                if team_channel:
                    await team_channel.set_permissions(member, overwrite=None)

                await self.message_sender.send_success(ctx, f"{member.mention} został wyrzucony z teamu!")

                # Notify kicked member
                try:
                    await member.send(
                        f"❌ Zostałeś wyrzucony z teamu **{team_role.name[2:]}** przez {ctx.author.mention}."
                    )
                except:
                    pass

            except Exception as e:
                logger.error(f"Error kicking member from team: {str(e)}")
                await self.message_sender.send_error(ctx, f"Wystąpił błąd podczas wyrzucania z teamu: {str(e)}")

    @commands.command(name="team_leave")
    async def team_leave(self, ctx):
        """Leave your current team."""
        # Get user's team role
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            await self._send_premium_embed(ctx, description="❌ Nie należysz do żadnego teamu!", color=0xFF0000)
            return

        async with self.bot.get_db() as session:
            role_service = await self.bot.get_service(IRoleService, session)

            # Check if user owns the team
            db_role = await role_service.get_role_by_id(team_role.id)
            if db_role and db_role.name == str(ctx.author.id):
                await self._send_premium_embed(
                    ctx,
                    description=(
                        "❌ Jesteś właścicielem tego teamu!\n\n"
                        "Możesz:\n"
                        "• Przekazać własność innemu członkowi: `/team transfer @user`\n"
                        "• Usunąć team: `/team delete`"
                    ),
                    color=0xFF0000,
                )
                return

            # Leave team
            try:
                await ctx.author.remove_roles(team_role)

                # Remove access to team channel if exists
                team_channel = discord.utils.get(
                    ctx.guild.channels, name=f"💬・{team_role.name[2:].lower().replace(' ', '-')}"
                )
                if team_channel:
                    await team_channel.set_permissions(ctx.author, overwrite=None)

                await self.message_sender.send_success(ctx, f"Opuściłeś team **{team_role.name[2:]}**!")

                # Notify team owner
                if db_role and db_role.name.isdigit():
                    owner = ctx.guild.get_member(int(db_role.name))
                    if owner:
                        try:
                            await owner.send(f"ℹ️ {ctx.author.mention} opuścił team **{team_role.name[2:]}**.")
                        except:
                            pass

            except Exception as e:
                logger.error(f"Error leaving team: {str(e)}")
                await self.message_sender.send_error(ctx, f"Wystąpił błąd podczas opuszczania teamu: {str(e)}")

    @commands.command(name="team_transfer")
    @app_commands.describe(member="Nowy właściciel teamu")
    async def team_transfer(self, ctx, member: discord.Member):
        """Transfer team ownership to another member."""
        # Get user's team role
        team_role = await self._get_user_team_role(ctx.author)
        if not team_role:
            await self._send_premium_embed(ctx, description="❌ Nie posiadasz teamu!", color=0xFF0000)
            return

        async with self.bot.get_db() as session:
            role_service = await self.bot.get_service(IRoleService, session)
            premium_service = await self.bot.get_service(IPremiumService, session)

            # Check if user owns the team
            db_role = await role_service.get_role_by_id(team_role.id)
            if not db_role or db_role.name != str(ctx.author.id):
                await self._send_premium_embed(
                    ctx,
                    description="❌ Nie jesteś właścicielem tego teamu!",
                    color=0xFF0000,
                )
                return

            # Check if target is in the team
            if team_role not in member.roles:
                await self._send_premium_embed(
                    ctx,
                    description=f"❌ {member.mention} nie należy do Twojego teamu!",
                    color=0xFF0000,
                )
                return

            # Can't transfer to yourself
            if member == ctx.author:
                await self._send_premium_embed(
                    ctx, description="❌ Nie możesz przekazać teamu samemu sobie!", color=0xFF0000
                )
                return

            # Check if new owner has premium
            premium_service.set_guild(ctx.guild)
            has_premium = await premium_service.has_premium_role(member)
            if not has_premium:
                await self._send_premium_embed(
                    ctx,
                    description=(
                        f"❌ {member.mention} nie posiada rangi premium wymaganej do posiadania teamu!\n\n"
                        "Wymagana jedna z rang:\n"
                        "• <@&1027629813788106814>\n"
                        "• <@&1027629916951326761>\n"
                        "• <@&1027630008227659826>"
                    ),
                    color=0xFF0000,
                )
                return

            # Transfer ownership
            try:
                # Update database
                db_role.name = str(member.id)
                await session.commit()

                await self.message_sender.send_success(
                    ctx,
                    f"Przekazano własność teamu **{team_role.name[2:]}** użytkownikowi {member.mention}!",
                )

                # Notify new owner
                try:
                    await member.send(f"✅ Otrzymałeś własność teamu **{team_role.name[2:]}** od {ctx.author.mention}!")
                except:
                    pass

            except Exception as e:
                logger.error(f"Error transferring team ownership: {str(e)}")
                await self.message_sender.send_error(ctx, f"Wystąpił błąd podczas przekazywania teamu: {str(e)}")
