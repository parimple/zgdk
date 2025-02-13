"""Message sender utility for sending formatted messages."""

import random

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
            f"**Wybierz swój** {premium_channel.mention}"
            if premium_channel
            else f"**Wybierz swój** <#{premium_channel_id}>"
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
        """Build description with channel info and premium link."""
        # Remove trailing whitespace and newlines
        description = base_text.rstrip()

        # Only bold text that doesn't contain backticks and isn't already bold
        # and doesn't start with backtick (for command examples)
        if (
            description
            and not description.startswith("**")
            and not description.strip().startswith("`")
            and "`" not in description
        ):
            description = f"**{description}**"

        # Add channel info and premium link at the bottom if we have a channel
        if channel and hasattr(ctx, "bot") and hasattr(ctx.bot, "config"):
            proxy_bunny = ctx.bot.config.get("emojis", {}).get("proxy_bunny", "")
            premium_channel_id = ctx.bot.config["channels"]["premium_info"]
            premium_channel = ctx.guild.get_channel(premium_channel_id)
            premium_text = (
                f"**Wybierz swój** {proxy_bunny}{premium_channel.mention}"
                if premium_channel
                else f"**Wybierz swój** {proxy_bunny}<#{premium_channel_id}>"
            )
            description += f"\n**Kanał:** {channel.mention} • {premium_text}"

        return description

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
        """Sends a message about permission update."""
        mention_str = target.mention if isinstance(target, discord.Member) else "wszystkich"
        value_str = "+" if new_value else "-"
        command_name = ctx.command.name if ctx.command else permission_flag
        base_text = f"Ustawiono `{command_name}` na `{value_str}` dla {mention_str}"

        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.green()
        embed = discord.Embed(color=embed_color)
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed, reply=True)

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
        base_text = f"Limit członków ustawiony na {limit_text}"
        embed = discord.Embed(color=discord.Color.green())
        embed.description = MessageSender.build_description(base_text, ctx, voice_channel)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_no_mod_permission(ctx):
        base_text = "Nie masz uprawnień do nadawania channel moda!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_cant_remove_self_mod(ctx):
        base_text = "Nie możesz odebrać sobie uprawnień do zarządzania kanałem!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_mod_limit_exceeded(ctx, mod_limit, current_mods):
        """Sends a message when the mod limit is exceeded."""
        base_text = f"Osiągnięto limit {mod_limit} moderatorów kanału."
        channel = ctx.author.voice.channel if ctx.author.voice else None

        embed_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.yellow()
        embed = discord.Embed(color=embed_color)

        # Add base text first
        embed.description = base_text.rstrip()
        if not embed.description.startswith("**"):
            embed.description = f"**{embed.description}**"

        # Create fields content
        fields_content = []
        # Convert Member objects to mentions string with display names
        current_mods_mentions = (
            ", ".join(f"{member.mention} ({member.display_name})" for member in current_mods)
            or "brak"
        )
        fields_content.append(
            {"name": "Aktualni Moderatorzy", "value": current_mods_mentions, "inline": False}
        )

        # Add channel info
        if channel and hasattr(ctx, "bot") and hasattr(ctx.bot, "config"):
            proxy_bunny = ctx.bot.config.get("emojis", {}).get("proxy_bunny", "")
            premium_channel_id = ctx.bot.config["channels"]["premium_info"]
            premium_channel = ctx.guild.get_channel(premium_channel_id)
            premium_text = (
                f"**Wybierz swój** {proxy_bunny}{premium_channel.mention}"
                if premium_channel
                else f"**Wybierz swój** {proxy_bunny}<#{premium_channel_id}>"
            )
            fields_content.append(
                {"name": "Kanał", "value": f"{channel.mention} • {premium_text}", "inline": False}
            )

        # Add all fields at once to maintain consistent spacing
        for field in fields_content:
            embed.add_field(**field)

        await MessageSender._send_embed(ctx, embed, reply=True)

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

        # Convert Member objects to mentions string
        current_mods_mentions = (
            ", ".join(member.mention for member in current_mods if member != ctx.author) or "brak"
        )
        remaining_slots = max(0, mod_limit - len(current_mods))

        base_text = f"{target.mention} {action} moderatora kanału"
        embed = discord.Embed(color=discord.Color.green())

        # Add base text first
        embed.description = base_text.rstrip()
        if not embed.description.startswith("**"):
            embed.description = f"**{embed.description}**"

        # Create fields content
        fields_content = []
        fields_content.append(
            {"name": "Pozostałe Sloty", "value": str(remaining_slots), "inline": True}
        )
        fields_content.append(
            {"name": "Limit Moderatorów", "value": str(mod_limit), "inline": True}
        )
        fields_content.append(
            {"name": "Aktualni Moderatorzy", "value": current_mods_mentions, "inline": False}
        )

        # Add channel info
        if voice_channel and hasattr(ctx, "bot") and hasattr(ctx.bot, "config"):
            proxy_bunny = ctx.bot.config.get("emojis", {}).get("proxy_bunny", "")
            premium_channel_id = ctx.bot.config["channels"]["premium_info"]
            premium_channel = ctx.guild.get_channel(premium_channel_id)
            premium_text = (
                f"**Wybierz swój** {proxy_bunny}{premium_channel.mention}"
                if premium_channel
                else f"**Wybierz swój** {proxy_bunny}<#{premium_channel_id}>"
            )
            fields_content.append(
                {
                    "name": "Kanał",
                    "value": f"{voice_channel.mention} • {premium_text}",
                    "inline": False,
                }
            )

        # Add all fields at once to maintain consistent spacing
        for field in fields_content:
            embed.add_field(**field)

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

        # Tworzymy treść wiadomości
        base_text = f"**Właściciel:** {owner_value} • **Moderatorzy:** {mods_value}\n**Wyłączone uprawnienia:** {perms_value}"

        # Tworzymy embed
        embed_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.blue()
        embed = discord.Embed(color=embed_color)
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_no_premium_role(ctx, premium_channel_id):
        """Sends a message when user has no premium role."""
        premium_channel = ctx.guild.get_channel(premium_channel_id)
        mention_text = premium_channel.mention if premium_channel else f"<#{premium_channel_id}>"
        channel = (
            ctx.author.voice.channel if (ctx.author.voice and ctx.author.voice.channel) else None
        )

        fields = [("Rangi Premium", mention_text, True)]

        base_text = "Nie posiadasz żadnej rangi premium. Możesz przypisać 0 channel modów."
        await MessageSender.build_and_send_embed(
            ctx,
            title="Brak Rangi Premium",
            base_text=base_text,
            color="warning",
            fields=fields,
            channel=channel,
        )

    @staticmethod
    async def send_permission_update_error(ctx, target, permission_flag):
        """Sends a message when there is an error updating the permission."""
        base_text = f"Nie udało się ustawić uprawnienia `{permission_flag}` dla {target.mention}."
        channel = (
            ctx.author.voice.channel if (ctx.author.voice and ctx.author.voice.channel) else None
        )
        await MessageSender.build_and_send_embed(
            ctx,
            title="Błąd Aktualizacji Uprawnień",
            base_text=base_text,
            color="error",
            channel=channel,
            reply=True,
        )

    @staticmethod
    async def send_no_autokick_permission(ctx, premium_channel_id):
        """Sends a message when user doesn't have required role for autokick."""
        base_text = "Ta komenda wymaga jednej z rang: zG500, zG1000"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        embed = discord.Embed(color=embed_color)
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_limit_reached(ctx, max_autokicks, premium_channel_id):
        """Sends a message when user has reached their autokick limit."""
        premium_channel = ctx.guild.get_channel(premium_channel_id)
        mention_text = premium_channel.mention if premium_channel else f"<#{premium_channel_id}>"
        channel = (
            ctx.author.voice.channel if (ctx.author.voice and ctx.author.voice.channel) else None
        )

        fields = [("Rangi Premium", mention_text, True)]

        base_text = f"Osiągnąłeś limit {max_autokicks} osób na liście autokick."
        await MessageSender.build_and_send_embed(
            ctx,
            title="Limit Autokick",
            base_text=base_text,
            color="warning",
            fields=fields,
            channel=channel,
        )

    @staticmethod
    async def send_autokick_already_exists(ctx, target):
        """Sends a message when target is already on autokick list."""
        base_text = f"{target.mention} jest już na twojej liście autokick"
        channel = ctx.author.voice.channel if ctx.author.voice else None

        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.yellow()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_added(ctx, target):
        """Sends a message when target is added to autokick list."""
        base_text = f"Dodano {target.mention} do twojej listy autokick"
        channel = ctx.author.voice.channel if ctx.author.voice else None

        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.green()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_not_found(ctx, target):
        """Sends a message when target is not on autokick list."""
        base_text = f"{target.mention} nie jest na twojej liście autokick"
        channel = ctx.author.voice.channel if ctx.author.voice else None

        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_removed(ctx, target):
        """Sends a message when target is removed from autokick list."""
        base_text = f"Usunięto {target.mention} z twojej listy autokick"
        channel = ctx.author.voice.channel if ctx.author.voice else None

        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.green()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_list_empty(ctx):
        """Sends a message when autokick list is empty."""
        base_text = "Twoja lista autokick jest pusta"
        channel = ctx.author.voice.channel if ctx.author.voice else None

        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.blue()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_list(ctx, user_autokicks, max_autokicks):
        """Sends an embed with the user's autokick list."""
        base_text = []
        for target_id in user_autokicks:
            member = ctx.guild.get_member(target_id)
            if member:
                base_text.append(f"• {member.mention} ({member.display_name})")

        if base_text:
            base_text = "\n".join(base_text)
            base_text = f"Lista użytkowników na autokick ({len(user_autokicks)}/{max_autokicks}):\n{base_text}"
        else:
            base_text = "Lista autokick jest pusta"

        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.blue()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    async def send_autokick_notification(self, channel, target, owner):
        """
        Sends a notification when a member is autokicked.
        Note: This method is special as it sends to channel directly, not through ctx.
        """
        base_text = f"{target.mention} został wyrzucony z kanału, ponieważ {owner.mention} ma go na liście autokick"

        # Get premium channel info
        if self.bot:
            proxy_bunny = self.bot.config.get("emojis", {}).get("proxy_bunny", "")
            premium_channel_id = self.bot.config["channels"]["premium_info"]
            premium_channel = channel.guild.get_channel(premium_channel_id)
            premium_text = (
                f"**Wybierz swój** {proxy_bunny}{premium_channel.mention}"
                if premium_channel
                else f"**Wybierz swój** {proxy_bunny}<#{premium_channel_id}>"
            )
            base_text += f"\n**Kanał:** {channel.mention} • {premium_text}"
        else:
            base_text += f"\n**Kanał:** {channel.mention}"

        embed = discord.Embed(color=owner.color if owner.color.value != 0 else discord.Color.blue())
        embed.description = base_text
        await channel.send(embed=embed, allowed_mentions=AllowedMentions(users=False, roles=False))

    @staticmethod
    async def send_cant_modify_owner_permissions(ctx):
        """Sends a message when a mod tries to modify owner permissions."""
        base_text = "Nie możesz modyfikować uprawnień właściciela kanału!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_cant_modify_mod_permissions(ctx):
        """Sends a message when a mod tries to modify other mod permissions."""
        base_text = "Nie możesz modyfikować uprawnień innych moderatorów!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = discord.Embed(
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        )
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_mod_info(ctx, current_mods_mentions, mod_limit, remaining_slots):
        """Sends a message with mod information."""
        base_text = "Lista aktualnych moderatorów kanału."
        channel = ctx.author.voice.channel if ctx.author.voice else None

        embed_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.blue()
        embed = discord.Embed(color=embed_color)

        # Add base text first
        embed.description = base_text.rstrip()
        if not embed.description.startswith("**"):
            embed.description = f"**{embed.description}**"

        # Create fields content
        fields_content = []
        fields_content.append(
            {"name": "Pozostałe Sloty", "value": str(remaining_slots), "inline": True}
        )
        fields_content.append(
            {"name": "Limit Moderatorów", "value": str(mod_limit), "inline": True}
        )
        fields_content.append(
            {"name": "Aktualni Moderatorzy", "value": current_mods_mentions, "inline": False}
        )

        # Add channel info
        if channel and hasattr(ctx, "bot") and hasattr(ctx.bot, "config"):
            proxy_bunny = ctx.bot.config.get("emojis", {}).get("proxy_bunny", "")
            premium_channel_id = ctx.bot.config["channels"]["premium_info"]
            premium_channel = ctx.guild.get_channel(premium_channel_id)
            premium_text = (
                f"**Wybierz swój** {proxy_bunny}{premium_channel.mention}"
                if premium_channel
                else f"**Wybierz swój** {proxy_bunny}<#{premium_channel_id}>"
            )
            fields_content.append(
                {"name": "Kanał", "value": f"{channel.mention} • {premium_text}", "inline": False}
            )

        # Add all fields at once to maintain consistent spacing
        for field in fields_content:
            embed.add_field(**field)

        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_permission_reset(ctx, target):
        """Send message confirming user permissions reset."""
        base_text = f"Zresetowano wszystkie uprawnienia dla {target.mention}"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = discord.Embed(color=discord.Color.green())
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_channel_reset(ctx):
        """Send message confirming channel permissions reset."""
        base_text = "Zresetowano wszystkie uprawnienia do ustawień domyślnych"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = discord.Embed(color=discord.Color.green())
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed, reply=True)

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

    async def send_channel_creation_info(self, channel, ctx, owner):
        """Send channel creation info message."""
        prefix = ctx.bot.config["prefix"]

        base_text = (
            "**Komendy do zarządzania uprawnieniami**\n"
            f"• `{prefix}speak @użytkownik +` – nadaj prawo mówienia\n"
            f"• `{prefix}speak @użytkownik -` – zabierz prawo mówienia\n"
            f"• `{prefix}speak +` – włącz wszystkim prawo mówienia\n"
            f"• Tak samo działają komendy `{prefix}connect`, `{prefix}live`, `{prefix}view`, `{prefix}text`, `{prefix}mod`, `{prefix}autokick`\n\n"
            "**Dodatkowe**\n"
            f"• `{prefix}voicechat` – Informacje o kanale\n"
            f"• `{prefix}reset` – Resetuje wszystkie uprawnienia\n"
            f"• `{prefix}limit <liczba>` – Ustaw limit użytkowników (1–99)"
        ).rstrip()

        embed = discord.Embed(color=owner.color if owner.color.value != 0 else discord.Color.blue())

        # Add base text first
        embed.description = base_text

        # Add channel info as the last field
        if hasattr(ctx, "bot") and hasattr(ctx.bot, "config"):
            proxy_bunny = ctx.bot.config.get("emojis", {}).get("proxy_bunny", "")
            premium_channel_id = ctx.bot.config["channels"]["premium_info"]
            premium_channel = ctx.guild.get_channel(premium_channel_id)
            premium_text = (
                f"**Wybierz swój** {proxy_bunny}{premium_channel.mention}"
                if premium_channel
                else f"**Wybierz swój** {proxy_bunny}<#{premium_channel_id}>"
            )
            embed.add_field(name="Kanał", value=f"{channel.mention} • {premium_text}", inline=False)

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
        embed_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        embed = discord.Embed(color=embed_color)
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_bypass_expired(ctx):
        """Send message when user's bypass (T) has expired."""
        base_text = "Twój czas T (bypass) wygasł! Użyj `/bump`, aby przedłużyć ten czas."
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        embed = discord.Embed(color=embed_color)
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_premium_required(ctx):
        """Send message when premium role is required."""
        base_text = "Aby użyć tej komendy, potrzebujesz rangi premium!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        embed = discord.Embed(color=embed_color)
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_specific_roles_required(ctx, allowed_roles):
        """Send message when specific premium roles are required."""
        base_text = f"Ta komenda wymaga jednej z rang: {', '.join(allowed_roles)}"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.red()
        embed = discord.Embed(color=embed_color)
        embed.description = MessageSender.build_description(base_text, ctx, channel)
        await MessageSender._send_embed(ctx, embed, reply=True)
