"""Voice commands cog for managing voice channel permissions and operations."""

import logging
from typing import Literal, Optional

import discord
from discord import AllowedMentions, Member, PermissionOverwrite, Permissions
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession

from datasources.queries import ChannelPermissionQueries
from utils.user import get_target_and_permission

logger = logging.getLogger(__name__)


class MessageSender:
    """Handles sending messages to the server."""

    @staticmethod
    async def send_permission_update(ctx, target, permission_flag, new_value):
        """Sends a message about the updated permission."""
        mention_str = target.mention if isinstance(target, discord.Member) else "wszystkich"
        value_str = "+" if new_value else "-"
        await ctx.reply(
            f"Ustawiono uprawnienie {permission_flag} na {value_str} dla {mention_str}.",
            allowed_mentions=AllowedMentions(users=False, roles=False),
        )

    @staticmethod
    async def send_user_not_found(ctx):
        """Sends a message when the target user is not found."""
        await ctx.send("Nie znaleziono użytkownika.")

    @staticmethod
    async def send_not_in_voice_channel(ctx):
        """Sends a message when the user is not in a voice channel."""
        await ctx.send("Nie jesteś na żadnym kanale głosowym!")

    @staticmethod
    async def send_joined_channel(ctx, channel):
        """Sends a message when the bot joins a channel."""
        await ctx.send(f"Dołączono do {channel}")

    @staticmethod
    async def send_invalid_member_limit(ctx):
        """Sends a message when an invalid member limit is provided."""
        await ctx.reply("Podaj liczbę członków od 1 do 99.")

    @staticmethod
    async def send_member_limit_set(ctx, voice_channel, limit_text):
        """Sends a message when the member limit is set."""
        await ctx.reply(f"Limit członków na kanale {voice_channel} ustawiony na {limit_text}.")

    @staticmethod
    async def send_no_mod_permission(ctx):
        """Sends a message when the user doesn't have permission to assign channel mods."""
        await ctx.send("Nie masz uprawnień do nadawania channel moda!")

    @staticmethod
    async def send_cant_remove_self_mod(ctx):
        """Sends a message when the user tries to remove their own mod permissions."""
        await ctx.send("Nie możesz odebrać sobie uprawnień do zarządzania kanałem!")

    @staticmethod
    async def send_mod_limit_exceeded(ctx, mod_limit, current_mods):
        """Sends a message when the mod limit is exceeded."""
        current_mods_mentions = ", ".join(
            [member.mention for member in current_mods if member != ctx.author]
        )
        remaining_slots = max(0, mod_limit - len(current_mods))
        await ctx.send(
            f"Możesz przypisać maksymalnie {mod_limit} channel modów (pozostało: {remaining_slots}). "
            f"Aktualni channel modzi: {current_mods_mentions}.",
            allowed_mentions=AllowedMentions(users=False, roles=False),
        )

    @staticmethod
    async def send_permission_limit_exceeded(ctx, permission_limit):
        """Sends a message when the permission limit is exceeded."""
        await ctx.send(
            f"Osiągnąłeś limit {permission_limit} uprawnień. Najstarsze uprawnienie nie dotyczące zarządzania wiadomościami zostało nadpisane. Aby uzyskać więcej uprawnień, rozważ zakup wyższej rangi premium.",
            allowed_mentions=AllowedMentions(users=False, roles=False),
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
            and overwrite.manage_messages is True  # Musi być dokładnie True (nie None ani False)
            and not (
                overwrite.priority_speaker is True and t == ctx.author
            )  # Wykluczamy tylko właściciela kanału
            and t != target  # Nie pokazujemy użytkownika któremu właśnie zmieniamy uprawnienia
        ]

        # Dodaj target tylko jeśli nadajemy uprawnienia
        if is_mod:
            current_mods.append(target)

        current_mods_mentions = ", ".join(
            [member.mention for member in current_mods if member != ctx.author]
        )
        if not current_mods_mentions:
            current_mods_mentions = "brak"

        remaining_slots = max(0, mod_limit - len(current_mods))

        message = (
            f"{target.mention} {action} moderatora kanału.\n"
            f"Aktualni moderatorzy: {current_mods_mentions}\n"
            f"Możesz przypisać maksymalnie {mod_limit} moderatorów (pozostało slotów: {remaining_slots})"
        )

        await ctx.reply(
            message,
            allowed_mentions=AllowedMentions(users=False, roles=False),
        )

    @staticmethod
    async def send_voice_channel_info(ctx, author_info, target_info=None):
        """Sends a message with voice channel information."""
        message = author_info
        if target_info:
            message += f"\n{target_info}"
        await ctx.send(message)

    @staticmethod
    async def send_no_premium_role(ctx, premium_channel_id):
        """Sends a message when user has no premium role."""
        await ctx.send(
            f"Nie posiadasz żadnej rangi premium. Możesz przypisać 0 channel modów. "
            f"Jeśli chcesz mieć możliwość dodawania moderatorów, sprawdź kanał <#{premium_channel_id}>."
        )

    @staticmethod
    async def send_permission_update_error(ctx, target, permission_flag):
        """Sends a message when there is an error updating the permission."""
        await ctx.reply(
            f"Nie udało się ustawić uprawnienia {permission_flag} dla {target.mention}.",
            allowed_mentions=AllowedMentions(users=False, roles=False),
        )


