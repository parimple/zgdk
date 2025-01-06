"""Message sender utility for sending formatted messages."""

import discord
from discord import AllowedMentions


class MessageSender:
    """Handles sending messages to the server."""

    # Kolory dla różnych typów wiadomości
    COLORS = {
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "info": discord.Color.blue(),
        "warning": discord.Color.orange(),
    }

    @staticmethod
    def _create_embed(title, description=None, color="info", fields=None, footer=None):
        """Creates a consistent embed with the given parameters."""
        embed = discord.Embed(
            title=title,
            description=description,
            color=MessageSender.COLORS.get(color, MessageSender.COLORS["info"]),
        )

        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)

        if footer:
            embed.set_footer(text=footer)

        return embed

    @staticmethod
    async def _send_embed(ctx, embed, reply=False, allowed_mentions=None):
        """Sends an embed with consistent settings."""
        if allowed_mentions is None:
            allowed_mentions = AllowedMentions(users=False, roles=False)

        if reply:
            return await ctx.reply(embed=embed, allowed_mentions=allowed_mentions)
        return await ctx.send(embed=embed, allowed_mentions=allowed_mentions)

    @staticmethod
    async def send_permission_update(ctx, target, permission_flag, new_value):
        """Sends a message about the updated permission."""
        mention_str = target.mention if isinstance(target, discord.Member) else "wszystkich"
        value_str = "+" if new_value else "-"

        embed = MessageSender._create_embed(
            title="Aktualizacja Uprawnień",
            description=f"Ustawiono uprawnienie {permission_flag} na {value_str} dla {mention_str}.",
            color="success",
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_user_not_found(ctx):
        """Sends a message when the target user is not found."""
        embed = MessageSender._create_embed(
            title="Błąd",
            description="Nie znaleziono użytkownika.",
            color="error",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_not_in_voice_channel(ctx):
        """Sends a message when the user is not in a voice channel."""
        embed = MessageSender._create_embed(
            title="Błąd",
            description="Nie jesteś na żadnym kanale głosowym!",
            color="error",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_joined_channel(ctx, channel):
        """Sends a message when the bot joins a channel."""
        embed = MessageSender._create_embed(
            title="Dołączono do Kanału",
            description=f"Dołączono do {channel}",
            color="success",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_invalid_member_limit(ctx):
        """Sends a message when an invalid member limit is provided."""
        embed = MessageSender._create_embed(
            title="Błąd",
            description="Podaj liczbę członków od 1 do 99.",
            color="error",
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_member_limit_set(ctx, voice_channel, limit_text):
        """Sends a message when the member limit is set."""
        embed = MessageSender._create_embed(
            title="Limit Członków",
            description=f"Limit członków na kanale {voice_channel} ustawiony na {limit_text}.",
            color="success",
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_no_mod_permission(ctx):
        """Sends a message when the user doesn't have permission to assign channel mods."""
        embed = MessageSender._create_embed(
            title="Brak Uprawnień",
            description="Nie masz uprawnień do nadawania channel moda!",
            color="error",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_cant_remove_self_mod(ctx):
        """Sends a message when the user tries to remove their own mod permissions."""
        embed = MessageSender._create_embed(
            title="Błąd",
            description="Nie możesz odebrać sobie uprawnień do zarządzania kanałem!",
            color="error",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_mod_limit_exceeded(ctx, mod_limit, current_mods):
        """Sends a message when the mod limit is exceeded."""
        current_mods_mentions = ", ".join(
            [member.mention for member in current_mods if member != ctx.author]
        )
        remaining_slots = max(0, mod_limit - len(current_mods))

        fields = [
            ("Aktualni Moderatorzy", current_mods_mentions or "brak", False),
            ("Pozostałe Sloty", str(remaining_slots), True),
            ("Limit Moderatorów", str(mod_limit), True),
        ]

        embed = MessageSender._create_embed(
            title="Limit Moderatorów",
            description="Osiągnięto limit moderatorów kanału.",
            color="warning",
            fields=fields,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_permission_limit_exceeded(ctx, permission_limit):
        """Sends a message when the permission limit is exceeded."""
        embed = MessageSender._create_embed(
            title="Limit Uprawnień",
            description=(
                f"Osiągnąłeś limit {permission_limit} uprawnień.\n"
                "Najstarsze uprawnienie nie dotyczące zarządzania wiadomościami zostało nadpisane."
            ),
            color="warning",
            footer="Aby uzyskać więcej uprawnień, rozważ zakup wyższej rangi premium.",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_channel_mod_update(ctx, target, is_mod, voice_channel, mod_limit):
        """Sends a message about updating channel mod status and displays mod information."""
        action = "nadano uprawnienia" if is_mod else "odebrano uprawnienia"

        # Get current mods from channel overwrites only
        current_mods = [
            t
            for t, overwrite in voice_channel.overwrites.items()
            if isinstance(t, discord.Member)
            and overwrite.manage_messages is True
            and not (overwrite.priority_speaker is True and t == ctx.author)
            and t != target
        ]

        if is_mod:
            current_mods.append(target)

        current_mods_mentions = ", ".join(
            [member.mention for member in current_mods if member != ctx.author]
        )
        remaining_slots = max(0, mod_limit - len(current_mods))

        fields = [
            ("Aktualni Moderatorzy", current_mods_mentions or "brak", False),
            ("Pozostałe Sloty", str(remaining_slots), True),
            ("Limit Moderatorów", str(mod_limit), True),
        ]

        embed = MessageSender._create_embed(
            title="Aktualizacja Moderatorów",
            description=f"{target.mention} {action} moderatora kanału.",
            color="success",
            fields=fields,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_voice_channel_info(ctx, author_info, target_info=None):
        """Sends a message with voice channel information."""
        fields = [("Twój Kanał", author_info, False)]
        if target_info:
            fields.append(("Kanał Użytkownika", target_info, False))

        embed = MessageSender._create_embed(
            title="Informacje o Kanale",
            fields=fields,
            color="info",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_no_premium_role(ctx, premium_channel_id):
        """Sends a message when user has no premium role."""
        embed = MessageSender._create_embed(
            title="Brak Rangi Premium",
            description=("Nie posiadasz żadnej rangi premium. Możesz przypisać 0 channel modów."),
            color="warning",
            footer=f"Jeśli chcesz mieć możliwość dodawania moderatorów, sprawdź kanał <#{premium_channel_id}>",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_permission_update_error(ctx, target, permission_flag):
        """Sends a message when there is an error updating the permission."""
        embed = MessageSender._create_embed(
            title="Błąd Aktualizacji Uprawnień",
            description=f"Nie udało się ustawić uprawnienia {permission_flag} dla {target.mention}.",
            color="error",
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_no_autokick_permission(ctx, premium_channel_id):
        """Sends a message when user doesn't have required role for autokick."""
        embed = MessageSender._create_embed(
            title="Brak Uprawnień Autokick",
            description=(
                "Nie posiadasz wymaganych uprawnień do używania autokicka.\n"
                "Aby móc używać autokicka, musisz posiadać rangę zG500 (1 slot) lub zG1000 (3 sloty)."
            ),
            color="warning",
            footer=f"Sprawdź dostępne rangi premium na kanale <#{premium_channel_id}>",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_limit_reached(ctx, max_autokicks, premium_channel_id):
        """Sends a message when user has reached their autokick limit."""
        embed = MessageSender._create_embed(
            title="Limit Autokick",
            description=f"Osiągnąłeś limit {max_autokicks} osób na liście autokick.",
            color="warning",
            footer=f"Aby móc dodać więcej osób, rozważ zakup wyższej rangi premium na kanale <#{premium_channel_id}>",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_already_exists(ctx, target):
        """Sends a message when target is already on autokick list."""
        embed = MessageSender._create_embed(
            title="Autokick",
            description=f"{target.mention} jest już na twojej liście autokick.",
            color="warning",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_added(ctx, target):
        """Sends a message when target is added to autokick list."""
        embed = MessageSender._create_embed(
            title="Autokick",
            description=f"Dodano {target.mention} do twojej listy autokick.",
            color="success",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_not_found(ctx, target):
        """Sends a message when target is not on autokick list."""
        embed = MessageSender._create_embed(
            title="Autokick",
            description=f"{target.mention} nie jest na twojej liście autokick.",
            color="error",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_removed(ctx, target):
        """Sends a message when target is removed from autokick list."""
        embed = MessageSender._create_embed(
            title="Autokick",
            description=f"Usunięto {target.mention} z twojej listy autokick.",
            color="success",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_list_empty(ctx):
        """Sends a message when autokick list is empty."""
        embed = MessageSender._create_embed(
            title="Lista Autokick",
            description="Twoja lista autokick jest pusta.",
            color="info",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_list(ctx, user_autokicks, max_autokicks):
        """Sends an embed with the user's autokick list."""
        fields = []
        for target_id in user_autokicks:
            member = ctx.guild.get_member(target_id)
            if member:
                fields.append((member.display_name, f"{member.mention}\nID: {member.id}", False))

        embed = MessageSender._create_embed(
            title="Twoja Lista Autokick",
            description="Lista użytkowników, którzy będą automatycznie wyrzucani z kanałów głosowych.",
            color="info",
            fields=fields,
            footer=f"Wykorzystano {len(user_autokicks)}/{max_autokicks} dostępnych slotów",
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_notification(channel, target, owner):
        """Sends a notification when a member is autokicked."""
        embed = MessageSender._create_embed(
            title="Autokick",
            description=f"{target.mention} został wyrzucony z kanału, ponieważ {owner.mention} ma go na liście autokick.",
            color="info",
        )
        await channel.send(embed=embed, allowed_mentions=AllowedMentions(users=False, roles=False))

    @staticmethod
    async def send_cant_modify_owner_permissions(ctx):
        """Sends a message when a mod tries to modify owner permissions."""
        embed = MessageSender._create_embed(
            title="Brak Uprawnień",
            description="Nie możesz modyfikować uprawnień właściciela kanału!",
            color="error",
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_cant_modify_mod_permissions(ctx):
        """Sends a message when a mod tries to modify other mod permissions."""
        embed = MessageSender._create_embed(
            title="Brak Uprawnień",
            description="Nie możesz modyfikować uprawnień innych moderatorów!",
            color="error",
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_mod_info(ctx, current_mods_mentions, mod_limit, remaining_slots):
        """Sends a message with mod information."""
        fields = [
            ("Aktualni Moderatorzy", current_mods_mentions or "brak", False),
            ("Pozostałe Sloty", str(remaining_slots), True),
            ("Limit Moderatorów", str(mod_limit), True),
        ]

        embed = MessageSender._create_embed(
            title="Informacje o Moderatorach",
            description="Lista aktualnych moderatorów kanału.",
            color="info",
            fields=fields,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)
