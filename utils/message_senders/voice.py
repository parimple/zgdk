"""Voice channel related message senders."""

from datetime import datetime, timezone
from typing import List, Optional, Union

import discord
from discord.ext import commands

from datasources.queries import MemberQueries
from utils.bump_checker import BumpChecker

from .base import BaseMessageSender


class VoiceMessageSender(BaseMessageSender):
    """Handles voice channel related messages."""

    async def send_voice_channel_info(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        channel: discord.VoiceChannel,
        owner: discord.Member,
        mods: List[discord.Member],
        disabled_perms: List[str],
    ) -> None:
        """Send voice channel information."""
        # Owner field
        owner_value = owner.mention if owner else "brak"

        # Moderators field
        mods_value = ", ".join(mod.mention for mod in mods) if mods else "brak"

        # Permissions field
        perm_to_cmd = {
            "połączenia": "connect",
            "mówienia": "speak",
            "streamowania": "live",
            "widzenia kanału": "view",
            "pisania": "text",
        }

        if disabled_perms:
            converted_perms = [f"`{perm_to_cmd.get(perm, perm)}`" for perm in disabled_perms]
            perms_value = ", ".join(converted_perms)
        else:
            perms_value = "brak"

        # Create message content
        base_text = (
            f"**Właściciel:** {owner_value} • **Moderatorzy:** {mods_value}\n**Wyłączone uprawnienia:** {perms_value}"
        )

        # Create embed with user's color
        embed = self._create_embed(description=base_text, ctx=ctx)

        # Add channel info directly to description
        if channel:
            _, channel_text = self._get_premium_text(ctx, channel)
            if channel_text:
                embed.description = f"{embed.description}\n{channel_text}"

        # Send the embed
        await self._send_embed(ctx=ctx, embed=embed, ephemeral=False, reply=True)

    async def send_not_in_voice_channel(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        action: str = "tej komendy",
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send not in voice channel message."""
        description = f"Musisz być na kanale głosowym, aby użyć {action}."

        # Check if user is in a voice channel
        if hasattr(ctx, "author"):
            member = ctx.author
        else:
            member = ctx.user

        if member.voice and member.voice.channel:
            # User is in voice but maybe wrong channel
            description = f"Musisz być na swoim kanale głosowym, aby użyć {action}."

        return await self.send_error(
            ctx=ctx,
            message=description,
            title="🎙️ Brak kanału głosowego",
            ephemeral=ephemeral,
        )

    async def send_channel_creation_info(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        channel: discord.VoiceChannel,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        """Send channel creation info."""
        # When called from voice state update, ctx might be a FakeContext
        # In that case, send directly to the channel
        if hasattr(ctx, "__class__") and ctx.__class__.__name__ == "FakeContext":
            # Get the owner from channel overwrites
            owner = None
            for target, overwrite in channel.overwrites.items():
                if isinstance(target, discord.Member) and overwrite.priority_speaker:
                    owner = target
                    break

            embed = self._create_embed(
                title="🎙️ Kanał utworzony!",
                description=f"Twój prywatny kanał {channel.mention} został utworzony.",
                color="success",
                ctx=owner,  # Use owner for color/author
                add_author=True,
            )

            embed.add_field(
                name="💡 Dostępne komendy",
                value=(
                    "`/voice limit <liczba>` - ustaw limit użytkowników\n"
                    "`/voice mod <@user>` - dodaj moderatora\n"
                    "`/voice kick <@user>` - wyrzuć użytkownika\n"
                    "`/voice ban <@user>` - zbanuj użytkownika\n"
                    "`/voice reset` - zresetuj wszystkie ustawienia"
                ),
                inline=False,
            )

            # Send directly to the channel
            return await channel.send(embed=embed)
        else:
            # Normal command context
            embed = self._create_embed(
                title="🎙️ Kanał utworzony!",
                description=f"Twój prywatny kanał {channel.mention} został utworzony.",
                color="success",
                ctx=ctx,
                add_author=True,
            )

            embed.add_field(
                name="💡 Dostępne komendy",
                value=(
                    "`/voice limit <liczba>` - ustaw limit użytkowników\n"
                    "`/voice mod <@user>` - dodaj moderatora\n"
                    "`/voice kick <@user>` - wyrzuć użytkownika\n"
                    "`/voice ban <@user>` - zbanuj użytkownika\n"
                    "`/voice reset` - zresetuj wszystkie ustawienia"
                ),
                inline=False,
            )

            return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_channel_reset(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        channel: discord.VoiceChannel,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send channel reset confirmation."""
        return await self.send_success(
            ctx=ctx,
            message=f"Kanał {channel.mention} został zresetowany do ustawień domyślnych.",
            title="🔄 Kanał zresetowany",
            ephemeral=ephemeral,
        )

    async def send_member_limit_set(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        channel: discord.VoiceChannel,
        limit: int,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send member limit set confirmation."""
        limit_text = f"{limit} użytkowników" if limit > 0 else "brak limitu"
        return await self.send_success(
            ctx=ctx,
            message=f"Limit użytkowników na kanale {channel.mention} ustawiony na: **{limit_text}**",
            title="👥 Limit ustawiony",
            ephemeral=ephemeral,
        )

    async def send_invalid_member_limit(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send invalid member limit message."""
        return await self.send_error(
            ctx=ctx,
            message="Limit musi być liczbą od 0 do 99.\n`0` oznacza brak limitu.",
            title="❌ Nieprawidłowy limit",
            ephemeral=ephemeral,
        )