class DatabaseManager:
    """Manages database operations."""

    def __init__(self, bot):
        self.bot = bot

    async def should_update_db(
        self, member: discord.Member, voice_channel: Optional[discord.VoiceChannel]
    ) -> bool:
        """
        Determine if the database should be updated based on the member's roles and voice channel.

        :param member: The member to check
        :param voice_channel: The voice channel the member is in (if any)
        :return: True if the database should be updated, False otherwise
        """
        has_premium = any(
            role["name"] in [r.name for r in member.roles]
            for role in self.bot.config["premium_roles"]
        )
        is_in_specific_category = (
            voice_channel
            and voice_channel.category_id in self.bot.config.get("premium_categories", [])
        )
        return has_premium and is_in_specific_category

    async def update_permission(
        self,
        session: AsyncSession,
        member_id: int,
        target_id: int,
        allow_permissions_value: Permissions,
        deny_permissions_value: Permissions,
        update_db: Optional[Literal["+", "-"]],
    ):
        """Updates the permission in the database."""
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

    async def get_member_permissions(self, session: AsyncSession, member_id: int):
        """Retrieves permissions for a member from the database."""
        return await ChannelPermissionQueries.get_permissions_for_member(session, member_id)


class VoicePermissionManager:
    """Manages voice channel permissions."""

    def __init__(self, bot):
        self.bot = bot
        self.db_manager = DatabaseManager(bot)
        self.message_sender = MessageSender()

    async def modify_channel_permission(
        self,
        ctx,
        target,
        permission_flag: str,
        value: Optional[Literal["+", "-"]],
        update_db: Optional[Literal["+", "-"]],
        default_to_true=False,
        toggle=False,
    ):
        """Modifies the channel permission for a target user or role."""
        current_channel = ctx.author.voice.channel
        current_perms = current_channel.overwrites_for(target) or PermissionOverwrite()
        new_value = self._determine_new_permission_value(
            current_perms, permission_flag, value, default_to_true, toggle
        )
        setattr(current_perms, permission_flag, new_value)

        # Aktualizuj uprawnienia na kanale i w bazie
        await self._update_channel_permission(ctx, target, current_perms)

        if permission_flag == "manage_messages":
            await self.message_sender.send_channel_mod_update(
                ctx,
                target,
                new_value,
                current_channel,
                await self.get_premium_role_limit(ctx.author),
            )
        else:
            await self.message_sender.send_permission_update(
                ctx, target, permission_flag, new_value
            )

        if (
            isinstance(target, discord.Member)
            and target.voice
            and target.voice.channel == current_channel
        ):
            await self._move_to_afk_if_needed(
                ctx, target, target.voice.channel, permission_flag, new_value
            )

    def _determine_new_permission_value(
        self,
        current_perms,
        permission_flag: str,
        value: Optional[Literal["+", "-"]],
        default_to_true=False,
        toggle=False,
    ):
        """Determines the new permission value based on inputs."""
        current_value = getattr(current_perms, permission_flag, None)

        if toggle:
            if current_value is True:
                return None if permission_flag == "manage_messages" else False
            return True

        if value is None:
            if current_value is None:
                return True if default_to_true else False
            if current_value is True:
                return None if permission_flag == "manage_messages" else False
            return True

        if value == "+":
            return True
        if value == "-":
            return None if permission_flag == "manage_messages" else False

    async def _update_db_permission(self, ctx, target, current_perms, update_db):
        """Updates the database permissions if required."""
        if update_db:
            allow_bits, deny_bits = current_perms.pair()
            async with self.bot.get_db() as session:
                # Zawsze aktualizujemy uprawnienia w bazie
                await ChannelPermissionQueries.add_or_update_permission(
                    session,
                    ctx.author.id,
                    target.id,
                    allow_bits.value,
                    deny_bits.value,
                    ctx.guild.id,
                )

    async def _update_channel_permission(self, ctx, target, current_perms):
        """Updates the channel permissions."""
        # Najpierw aktualizujemy uprawnienia na kanale
        await ctx.author.voice.channel.set_permissions(target, overwrite=current_perms)

        # Następnie aktualizujemy uprawnienia w bazie
        allow_bits, deny_bits = current_perms.pair()

        async with self.bot.get_db() as session:
            # Jeśli odbieramy uprawnienia moderatora (manage_messages=None)
            if getattr(current_perms, "manage_messages", None) is None:
                # Usuń uprawnienia z bazy
                await ChannelPermissionQueries.remove_permission(
                    session,
                    ctx.author.id,
                    target.id,
                )
            else:
                # W przeciwnym razie aktualizuj uprawnienia
                await ChannelPermissionQueries.add_or_update_permission(
                    session,
                    ctx.author.id,
                    target.id,
                    allow_bits.value,
                    deny_bits.value,
                    ctx.guild.id,
                )

    async def _handle_limit_exceeded(self, ctx, session, member_id, permission_limit):
        """Handles the case when a user exceeds their permission limit."""
        current_permissions = await self.db_manager.get_member_permissions(session, member_id)
        current_permissions.sort(key=lambda p: p.created_at)
        for permission in current_permissions:
            if permission.permission_flag != "manage_messages":
                await ChannelPermissionQueries.remove_permission(
                    session, member_id, permission.target_id
                )
                await self.message_sender.send_permission_limit_exceeded(ctx, permission_limit)
                break

    async def get_premium_role_limit(self, member):
        """Gets the maximum number of channel mods a member can assign based on their premium role."""
        premium_roles = self.bot.config["premium_roles"]
        logger.info(f"Member roles: {[r.name for r in member.roles]}")

        for role in reversed(premium_roles):
            # logger.info(f"Checking role: {role}")
            if any(r.name == role["name"] for r in member.roles):
                logger.info(f"Found matching role: {role}, limit: {role['moderator_count']}")
                return role["moderator_count"]
        return 0

    async def _move_to_afk_if_needed(self, ctx, target, target_channel, permission_flag, value):
        """Moves the target to the AFK channel if needed based on permission changes."""
        afk_channel_id = self.bot.config["channels_voice"]["afk"]
        afk_channel = ctx.guild.get_channel(afk_channel_id)

        if target and target_channel == ctx.author.voice.channel:
            # Dla view_channel i connect przenoś tylko gdy odbieramy uprawnienia
            if permission_flag in ["view_channel", "connect"] and not value:
                if afk_channel:
                    await target.move_to(afk_channel)
            # Dla speak przenoś na AFK i z powrotem zawsze aby odświeżyć uprawnienia
            if permission_flag == "speak":
                if afk_channel:
                    await target.move_to(afk_channel)
                    await target.move_to(ctx.author.voice.channel)

    async def get_permission(self, target, channel, permission_name: str) -> bool:
        """Gets the current permission value for a target in a channel."""
        overwrites = channel.overwrites_for(target)
        return getattr(overwrites, permission_name, None)

    async def can_manage_channel(self, member, channel):
        """Checks if a member has manage_messages permission on the channel."""
        return await self.get_permission(member, channel, "manage_messages")

    async def can_assign_channel_mod(self, member, channel):
        """Checks if a member has priority_speaker permission on the channel."""
        return await self.get_permission(member, channel, "priority_speaker")

    async def sync_permissions_from_db(self, ctx, channel, is_public=False):
        """Synchronizes channel permissions from database.

        Args:
            ctx: The command context
            channel: The voice channel to sync permissions to
            is_public: If True, don't sync permissions from database (for public channels)
        """
        # Dla kanałów publicznych nie synchronizujemy uprawnień z bazy
        if is_public:
            return

        # Dla kanałów prywatnych synchronizujemy wszystkie uprawnienia
        async with self.bot.get_db() as session:
            # Pobierz wszystkie uprawnienia z bazy dla tego właściciela
            db_permissions = await ChannelPermissionQueries.get_permissions_for_member(
                session, ctx.author.id
            )

            # Dla każdego uprawnienia w bazie
            for perm in db_permissions:
                target = ctx.guild.get_member(perm.target_id)
                if target:
                    # Konwertuj bity uprawnień na obiekt PermissionOverwrite
                    allow_perms = discord.Permissions(perm.allow_permissions_value)
                    deny_perms = discord.Permissions(perm.deny_permissions_value)

                    overwrite = discord.PermissionOverwrite()
                    for perm_name, value in allow_perms:
                        if value:
                            setattr(overwrite, perm_name, True)
                    for perm_name, value in deny_perms:
                        if value:
                            setattr(overwrite, perm_name, False)

                    # Ustaw uprawnienia na kanale
                    await channel.set_permissions(target, overwrite=overwrite)


