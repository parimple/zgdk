"""Voice channel permission management utilities."""

import logging
from typing import Literal, Optional

import discord
from discord import PermissionOverwrite
from discord.ext import commands

from datasources.queries import ChannelPermissionQueries
from utils.channel_permissions import ChannelPermissionManager
from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class BasePermissionCommand:
    """
    Base class for permission-related commands.
    Handles permission modification in voice channels based on owner/mod status.
    """

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
        """
        Execute the permission command.

        The execution flow is:
        1. Check if user is in voice channel
        2. Check if user has required permissions (owner/mod)
        3. Parse and validate target
        4. Check if user can modify target's permissions
        5. Apply the permission change
        """
        self.logger.info(
            f"Executing permission command: {self.permission_name} for target={target}, value={permission_value}"
        )

        # Block priority_speaker modification
        if self.permission_name == "priority_speaker":
            self.logger.warning("Attempted to modify priority_speaker permission")
            await cog.message_sender.send_no_permission(
                ctx, "modyfikacji uprawnień priority_speaker!"
            )
            return

        if self.is_reset:
            if not await cog.permission_checker.check_voice_channel(ctx):
                return

            voice_channel = ctx.author.voice.channel
            if not await cog.permission_checker.check_channel_owner(voice_channel, ctx):
                await cog.message_sender.send_no_permission(
                    ctx, "resetowania uprawnień (wymagany właściciel kanału)!"
                )
                return

            if target:
                await cog.reset_user_permissions(ctx, target)
            else:
                await cog.reset_channel_permissions(ctx)
            return

        if self.is_autokick:
            if target is None:
                await cog.autokick_manager.list_autokicks(ctx)
                return

            permission_value = permission_value or "+"  # domyślnie dodajemy do listy
            if permission_value == "+":
                await cog.autokick_manager.add_autokick(ctx, target)
            elif permission_value == "-":
                await cog.autokick_manager.remove_autokick(ctx, target)
            return

        # Check if user is in voice channel
        if not await cog.permission_checker.check_voice_channel(ctx):
            return

        voice_channel = ctx.author.voice.channel
        permission_level = await cog.permission_checker.check_permission_level(
            voice_channel, ctx
        )
        self.logger.info(f"User permission level: {permission_level}")

        # Check if user has required permissions
        if self.requires_owner and permission_level != "owner":
            self.logger.info("Command requires owner permission")
            await cog.message_sender.send_no_permission(
                ctx, "tej komendy (wymagany właściciel kanału)!"
            )
            return

        # Parse target and permission value
        target, permission_value = cog.permission_checker.parse_command_args(
            ctx, target, permission_value
        )
        if not target:
            self.logger.warning("Invalid target specified")
            await cog.message_sender.send_invalid_target(ctx)
            return

        # Block setting manage_messages for @everyone
        if (
            self.permission_name == "manage_messages"
            and target == ctx.guild.default_role
        ):
            await cog.message_sender.send_error(
                ctx, "Nie można ustawić uprawnień moderatora dla @everyone!"
            )
            return

        # Get current permissions and determine new value
        current_perms = voice_channel.overwrites_for(target)
        final_value = cog.permission_manager._determine_new_permission_value(
            current_perms,
            self.permission_name,
            permission_value,
            self.default_to_true,
            self.toggle,
            ctx=ctx,
            target=target,
        )

        # Check if target has blocking roles when trying to enable permission
        if isinstance(target, discord.Member) and final_value is True:
            mute_roles = ctx.bot.config.get("mute_roles", [])
            for role_config in mute_roles:
                role = ctx.guild.get_role(role_config["id"])
                if role and role in target.roles:
                    if (
                        role_config["description"] == "stream_off"
                        and self.permission_name == "stream"
                    ):
                        await cog.message_sender.send_error(
                            ctx,
                            f"Nie można nadać uprawnień do streamowania - użytkownik {target.mention} ma rolę {role.name}!",
                        )
                        return
                    elif (
                        role_config["description"] == "send_messages_off"
                        and self.permission_name == "send_messages"
                    ):
                        await cog.message_sender.send_error(
                            ctx,
                            f"Nie można nadać uprawnień do pisania - użytkownik {target.mention} ma rolę {role.name}!",
                        )
                        return

        # Check mod limit when adding a new moderator
        if self.permission_name == "manage_messages" and final_value is True:
            if not await cog.mod_manager.can_add_mod(ctx.author, voice_channel):
                mod_limit = 0
                for role in reversed(cog.bot.config["premium_roles"]):
                    if any(r.name == role["name"] for r in ctx.author.roles):
                        mod_limit = role["moderator_count"]
                        break
                current_mods = [
                    t
                    for t, overwrite in voice_channel.overwrites.items()
                    if isinstance(t, discord.Member)
                    and overwrite.manage_messages is True
                    and not overwrite.priority_speaker
                ]
                await cog.message_sender.send_mod_limit_exceeded(
                    ctx, mod_limit, current_mods
                )
                return

        # Check if user can modify target's permissions
        if not await cog.permission_checker.can_modify_permissions(
            voice_channel, ctx, target
        ):
            self.logger.info("User cannot modify target permissions")
            if permission_level == "mod":
                if await cog.permission_checker.check_channel_owner(
                    voice_channel, target
                ):
                    await cog.message_sender.send_cant_modify_owner_permissions(ctx)
                elif await cog.permission_checker.check_channel_mod(
                    voice_channel, target
                ):
                    await cog.message_sender.send_cant_modify_mod_permissions(ctx)
                else:
                    await cog.message_sender.send_no_permission(
                        ctx, "modyfikacji uprawnień tego użytkownika!"
                    )
            else:
                await cog.message_sender.send_no_permission(
                    ctx, "zarządzania uprawnieniami na tym kanale!"
                )
            return

        # Apply permission change
        await cog.permission_manager.modify_channel_permission(
            ctx,
            target,
            self.permission_name,
            permission_value,
            "+",  # Always update database
            self.default_to_true,
            self.toggle,
        )


