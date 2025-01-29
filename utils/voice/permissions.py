"""Voice channel permission management utilities."""

import logging
from typing import Literal, Optional

import discord
from discord import Member, PermissionOverwrite, Permissions

from datasources.queries import ChannelPermissionQueries
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class BasePermissionCommand:
    """Base class for permission-related commands."""

    def __init__(
        self,
        permission_name,
        requires_owner=False,
        default_to_true=False,
        toggle=False,
        is_autokick=False,
        is_reset=False,
    ):
        self.permission_name = permission_name
        self.requires_owner = requires_owner
        self.default_to_true = default_to_true
        self.toggle = toggle
        self.is_autokick = is_autokick
        self.is_reset = is_reset
        self.logger = logging.getLogger(__name__)

    async def execute(self, cog, ctx, target, permission_value):
        """Execute the permission command."""
        self.logger.info(
            f"Executing permission command: {self.permission_name} for target={target}, value={permission_value}"
        )

        if self.is_reset:
            if not await cog.permission_checker.check_voice_channel(ctx):
                return

            voice_channel = ctx.author.voice.channel
            if not await cog.permission_checker.check_channel_owner(voice_channel, ctx):
                await cog.message_sender.send_no_mod_permission(ctx)
                return

            if target:
                # Reset specific user permissions
                await cog.reset_user_permissions(ctx, target)
            else:
                # Reset entire channel permissions
                await cog.reset_channel_permissions(ctx)
            return

        if self.is_autokick:
            if target is None:
                await cog.autokick_manager.list_autokicks(ctx)
                return

            if permission_value is None:
                permission_value = "+"  # domyślnie dodajemy do listy

            if permission_value == "+":
                await cog.autokick_manager.add_autokick(ctx, target)
            elif permission_value == "-":
                await cog.autokick_manager.remove_autokick(ctx, target)
            return

        # Sprawdź czy użytkownik jest na kanale głosowym
        if not ctx.author.voice:
            self.logger.info("User not in voice channel")
            await cog.message_sender.send_not_in_voice_channel(ctx)
            return

        voice_channel = ctx.author.voice.channel
        if not voice_channel:
            self.logger.info("User not in voice channel")
            await cog.message_sender.send_not_in_voice_channel(ctx)
            return

        self.logger.info(f"Voice channel: {voice_channel.name} (ID: {voice_channel.id})")

        # Sprawdź uprawnienia
        is_owner = await cog.permission_checker.check_channel_owner(voice_channel, ctx)
        is_mod = await cog.permission_checker.check_channel_mod(voice_channel, ctx)
        has_permission = is_owner or (is_mod and not self.requires_owner)
        self.logger.info(
            f"Permission check: is_owner={is_owner}, is_mod={is_mod}, has_permission={has_permission}"
        )

        if not has_permission:
            self.logger.info("User lacks required permissions")
            await cog.message_sender.send_no_mod_permission(ctx)
            return

        # Jeśli nie ma argumentów, przełącz uprawnienie dla @everyone
        if target is None and permission_value is None:
            target = ctx.guild.default_role
            # Sprawdź aktualne uprawnienie
            current_perms = voice_channel.overwrites_for(target)
            current_value = getattr(current_perms, self.permission_name, None)
            # Przełącz na przeciwne (None lub True -> "-", False -> "+")
            permission_value = "+" if current_value is False else "-"
            self.logger.info(
                f"Toggling permission for @everyone: current_value={current_value}, new_value={permission_value}"
            )

        # Jeśli target to "-", ustaw dla @everyone
        elif isinstance(target, str) and target == "-":
            target = ctx.guild.default_role
            permission_value = "-" if permission_value is None else permission_value
            self.logger.info(f"Setting permission for @everyone: value={permission_value}")

        # Przetwórz argumenty dla komend tekstowych
        if target is not None or permission_value is not None:
            target, permission_value = self._handle_text_command_permission(
                ctx, target, permission_value
            )
            self.logger.info(
                f"After handling text command: target={target}, permission_value={permission_value}"
            )

        # Sprawdź czy moderator (nie właściciel) próbuje modyfikować uprawnienia właściciela lub innych moderatorów
        if not is_owner and is_mod:
            if target != ctx.guild.default_role:  # Pomijamy sprawdzanie dla @everyone
                target_perms = voice_channel.overwrites_for(target)
                if target_perms:
                    if target_perms.priority_speaker:
                        self.logger.info("Mod attempting to modify owner permissions")
                        await cog.message_sender.send_cant_modify_owner_permissions(ctx)
                        return
                    if target_perms.manage_messages:
                        self.logger.info("Mod attempting to modify other mod permissions")
                        await cog.message_sender.send_cant_modify_mod_permissions(ctx)
                        return

        # Dla komendy mod sprawdź dodatkowe warunki
        if self.permission_name == "manage_messages":
            if not await cog.mod_manager.validate_channel_mod(ctx, target, permission_value):
                self.logger.info("Mod validation failed")
                return

        # Modify channel permission with default_to_true and toggle parameters
        await cog.permission_manager.modify_channel_permission(
            ctx,
            target,
            self.permission_name,
            permission_value,
            "+",  # Always update database
            self.default_to_true,
            self.toggle,
        )

    def _handle_text_command_permission(self, ctx, target, permission_value):
        """Handle text command permission parsing for voice commands."""
        if not ctx.interaction:  # This means it's a text command, not a slash command
            message_parts = ctx.message.content.split()
            logger.info(f"Processing text command parts: {message_parts}")

            if len(message_parts) > 1:
                # Sprawdź drugi argument
                second_arg = message_parts[1]

                # Jeśli drugi argument to + lub - i nie ma trzeciego argumentu
                if second_arg in ["+", "-"] and len(message_parts) == 2:
                    target = ctx.guild.default_role
                    permission_value = second_arg
                    self.logger.info(f"Setting @everyone permission to {permission_value}")

                # Jeśli drugi argument to + lub - i jest trzeci argument (mention)
                elif second_arg in ["+", "-"] and len(message_parts) > 2:
                    mention = message_parts[2]
                    user_id = "".join(filter(str.isdigit, mention))
                    target = ctx.guild.get_member(int(user_id)) if user_id else None
                    permission_value = second_arg
                    logger.info(f"Setting permission {permission_value} for user {target}")

                # Jeśli drugi argument to mention
                elif second_arg.startswith("<@"):
                    user_id = "".join(filter(str.isdigit, second_arg))
                    target = ctx.guild.get_member(int(user_id)) if user_id else None
                    # Sprawdź czy jest trzeci argument (+ lub -)
                    if len(message_parts) > 2 and message_parts[2] in ["+", "-"]:
                        permission_value = message_parts[2]
                    logger.info(f"Setting permission for user {target} to {permission_value}")

            elif len(message_parts) == 1:
                # Jeśli jest tylko komenda, domyślnie dla @everyone
                target = ctx.guild.default_role
                permission_value = None
                self.logger.info("No arguments provided, defaulting to @everyone toggle")

        logger.info(f"Final target: {target}, permission_value: {permission_value}")  # Debug log
        return target, permission_value


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