class VoiceChannelManager:
    """Manages voice channel operations."""

    def __init__(self, bot):
        self.bot = bot
        self.message_sender = MessageSender()

    async def join_channel(self, ctx):
        """Joins the voice channel of the command author."""
        if ctx.author.voice is None:
            await self.message_sender.send_not_in_voice_channel(ctx)
            return

        channel = ctx.author.voice.channel

        if ctx.voice_client is not None:
            await ctx.voice_client.move_to(channel)
        else:
            await channel.connect()

        await self.message_sender.send_joined_channel(ctx, channel)

    async def set_channel_limit(self, ctx, max_members: int):
        """Sets the member limit for the current voice channel."""
        if ctx.author.voice is None:
            await self.message_sender.send_not_in_voice_channel(ctx)
            return

        if max_members > 99:
            max_members = 0  # Set to 0 for unlimited
        elif max_members < 1:
            max_members = 1  # Set to 1 as the minimum

        voice_channel = ctx.author.voice.channel
        await voice_channel.edit(user_limit=max_members)

        limit_text = "brak limitu" if max_members == 0 else str(max_members)
        await self.message_sender.send_member_limit_set(ctx, voice_channel, limit_text)


class ChannelModManager:
    """Manages channel moderators."""

    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = VoicePermissionManager(bot)
        self.message_sender = MessageSender()

    async def show_mod_status(self, ctx, voice_channel, mod_limit):
        """Shows current mod status."""
        # Get current mods from channel overwrites only
        current_mods = [
            t
            for t, overwrite in voice_channel.overwrites.items()
            if isinstance(t, discord.Member)
            and overwrite.manage_messages is True  # Musi być dokładnie True (nie None ani False)
            and not (
                overwrite.priority_speaker is True and t == ctx.author
            )  # Wykluczamy tylko właściciela kanału
        ]

        current_mods_mentions = ", ".join(
            [member.mention for member in current_mods if member != ctx.author]
        )
        if not current_mods_mentions:
            current_mods_mentions = "brak"

        remaining_slots = max(0, mod_limit - len(current_mods))

        message = (
            f"Aktualni moderatorzy: {current_mods_mentions}\n"
            f"Możesz przypisać maksymalnie {mod_limit} moderatorów (pozostało slotów: {remaining_slots})"
        )

        await ctx.reply(
            message,
            allowed_mentions=AllowedMentions(users=False, roles=False),
        )

    async def check_prerequisites(self, ctx, target, can_manage):
        """Checks prerequisites for assigning channel mod."""
        author = ctx.author
        voice_channel = author.voice.channel if author.voice else None

        if not voice_channel:
            await self.message_sender.send_not_in_voice_channel(ctx)
            return False

        if not await self.permission_manager.can_assign_channel_mod(author, voice_channel):
            await self.message_sender.send_no_mod_permission(ctx)
            return False

        if author == target and can_manage == "-":
            await self.message_sender.send_cant_remove_self_mod(ctx)
            return False

        return True

    async def check_mod_limit(self, ctx, target, mod_limit, can_manage):
        """Checks if the mod limit would be exceeded by this action."""
        logger.info(f"Checking mod limit. Current limit: {mod_limit}")
        logger.info(f"Can manage value: {can_manage}")

        # Nie sprawdzamy limitu przy usuwaniu moda
        if can_manage == "-":
            logger.info("Skipping mod limit check for removal operation")
            return False

        if mod_limit <= 0:
            premium_channel_id = self.bot.config["channels"]["premium_info"]
            await self.message_sender.send_no_premium_role(ctx, premium_channel_id)
            return True

        voice_channel = ctx.author.voice.channel
        current_mods = [
            t
            for t, overwrite in voice_channel.overwrites.items()
            if isinstance(t, discord.Member)
            and overwrite.manage_messages is True
            and not overwrite.priority_speaker
        ]

        current_mods_count = len(current_mods)
        logger.info(f"Current mods count: {current_mods_count}")
        logger.info(f"Current mods: {[m.name for m in current_mods]}")

        # Sprawdzamy limit tylko przy dodawaniu moda
        if can_manage == "+" or (
            can_manage is None
            and not await self.permission_manager.can_manage_channel(target, voice_channel)
        ):
            if current_mods_count >= mod_limit:
                await self.message_sender.send_mod_limit_exceeded(ctx, mod_limit, current_mods)
                return True

        return False

    async def validate_channel_mod(self, ctx, target, can_manage):
        """Validates prerequisites and mod limit for channel mod action."""
        if not await self.check_prerequisites(ctx, target, can_manage):
            return False

        mod_limit = await self.permission_manager.get_premium_role_limit(ctx.author)
        logger.info(f"Got mod limit: {mod_limit}")
        if await self.check_mod_limit(ctx, target, mod_limit, can_manage):
            return False

        return True

    async def get_mod_limit(self, ctx):
        """Get the mod limit for the user based on their roles."""
        premium_roles = self.bot.config["premium_roles"]
        member_roles = [role.name for role in ctx.author.roles]
        # logger.info(f"Premium roles config: {premium_roles}")
        logger.info(f"Member roles: {member_roles}")

        # Sprawdź role od najwyższej do najniższej
        for role_config in reversed(premium_roles):
            # logger.info(f"Checking role: {role_config}")
            if role_config["name"] in member_roles:
                logger.info(
                    f"Found matching role: {role_config}, limit: {role_config['moderator_count']}"
                )
                return role_config["moderator_count"]

        return 0


