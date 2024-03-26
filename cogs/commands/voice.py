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

    async def determine_new_permission_value(
        self, current_channel, current_perms, permission_flag, value
    ):
        """Determine the new permission value."""
        if value is None:
            current_value = getattr(current_perms, permission_flag, None)
            if current_value is None:
                default_perms = (
                    current_channel.overwrites_for(self.bot.guild.default_role)
                    or PermissionOverwrite()
                )
                current_value = getattr(default_perms, permission_flag, None)
            return False if current_value is None else not current_value
        elif value == "+":
            return True
        elif value == "-":
            return False

    async def update_channel_and_db(self, ctx, target, current_perms, update_db):
        """Update the channel and the database."""
        await ctx.author.voice.channel.set_permissions(
            target or ctx.guild.default_role, overwrite=current_perms
        )

        if update_db:
            target_id = target.id if target else ctx.guild.id
            # allow_permissions = Permissions(current_perms.pair()[0])
            # deny_permissions = Permissions(current_perms.pair()[1])
            allow_bits, deny_bits = current_perms.pair()
            await self.update_permission_in_db(
                self.session,
                ctx.author.id,
                target_id,
                allow_bits,
                deny_bits,
                update_db,
            )

    async def move_to_afk_if_needed(self, ctx, target, target_channel, permission_flag, value):
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
        target: Optional[Member] = None,
        permission_flag: str = "",
        value: Optional[Literal["+", "-"]] = None,
        update_db: Optional[Literal["+", "-"]] = None,
    ):
        current_channel = ctx.author.voice.channel
        current_perms = current_channel.overwrites_for(target) or PermissionOverwrite()
        value = await self.determine_new_permission_value(
            current_channel, current_perms, permission_flag, value
        )
        setattr(current_perms, permission_flag, value)

        await self.update_channel_and_db(ctx, target, current_perms, update_db)

        mention_str = target.mention if target else "everyone"

        await ctx.reply(
            f"Ustawiono uprawnienie {permission_flag} na {value} dla {mention_str}.",
            allowed_mentions=AllowedMentions(users=False, roles=False),
        )

        target_channel = target.voice.channel if target and target.voice else None
        await self.move_to_afk_if_needed(ctx, target, target_channel, permission_flag, value)

    @commands.hybrid_command(aliases=["v"])
    @commands.has_permissions(administrator=True)
    async def view(
        self,
        ctx,
        target: Optional[Member] = None,
        can_view: Optional[Literal["+", "-"]] = None,
        update_db: Optional[Literal["+", "-"]] = None,
    ):
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


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(VoiceCog(bot))
