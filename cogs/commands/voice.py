"""Voice commands cog for managing voice channel permissions and operations."""

from typing import Literal, Optional, Tuple, Union

import discord
from discord import AllowedMentions, Member, PermissionOverwrite, Permissions
from discord.ext import commands
from sqlalchemy.ext.asyncio import AsyncSession

from datasources.queries import ChannelPermissionQueries
from utils.user import get_target_user


class MessageSender:
    """Handles sending messages to the server."""

    @staticmethod
    async def send_permission_update(ctx, target, permission_flag, new_value):
        """Sends a message about the updated permission."""
        mention_str = (
            target.mention if isinstance(target, discord.Member) else "wszystkich"
        )
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
    async def send_member_limit_set(ctx, voice_channel, max_members):
        """Sends a message when the member limit is set."""
        await ctx.reply(f"Limit członków na kanale {voice_channel} ustawiony na {max_members}.")

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
        await ctx.send(
            f"Możesz przypisać maksymalnie {mod_limit - 1} channel modów. Aktualni channel modzi: {current_mods_mentions}.",
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
    async def send_channel_mod_update(ctx, target, is_mod):
        """Sends a message about updating channel mod status."""
        action = "nadano uprawnienia" if is_mod else "odebrano uprawnienia"
        await ctx.reply(
            f"{target.mention} {action} moderatora kanału.",
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
        """Modifies the channel permission for a target user."""
        current_channel = ctx.author.voice.channel
        current_perms = current_channel.overwrites_for(target) or PermissionOverwrite()
        new_value = self._determine_new_permission_value(
            current_perms, permission_flag, value, default_to_true, toggle
        )
        setattr(current_perms, permission_flag, new_value)

        await self._update_channel_permission(ctx, target, current_perms)
        await self._update_db_permission(ctx, target, current_perms, update_db)
        await self._check_and_handle_permission_limit(ctx, ctx.author.id, current_perms)

        if permission_flag == "manage_messages":
            await self.message_sender.send_channel_mod_update(ctx, target, new_value)
        else:
            await self.message_sender.send_permission_update(
                ctx, target, permission_flag, new_value
            )

        await self._move_to_afk_if_needed(
            ctx, target, target.voice.channel if target.voice else None, permission_flag, new_value
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
            return None if current_value is True else True

        if value is None:
            if current_value is None:
                return True if default_to_true else False
            return not current_value

        if value == "+":
            return True
        if value == "-":
            if permission_flag == "manage_messages":
                return None
            return False

    async def _update_channel_permission(self, ctx, target, current_perms):
        """Updates the channel permissions."""
        await ctx.author.voice.channel.set_permissions(target, overwrite=current_perms)

    async def _update_db_permission(self, ctx, target, current_perms, update_db):
        """Updates the database permissions if required."""
        if update_db:
            allow_bits, deny_bits = current_perms.pair()
            async with self.bot.get_db() as session:
                await self.db_manager.update_permission(
                    session, ctx.author.id, target.id, allow_bits, deny_bits, update_db
                )

    async def _check_and_handle_permission_limit(
        self, ctx, member_id: int, new_permission: discord.PermissionOverwrite
    ):
        """Checks and handles the permission limit for a user."""
        premium_role = self._get_user_premium_role(ctx.author)
        if not premium_role:
            return

        permission_limit = premium_role.get("permission_limit", 50)  # default to 50 if not set
        async with self.bot.get_db() as session:
            current_permissions = await self.db_manager.get_member_permissions(session, member_id)

            if len(current_permissions) >= permission_limit:
                await self._handle_limit_exceeded(ctx, session, member_id, permission_limit)

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

    def _get_user_premium_role(self, member):
        """Gets the premium role of the member."""
        premium_roles = self.bot.config["premium_roles"]
        for role in reversed(premium_roles):
            if any(r.name == role["name"] for r in member.roles):
                return role
        return None

    async def _move_to_afk_if_needed(self, ctx, target, target_channel, permission_flag, value):
        """Moves the target to the AFK channel if needed based on permission changes."""
        afk_channel_id = self.bot.config["channels_voice"]["afk"]
        afk_channel = ctx.guild.get_channel(afk_channel_id)

        if target and target_channel == ctx.author.voice.channel:
            if permission_flag in ["view_channel", "connect"] and not value:
                if afk_channel:
                    await target.move_to(afk_channel)
            if permission_flag == "speak" and not value:
                if afk_channel:
                    await target.move_to(afk_channel)
                    await target.move_to(ctx.author.voice.channel)

    async def can_manage_channel(self, member, channel):
        """Checks if a member has manage_messages permission on the channel."""
        overwrites = channel.overwrites_for(member)
        return overwrites.manage_messages is True

    async def can_assign_channel_mod(self, member, channel):
        """Checks if a member has priority_speaker permission on the channel."""
        overwrites = channel.overwrites_for(member)
        return overwrites.priority_speaker is True

    async def get_premium_role_limit(self, member):
        """Gets the maximum number of channel mods a member can assign based on their premium role."""
        premium_roles = self.bot.config["premium_roles"]
        for role in reversed(premium_roles):
            if any(r.name == role["name"] for r in member.roles):
                return premium_roles.index(role) + 1
        return 0


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

        if max_members < 1 or max_members > 99:
            await self.message_sender.send_invalid_member_limit(ctx)
            return

        voice_channel = ctx.author.voice.channel
        await voice_channel.edit(user_limit=max_members)
        await self.message_sender.send_member_limit_set(ctx, voice_channel, max_members)


class ChannelModManager:
    """Manages channel moderators."""

    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = VoicePermissionManager(bot)
        self.message_sender = MessageSender()

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
        voice_channel = ctx.author.voice.channel
        current_mods = [
            t
            for t, overwrite in voice_channel.overwrites.items()
            if isinstance(t, discord.Member) and overwrite.manage_messages is True
        ]

        author_is_mod = await self.permission_manager.can_manage_channel(ctx.author, voice_channel)
        current_mods_count = len(current_mods) + (1 if author_is_mod else 0)

        if (
            can_manage == "+"
            or (
                can_manage is None
                and not await self.permission_manager.can_manage_channel(target, voice_channel)
            )
        ) and current_mods_count > mod_limit:
            await self.message_sender.send_mod_limit_exceeded(ctx, mod_limit, current_mods)
            return True

        return False

    async def validate_channel_mod(self, ctx, target, can_manage):
        """Validates prerequisites and mod limit for channel mod action."""
        if not await self.check_prerequisites(ctx, target, can_manage):
            return False

        mod_limit = await self.permission_manager.get_premium_role_limit(ctx.author)
        if await self.check_mod_limit(ctx, target, mod_limit, can_manage):
            return False

        return True


class TargetHelper:
    """Helper class for target-related operations."""

    def __init__(self, bot):
        self.bot = bot
        self.message_sender = MessageSender()
        self.db_manager = DatabaseManager(bot)

    async def get_target(
        self, ctx, target: Optional[Union[discord.Member, str]] = None
    ) -> Optional[Union[discord.Member, discord.Role]]:
        """
        Get the target member or role.

        :param ctx: The command context
        :param target: The target user input (can be None, Member object, ID, mention, or username)
        :return: Target member, @everyone role if target is None, or None if not found
        """
        target_member = await get_target_user(ctx, target)
        if target_member:
            return target_member
        elif target is None:
            return ctx.guild.default_role  # @everyone role
        else:
            await self.message_sender.send_user_not_found(ctx)
            return None

    async def get_target_and_update_db(
        self, ctx, target: Optional[Union[discord.Member, str]] = None
    ) -> Tuple[Optional[Union[discord.Member, discord.Role]], bool]:
        """
        Get the target and determine if the database should be updated.

        :param ctx: The command context
        :param target: The target user input
        :return: Tuple of (target_member_or_role, update_db)
        """
        target_member_or_role = await self.get_target(ctx, target)
        if not target_member_or_role:
            return None, False

        update_db = await self.db_manager.should_update_db(
            ctx.author, ctx.author.voice.channel if ctx.author.voice else None
        )
        return target_member_or_role, update_db

    async def validate_and_get_target(
        self, ctx, target: Optional[Union[discord.Member, str]], can_manage: Optional[Literal["+", "-"]]
    ) -> Tuple[Optional[Union[discord.Member, discord.Role]], bool]:
        """
        Validate and get the target member or role.

        :param ctx: The command context
        :param target: The target user input
        :param can_manage: The permission to manage
        :return: Tuple of (target_member_or_role, update_db) if valid, (None, False) otherwise
        """
        target_member_or_role, update_db = await self.get_target_and_update_db(ctx, target)
        if not target_member_or_role:
            return None, False

        if not await self.bot.get_cog("ChannelModManager").validate_channel_mod(ctx, target_member_or_role, can_manage):
            return None, False

        return target_member_or_role, update_db


class VoiceCog(commands.Cog):
    """Voice commands cog for managing voice channel permissions and operations."""

    def __init__(self, bot):
        self.bot = bot
        self.permission_manager = VoicePermissionManager(bot)
        self.channel_manager = VoiceChannelManager(bot)
        self.mod_manager = ChannelModManager(bot)
        self.message_sender = MessageSender()
        self.db_manager = DatabaseManager(bot)
        self.target_helper = TargetHelper(bot)

    @commands.hybrid_command(aliases=["s"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="User to modify permissions (ID, mention, or username)",
        can_speak="Set speak permission (+ or -)",
    )
    async def speak(
        self,
        ctx,
        target: Optional[Member] = None,
        can_speak: Optional[Literal["+", "-"]] = None,
    ):
        """Set the speak permission for the target."""
        target_member_or_role, update_db = await self.target_helper.get_target_and_update_db(ctx, target)
        if not target_member_or_role:
            return

        await self.permission_manager.modify_channel_permission(
            ctx, target_member_or_role, "speak", can_speak, update_db
        )

    @commands.hybrid_command(aliases=["v"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="User to modify permissions (ID, mention, or username)",
        can_view="Set view permission (+ or -)",
    )
    async def view(
        self,
        ctx,
        target: Optional[Member] = None,
        can_view: Optional[Literal["+", "-"]] = None,
    ):
        """Set the view permission for the target."""
        target_member_or_role, update_db = await self.target_helper.get_target_and_update_db(ctx, target)
        if not target_member_or_role:
            return

        await self.permission_manager.modify_channel_permission(
            ctx, target_member_or_role, "view_channel", can_view, update_db
        )

    @commands.hybrid_command(aliases=["c"])
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="User to modify permissions (ID, mention, or username)",
        can_connect="Set connect permission (+ or -)",
    )
    async def connect(
        self,
        ctx,
        target: Optional[Member] = None,
        can_connect: Optional[Literal["+", "-"]] = None,
    ):
        """Set the connect permission for the target."""
        target_member_or_role, update_db = await self.target_helper.get_target_and_update_db(ctx, target)
        if not target_member_or_role:
            return

        await self.permission_manager.modify_channel_permission(
            ctx, target_member_or_role, "connect", can_connect, update_db
        )

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    @discord.app_commands.describe(
        target="User to add or remove as channel mod (ID, mention, or username)",
        can_manage="Add (+) or remove (-) channel mod permissions",
    )
    async def channel_mod(
        self,
        ctx,
        target: Optional[Member] = None,
        can_manage: Optional[Literal["+", "-"]] = None,
    ):
        """Add or remove channel moderator permissions for the selected user."""
        target_member_or_role, update_db = await self.target_helper.validate_and_get_target(ctx, target, can_manage)
        if not target_member_or_role:
            return

        await self.permission_manager.modify_channel_permission(
            ctx,
            target_member_or_role,
            "manage_messages",
            can_manage,
            update_db,
            default_to_true=True,
            toggle=(can_manage is None),
        )

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    async def join(self, ctx):
        """Join the voice channel of the person who used the command."""
        await self.channel_manager.join_channel(ctx)

    @commands.hybrid_command()
    @commands.has_permissions(administrator=True)
    async def limit(self, ctx, max_members: int):
        """Change the maximum number of members that can join the current voice channel."""
        await self.channel_manager.set_channel_limit(ctx, max_members)


async def setup(bot):
    """This function is called when the cog is loaded."""
    await bot.add_cog(VoiceCog(bot))
