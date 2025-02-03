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

    def __init__(self, bot=None):
        self.bot = bot

    @staticmethod
    def _create_embed(title, description=None, color="info", fields=None, footer=None, ctx=None):
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

        # Add author's avatar and name if context or member is provided
        if ctx:
            if isinstance(ctx, discord.Member):
                # If ctx is a Member object (e.g. from channel creation)
                embed.set_author(name=ctx.display_name, icon_url=ctx.display_avatar.url)
                if ctx.color.value != 0:
                    embed.colour = ctx.color
            elif hasattr(ctx, "author"):
                # If ctx is a Context object (from commands)
                embed.set_author(
                    name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url
                )
                if ctx.author.color.value != 0:
                    embed.colour = ctx.author.color

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
    def _with_premium_link(description: str, ctx) -> str:
        """Add premium channel link to description if ctx has bot config."""
        if not hasattr(ctx, "bot") or not hasattr(ctx.bot, "config"):
            return description

        premium_channel_id = ctx.bot.config["channels"]["premium_info"]
        premium_channel = ctx.guild.get_channel(premium_channel_id)
        premium_text = (
            f"**Rangi Premium:** {premium_channel.mention}"
            if premium_channel
            else f"**Rangi Premium:** <#{premium_channel_id}>"
        )

        # Sprawdź czy opis już zawiera informację o kanale
        if "**Kanał:**" in description:
            # Znajdź pozycję gdzie kończy się linia z informacją o kanale
            channel_info_end = description.find("**Kanał:**")
            channel_line_end = description.find("\n", channel_info_end)
            if channel_line_end == -1:  # Jeśli nie ma nowej linii, to znaczy że to ostatnia linia
                channel_line_end = len(description)

            # Wstaw informację o rangach premium na końcu linii z kanałem
            description = (
                description[:channel_line_end]
                + " • "
                + premium_text
                + description[channel_line_end:]
            )
        else:
            # Jeśli nie ma informacji o kanale, dodaj obie informacje w nowej linii
            description += f"\n**Kanał:** brak • {premium_text}"

        return description

    @staticmethod
    async def send_permission_update(ctx, target, permission_flag, new_value):
        """Sends a message about the updated permission."""
        mention_str = target.mention if isinstance(target, discord.Member) else "wszystkich"
        value_str = "+" if new_value else "-"
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            f"Ustawiono uprawnienie **{permission_flag}** na **{value_str}** "
            f"dla {mention_str}.\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Aktualizacja Uprawnień",
            description=description,
            color="success",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_user_not_found(ctx):
        """Sends a message when the target user is not found."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = f"Nie znaleziono użytkownika.\n\n**Kanał:** {channel_mention}"
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Błąd",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_not_in_voice_channel(ctx, target=None):
        """Sends a message when the user is not in a voice channel."""
        if target:
            description = f"{target.mention} nie jest na żadnym kanale głosowym!"
        else:
            description = "Nie jesteś na żadnym kanale głosowym!"

        # Jeśli sprawdzamy innego użytkownika, to pokazujemy jego kanał
        channel_mention = None
        if target and target.voice and target.voice.channel:
            channel_mention = target.voice.channel.mention
        elif ctx.author.voice and ctx.author.voice.channel:
            channel_mention = ctx.author.voice.channel.mention

        if channel_mention:
            description += f"\n\n**Kanał:** {channel_mention}"
        else:
            description += "\n\n**Kanał:** brak"

        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Błąd",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_joined_channel(ctx, channel):
        """Sends a message when the bot joins a channel."""
        description = f"Dołączono do {channel.mention}\n\n**Kanał:** {channel.mention}"
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Dołączono do Kanału",
            description=description,
            color="success",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_invalid_member_limit(ctx):
        """Sends a message when an invalid member limit is provided."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = f"Podaj liczbę członków od 1 do 99.\n\n**Kanał:** {channel_mention}"
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Błąd",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_member_limit_set(ctx, voice_channel, limit_text):
        """Sends a message when the member limit is set."""
        description = (
            f"Limit członków na kanale {voice_channel.mention} ustawiony na {limit_text}.\n\n"
            f"**Kanał:** {voice_channel.mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Limit Członków",
            description=description,
            color="success",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_no_mod_permission(ctx):
        """Sends a message when the user doesn't have permission to assign channel mods."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            f"Nie masz uprawnień do nadawania channel moda!\n\n**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Brak Uprawnień",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_cant_remove_self_mod(ctx):
        """Sends a message when the user tries to remove their own mod permissions."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            "Nie możesz odebrać sobie uprawnień do zarządzania kanałem!\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Błąd",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_mod_limit_exceeded(ctx, mod_limit, current_mods):
        """Sends a message when the mod limit is exceeded."""
        current_mods_mentions = ", ".join(
            [member.mention for member in current_mods if member != ctx.author]
        )
        remaining_slots = max(0, mod_limit - len(current_mods))
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        premium_channel_id = ctx.bot.config["channels"]["premium_info"]
        premium_channel = ctx.guild.get_channel(premium_channel_id)
        premium_text = (
            f"**Rangi Premium:** {premium_channel.mention}"
            if premium_channel
            else f"**Rangi Premium:** <#{premium_channel_id}>"
        )

        fields = [
            ("Aktualni Moderatorzy", current_mods_mentions or "brak", False),
            ("Pozostałe Sloty", str(remaining_slots), True),
            ("Limit Moderatorów", str(mod_limit), True),
        ]

        embed = MessageSender._create_embed(
            title="Limit Moderatorów",
            description=(
                "Osiągnięto limit moderatorów kanału.\n\n"
                f"**Kanał:** {channel_mention} • {premium_text}"
            ),
            color="warning",
            fields=fields,
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_permission_limit_exceeded(ctx, permission_limit):
        """Sends a message when the permission limit is exceeded."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        premium_channel_id = ctx.bot.config["channels"]["premium_info"]
        premium_channel = ctx.guild.get_channel(premium_channel_id)
        premium_text = (
            f"**Rangi Premium:** {premium_channel.mention}"
            if premium_channel
            else f"**Rangi Premium:** <#{premium_channel_id}>"
        )

        embed = MessageSender._create_embed(
            title="Limit Uprawnień",
            description=(
                f"Osiągnąłeś limit {permission_limit} uprawnień.\n"
                "Najstarsze uprawnienie nie dotyczące zarządzania wiadomościami zostało nadpisane.\n\n"
                f"**Kanał:** {channel_mention} • {premium_text}"
            ),
            color="warning",
            ctx=ctx,
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
            description=(
                f"{target.mention} {action} moderatora kanału.\n\n"
                f"**Kanał:** {voice_channel.mention}"
            ),
            color="success",
            fields=fields,
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_voice_channel_info(ctx, channel, owner, mods, disabled_perms, target=None):
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

        fields = [
            ("Właściciel", owner_value, False),
            ("Moderatorzy", mods_value, False),
            ("Wyłączone uprawnienia", perms_value, False),
        ]

        # Jeśli sprawdzamy kanał innego użytkownika, dodajemy informację o tym
        if target and target != ctx.author:
            description = (
                f"Szczegółowe informacje o kanale użytkownika {target.mention}.\n\n"
                f"**Kanał:** {channel.mention}"
            )
        else:
            description = (
                f"Szczegółowe informacje o kanale {channel.mention}.\n\n"
                f"**Kanał:** {channel.mention}"
            )

        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Informacje o Kanale",
            description=description,
            color="info",
            fields=fields,
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_no_premium_role(ctx, premium_channel_id):
        """Sends a message when user has no premium role."""
        premium_channel = ctx.guild.get_channel(premium_channel_id)
        mention_text = premium_channel.mention if premium_channel else f"<#{premium_channel_id}>"

        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            "Nie posiadasz żadnej rangi premium. Możesz przypisać 0 channel modów.\n\n"
            f"**Kanał:** {channel_mention} • **Rangi Premium:** {mention_text}"
        )

        embed = MessageSender._create_embed(
            title="Brak Rangi Premium",
            description=description,
            color="warning",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_permission_update_error(ctx, target, permission_flag):
        """Sends a message when there is an error updating the permission."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            f"Nie udało się ustawić uprawnienia {permission_flag} dla {target.mention}.\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Błąd Aktualizacji Uprawnień",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_no_autokick_permission(ctx, premium_channel_id):
        """Sends a message when user doesn't have required role for autokick."""
        premium_channel = ctx.guild.get_channel(premium_channel_id)
        mention_text = premium_channel.mention if premium_channel else f"<#{premium_channel_id}>"

        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            "Nie posiadasz wymaganych uprawnień do używania autokicka.\n"
            "Aby móc używać autokicka, musisz posiadać rangę zG500 (1 slot) lub zG1000 (3 sloty).\n\n"
            f"**Kanał:** {channel_mention} • **Rangi Premium:** {mention_text}"
        )

        embed = MessageSender._create_embed(
            title="Brak Uprawnień Autokick",
            description=description,
            color="warning",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_limit_reached(ctx, max_autokicks, premium_channel_id):
        """Sends a message when user has reached their autokick limit."""
        premium_channel = ctx.guild.get_channel(premium_channel_id)
        mention_text = premium_channel.mention if premium_channel else f"<#{premium_channel_id}>"

        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            f"Osiągnąłeś limit {max_autokicks} osób na liście autokick.\n\n"
            f"**Kanał:** {channel_mention} • **Rangi Premium:** {mention_text}"
        )

        embed = MessageSender._create_embed(
            title="Limit Autokick",
            description=description,
            color="warning",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_already_exists(ctx, target):
        """Sends a message when target is already on autokick list."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            f"{target.mention} jest już na twojej liście autokick.\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Autokick",
            description=description,
            color="warning",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_added(ctx, target):
        """Sends a message when target is added to autokick list."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            f"Dodano {target.mention} do twojej listy autokick.\n\n" f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Autokick",
            description=description,
            color="success",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_not_found(ctx, target):
        """Sends a message when target is not on autokick list."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            f"{target.mention} nie jest na twojej liście autokick.\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Autokick",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_removed(ctx, target):
        """Sends a message when target is removed from autokick list."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            f"Usunięto {target.mention} z twojej listy autokick.\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Autokick",
            description=description,
            color="success",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_list_empty(ctx):
        """Sends a message when autokick list is empty."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = f"Twoja lista autokick jest pusta.\n\n**Kanał:** {channel_mention}"
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Lista Autokick",
            description=description,
            color="info",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_list(ctx, user_autokicks, max_autokicks):
        """Sends an embed with the user's autokick list."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        fields = []
        for target_id in user_autokicks:
            member = ctx.guild.get_member(target_id)
            if member:
                fields.append((member.display_name, f"{member.mention}\nID: {member.id}", False))

        description = (
            "Lista użytkowników, którzy będą automatycznie wyrzucani z kanałów głosowych.\n\n"
            f"**Kanał:** {channel_mention}\n"
            f"**Wykorzystano:** {len(user_autokicks)}/{max_autokicks} dostępnych slotów"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Twoja Lista Autokick",
            description=description,
            color="info",
            fields=fields,
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_notification(channel, target, owner):
        """Sends a notification when a member is autokicked."""
        description = (
            f"{target.mention} został wyrzucony z kanału, ponieważ {owner.mention} ma go na liście autokick.\n\n"
            f"**Kanał:** {channel.mention}"
        )

        embed = MessageSender._create_embed(
            title="Autokick",
            description=description,
            color="info",
        )
        await channel.send(embed=embed, allowed_mentions=AllowedMentions(users=False, roles=False))

    @staticmethod
    async def send_cant_modify_owner_permissions(ctx):
        """Sends a message when a mod tries to modify owner permissions."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            "Nie możesz modyfikować uprawnień właściciela kanału!\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Brak Uprawnień",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_cant_modify_mod_permissions(ctx):
        """Sends a message when a mod tries to modify other mod permissions."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            "Nie możesz modyfikować uprawnień innych moderatorów!\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Brak Uprawnień",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_mod_info(ctx, current_mods_mentions, mod_limit, remaining_slots):
        """Sends a message with mod information."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        fields = [
            ("Aktualni Moderatorzy", current_mods_mentions or "brak", False),
            ("Pozostałe Sloty", str(remaining_slots), True),
            ("Limit Moderatorów", str(mod_limit), True),
        ]

        embed = MessageSender._create_embed(
            title="Informacje o Moderatorach",
            description=(
                "Lista aktualnych moderatorów kanału.\n\n" f"**Kanał:** {channel_mention}"
            ),
            color="info",
            fields=fields,
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    async def send_permission_reset(self, ctx, target):
        """Send message confirming user permissions reset."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            f"Zresetowano wszystkie uprawnienia dla {target.mention} na tym kanale.\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Reset Uprawnień",
            description=description,
            color="success",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    async def send_channel_reset(self, ctx):
        """Send message confirming channel permissions reset."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = (
            "Zresetowano wszystkie uprawnienia na tym kanale do ustawień domyślnych.\n\n"
            f"**Kanał:** {channel_mention}"
        )
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Reset Kanału",
            description=description,
            color="success",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_error(ctx, message: str):
        """Sends an error message."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = f"{message}\n\n**Kanał:** {channel_mention}"
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Błąd",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_success(ctx, message: str):
        """Sends a success message."""
        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = f"{message}\n\n**Kanał:** {channel_mention}"
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Sukces",
            description=description,
            color="success",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_giveaway_results(
        ctx, winners: list, channel: discord.TextChannel, winners_count: int
    ):
        """Send giveaway results."""
        description = []
        for i, message in enumerate(winners, 1):
            jump_url = message.jump_url
            if message.webhook_id:
                author_text = f"Webhook ({message.author.name})"
            else:
                author_text = message.author.mention if message.author else "Nieznany użytkownik"
            description.append(f"{i}. {author_text} - [Link do wiadomości]({jump_url})")

        if len(winners) < winners_count:
            description.append(
                f"\n⚠️ Wylosowano tylko {len(winners)} wiadomości z {winners_count} żądanych."
            )

        description = "\n".join(description)
        description = MessageSender._with_premium_link(description, ctx)

        fields = [
            ("Kanał", channel.mention, True),
            ("Liczba wygranych", str(len(winners)), True),
        ]

        embed = MessageSender._create_embed(
            title="🎉 Wyniki Losowania",
            description=description,
            color="success",
            fields=fields,
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    async def send_channel_creation_info(self, channel, owner):
        """Send channel creation info message."""
        # Get premium channel info
        premium_channel_id = self.bot.config["channels"]["premium_info"]
        premium_channel = channel.guild.get_channel(premium_channel_id)
        premium_text = (
            f"**Rangi Premium:** {premium_channel.mention}"
            if premium_channel
            else f"**Rangi Premium:** <#{premium_channel_id}>"
        )

        # Get current mods from channel overwrites
        current_mods = [
            t
            for t, overwrite in channel.overwrites.items()
            if isinstance(t, discord.Member)
            and overwrite.manage_messages is True
            and not overwrite.priority_speaker
        ]

        # Get mod limit from owner's roles
        mod_limit = 0
        for role in reversed(self.bot.config["premium_roles"]):
            if any(r.name == role["name"] for r in owner.roles):
                mod_limit = role["moderator_count"]
                break

        current_mods_mentions = ", ".join(m.mention for m in current_mods) or "brak"
        remaining_slots = max(0, mod_limit - len(current_mods))

        # Get disabled permissions for @everyone
        everyone_perms = channel.overwrites_for(channel.guild.default_role)
        perm_to_cmd = {
            "connect": "connect",
            "speak": "speak",
            "stream": "live",
            "view_channel": "view",
            "send_messages": "text",
        }
        disabled_perms = []
        for perm_name, cmd_name in perm_to_cmd.items():
            if getattr(everyone_perms, perm_name) is False:
                disabled_perms.append(f"`{cmd_name}`")

        prefix = self.bot.config["prefix"]

        # Create a fake context-like object that has the required attributes
        class FakeContext:
            def __init__(self, member):
                self.author = member
                self.guild = member.guild

        ctx = FakeContext(owner)

        fields = [
            ("Moderatorzy", current_mods_mentions, False),
            ("Limit Moderatorów", str(mod_limit), True),
            ("Pozostałe Sloty", str(remaining_slots), True),
        ]

        # Add disabled permissions field if any exist
        if disabled_perms:
            fields.append(("Wyłączone uprawnienia", ", ".join(disabled_perms), False))

        fields.extend(
            [
                (
                    "Komendy",
                    f"• `{prefix}speak <@użytkownik> [+/-]` - Zarządzaj uprawnieniami do mówienia\n"
                    f"• `{prefix}live <@użytkownik> [+/-]` - Zarządzaj uprawnieniami do streamowania\n"
                    f"• `{prefix}connect <@użytkownik> [+/-]` - Zarządzaj uprawnieniami do dołączania\n"
                    f"• `{prefix}view <@użytkownik> [+/-]` - Zarządzaj uprawnieniami do widzenia kanału\n"
                    f"• `{prefix}text <@użytkownik> [+/-]` - Zarządzaj uprawnieniami do pisania\n"
                    f"• `{prefix}mod <@użytkownik> [+/-]` - Dodaj/usuń moderatora kanału\n"
                    f"• `{prefix}limit <liczba>` - Ustaw limit użytkowników (0-99)\n"
                    f"• `{prefix}reset` - Zresetuj wszystkie uprawnienia",
                    False,
                ),
                (
                    "Globalne Uprawnienia",
                    "Aby zmienić uprawnienia dla wszystkich użytkowników:\n"
                    f"• Użyj komendy bez oznaczania użytkownika, np. `{prefix}live +` włączy streamowanie dla wszystkich\n"
                    "• Możesz użyć `+` aby włączyć lub `-` aby wyłączyć uprawnienie\n"
                    "• Użycie komendy bez `+/-` przełączy uprawnienie na przeciwne",
                    False,
                ),
                (
                    "Uwaga",
                    f"Komenda `{prefix}limit` jest dostępna dla wszystkich.",
                    False,
                ),
            ]
        )

        embed = MessageSender._create_embed(
            title="Kanał Głosowy Utworzony",
            description=(
                f"Utworzono nowy kanał głosowy dla {owner.mention}\n\n"
                f"**Kanał:** {channel.mention} • {premium_text}"
            ),
            color="success",
            fields=fields,
            ctx=ctx,  # Pass the fake context instead of just the owner
        )
        await channel.send(embed=embed)

    @staticmethod
    async def send_no_permission(ctx, reason=None):
        """
        Sends a generic 'no permission' message.
        Optionally provide a `reason` for more context.
        """
        if reason is None:
            reason = "wykonania tej akcji!"

        channel_mention = (
            ctx.author.voice.channel.mention
            if (ctx.author.voice and ctx.author.voice.channel)
            else "brak (nie jesteś na kanale)"
        )

        description = f"Nie masz uprawnień do {reason}\n\n" f"**Kanał:** {channel_mention}"
        description = MessageSender._with_premium_link(description, ctx)

        embed = MessageSender._create_embed(
            title="Brak Uprawnień",
            description=description,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed)