class BasePermissionCommand:
    """Base class for permission-related commands."""

    def __init__(
        self,
        permission_name: str,
        permission_display_name: str,
        default_to_true=False,
        toggle=False,
        requires_mod=False,  # Czy wymaga uprawnień moderatora
        requires_owner=False,  # Czy wymaga uprawnień właściciela
    ):
        self.permission_name = permission_name
        self.permission_display_name = permission_display_name
        self.default_to_true = default_to_true
        self.toggle = toggle
        self.requires_mod = requires_mod
        self.requires_owner = requires_owner

    async def execute(self, cog, ctx, target, permission_value):
        """Execute the permission command."""
        if not await cog.permission_checker.check_voice_channel(ctx):
            return

        voice_channel = ctx.author.voice.channel

        # Sprawdź uprawnienia
        if self.requires_owner and not await cog.permission_checker.check_channel_owner(
            voice_channel, ctx
        ):
            await cog.message_sender.send_no_mod_permission(ctx)
            return

        if self.requires_mod and not await cog.permission_checker.check_channel_mod_or_owner(
            voice_channel, ctx
        ):
            await cog.message_sender.send_no_mod_permission(ctx)
            return

        # Sprawdź czy moderator (nie właściciel) próbuje modyfikować uprawnienia właściciela lub innych moderatorów
        is_owner = await cog.permission_checker.check_channel_owner(voice_channel, ctx)
        if not is_owner and await cog.permission_checker.check_channel_mod(voice_channel, ctx):
            target_perms = voice_channel.overwrites_for(target)
            if target_perms:
                if target_perms.priority_speaker:
                    await ctx.reply("Nie możesz modyfikować uprawnień właściciela kanału!")
                    return
                if target_perms.manage_messages:
                    await ctx.reply("Nie możesz modyfikować uprawnień innych moderatorów!")
                    return

        # Przetwórz argumenty dla komend tekstowych
        target, permission_value = cog._handle_text_command_permission(
            ctx, target, permission_value
        )
        logger.info(
            f"After handling text command: target={target}, permission_value={permission_value}"
        )

        # Dla komendy mod sprawdź dodatkowe warunki
        if self.permission_name == "manage_messages":
            if not await cog.mod_manager.validate_channel_mod(ctx, target, permission_value):
                return

        # For all commands
        await cog.permission_manager.modify_channel_permission(
            ctx,
            target,
            self.permission_name,
            permission_value,
            permission_value,  # update_db - używamy tej samej wartości co dla uprawnienia
            self.default_to_true,
            self.toggle,
        )


