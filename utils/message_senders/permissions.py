"""Permission related message senders."""

from typing import Optional, Union, List

import discord
from discord.ext import commands

from .base import BaseMessageSender


class PermissionsMessageSender(BaseMessageSender):
    """Handles permission related messages."""

    async def send_no_permission(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        reason: str = None,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send generic no permission message."""
        if reason is None:
            reason = "wykonania tej akcji!"
        
        base_text = f"Nie masz uprawnień do {reason}"
        channel = None
        
        # Get voice channel if user is in one
        if hasattr(ctx, 'author'):
            member = ctx.author
        else:
            member = ctx.user
            
        if member.voice:
            channel = member.voice.channel
        
        description = self.build_description(base_text, ctx, channel)
        
        return await self.send_error(
            ctx=ctx,
            message=description,
            title="🚫 Brak uprawnień",
            ephemeral=ephemeral,
        )

    async def send_no_mod_permission(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        channel: discord.VoiceChannel = None,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send no moderator permission message."""
        base_text = "Nie jesteś moderatorem tego kanału!"
        
        if not channel:
            # Try to get channel from context
            member = ctx.author if hasattr(ctx, 'author') else ctx.user
            if member.voice:
                channel = member.voice.channel
        
        description = self.build_description(base_text, ctx, channel)
        
        embed = self._create_embed(
            title="🚫 Brak uprawnień moderatora",
            description=description,
            color="error",
        )
        
        # Add tips
        embed.add_field(
            name="💡 Wskazówka",
            value=(
                "Tylko właściciel kanału może:\n"
                "• Dodawać i usuwać moderatorów\n"
                "• Zarządzać uprawnieniami moderatorów\n"
                "• Resetować kanał"
            ),
            inline=False,
        )
        
        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_permission_update(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        user: discord.Member,
        permission: str,
        enabled: bool,
        channel: discord.VoiceChannel,
        ephemeral: bool = False,
    ) -> Optional[discord.Message]:
        """Send permission update confirmation."""
        # Use original formatting
        mention_str = user.mention if isinstance(user, discord.Member) else "wszystkich"
        value_str = "+" if enabled else "-"
        
        # Map permission flag to command name
        permission_map = {
            "speak": "speak",
            "view_channel": "view", 
            "connect": "connect",
            "send_messages": "text",
            "stream": "live",
            "manage_messages": "mod"
        }
        command_name = permission_map.get(permission, permission)
        
        base_text = f"Ustawiono `{command_name}` na `{value_str}` dla {mention_str}"
        
        # Create embed with channel info - don't override user color for voice commands
        embed = self._create_embed(
            description=base_text,
            ctx=ctx
        )
        
        # Add channel info to description
        if channel:
            _, channel_text = self._get_premium_text(ctx, channel)
            if channel_text:
                embed.description = f"{embed.description}\n{channel_text}"
        
        # Send with reply=True to match original behavior
        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral, reply=True)

    async def send_permission_update_error(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        error: str,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send permission update error."""
        return await self.send_error(
            ctx=ctx,
            message=f"Nie udało się zaktualizować uprawnień: {error}",
            title="❌ Błąd uprawnień",
            ephemeral=ephemeral,
        )

    async def send_permission_reset(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        user: discord.Member,
        channel: discord.VoiceChannel,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send permission reset confirmation."""
        return await self.send_success(
            ctx=ctx,
            message=(
                f"Wszystkie uprawnienia dla {user.mention} "
                f"na kanale {channel.mention} zostały zresetowane."
            ),
            title="🔄 Uprawnienia zresetowane",
            ephemeral=ephemeral,
        )

    async def send_cant_modify_owner_permissions(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send can't modify owner permissions message."""
        return await self.send_error(
            ctx=ctx,
            message="Nie możesz modyfikować uprawnień właściciela kanału!",
            title="❌ Nie można zmienić uprawnień",
            ephemeral=ephemeral,
        )

    async def send_cant_modify_mod_permissions(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send can't modify mod permissions message."""
        return await self.send_error(
            ctx=ctx,
            message=(
                "Nie możesz modyfikować uprawnień innych moderatorów!\n"
                "Tylko właściciel kanału może to zrobić."
            ),
            title="❌ Brak uprawnień",
            ephemeral=ephemeral,
        )

    async def send_cant_remove_self_mod(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send can't remove self as mod message."""
        return await self.send_error(
            ctx=ctx,
            message="Nie możesz usunąć siebie jako moderatora!",
            title="❌ Nie można usunąć",
            ephemeral=ephemeral,
        )

    async def send_channel_mod_update(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        user: discord.Member,
        channel: discord.VoiceChannel,
        is_add: bool,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send channel moderator update message."""
        action = "dodany jako moderator" if is_add else "usunięty z moderatorów"
        emoji = "➕" if is_add else "➖"
        
        return await self.send_success(
            ctx=ctx,
            message=(
                f"{emoji} {user.mention} został {action} "
                f"kanału {channel.mention}"
            ),
            title="👮 Moderator zaktualizowany",
            ephemeral=ephemeral,
        )

    async def send_mod_limit_exceeded(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        max_mods: int,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send moderator limit exceeded message."""
        base_text = f"Osiągnięto limit {max_mods} moderatorów dla tego kanału!"
        
        # Get voice channel
        member = ctx.author if hasattr(ctx, 'author') else ctx.user
        channel = member.voice.channel if member.voice else None
        
        description = self.build_description(base_text, ctx, channel)
        
        embed = self._create_embed(
            title="❌ Limit moderatorów",
            description=description,
            color="error",
        )
        
        # Add premium info
        embed.add_field(
            name="💎 Premium",
            value="Z rolą premium możesz mieć więcej moderatorów!",
            inline=False,
        )
        
        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)

    async def send_mod_info(
        self,
        ctx: Union[discord.Interaction, commands.Context],
        mods: List[discord.Member],
        channel: discord.VoiceChannel,
        max_mods: int,
        ephemeral: bool = True,
    ) -> Optional[discord.Message]:
        """Send moderator info for a channel."""
        embed = self._create_embed(
            title=f"👮 Moderatorzy kanału {channel.name}",
            color="info",
        )
        
        if mods:
            mod_list = "\n".join([f"• {mod.mention}" for mod in mods])
            embed.add_field(
                name=f"Moderatorzy ({len(mods)}/{max_mods})",
                value=mod_list,
                inline=False,
            )
        else:
            embed.description = "Ten kanał nie ma moderatorów."
        
        # Add available commands
        embed.add_field(
            name="📝 Zarządzanie moderatorami",
            value=(
                "`/voice mod add @user` - dodaj moderatora\n"
                "`/voice mod remove @user` - usuń moderatora\n"
                "`/voice mod list` - lista moderatorów"
            ),
            inline=False,
        )
        
        return await self._send_embed(ctx=ctx, embed=embed, ephemeral=ephemeral)