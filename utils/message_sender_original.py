"""Message sender utility for sending formatted messages."""

from datetime import datetime, timezone

import discord
from discord import AllowedMentions

from datasources.queries import MemberQueries
from utils.bump_checker import BumpChecker


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
        title: str = None,
        description: str = None,
        color: str = None,
        fields: list = None,
        footer: str = None,
        ctx=None,
        add_author: bool = False,
    ) -> discord.Embed:
        """
        Creates a consistent embed with the given parameters.
        Also sets embed author if 'ctx' is provided and add_author is True.
        """
        # Get user's color if available
        embed_color = None
        if ctx:
            if isinstance(ctx, discord.Member):
                embed_color = ctx.color if ctx.color.value != 0 else None
            elif hasattr(ctx, "author"):
                embed_color = ctx.author.color if ctx.author.color.value != 0 else None

        # If no user color and color parameter is provided, use it from COLORS
        if not embed_color and color and color in MessageSender.COLORS:
            embed_color = MessageSender.COLORS[color]

        # If still no color, use black
        if not embed_color:
            embed_color = discord.Color.from_rgb(1, 1, 1)  # Almost black

        embed = discord.Embed(
            title=title,
            description=description or "",
            color=embed_color,
        )

        if fields:
            for name, value, inline in fields:
                embed.add_field(name=name, value=value, inline=inline)

        if footer:
            embed.set_footer(text=footer)

        # Add author's avatar and name if requested
        if add_author and ctx:
            if isinstance(ctx, discord.Member):
                # If ctx is a Member object (e.g. from channel creation)
                embed.set_author(name=ctx.display_name, icon_url=ctx.display_avatar.url)
            elif hasattr(ctx, "author"):
                # If ctx is a Context object (from commands)
                embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.display_avatar.url)

        return embed

    @staticmethod
    async def _send_embed(
        ctx,
        embed: discord.Embed,
        reply: bool = False,
        allowed_mentions: AllowedMentions = None,
        view=None,
    ):
        """
        Sends an embed with consistent settings.
        """
        if allowed_mentions is None:
            allowed_mentions = AllowedMentions(users=False, roles=False)

        if reply:
            return await ctx.reply(embed=embed, allowed_mentions=allowed_mentions, view=view)
        return await ctx.send(embed=embed, allowed_mentions=allowed_mentions, view=view)

    @staticmethod
    def build_description(base_text: str, ctx, channel=None) -> str:
        """Build description with channel info and premium link."""
        # Remove trailing whitespace and newlines
        description = base_text.rstrip() if base_text else ""

        # Only bold text that doesn't contain backticks and isn't already bold
        # and doesn't start with backtick (for command examples)
        if (
            description
            and not description.startswith("**")
            and not description.strip().startswith("`")
            and "`" not in description
        ):
            description = f"**{description}**"

        return description

    @staticmethod
    async def build_and_send_embed(
        ctx,
        title: str = None,
        base_text: str = None,
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
        embed = MessageSender._create_embed(title=title, description=description, color=color, fields=fields, ctx=ctx)

        # Add channel info as the last field to ensure it appears at the bottom
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                embed.add_field(name="\u200b", value=channel_text, inline=False)

        return await MessageSender._send_embed(ctx, embed, reply=reply)

    @staticmethod
    async def send_permission_update(ctx, target, permission_flag, new_value):
        """Sends a message about permission update."""
        mention_str = target.mention if isinstance(target, discord.Member) else "wszystkich"
        value_str = "+" if new_value else "-"
        command_name = ctx.command.name if ctx.command else permission_flag
        base_text = f"Ustawiono `{command_name}` na `{value_str}` dla {mention_str}"

        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)

        # Add channel info directly to description
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                embed.description = f"{embed.description}\n{channel_text}"

        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_user_not_found(ctx):
        """Sends a message when user is not found."""
        base_text = "Nie znaleziono użytkownika."
        channel = ctx.author.voice.channel if (ctx.author.voice) else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_not_in_voice_channel(ctx, target=None):
        """Sends a message when user is not in a voice channel."""
        if target:
            base_text = f"{target.mention} nie jest na żadnym kanale głosowym!"
            channel = target.voice.channel if (target.voice and target.voice.channel) else None
        else:
            base_text = "Nie jesteś na żadnym kanale głosowym!"
            channel = ctx.author.voice.channel if (ctx.author.voice) else None

        # Get premium text regardless of whether the user is in a voice channel
        _, premium_text = MessageSender._get_premium_text(ctx, channel)
        if premium_text:
            base_text = f"{base_text}\n{premium_text}"

        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_invalid_member_limit(ctx):
        """Sends a message when member limit is invalid."""
        base_text = "Podaj liczbę członków od 1 do 99."
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_no_mod_permission(ctx):
        """Sends a message when user doesn't have mod permission."""
        base_text = "Nie masz uprawnień do nadawania channel moda!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_cant_remove_self_mod(ctx):
        """Sends a message when user tries to remove their own mod permissions."""
        base_text = "Nie możesz odebrać sobie uprawnień do zarządzania kanałem!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_mod_limit_exceeded(ctx, mod_limit, current_mods):
        """Sends a message when the mod limit is exceeded."""
        channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = MessageSender._create_embed(ctx=ctx, add_author=False)

        # Check if user has zG1000
        has_zg1000 = any(role.name == "zG1000" for role in ctx.author.roles)

        current_mods_count = len(current_mods)
        current_mods_mentions = ", ".join(member.mention for member in current_mods) or "brak"

        if has_zg1000:
            base_text = f"Osiągnięto limit moderatorów ({current_mods_count}/{mod_limit}). Usuń któregoś z aktualnych moderatorów przed dodaniem nowego.\nModeratorzy: {current_mods_mentions}"
        else:
            base_text = f"Osiągnięto limit moderatorów ({current_mods_count}/{mod_limit}). Wybierz wyższy plan, aby móc dodać więcej moderatorów.\nModeratorzy: {current_mods_mentions}"

        # Add channel info directly to description
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"

        embed.description = base_text
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_channel_mod_update(ctx, target, is_mod, voice_channel, mod_limit):
        """Sends a message about updating channel mod status and displays mod information."""
        action = "nadano uprawnienia" if is_mod else "odebrano uprawnienia"
        base_text = f"{target.mention} {action} moderatora kanału"

        # Add channel info directly to description
        _, channel_text = MessageSender._get_premium_text(ctx, voice_channel)
        if channel_text:
            base_text = f"{base_text}\n{channel_text}"

        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
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
        base_text = (
            f"**Właściciel:** {owner_value} • **Moderatorzy:** {mods_value}\n**Wyłączone uprawnienia:** {perms_value}"
        )

        # Tworzymy embed
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)

        # Add channel info directly to description to avoid empty line
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                embed.description = f"{embed.description}\n{channel_text}"

        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_no_premium_role(ctx, premium_channel_id):
        """Sends a message when user has no premium role."""
        base_text = "Nie posiadasz żadnej rangi premium. Możesz przypisać 0 channel modów."
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(title="Brak Rangi Premium", description=base_text, color="warning", ctx=ctx)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_permission_update_error(ctx, target, permission_flag):
        """Sends a message when there is an error updating the permission."""
        base_text = f"Nie udało się ustawić uprawnienia `{permission_flag}` dla {target.mention}."
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(
            title="Błąd Aktualizacji Uprawnień",
            description=base_text,
            color="error",
            ctx=ctx,
        )
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_no_autokick_permission(ctx, premium_channel_id):
        """Sends a message when user doesn't have required role for autokick."""
        base_text = "Ta komenda wymaga jednej z rang: zG500, zG1000"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_autokick_limit_reached(ctx, max_autokicks, premium_channel_id):
        """Sends a message when user has reached their autokick limit."""
        base_text = f"Osiągnąłeś limit {max_autokicks} osób na liście autokick."
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, color="warning", ctx=ctx)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_already_exists(ctx, target):
        """Sends a message when target is already on autokick list."""
        base_text = f"{target.mention} jest już na twojej liście autokick"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx, color="warning")
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_added(ctx, target):
        """Sends a message when target is added to autokick list."""
        base_text = f"Dodano {target.mention} do twojej listy autokick"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx, color="success")
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_not_found(ctx, target):
        """Sends a message when target is not on autokick list."""
        base_text = f"{target.mention} nie jest na twojej liście autokick"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx, color="error")
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_removed(ctx, target):
        """Sends a message when target is removed from autokick list."""
        base_text = f"Usunięto {target.mention} z twojej listy autokick"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx, color="success")
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_list_empty(ctx):
        """Sends a message when autokick list is empty."""
        base_text = "**Lista autokick jest pusta**"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_autokick_list(ctx, user_autokicks, max_autokicks):
        """Sends an embed with the user's autokick list."""
        base_text = []

        async with ctx.bot.get_db() as session:
            for target_id in user_autokicks:
                member = ctx.guild.get_member(target_id)
                if member:
                    bypass = await MemberQueries.get_voice_bypass_status(session, member.id)
                    t_count = "0"
                    if bypass:
                        time_left = bypass - datetime.now(timezone.utc)
                        hours = int(time_left.total_seconds() // 3600)
                        if hours > 0:
                            t_count = str(hours)
                    base_text.append(f"{member.mention} `{t_count}T`")

        if base_text:
            base_text = "\n".join(base_text)
            base_text = f"**Lista autokick:** `{len(user_autokicks)}/{max_autokicks}`\n{base_text}"
        else:
            base_text = "**Lista autokick jest pusta**"

        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"

        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed)

    async def send_autokick_notification(self, channel, target, owner):
        """
        Sends a notification when a member is autokicked.
        Note: This method is special as it sends to channel directly, not through ctx.
        """
        base_text = f"{target.mention} został wyrzucony z kanału, ponieważ {owner.mention} ma go na liście autokick"

        # Create a mock context for _get_premium_text
        class MockContext:
            def __init__(self, bot, guild):
                self.bot = bot
                self.guild = guild

        ctx = MockContext(self.bot, channel.guild)
        _, channel_text = MessageSender._get_premium_text(ctx, channel)
        if channel_text:
            base_text = f"{base_text}\n{channel_text}"

        embed = MessageSender._create_embed(description=base_text, ctx=owner)
        await channel.send(embed=embed, allowed_mentions=AllowedMentions(users=False, roles=False))

    @staticmethod
    async def send_cant_modify_owner_permissions(ctx):
        """Sends a message when a mod tries to modify owner permissions."""
        base_text = "Nie możesz modyfikować uprawnień właściciela kanału!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_cant_modify_mod_permissions(ctx):
        """Sends a message when a mod tries to modify other mod permissions."""
        base_text = "Nie możesz modyfikować uprawnień innych moderatorów!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_mod_info(ctx, current_mods_mentions, mod_limit, remaining_slots):
        """Sends an embed with the current moderators and remaining slots."""
        async with ctx.bot.get_db() as session:
            mods_text = []
            for mod_mention in current_mods_mentions.split(", "):
                if mod_mention != "brak":
                    # Extract just the mention part if it contains display name in parentheses
                    mention = mod_mention.split(" (")[0]
                    member_id = int(mention.split("@")[1].split(">")[0])
                    bypass = await MemberQueries.get_voice_bypass_status(session, member_id)
                    t_count = "0"
                    if bypass:
                        time_left = bypass - datetime.now(timezone.utc)
                        hours = int(time_left.total_seconds() // 3600)
                        if hours > 0:
                            t_count = str(hours)
                    mods_text.append(f"{mention} `{t_count}T`")
            mods_text = ", ".join(mods_text) if mods_text else "brak"

        base_text = f"**Moderatorzy:** {mods_text}\n**Pozostałe sloty:** `{remaining_slots}/{mod_limit}`"

        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"

        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed)

    @staticmethod
    async def send_permission_reset(ctx, target):
        """Send message confirming user permissions reset."""
        base_text = f"Zresetowano wszystkie uprawnienia dla {target.mention}"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, color="success", ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_channel_reset(ctx):
        """Send message confirming channel permissions reset."""
        base_text = "Zresetowano wszystkie uprawnienia do ustawień domyślnych"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, color="success", ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_error(ctx, message: str):
        """Sends an error message."""
        _channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = MessageSender._create_embed(description=message, ctx=ctx, color="error")
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_success(ctx, message: str):
        """Sends a success message."""
        _channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = MessageSender._create_embed(description=message, ctx=ctx, color="success")
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_giveaway_results(ctx, winners: list, channel: discord.TextChannel, winners_count: int):
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
            description.append(f"\n⚠️ Wylosowano tylko {len(winners)} wiadomości z {winners_count} żądanych.")

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

        embed = MessageSender._create_embed(description=base_text, ctx=owner)

        # Znajdź moderatorów i wyłączone uprawnienia
        mods = []
        disabled_perms = []

        for target, overwrite in channel.overwrites.items():
            if isinstance(target, discord.Member):
                if overwrite.manage_messages and not overwrite.priority_speaker:
                    mods.append(target)
            # Sprawdź wyłączone uprawnienia dla @everyone
            if isinstance(target, discord.Role) and target.name == "@everyone":
                if overwrite.connect is False:
                    disabled_perms.append("connect")
                if overwrite.speak is False:
                    disabled_perms.append("speak")
                if overwrite.stream is False:
                    disabled_perms.append("stream")
                if overwrite.view_channel is False:
                    disabled_perms.append("view")
                if overwrite.send_messages is False:
                    disabled_perms.append("text")

        # Get T count for owner and mods
        async with ctx.bot.get_db() as session:
            owner_bypass = await MemberQueries.get_voice_bypass_status(session, owner.id)
            owner_t = "0T"
            if owner_bypass:
                time_left = owner_bypass - datetime.now(timezone.utc)
                hours = int(time_left.total_seconds() // 3600)
                if hours > 0:
                    owner_t = f"{hours}T"

            mod_t_counts = []
            for mod in mods:
                mod_bypass = await MemberQueries.get_voice_bypass_status(session, mod.id)
                mod_t = "0T"
                if mod_bypass:
                    time_left = mod_bypass - datetime.now(timezone.utc)
                    hours = int(time_left.total_seconds() // 3600)
                    if hours > 0:
                        mod_t = f"{hours}T"
                mod_t_counts.append((mod, mod_t))

        # Add channel information
        channel_info = []
        channel_info.append(f"**Właściciel:** {owner.mention} `{owner_t}`")

        if mod_t_counts:
            mod_list = [f"{mod.mention} `{t}`" for mod, t in mod_t_counts]
            channel_info.append(f"**Moderatorzy:** {' • '.join(mod_list)}")
        else:
            channel_info.append("**Moderatorzy:** brak")

        if disabled_perms:
            channel_info.append(f"**Wyłączone uprawnienia:** `{', '.join(disabled_perms)}`")

        embed.add_field(name="\u200b", value="\n".join(channel_info), inline=False)

        # Add bump services information
        bump_checker = BumpChecker(ctx.bot)

        available_services = []

        for service in ["disboard", "dzik", "discadia", "discordservers", "dsme"]:
            status = await bump_checker.get_service_status(service, owner.id)
            if status["available"]:
                service_name = service
                details = bump_checker.get_service_details(service)
                emoji = bump_checker.get_service_emoji(service)
                service_text = f"{emoji} **{details['name']}** • {details['cooldown']} {details['cooldown_type']} • {details['reward']}"
                if "command" in details:
                    service_text += f" • `{details['command']}`"
                elif "url" in details:
                    service_text += f" • [Zagłosuj]({details['url']})"
                available_services.append(service_text)

        if available_services:
            embed.add_field(name="💰 Odbierz T", value="\n".join(available_services), inline=False)

        # Create view with buttons for voting services
        view = None
        if available_services:
            view = discord.ui.View()
            for service_text in available_services:
                if "[Zagłosuj]" in service_text:
                    # Extract service name from the beginning of the text (after emoji)
                    service_name = service_text.split("**")[1].split("**")[0].strip()
                    for service in [
                        "disboard",
                        "dzik",
                        "discadia",
                        "discordservers",
                        "dsme",
                    ]:
                        details = bump_checker.get_service_details(service)
                        if details["name"] == service_name:
                            emoji = bump_checker.get_service_emoji(service)
                            button = discord.ui.Button(
                                style=discord.ButtonStyle.link,
                                label=service_name,
                                emoji=emoji,
                                url=details["url"],
                            )
                            view.add_item(button)
                            break

        # Get premium text and add it as the last field
        _, channel_text = self._get_premium_text(ctx, channel)
        if channel_text:
            embed.add_field(name="\u200b", value=channel_text, inline=False)

        # Send the embed
        await channel.send(embed=embed, view=view)

    @staticmethod
    async def send_no_permission(ctx, reason=None):
        """
        Sends a generic 'no permission' message.
        Optionally provide a `reason` for more context.
        """
        if reason is None:
            reason = "wykonania tej akcji!"

        base_text = f"Nie masz uprawnień do {reason}"
        _channel = ctx.author.voice.channel if ctx.author.voice else None
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_bypass_expired(ctx):
        """Send message when user's bypass (T) has expired."""
        services = ["disboard", "dzik", "discadia", "discordservers", "dsme"]
        available_services = []

        for service in services:
            status = await BumpChecker(ctx.bot).get_service_status(service, ctx.author.id)
            if status["available"]:
                available_services.append((service, status))

        # Create base description
        embed = MessageSender._create_embed(
            description="Aby użyć tej komendy, wybierz plan, zaproś znajomych na serwer lub zbumpuj serwer!",
            ctx=ctx,
        )

        # Add available services
        if available_services:
            available_text = []
            for service, status in available_services:
                emoji = BumpChecker.get_service_emoji(service)
                details = BumpChecker.get_service_details(service)
                service_text = f"{emoji} **{details['name']}** • {details['cooldown']} {details['cooldown_type']} • {details['reward']} • "
                if "command" in details:
                    service_text += f"`{details['command']}`"
                elif "url" in details:
                    service_text += f"[Zagłosuj]({details['url']})"
                available_text.append(service_text)

            if available_text:
                embed.add_field(name="💰 Odbierz T:", value="\n".join(available_text), inline=False)

        # Create view with buttons for voting services
        view = None
        if available_services:
            view = discord.ui.View()
            for service, status in available_services:
                details = BumpChecker.get_service_details(service)
                if "url" in details:
                    emoji = BumpChecker.get_service_emoji(service)
                    button = discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        label=details["name"],
                        emoji=emoji,
                        url=details["url"],
                    )
                    view.add_item(button)

        # Add channel info as the last field
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                embed.add_field(name="\u200b", value=channel_text, inline=False)

        await MessageSender._send_embed(ctx, embed, reply=True, view=view)

    @staticmethod
    async def send_tier_t_bypass_required(ctx):
        """Send message when user needs T>0 for TIER_T commands (like limit)."""
        services = ["disboard", "dzik", "discadia", "discordservers", "dsme"]
        available_services = []

        for service in services:
            status = await BumpChecker(ctx.bot).get_service_status(service, ctx.author.id)
            if status["available"]:
                available_services.append((service, status))

        # Create more specific description for TIER_T
        embed = MessageSender._create_embed(
            description="**Masz 0T!** Zbumpuj serwer żeby móc użyć tej komendy (wystarczy minimum 1T).",
            ctx=ctx,
        )

        # Add available services
        if available_services:
            available_text = []
            for service, status in available_services:
                emoji = BumpChecker.get_service_emoji(service)
                details = BumpChecker.get_service_details(service)
                service_text = f"{emoji} **{details['name']}** • {details['cooldown']} {details['cooldown_type']} • {details['reward']} • "
                if "command" in details:
                    service_text += f"`{details['command']}`"
                elif "url" in details:
                    service_text += f"[Zagłosuj]({details['url']})"
                available_text.append(service_text)

            if available_text:
                embed.add_field(
                    name="💰 Zbumpuj i odbierz T:",
                    value="\n".join(available_text),
                    inline=False,
                )

        # Create view with buttons for voting services
        view = None
        if available_services:
            view = discord.ui.View()
            for service, status in available_services:
                details = BumpChecker.get_service_details(service)
                if "url" in details:
                    emoji = BumpChecker.get_service_emoji(service)
                    button = discord.ui.Button(
                        style=discord.ButtonStyle.link,
                        label=details["name"],
                        emoji=emoji,
                        url=details["url"],
                    )
                    view.add_item(button)

        # Add channel info as the last field
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                embed.add_field(name="\u200b", value=channel_text, inline=False)

        await MessageSender._send_embed(ctx, embed, reply=True, view=view)

    @staticmethod
    async def send_premium_required(ctx):
        """Send message when premium role is required."""
        base_text = "Aby użyć tej komendy, wybierz plan lub zaproś 4 znajomych na serwer (ranga ♵)!"
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    async def send_specific_roles_required(ctx, allowed_roles):
        """Send message when specific premium roles are required."""
        base_text = f"Ta komenda wymaga jednej z rang premium: {', '.join(allowed_roles)}."

        # Add channel info directly to description
        channel = ctx.author.voice.channel if ctx.author.voice else None
        if channel:
            _, channel_text = MessageSender._get_premium_text(ctx, channel)
            if channel_text:
                base_text = f"{base_text}\n{channel_text}"
        else:
            # Add premium plan text even when not in a voice channel
            _, premium_text = MessageSender._get_premium_text(ctx)
            if premium_text:
                base_text = f"{base_text}\n{premium_text}"

        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)

    @staticmethod
    def _get_premium_text(ctx, channel=None) -> tuple[str, str]:
        """Get premium text for embed description."""
        if not hasattr(ctx, "bot") or not hasattr(ctx.bot, "config"):
            return "", ""

        mastercard = ctx.bot.config.get("emojis", {}).get("mastercard", "💳")
        premium_channel_id = ctx.bot.config["channels"]["premium_info"]
        premium_channel = ctx.guild.get_channel(premium_channel_id)

        premium_text = (
            f"Wybierz swój {premium_channel.mention} {mastercard}"
            if premium_channel
            else f"Wybierz swój <#{premium_channel_id}> {mastercard}"
        )

        if not channel:
            # For non-voice commands, return only plan selection text
            return "", premium_text

        # For voice commands, return channel info
        return (
            f"Kanał: {channel.mention}",
            f"Kanał: {channel.mention} • {premium_text}",
        )

    @staticmethod
    async def send_member_limit_set(ctx, voice_channel, limit_text):
        """Send message confirming member limit was set."""
        base_text = f"Limit członków ustawiony na {limit_text}"
        embed = MessageSender._create_embed(description=base_text, ctx=ctx)

        # Add channel info directly to description
        if voice_channel:
            _, channel_text = MessageSender._get_premium_text(ctx, voice_channel)
            if channel_text:
                embed.description = f"{embed.description}\n{channel_text}"

        await MessageSender._send_embed(ctx, embed, reply=True)