class PermissionChecker:
    """
    Handles permission checking logic for voice commands.
    This class is responsible for checking channel-level permissions:
    - Owner: has priority_speaker permission in channel overwrites
    - Mod: has manage_messages permission in channel overwrites
    """

    def __init__(self, bot):
        self.bot = bot
        self.message_sender = MessageSender()
        self.logger = logging.getLogger(__name__)

    def voice_command(requires_owner: bool = False):
        """
        Decorator for voice commands that enforces channel permission requirements.

        Args:
            requires_owner (bool): If True, only channel owner (priority_speaker) can use the command.
                                 If False, both owner and mod can use the command.
        """

        async def predicate(ctx):
            # Skip checks for help command and help context
            if ctx.command.name in ["help", "pomoc"] or ctx.invoked_with in [
                "help",
                "pomoc",
            ]:
                return True

            checker = ctx.cog.permission_checker

            # Check if user is in voice channel
            if not await checker.check_voice_channel(ctx):
                return False

            voice_channel = ctx.author.voice.channel
            permission_level = await checker.check_permission_level(voice_channel, ctx)

            if requires_owner and permission_level != "owner":
                await checker.message_sender.send_no_permission(
                    ctx, "tej komendy (wymagany właściciel kanału)!"
                )
                return False
            elif permission_level == "none":
                await checker.message_sender.send_no_permission(
                    ctx, "zarządzania tym kanałem!"
                )
                return False

            return True

        return commands.check(predicate)

    async def check_voice_channel(self, ctx) -> bool:
        """Check if user is in voice channel."""
        if ctx.author.voice is None:
            await self.message_sender.send_not_in_voice_channel(ctx)
            return False
        return True

    async def check_channel_owner(self, channel, ctx) -> bool:
        """Check if user has priority_speaker permission in channel overwrites."""
        if not channel:
            return False
        perms = channel.overwrites_for(ctx.author)
        return perms and perms.priority_speaker is True

    async def check_channel_mod(self, channel, ctx) -> bool:
        """Check if user has manage_messages (but not priority_speaker) in channel overwrites."""
        if not channel:
            return False
        perms = channel.overwrites_for(ctx.author)
        return perms and perms.manage_messages is True and not perms.priority_speaker

    async def check_permission_level(
        self, channel, ctx
    ) -> Literal["owner", "mod", "none"]:
        """
        Check user's permission level in the channel based on overwrites.

        Returns:
            - "owner" if user has priority_speaker
            - "mod" if user has manage_messages (but not priority_speaker)
            - "none" otherwise
        """
        if not channel:
            return "none"
        perms = channel.overwrites_for(ctx.author)
        if not perms:
            return "none"

        if perms.priority_speaker:
            return "owner"
        elif perms.manage_messages:
            return "mod"
        return "none"

    async def can_modify_permissions(self, channel, ctx, target=None) -> bool:
        """
        Check if user can modify permissions.

        Rules:
        - Owner (priority_speaker) can modify all permissions except priority_speaker
        - Mod (manage_messages) can modify regular user permissions only
        - Regular users cannot modify any permissions
        """
        if not channel:
            return False

        permission_level = await self.check_permission_level(channel, ctx)

        if permission_level == "owner":
            return True
        elif permission_level == "mod" and target:
            target_perms = channel.overwrites_for(target)
            # Mods cannot modify owner or other mod permissions
            if target_perms and (
                target_perms.priority_speaker or target_perms.manage_messages
            ):
                return False
            return True
        return False

    def parse_command_args(
        self, ctx, target, permission_value
    ) -> tuple[discord.Member | discord.Role, Optional[Literal["+", "-"]]]:
        """
        Parse command arguments for both text and slash commands.
        Only handles user mentions and @everyone role.

        Returns:
            tuple: (target object, permission value)
                target is either Member or the @everyone role
                permission_value is either "+", "-" or None for toggle
        """
        if not ctx.interaction:  # Text command
            message_parts = ctx.message.content.split()

            if len(message_parts) > 1:
                second_arg = message_parts[1]

                # Handle +/- with or without target
                if second_arg in ["+", "-"]:
                    if len(message_parts) == 2:
                        return ctx.guild.default_role, second_arg
                    else:
                        mention = message_parts[2]
                        if mention.startswith("<@") and not mention.startswith("<@&"):
                            user_id = "".join(filter(str.isdigit, mention))
                            target = (
                                ctx.guild.get_member(int(user_id)) if user_id else None
                            )
                        elif mention.isdigit():  # Handle raw user ID
                            target = ctx.guild.get_member(int(mention))
                            if not target:
                                # Log when member is not found
                                logger.warning(f"Member with ID {mention} not found in guild")
                        else:
                            target = ctx.guild.default_role
                        return target, second_arg

                # Handle target with optional +/-
                elif second_arg.startswith("<@") and not second_arg.startswith("<@&"):
                    user_id = "".join(filter(str.isdigit, second_arg))
                    target = ctx.guild.get_member(int(user_id)) if user_id else None
                    permission_value = (
                        message_parts[2]
                        if len(message_parts) > 2 and message_parts[2] in ["+", "-"]
                        else None
                    )
                    return target, permission_value
                elif second_arg.isdigit():  # Handle raw user ID
                    target = ctx.guild.get_member(int(second_arg))
                    permission_value = (
                        message_parts[2]
                        if len(message_parts) > 2 and message_parts[2] in ["+", "-"]
                        else None
                    )
                    return target, permission_value

            # Default to @everyone toggle
            return ctx.guild.default_role, None

        # Slash command - arguments already properly parsed
        return target, permission_value