class PermissionChecker:
    """Handles permission checking logic."""

    def __init__(self, bot):
        self.bot = bot
        self.message_sender = MessageSender()

    async def check_voice_channel(self, ctx) -> bool:
        """Check if user is in voice channel."""
        if ctx.author.voice is None:
            await self.message_sender.send_not_in_voice_channel(ctx)
            return False
        return True

    async def check_channel_owner(self, channel, ctx) -> bool:
        """Check if user is the channel owner (has priority_speaker)."""
        if not channel:
            return False

        perms = channel.overwrites_for(ctx.author)
        return perms and perms.priority_speaker

    async def check_channel_mod(self, channel, ctx) -> bool:
        """Check if user is a channel mod (has manage_messages)."""
        if not channel:
            return False

        perms = channel.overwrites_for(ctx.author)
        return perms and perms.manage_messages

    async def check_channel_mod_or_owner(self, channel, ctx) -> bool:
        """Check if user is either channel owner or mod."""
        if not channel:
            return False

        perms = channel.overwrites_for(ctx.author)
        return perms and (perms.priority_speaker or perms.manage_messages)


class VoiceCog(commands.Cog):
    """Voice commands cog for managing voice channel permissions and operations."""

    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = VoicePermissionManager(bot)
        self.channel_manager = VoiceChannelManager(bot)
        self.mod_manager = ChannelModManager(bot)
        self.message_sender = MessageSender()
        self.db_manager = DatabaseManager(bot)
        self.permission_checker = PermissionChecker(bot)

        # Initialize permission commands
        self.permission_commands = {
            "speak": BasePermissionCommand("speak", "mówienia", requires_mod=True),
            "view": BasePermissionCommand("view_channel", "wyświetlania", requires_mod=True),
            "connect": BasePermissionCommand("connect", "połączenia", requires_mod=True),
            "text": BasePermissionCommand("send_messages", "pisania", requires_mod=True),
            "mod": BasePermissionCommand(
                "manage_messages",
                "moderatora",
                default_to_true=True,
                toggle=True,
                requires_owner=True,
            ),
        }

    @commands.hybrid_command(aliases=["s"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_speak="Ustaw uprawnienie mówienia (+ lub -)",
    )
    async def speak(
        self,
        ctx,
        target: Optional[Member] = None,
        can_speak: Optional[Literal["+", "-"]] = None,
    ):
        """Set the speak permission for the target."""
        await self.permission_commands["speak"].execute(self, ctx, target, can_speak)

    @commands.hybrid_command(aliases=["v"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_view="Ustaw uprawnienie wyświetlania (+ lub -)",
    )
    async def view(
        self,
        ctx,
        target: Optional[Member] = None,
        can_view: Optional[Literal["+", "-"]] = None,
    ):
        """Set the view permission for the target."""
        await self.permission_commands["view"].execute(self, ctx, target, can_view)

    @commands.hybrid_command(aliases=["c"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_connect="Ustaw uprawnienie połączenia (+ lub -)",
    )
    async def connect(
        self,
        ctx,
        target: Optional[Member] = None,
        can_connect: Optional[Literal["+", "-"]] = None,
    ):
        """Set the connect permission for the target."""
        await self.permission_commands["connect"].execute(self, ctx, target, can_connect)

    @commands.hybrid_command(aliases=["t"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Użytkownik do modyfikacji uprawnień",
        can_message="Ustaw uprawnienie pisania (+ lub -)",
    )
    async def text(
        self,
        ctx,
        target: Optional[Member] = None,
        can_message: Optional[Literal["+", "-"]] = None,
    ):
        """Set the message permission for the target."""
        await self.permission_commands["text"].execute(self, ctx, target, can_message)

    @commands.hybrid_command(aliases=["m"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Użytkownik do dodania lub usunięcia jako moderator kanału",
        can_manage="Dodaj (+) lub usuń (-) uprawnienia moderatora kanału",
    )
    async def mod(
        self,
        ctx,
        target: Optional[Member] = None,
        can_manage: Optional[Literal["+", "-"]] = None,
    ):
        """Add or remove channel moderator permissions for the selected user."""
        if not await self.permission_checker.check_voice_channel(ctx):
            return

        voice_channel = ctx.author.voice.channel
        mod_limit = await self.permission_manager.get_premium_role_limit(ctx.author)

        # If no target is provided, just show current mod information
        if target is None:
            await self.mod_manager.show_mod_status(ctx, voice_channel, mod_limit)
            return

        await self.permission_commands["mod"].execute(self, ctx, target, can_manage)

    @commands.hybrid_command(aliases=["j"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe()
    async def join(self, ctx):
        """Dołącz do kanału głosowego osoby, która użyła komendy."""
        await self.channel_manager.join_channel(ctx)

    @commands.hybrid_command(aliases=["l"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        max_members="Maksymalna liczba członków (1-99 dla konkretnej wartości)"
    )
    async def limit(self, ctx, max_members: int):
        """Zmień maksymalną liczbę członków, którzy mogą dołączyć do bieżącego kanału głosowego."""
        await self.channel_manager.set_channel_limit(ctx, max_members)

    @commands.hybrid_command(aliases=["vc"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="Użytkownik do sprawdzenia kanału głosowego (ID, wzmianka lub nazwa użytkownika)",
    )
    async def voicechat(self, ctx, target: Optional[Member] = None):
        """Wylij link do kanału głosowego użytkownika i/lub kanału głosowego docelowego."""
        author_info = await self.target_helper.get_voice_channel_info(ctx.author)

        target_info = None
        if target:
            target_member = await self.target_helper.get_target(ctx, target)
            if target_member:
                target_info = await self.target_helper.get_voice_channel_info(target_member)

        await self.message_sender.send_voice_channel_info(ctx, author_info, target_info)

    def _handle_text_command_permission(self, ctx, target, permission_value):
        """Handle text command permission parsing for voice commands."""
        if not ctx.interaction:  # This means it's a text command, not a slash command
            message_parts = ctx.message.content.split()
            logger.info(f"Processing text command parts: {message_parts}")

            if len(message_parts) > 2:
                # Jeśli drugi argument to + lub -, zamieniamy miejscami argumenty
                if message_parts[1] in ["+", "-"]:
                    # Pobierz target z trzeciego argumentu - użyj discord.utils.get
                    mention = message_parts[2]
                    # Usuń <@! lub <@ i > z ID
                    user_id = "".join(filter(str.isdigit, mention))
                    target = ctx.guild.get_member(int(user_id)) if user_id else None
                    permission_value = message_parts[1]  # Ustaw permission_value na znak + lub -
                    logger.info(
                        f"Extracted user_id: {user_id}, found member: {target}, permission: {permission_value}"
                    )
                elif message_parts[2] in ["+", "-"]:
                    permission_value = message_parts[2]
            elif len(message_parts) > 1 and message_parts[1] in ["+", "-"]:
                permission_value = message_parts[1]

        logger.info(f"Final target: {target}, permission_value: {permission_value}")  # Debug log
        return target, permission_value


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(VoiceCog(bot))


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(VoiceCog(bot))