class VoicePermissionManager:
    """Manages voice channel permissions."""

    def __init__(self, bot):
        self.bot = bot
        self.db_manager = None  # Will be set after import to avoid circular dependency
        self.message_sender = MessageSender()
        self.logger = logging.getLogger(__name__)

    def get_default_permission_overwrites(
        self, guild: discord.Guild, owner: discord.Member
    ) -> dict:
        """
        Get the default permission overwrites for a voice channel.

        Args:
            guild: The guild to get roles from
            owner: The channel owner to set permissions for

        Returns:
            dict: A dictionary of permission overwrites
        """
        # Initialize mute roles dictionary
        mute_roles = {
            role["description"]: guild.get_role(role["id"])
            for role in self.bot.config["mute_roles"]
        }

        # Set up permission overwrites
        return {
            mute_roles["stream_off"]: PermissionOverwrite(stream=False),
            mute_roles["send_messages_off"]: PermissionOverwrite(send_messages=False),
            mute_roles["attach_files_off"]: PermissionOverwrite(
                attach_files=False, embed_links=False, external_emojis=False
            ),
            owner: PermissionOverwrite(
                view_channel=True,
                connect=True,
                speak=True,
                priority_speaker=True,
                manage_messages=True,
            ),
        }

    def _get_clean_everyone_permissions(self) -> PermissionOverwrite:
        """Get clean/default permissions for @everyone role in max/public channels."""
        return PermissionOverwrite(
            view_channel=None,
            connect=None,
            speak=None,
            stream=None,
            use_voice_activation=None,
            priority_speaker=None,
            mute_members=None,
            deafen_members=None,
            move_members=None,
            manage_messages=None,
            send_messages=None,
            embed_links=None,
            attach_files=None,
            add_reactions=None,
            external_emojis=None,
            manage_channels=None,
            create_instant_invite=None,
        )

    def _get_default_user_limit(self, category_id: int) -> int:
        """Get default user limit for a channel based on its category."""
        config = self.bot.config.get("default_user_limits", {})

        # Sprawdź kategorie git i public
        for cat_type in ["git_categories", "public_categories"]:
            cat_config = config.get(cat_type, {})
            if category_id in cat_config.get("categories", []):
                self.logger.info(f"Found {cat_type} limit: {cat_config.get('limit', 0)}")
                return cat_config.get("limit", 0)

        # Sprawdź kategorie max
        max_categories = config.get("max_categories", {})
        for max_type, max_config in max_categories.items():
            if category_id == max_config.get("id"):
                limit = max_config.get("limit", 0)
                self.logger.info(f"Found max channel limit for {max_type}: {limit}")
                return limit

        self.logger.info(f"No limit found for category {category_id}")
        return 0  # Domyślnie brak limitu

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
        self.logger.info(
            f"Modifying channel permission: target={target}, permission={permission_flag}, value={value}, update_db={update_db}, default_to_true={default_to_true}, toggle={toggle}"
        )

        current_channel = ctx.author.voice.channel

        # Special handling for @everyone role in channels that should have clean permissions
        if isinstance(target, discord.Role) and target.id == ctx.guild.id:
            if current_channel.category and current_channel.category.id in self.bot.config.get(
                "clean_permission_categories", []
            ):
                current_perms = current_channel.overwrites_for(target) or PermissionOverwrite()
                current_value = getattr(current_perms, permission_flag, None)
                self.logger.info(f"Current @everyone permission value: {current_value}")

                # Determine new value based on input
                if value is None:
                    # Toggle logic: None -> False, False -> True, True -> False
                    if current_value is None:
                        new_value = False
                    elif current_value is False:
                        new_value = True
                    else:
                        new_value = False
                else:
                    # Direct setting with + or -
                    new_value = True if value == "+" else False

                self.logger.info(f"Setting @everyone {permission_flag} to {new_value}")
                setattr(current_perms, permission_flag, new_value)
                await current_channel.set_permissions(target, overwrite=current_perms)
                await self.message_sender.send_permission_update(
                    ctx, target, permission_flag, new_value
                )
                return

        current_perms = current_channel.overwrites_for(target) or PermissionOverwrite()

        new_value = self._determine_new_permission_value(
            current_perms, permission_flag, value, default_to_true, toggle, ctx=ctx, target=target
        )
        self.logger.info(f"New permission value determined: {new_value}")

        setattr(current_perms, permission_flag, new_value)

        # Aktualizuj uprawnienia na kanale i w bazie
        try:
            await self._update_channel_permission(ctx, target, current_perms, permission_flag)
        except Exception as e:
            self.logger.error(f"Error updating channel permissions: {str(e)}", exc_info=True)
            await self.message_sender.send_permission_update_error(ctx, target, permission_flag)
            return

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
        ctx=None,
        target=None,
    ):
        """Determines the new permission value based on inputs."""
        current_value = getattr(current_perms, permission_flag, None)
        self.logger.info(f"Current permission value: {current_value}")

        if toggle:
            if current_value is True:
                return None if permission_flag == "manage_messages" else False
            return True

        if value is None:
            if current_value is None:
                if permission_flag == "manage_messages":
                    # Dla manage_messages (mod) używamy default_to_true
                    return True if default_to_true else False
                else:
                    # Dla innych uprawnień sprawdzamy @everyone
                    everyone_perms = ctx.author.voice.channel.overwrites_for(ctx.guild.default_role)
                    everyone_value = getattr(everyone_perms, permission_flag, None)
                    self.logger.info(f"@everyone permission value: {everyone_value}")

                    # Jeśli @everyone ma jawne uprawnienie lub brak uprawnienia (None = dozwolone)
                    if everyone_value is None or everyone_value:
                        return False  # Ograniczamy uprawnienie
                    return True  # Zezwalamy na uprawnienie
            if current_value is True:
                return None if permission_flag == "manage_messages" else False
            return True

        if value == "+":
            return True
        if value == "-":
            return None if permission_flag == "manage_messages" else False

    async def _update_channel_permission(self, ctx, target, current_perms, permission_name):
        """Updates the channel permissions."""
        self.logger.info(
            f"Updating channel permissions for target={target} in channel={ctx.author.voice.channel}"
        )

        # Najpierw aktualizujemy uprawnienia na kanale
        await ctx.author.voice.channel.set_permissions(target, overwrite=current_perms)
        self.logger.info("Successfully updated Discord channel permissions")

        # Następnie aktualizujemy uprawnienia w bazie
        allow_bits, deny_bits = current_perms.pair()
        self.logger.info(
            f"Permission bits for {target}: allow={allow_bits.value}, deny={deny_bits.value}"
        )

        try:
            async with self.bot.get_db() as session:
                # Dla uprawnienia manage_messages, usuwamy z bazy gdy jest None
                if (
                    permission_name == "manage_messages"
                    and getattr(current_perms, "manage_messages", None) is None
                ):
                    self.logger.info(
                        f"Removing mod permissions from database for target={target.id}"
                    )
                    await ChannelPermissionQueries.remove_permission(
                        session, ctx.author.id, target.id
                    )
                else:
                    # Dla wszystkich innych przypadków aktualizujemy uprawnienia
                    self.logger.info(
                        f"Updating permissions in database for target={target.id} "
                        f"with allow={allow_bits.value}, deny={deny_bits.value}"
                    )
                    await ChannelPermissionQueries.add_or_update_permission(
                        session,
                        ctx.author.id,
                        target.id,
                        allow_bits.value,
                        deny_bits.value,
                        ctx.guild.id,
                    )
                await session.commit()
                self.logger.info("Successfully committed database changes")
        except Exception as e:
            self.logger.error(f"Error in _update_channel_permission: {str(e)}", exc_info=True)
            raise

    async def get_premium_role_limit(self, member):
        """Gets the maximum number of channel mods a member can assign based on their premium role."""
        premium_roles = self.bot.config["premium_roles"]
        logger.info(f"Member roles: {[r.name for r in member.roles]}")

        for role in reversed(premium_roles):
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
            # Dla speak i stream przenoś na AFK i z powrotem zawsze aby odświeżyć uprawnienia
            if permission_flag in ["speak", "stream"]:
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
        # Ustaw domyślny limit użytkowników
        if channel.category:
            user_limit = self._get_default_user_limit(channel.category.id)
            if user_limit > 0:
                self.logger.info(
                    f"Setting user limit to {user_limit} for channel in category {channel.category.id}"
                )
                try:
                    await channel.edit(user_limit=user_limit)
                except Exception as e:
                    self.logger.error(f"Failed to set user limit: {str(e)}", exc_info=True)

        # Sprawdź czy kanał jest w kategorii gdzie @everyone ma mieć czyste permisje
        clean_perms_category = channel.category and channel.category.id in self.bot.config.get(
            "clean_permission_categories", []
        )
        if clean_perms_category:
            # Ustaw czyste permisje dla @everyone
            clean_perms = self._get_clean_everyone_permissions()
            try:
                await channel.set_permissions(channel.guild.default_role, overwrite=clean_perms)
                self.logger.info(f"Set clean permissions for @everyone in channel {channel.name}")
            except Exception as e:
                self.logger.error(f"Failed to set clean permissions: {str(e)}", exc_info=True)

        # Dla kanałów publicznych nie synchronizujemy uprawnień z bazy
        if is_public:
            return

        # Dla kanałów prywatnych synchronizujemy uprawnienia z bazy
        async with self.bot.get_db() as session:
            # Pobierz wszystkie uprawnienia z bazy dla tego właściciela
            db_permissions = await ChannelPermissionQueries.get_permissions_for_member(
                session, ctx.author.id
            )

            # Dla każdego uprawnienia w bazie
            for perm in db_permissions:
                # Pomijamy uprawnienia dla roli @everyone dla kanałów z czystymi permisjami
                if perm.target_id == channel.guild.id and clean_perms_category:
                    self.logger.info(
                        f"Skipping @everyone permissions from DB for channel {channel.name} in clean perms category"
                    )
                    continue

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

    async def add_db_overwrites_to_permissions(
        self,
        guild: discord.Guild,
        member_id: int,
        permission_overwrites: dict,
        is_clean_perms: bool = False,
    ) -> dict:
        """
        Fetch permissions from the database and add them to the provided permission_overwrites dict.

        Args:
            guild: The guild to get members/roles from
            member_id: The ID of the member whose permissions to fetch
            permission_overwrites: The existing permission overwrites to add to
            is_clean_perms: Whether this is a channel that should have clean @everyone permissions

        Returns:
            dict: Additional overwrites that couldn't be added to the main dict
        """
        remaining_overwrites = {}
        async with self.bot.get_db() as session:
            member_permissions = await ChannelPermissionQueries.get_permissions_for_member(
                session, member_id, limit=95
            )
            self.logger.info(
                f"Found {len(member_permissions)} permissions in database for member {member_id}"
            )

        for permission in member_permissions:
            # Skip @everyone permissions for clean_perms channels
            if is_clean_perms and permission.target_id == guild.id:
                self.logger.info(f"Skipping @everyone permissions from DB for clean perms channel")
                continue

            allow_permissions = discord.Permissions(permission.allow_permissions_value)
            deny_permissions = discord.Permissions(permission.deny_permissions_value)
            overwrite = PermissionOverwrite.from_pair(allow_permissions, deny_permissions)
            self.logger.info(
                f"Processing permission for target {permission.target_id}: "
                f"allow={permission.allow_permissions_value}, deny={permission.deny_permissions_value}"
            )

            # Convert target_id to appropriate Discord object
            target = guild.get_member(permission.target_id) or guild.get_role(permission.target_id)
            if target:
                if target in permission_overwrites:
                    # If target already exists in main permissions, add new permissions to it
                    # Skip @everyone for clean_perms channels
                    if not (is_clean_perms and target == guild.default_role):
                        for key, value in overwrite._values.items():
                            if value is not None:
                                setattr(permission_overwrites[target], key, value)
                                self.logger.info(
                                    f"Updated existing permission {key}={value} for {target}"
                                )
                else:
                    # If target doesn't exist in main permissions, add to remaining
                    remaining_overwrites[target] = overwrite
                    self.logger.info(f"Added to remaining overwrites for {target}")

        return remaining_overwrites