class VoicePermissionManager:
    """Manages voice channel permissions."""

    # Permission value mapping tables
    TOGGLE_MAP = {
        True: lambda pf: None if pf == "manage_messages" else False,
        False: lambda _: True,
        None: lambda _: True,
    }

    DIRECT_MAP = {
        "+": lambda _: True,
        "-": lambda pf: None if pf == "manage_messages" else False,
        None: None,  # Special case - handled separately
    }

    def __init__(self, bot):
        self.bot = bot
        self.db_manager = None  # Will be set after import to avoid circular dependency
        self.message_sender = MessageSender()
        self.logger = logging.getLogger(__name__)
        self.channel_perm_manager = ChannelPermissionManager(bot)

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
                self.logger.info(
                    f"Found {cat_type} limit: {cat_config.get('limit', 0)}"
                )
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
            if (
                current_channel.category
                and current_channel.category.id
                in self.bot.config.get("clean_permission_categories", [])
            ):
                current_perms = (
                    current_channel.overwrites_for(target) or PermissionOverwrite()
                )
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
            current_perms,
            permission_flag,
            value,
            default_to_true,
            toggle,
            ctx=ctx,
            target=target,
        )
        self.logger.info(f"New permission value determined: {new_value}")

        setattr(current_perms, permission_flag, new_value)

        # Aktualizuj uprawnienia na kanale i w bazie
        try:
            await self._update_channel_permission(
                ctx, target, current_perms, permission_flag
            )
        except Exception as e:
            self.logger.error(
                f"Error updating channel permissions: {str(e)}", exc_info=True
            )
            await self.message_sender.send_permission_update_error(
                ctx, target, permission_flag
            )
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
    ) -> Optional[bool]:
        """
        Determines the new permission value based on inputs.
        Uses mapping tables to simplify logic.

        The logic is:
        1. For toggle mode: True -> False/None, False/None -> True
        2. For direct mode (+/-): + -> True, - -> False/None
        3. For None value: Check @everyone permissions or use defaults

        Args:
            current_perms: Current permission overwrite
            permission_flag: The permission being modified
            value: Direct value to set (+ or -)
            default_to_true: Whether to default to True for manage_messages
            toggle: Whether to toggle the current value
            ctx: Command context (for checking @everyone perms)
            target: Target member/role

        Returns:
            Optional[bool]: The new permission value
                - True: Allow permission
                - False: Deny permission
                - None: Reset permission (for manage_messages)
        """
        current_value = getattr(current_perms, permission_flag, None)
        self.logger.info(f"Current permission value: {current_value}")

        # Handle toggle mode
        if toggle:
            return self.TOGGLE_MAP[bool(current_value)](permission_flag)

        # Handle direct value (+/-)
        if value in self.DIRECT_MAP:
            if self.DIRECT_MAP[value] is not None:
                return self.DIRECT_MAP[value](permission_flag)

        # Handle None value (no explicit +/-)
        if current_value is None:
            if permission_flag == "manage_messages":
                return True if default_to_true else False

            # Check @everyone permissions
            if ctx and ctx.author.voice and ctx.author.voice.channel:
                everyone_perms = ctx.author.voice.channel.overwrites_for(
                    ctx.guild.default_role
                )
                everyone_value = getattr(everyone_perms, permission_flag, None)
                self.logger.info(f"@everyone permission value: {everyone_value}")

                # If @everyone has explicit permission or no restriction
                return False if (everyone_value is None or everyone_value) else True

        # Default toggle behavior
        return self.TOGGLE_MAP[bool(current_value)](permission_flag)

    async def _update_channel_permission(
        self, ctx, target, current_perms, permission_name
    ):
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
            self.logger.error(
                f"Error in _update_channel_permission: {str(e)}", exc_info=True
            )
            raise

    async def get_premium_role_limit(self, member):
        """Gets the maximum number of channel mods a member can assign based on their premium role."""
        premium_roles = self.bot.config["premium_roles"]
        logger.info(f"Member roles: {[r.name for r in member.roles]}")

        for role in reversed(premium_roles):
            if any(r.name == role["name"] for r in member.roles):
                logger.info(
                    f"Found matching role: {role}, limit: {role['moderator_count']}"
                )
                return role["moderator_count"]
        return 0

    async def _move_to_afk_if_needed(
        self, ctx, target, target_channel, permission_flag, value
    ):
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
                    self.logger.error(
                        f"Failed to set user limit: {str(e)}", exc_info=True
                    )

        # Sprawdź czy kanał jest w kategorii gdzie @everyone ma mieć czyste permisje
        clean_perms_category = (
            channel.category
            and channel.category.id
            in self.bot.config.get("clean_permission_categories", [])
        )
        if clean_perms_category:
            # Ustaw czyste permisje dla @everyone
            clean_perms = self._get_clean_everyone_permissions()
            try:
                await channel.set_permissions(
                    channel.guild.default_role, overwrite=clean_perms
                )
                self.logger.info(
                    f"Set clean permissions for @everyone in channel {channel.name}"
                )
            except Exception as e:
                self.logger.error(
                    f"Failed to set clean permissions: {str(e)}", exc_info=True
                )

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
            member_permissions = (
                await ChannelPermissionQueries.get_permissions_for_member(
                    session, member_id, limit=95
                )
            )
            self.logger.info(
                f"Found {len(member_permissions)} permissions in database for member {member_id}"
            )

        for permission in member_permissions:
            # Skip @everyone permissions for clean_perms channels
            if is_clean_perms and permission.target_id == guild.id:
                self.logger.info(
                    f"Skipping @everyone permissions from DB for clean perms channel"
                )
                continue

            allow_permissions = discord.Permissions(permission.allow_permissions_value)
            deny_permissions = discord.Permissions(permission.deny_permissions_value)
            overwrite = PermissionOverwrite.from_pair(
                allow_permissions, deny_permissions
            )
            self.logger.info(
                f"Processing permission for target {permission.target_id}: "
                f"allow={permission.allow_permissions_value}, deny={permission.deny_permissions_value}"
            )

            # Convert target_id to appropriate Discord object
            target = guild.get_member(permission.target_id) or guild.get_role(
                permission.target_id
            )
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

    async def reset_channel_permissions(
        self, channel: discord.VoiceChannel, owner: discord.Member
    ):
        """Deleguje do channel_perm_manager."""
        await self.channel_perm_manager.reset_channel_permissions(channel, owner)

    async def reset_user_permissions(
        self,
        channel: discord.VoiceChannel,
        owner: discord.Member,
        target: discord.Member,
    ):
        """Deleguje do channel_perm_manager."""
        await self.channel_perm_manager.reset_user_permissions(channel, owner, target)
