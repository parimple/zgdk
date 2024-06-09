"""Voice commands cog."""
from typing import Literal, Optional

import discord
from discord import AllowedMentions, Member, PermissionOverwrite, Permissions
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession

from datasources.queries import ChannelPermissionQueries


class VoiceCog(commands.Cog):
    """Voice commands cog."""

    def __init__(self, bot):
        self.bot = bot
        self.session = bot.session

    async def update_permission_in_db(
        self,
        session: AsyncSession,
        member_id: int,
        target_id: int,
        allow_permissions_value: Permissions,
        deny_permissions_value: Permissions,
        update_db: Optional[Literal["+", "-"]],
    ):
        """Update the permission in the database."""
        if update_db is None:
            return

        if update_db == "+":
            await ChannelPermissionQueries.add_or_update_permission(
                session,
                member_id,
                target_id,
                allow_permissions_value,
                deny_permissions_value,
            )
        elif update_db == "-":
            await ChannelPermissionQueries.remove_permission(session, member_id, target_id)

    def determine_new_permission_value(
        self, current_perms, permission_flag, value, default_to_true=False, toggle=False
    ):
        """Determine the new permission value."""
        current_value = getattr(current_perms, permission_flag, None)

        if toggle:
            return None if current_value is True else True

        if value is None:
            if current_value is None:
                return True if default_to_true else False
            return not current_value

        if value == "+":
            return True
        if value == "-":
            if permission_flag == "manage_messages":
                return None
            return False

    async def update_channel_and_db(self, ctx, target, current_perms, update_db):
        """Update the channel and the database."""
        await ctx.author.voice.channel.set_permissions(target, overwrite=current_perms)

        if update_db:
            allow_bits, deny_bits = current_perms.pair()
            await self.update_permission_in_db(
                self.session, ctx.author.id, target.id, allow_bits, deny_bits, update_db
            )

    async def move_to_afk_if_needed(self, ctx, target, target_channel, permission_flag, value):
        """Move the target to the AFK channel if needed."""
        afk_channel_id = self.bot.config["channels_voice"]["afk"]
        afk_channel = ctx.guild.get_channel(afk_channel_id)

        if target and target_channel == ctx.author.voice.channel:
            if permission_flag in ["view_channel", "connect"] and not value:
                if afk_channel:
                    await target.move_to(afk_channel)
            if permission_flag == "speak" and not value:
                if afk_channel:
                    await target.move_to(afk_channel)
                    await target.move_to(ctx.author.voice.channel)

    async def modify_channel_permission(
        self,
        ctx,
        target: Member,
        permission_flag: str,
        value: Optional[Literal["+", "-"]],
        update_db: Optional[Literal["+", "-"]],
        default_to_true=False,
        toggle=False,
    ):
        """Modify the channel permission."""
        current_channel = ctx.author.voice.channel
        current_perms = current_channel.overwrites_for(target) or PermissionOverwrite()
        new_value = self.determine_new_permission_value(
            current_perms, permission_flag, value, default_to_true, toggle
        )
        setattr(current_perms, permission_flag, new_value)

        await self.update_channel_and_db(ctx, target, current_perms, update_db)

        mention_str = target.mention
        await ctx.reply(
            f"Ustawiono uprawnienie {permission_flag} na {new_value} dla {mention_str}.",
            allowed_mentions=AllowedMentions(users=False, roles=False),
        )

        target_channel = target.voice.channel if target.voice else None
        await self.move_to_afk_if_needed(ctx, target, target_channel, permission_flag, new_value)

    async def can_manage_channel(self, member, channel):
        """Check if a member has manage_messages permission on the channel."""
        overwrites = channel.overwrites_for(member)
        return overwrites.manage_messages is True

    async def can_assign_channel_mod(self, member, channel):
        """Check if a member has priority_speaker permission on the channel."""
        overwrites = channel.overwrites_for(member)
        return overwrites.priority_speaker is True

    async def get_premium_role_limit(self, member):
        """Get the maximum number of channel mods a member can assign based on their premium role."""
        premium_roles = self.bot.config["premium_roles"]
        for role in reversed(premium_roles):
            if any(r.name == role["name"] for r in member.roles):
                return premium_roles.index(role) + 1
        return 0

    @commands.hybrid_command(aliases=["v"])
    @commands.has_permissions(administrator=True)
    async def view(
        self,
        ctx,
        target: Optional[Member] = None,
        can_view: Optional[Literal["+", "-"]] = None,
        update_db: Optional[Literal["+", "-"]] = None,
    ):
        """Set the view permission for the target."""
        await self.modify_channel_permission(ctx, target, "view_channel", can_view, update_db)

    @commands.hybrid_command(aliases=["c"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Wybierz użytkownika",
        can_connect="Ustal uprawnienie do połączenia",
        update_db="Zaktualizuj uprawnienia w bazie danych",
    )
    async def connect(
        self,
        ctx,
        target: Optional[Member] = None,
        can_connect: Optional[Literal["+", "-"]] = None,
        update_db: Optional[Literal["+", "-"]] = None,
    ):
        """Set the connect permission for the target."""
        await self.modify_channel_permission(ctx, target, "connect", can_connect, update_db)

    @commands.hybrid_command(aliases=["s"])
    @commands.has_permissions(administrator=True)
    async def speak(
        self,
        ctx,
        target: Optional[Member] = None,
        can_speak: Optional[Literal["+", "-"]] = None,
        update_db: Optional[Literal["+", "-"]] = None,
    ):
        """Set the speak permission for the target."""
        await self.modify_channel_permission(ctx, target, "speak", can_speak, update_db)

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    async def join(self, ctx):
        """Join the voice channel of the person who used the command."""
        if ctx.author.voice is None:
            await ctx.send("Nie jesteś na żadnym kanale głosowym!")
            return

        channel = ctx.author.voice.channel

        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

        await ctx.send(f"Dołączono do {channel}")

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    async def limit(self, ctx, max_members: int):
        """Change the maximum number of members that can join the current voice channel."""
        if ctx.author.voice is None:
            await ctx.reply("Nie jesteś na żadnym kanale głosowym!")
            return

        if max_members < 1 or max_members > 99:
            await ctx.reply("Podaj liczbę członków od 1 do 99.")
            return

        voice_channel = ctx.author.voice.channel
        await voice_channel.edit(user_limit=max_members)
        await ctx.reply(f"Limit członków na kanale {voice_channel} ustawiony na {max_members}.")

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Użytkownik, którego chcesz dodać lub usunąć jako channel mod",
        can_manage="Ustal uprawnienie do zarządzania kanałem (+ lub -)",
        update_db="Zaktualizuj uprawnienia w bazie danych (+ lub -)",
    )
    async def channel_mod(
        self,
        ctx,
        target: Member,
        can_manage: Optional[Literal["+", "-"]] = None,
        update_db: Optional[Literal["+", "-"]] = None,
    ):
        """Set the can_manage permission for the target."""
        author = ctx.author
        voice_channel = author.voice.channel if author.voice else None

        if not voice_channel:
            await ctx.send("Nie jesteś na żadnym kanale głosowym!")
            return

        if not await self.can_assign_channel_mod(author, voice_channel):
            await ctx.send("Nie masz uprawnień do nadawania channel moda!")
            return

        if author == target and can_manage == "-":
            await ctx.send("Nie możesz odebrać sobie uprawnień do zarządzania kanałem!")
            return

        mod_limit = await self.get_premium_role_limit(author)
        current_mods = [
            target
            for target, overwrite in voice_channel.overwrites.items()
            if isinstance(target, discord.Member) and overwrite.manage_messages is True
        ]

        author_is_mod = await self.can_manage_channel(author, voice_channel)
        current_mods_count = len(current_mods)
        if author_is_mod:
            current_mods_count += 1

        if (
            can_manage == "+"
            or (can_manage is None and not await self.can_manage_channel(target, voice_channel))
        ) and current_mods_count > mod_limit:
            current_mods_mentions = ", ".join(
                [member.mention for member in current_mods if member != author]
            )
            await ctx.send(
                f"Możesz przypisać maksymalnie {mod_limit - 1} channel modów. Aktualni channel modzi: {current_mods_mentions}.",
                allowed_mentions=AllowedMentions(users=False, roles=False),
            )
            return

        await self.modify_channel_permission(
            ctx,
            target,
            "manage_messages",
            can_manage,
            update_db,
            default_to_true=True,
            toggle=(can_manage is None),
        )


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(VoiceCog(bot))
