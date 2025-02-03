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

    #
    # ──────────────────────────────────────────────────────────────────────────────
    #   1. PODSTAWOWE FUNKCJE POMOCNICZE
    # ──────────────────────────────────────────────────────────────────────────────
    #

    @staticmethod
    def _create_embed(
        title: str,
        description: str = None,
        color: str = "info",
        fields: list = None,
        footer: str = None,
        ctx=None,
    ) -> discord.Embed:
        """
        Creates a consistent embed with the given parameters.
        Also sets embed author if 'ctx' is provided.
        """
        embed = discord.Embed(
            title=title,
            description=description or "",
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
    async def _send_embed(
        ctx, embed: discord.Embed, reply: bool = False, allowed_mentions: AllowedMentions = None
    ):
        """
        Sends an embed with consistent settings.
        """
        if allowed_mentions is None:
            allowed_mentions = AllowedMentions(users=False, roles=False)

        if reply:
            return await ctx.reply(embed=embed, allowed_mentions=allowed_mentions)
        return await ctx.send(embed=embed, allowed_mentions=allowed_mentions)

    @staticmethod
    def _with_premium_link(description: str, ctx) -> str:
        """
        Add premium channel link to description if ctx has bot config.
        The premium link is added in one of two ways:
        1. If description contains "**Kanał:**", append premium link on the same line
        2. If no channel info exists, add a new line with both channel and premium info
        """
        if not hasattr(ctx, "bot") or not hasattr(ctx.bot, "config"):
            return description

        # Get premium channel info
        premium_channel_id = ctx.bot.config["channels"]["premium_info"]
        premium_channel = ctx.guild.get_channel(premium_channel_id)
        premium_text = (
            f"**Rangi Premium:** {premium_channel.mention}"
            if premium_channel
            else f"**Rangi Premium:** <#{premium_channel_id}>"
        )

        # Check if we already have channel info in the description
        if "**Kanał:**" in description:
            # Add premium link to the same line as channel info
            channel_info_end = description.find("**Kanał:**")
            channel_line_end = description.find("\n", channel_info_end)
            if channel_line_end == -1:  # Last line in description
                channel_line_end = len(description)

            description = (
                description[:channel_line_end]
                + " • "
                + premium_text
                + description[channel_line_end:]
            )
        else:
            # Add both channel and premium info in a new line
            description += f"\n**Kanał:** brak • {premium_text}"

        return description

    @staticmethod
    def build_description(base_text: str, ctx, channel=None) -> str:
        """
        Helper: build final description by appending channel mention and premium link.
          - base_text: main message content
          - ctx: the context (command) or member
          - channel: optional channel to mention
        """
        if channel:
            base_text += f"\n\n**Kanał:** {channel.mention}"
        else:
            base_text += "\n\n**Kanał:** brak"

        return MessageSender._with_premium_link(base_text, ctx)

    @staticmethod
    async def build_and_send_embed(
        ctx,
        title: str,
        base_text: str,
        color: str = "info",
        fields: list = None,
        channel=None,
        reply: bool = False,
    ):
        """
        Creates final description with build_description, then builds embed + sends it.
        You can optionally pass 'fields' if needed,
        and 'channel' if you want to mention a specific voice channel in the text.
        """
        description = MessageSender.build_description(base_text, ctx, channel)
        embed = MessageSender._create_embed(
            title=title, description=description, color=color, fields=fields, ctx=ctx
        )
        return await MessageSender._send_embed(ctx, embed, reply=reply)

    @staticmethod
    async def send_permission_update(ctx, target, permission_flag, new_value):
        mention_str = target.mention if isinstance(target, discord.Member) else "wszystkich"
        value_str = "+" if new_value else "-"
        base_text = (
            f"Ustawiono uprawnienie **{permission_flag}** na **{value_str}** " f"dla {mention_str}."
        )

        channel = ctx.author.voice.channel if (ctx.author.voice) else None
        await MessageSender.build_and_send_embed(
            ctx,
            title="Aktualizacja Uprawnień",
            base_text=base_text,
            color="success",
            channel=channel,
            reply=True,
        )

    @staticmethod
    async def send_user_not_found(ctx):
        channel = ctx.author.voice.channel if (ctx.author.voice) else None
        base_text = "Nie znaleziono użytkownika."
        await MessageSender.build_and_send_embed(
            ctx, title="Błąd", base_text=base_text, color="error", channel=channel
        )

    @staticmethod
    async def send_not_in_voice_channel(ctx, target=None):
        if target:
            base_text = f"{target.mention} nie jest na żadnym kanale głosowym!"
            channel = target.voice.channel if (target.voice and target.voice.channel) else None
        else:
            base_text = "Nie jesteś na żadnym kanale głosowym!"
            channel = ctx.author.voice.channel if (ctx.author.voice) else None

        await MessageSender.build_and_send_embed(
            ctx, title="Błąd", base_text=base_text, color="error", channel=channel
        )

    @staticmethod
    async def send_joined_channel(ctx, channel):
        """Sends a message when the bot joins a channel."""
        base_text = f"Dołączono do {channel.mention}"
        await MessageSender.build_and_send_embed(
            ctx, title="Dołączono do Kanału", base_text=base_text, color="success", channel=channel
        )

    @staticmethod
    async def send_invalid_member_limit(ctx):
        base_text = "Podaj liczbę członków od 1 do 99."
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx, title="Błąd", base_text=base_text, color="error", channel=channel, reply=True
        )

    @staticmethod
    async def send_member_limit_set(ctx, voice_channel, limit_text):
        base_text = f"Limit członków na kanale {voice_channel.mention} ustawiony na {limit_text}."
        await MessageSender.build_and_send_embed(
            ctx,
            title="Limit Członków",
            base_text=base_text,
            color="success",
            channel=voice_channel,
            reply=True,
        )

    @staticmethod
    async def send_no_mod_permission(ctx):
        base_text = "Nie masz uprawnień do nadawania channel moda!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx, title="Brak Uprawnień", base_text=base_text, color="error", channel=channel
        )

    @staticmethod
    async def send_cant_remove_self_mod(ctx):
        base_text = "Nie możesz odebrać sobie uprawnień do zarządzania kanałem!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx, title="Błąd", base_text=base_text, color="error", channel=channel
        )

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

        base_text = "Osiągnięto limit moderatorów kanału."
        channel = ctx.author.voice.channel if ctx.author.voice else None

        await MessageSender.build_and_send_embed(
            ctx,
            title="Limit Moderatorów",
            base_text=base_text,
            color="warning",
            fields=fields,
            channel=channel,
        )

    @staticmethod
    async def send_permission_limit_exceeded(ctx, permission_limit):
        """Sends a message when the permission limit is exceeded."""
        base_text = (
            f"Osiągnąłeś limit {permission_limit} uprawnień.\n"
            "Najstarsze uprawnienie nie dotyczące zarządzania wiadomościami zostało nadpisane."
        )
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx, title="Limit Uprawnień", base_text=base_text, color="warning", channel=channel
        )

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

        base_text = f"{target.mention} {action} moderatora kanału."
        await MessageSender.build_and_send_embed(
            ctx,
            title="Aktualizacja Moderatorów",
            base_text=base_text,
            color="success",
            fields=fields,
            channel=voice_channel,
            reply=True,
        )

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
        fields = []
        for target_id in user_autokicks:
            member = ctx.guild.get_member(target_id)
            if member:
                fields.append((member.display_name, f"{member.mention}\nID: {member.id}", False))

        base_text = (
            "Lista użytkowników, którzy będą automatycznie wyrzucani z kanałów głosowych.\n"
            f"**Wykorzystano:** {len(user_autokicks)}/{max_autokicks} dostępnych slotów"
        )
        channel = ctx.author.voice.channel if ctx.author.voice else None

        await MessageSender.build_and_send_embed(
            ctx,
            title="Twoja Lista Autokick",
            base_text=base_text,
            color="info",
            fields=fields,
            channel=channel,
        )

    @staticmethod
    async def send_autokick_notification(channel, target, owner):
        """
        Sends a notification when a member is autokicked.
        Note: This method is special as it sends to channel directly, not through ctx.
        """

        # Create a fake context for consistent embed styling
        class FakeContext:
            def __init__(self, guild):
                self.guild = guild
                self.bot = guild.me._state.http._state.client

        ctx = FakeContext(channel.guild)
        base_text = f"{target.mention} został wyrzucony z kanału, ponieważ {owner.mention} ma go na liście autokick."

        embed = MessageSender._create_embed(
            title="Autokick",
            description=MessageSender.build_description(base_text, ctx, channel),
            color="info",
        )
        await channel.send(embed=embed, allowed_mentions=AllowedMentions(users=False, roles=False))

    @staticmethod
    async def send_cant_modify_owner_permissions(ctx):
        """Sends a message when a mod tries to modify owner permissions."""
        base_text = "Nie możesz modyfikować uprawnień właściciela kanału!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx,
            title="Brak Uprawnień",
            base_text=base_text,
            color="error",
            channel=channel,
            reply=True,
        )

    @staticmethod
    async def send_cant_modify_mod_permissions(ctx):
        """Sends a message when a mod tries to modify other mod permissions."""
        base_text = "Nie możesz modyfikować uprawnień innych moderatorów!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx,
            title="Brak Uprawnień",
            base_text=base_text,
            color="error",
            channel=channel,
            reply=True,
        )

    @staticmethod
    async def send_mod_info(ctx, current_mods_mentions, mod_limit, remaining_slots):
        """Sends a message with mod information."""
        fields = [
            ("Aktualni Moderatorzy", current_mods_mentions or "brak", False),
            ("Pozostałe Sloty", str(remaining_slots), True),
            ("Limit Moderatorów", str(mod_limit), True),
        ]

        base_text = "Lista aktualnych moderatorów kanału."
        channel = ctx.author.voice.channel if (ctx.author.voice) else None

        await MessageSender.build_and_send_embed(
            ctx,
            title="Informacje o Moderatorach",
            base_text=base_text,
            color="info",
            fields=fields,
            channel=channel,
            reply=True,
        )

    async def send_permission_reset(self, ctx, target):
        """Send message confirming user permissions reset."""
        base_text = f"Zresetowano wszystkie uprawnienia dla {target.mention} na tym kanale."
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx,
            title="Reset Uprawnień",
            base_text=base_text,
            color="success",
            channel=channel,
            reply=True,
        )

    async def send_channel_reset(self, ctx):
        """Send message confirming channel permissions reset."""
        base_text = "Zresetowano wszystkie uprawnienia na tym kanale do ustawień domyślnych."
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx,
            title="Reset Kanału",
            base_text=base_text,
            color="success",
            channel=channel,
            reply=True,
        )

    @staticmethod
    async def send_error(ctx, message: str):
        """Sends an error message."""
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx, title="Błąd", base_text=message, color="error", channel=channel
        )

    @staticmethod
    async def send_success(ctx, message: str):
        """Sends a success message."""
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await MessageSender.build_and_send_embed(
            ctx, title="Sukces", base_text=message, color="success", channel=channel
        )

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

        base_text = "\n".join(description)
        fields = [
            ("Kanał", channel.mention, True),
            ("Liczba wygranych", str(len(winners)), True),
        ]

        await MessageSender.build_and_send_embed(
            ctx,
            title="🎉 Wyniki Losowania",
            base_text=base_text,
            color="success",
            fields=fields,
            reply=True,
        )

    async def send_channel_creation_info(self, channel, owner):
        """
        Send channel creation info message.

        Since this method is called during channel creation (not from a command),
        we create a FakeContext with the channel owner as the author.
        This ensures consistent embed styling (author name/avatar) with other messages.
        Note: We can't use build_and_send_embed here because FakeContext doesn't have send method,
        so we create the embed manually and send it directly to the channel.
        """
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

        # Create a fake context-like object that has the required attributes for embed styling
        class FakeContext:
            def __init__(self, member, bot):
                self.author = member
                self.guild = member.guild
                self.bot = bot

        ctx = FakeContext(owner, self.bot)

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

        base_text = f"Utworzono nowy kanał głosowy dla {owner.mention}"
        description = MessageSender.build_description(base_text, ctx, channel)
        embed = MessageSender._create_embed(
            title="Kanał Głosowy Utworzony",
            description=description,
            color="success",
            fields=fields,
            ctx=ctx,
        )
        await channel.send(embed=embed, allowed_mentions=AllowedMentions(users=False, roles=False))

    @staticmethod
    async def send_no_permission(ctx, reason=None):
        """
        Sends a generic 'no permission' message.
        Optionally provide a `reason` for more context.
        """
        if reason is None:
            reason = "wykonania tej akcji!"

        base_text = f"Nie masz uprawnień do {reason}"
        channel = ctx.author.voice.channel if ctx.author.voice else None

        await MessageSender.build_and_send_embed(
            ctx, title="Brak Uprawnień", base_text=base_text, color="error", channel=channel
        )

    async def send_bypass_expired(self, ctx):
        """Send message when user's bypass (T) has expired."""
        base_text = "Twój czas T (bypass) wygasł!\nUżyj `/bump`, aby przedłużyć ten czas."
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await self.build_and_send_embed(
            ctx,
            title="Czas T Wygasł",
            base_text=base_text,
            color="error",
            channel=channel,
            reply=True,
        )

    async def send_premium_required(self, ctx):
        """Send message when premium role is required."""
        base_text = "Aby użyć tej komendy, potrzebujesz rangi premium!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await self.build_and_send_embed(
            ctx,
            title="Wymagana Ranga Premium",
            base_text=base_text,
            color="error",
            channel=channel,
            reply=True,
        )

    async def send_specific_roles_required(self, ctx, allowed_roles):
        """Send message when specific premium roles are required."""
        base_text = f"Ta komenda wymaga jednej z rang: {', '.join(allowed_roles)}"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        await self.build_and_send_embed(
            ctx,
            title="Wymagana Ranga Premium",
            base_text=base_text,
            color="error",
            channel=channel,
            reply=True,
        )
