"""Autokick related message senders."""

from typing import Dict, List, Optional, Union

import discord
from discord.ext import commands

from .base import BaseMessageSender


class AutokickMessageSender(BaseMessageSender):
    """Handles autokick related messages."""

    async def send_autokick_added(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        user: discord.Member,
        channel: discord.VoiceChannel,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send autokick added confirmation."""
        return await self.send_success(
            ctx=ctx,
            message=(
                f"✅ {user.mention} został dodany do listy autokick "
                f"dla kanału {channel.mention}.\n"
                f"Zostanie automatycznie wyrzucony przy próbie dołączenia."
            ),
            title="🚫 Autokick dodany",
            ephemeral=ephemeral,
        )

    async def send_autokick_removed(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        user: discord.Member,
        channel: discord.VoiceChannel,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send autokick removed confirmation."""
        return await self.send_success(
            ctx=ctx,
            message=(
                f"✅ {user.mention} został usunięty z listy autokick "
                f"dla kanału {channel.mention}.\n"
                f"Może teraz dołączyć do kanału."
            ),
            title="✅ Autokick usunięty",
            ephemeral=ephemeral,
        )

    async def send_autokick_already_exists(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        user: discord.Member,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send autokick already exists message."""
        return await self.send_error(
            ctx=ctx,
            message=f"{user.mention} jest już na liście autokick!",
            title="❌ Już istnieje",
            ephemeral=ephemeral,
        )

    async def send_autokick_not_found(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        user: discord.Member,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send autokick not found message."""
        return await self.send_error(
            ctx=ctx,
            message=f"{user.mention} nie znajduje się na liście autokick!",
            title="❌ Nie znaleziono",
            ephemeral=ephemeral,
        )

    async def send_autokick_limit_reached(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        max_autokicks: int,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send autokick limit reached message."""
        base_text = f"Osiągnięto limit {max_autokicks} użytkowników na liście autokick!"

        # Get voice channel
        member = ctx.author if hasattr(ctx, "author") else ctx.user
        channel = member.voice.channel if member.voice else None

        description = self.build_description(base_text, ctx, channel)

        embed = self._create_embed(
            title="❌ Limit autokick",
            description=description,
            color="error",
        )

        # Add premium info
        embed.add_field(
            name="💎 Premium",
            value="Z rolą premium możesz dodać więcej użytkowników do autokick!",
            inline=False,
        )

        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_autokick_list(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        autokicks: List[Dict],
        channel: discord.VoiceChannel,
        max_autokicks: int,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send autokick list for a channel."""
        embed = self._create_embed(
            title=f"🚫 Lista autokick - {channel.name}",
            color="info",
        )

        if autokicks:
            # Group by moderator who added them
            by_mod = {}
            for ak in autokicks:
                mod_id = ak.get("added_by", "unknown")
                if mod_id not in by_mod:
                    by_mod[mod_id] = []
                by_mod[mod_id].append(ak)

            # Create list
            autokick_list = []
            for mod_id, users in by_mod.items():
                mod = ctx.guild.get_member(int(mod_id)) if mod_id != "unknown" else None
                mod_name = mod.display_name if mod else "Nieznany"

                for user_data in users:
                    user = ctx.guild.get_member(user_data["user_id"])
                    if user:
                        autokick_list.append(f"• {user.mention} - dodane przez {mod_name}")

            embed.add_field(
                name=f"Użytkownicy ({len(autokicks)}/{max_autokicks})",
                value="\n".join(autokick_list[:10]),  # Limit to 10 entries
                inline=False,
            )

            if len(autokick_list) > 10:
                embed.add_field(
                    name="",
                    value=f"... i {len(autokick_list) - 10} więcej",
                    inline=False,
                )
        else:
            embed.description = "Lista autokick jest pusta."

        # Add commands info
        embed.add_field(
            name="📝 Zarządzanie autokick",
            value=(
                "`/voice autokick add @user` - dodaj do autokick\n"
                "`/voice autokick remove @user` - usuń z autokick\n"
                "`/voice autokick clear` - wyczyść listę"
            ),
            inline=False,
        )

        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_autokick_list_empty(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        channel: discord.VoiceChannel,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send autokick list empty message."""
        return await self.build_and_send_embed(
            ctx=ctx,
            title=f"📋 Lista autokick - {channel.name}",
            description="Lista autokick jest pusta.",
            color="info",
            ephemeral=ephemeral,
        )

    async def send_autokick_notification(
        self,
        user: discord.Member,
        channel: discord.VoiceChannel,
        moderator: discord.Member = None,
    ) -> None:
        """Send autokick notification to user via DM."""
        try:
            embed = self._create_embed(
                title="🚫 Zostałeś wyrzucony z kanału",
                description=(
                    f"Zostałeś automatycznie wyrzucony z kanału **{channel.name}** "
                    f"na serwerze **{channel.guild.name}**.\n\n"
                    f"Jesteś na liście autokick tego kanału."
                ),
                color="error",
            )

            if moderator:
                embed.add_field(
                    name="Dodane przez",
                    value=moderator.mention,
                    inline=True,
                )

            embed.set_footer(text="Skontaktuj się z właścicielem kanału, aby usunąć Cię z listy.")

            await user.send(embed=embed)
        except discord.Forbidden:
            # User has DMs disabled
            pass
        except Exception as e:
            print(f"Failed to send autokick notification: {e}")

    async def send_no_autokick_permission(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send no autokick permission message."""
        return await self.send_error(
            ctx=ctx,
            message=(
                "Nie masz uprawnień do zarządzania listą autokick!\n"
                "Tylko właściciel i moderatorzy kanału mogą to robić."
            ),
            title="🚫 Brak uprawnień",
            ephemeral=ephemeral,
        )
