"""Event handler for voice state updates."""

import asyncio
import logging
import random

import discord
from discord.ext import commands

from utils.message_sender import MessageSender
from utils.voice.autokick import AutoKickManager
from utils.voice.permissions import VoicePermissionManager

logger = logging.getLogger(__name__)


class FakeContext:
    """A fake context class to provide bot and guild attributes."""

    def __init__(self, bot, guild):
        self.bot = bot
        self.guild = guild


class OnVoiceStateUpdateEvent(commands.Cog):
    """Class for handling the event when a member's voice state is updated."""

    def __init__(self, bot):
        self.bot = bot
        self.guild = None
        self.logger = logging.getLogger(__name__)
        self.message_sender = MessageSender(bot)
        self.permission_manager = VoicePermissionManager(bot)
        self.autokick_manager = AutoKickManager(bot)

        self.channels_create = self.bot.config["channels_create"]
        self.vc_categories = self.bot.config["vc_categories"]

    @commands.Cog.listener()
    async def on_ready(self):
        """Set guild when bot is ready"""
        self.guild = self.bot.get_guild(self.bot.guild_id)
        if not self.guild:
            logger.error("Cannot find guild with ID %d", self.bot.guild_id)
            return

        logger.info("Setting guild for VoicePermissionManager in OnVoiceStateUpdateEvent")
        self.permission_manager.guild = self.guild

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle the event when a member joins or leaves a voice channel."""
        # Check for autokicks when a member joins a voice channel
        if after.channel and before.channel != after.channel:
            if member.id != self.bot.config["owner_id"]:
                await self.handle_autokicks(member, after.channel)

            if after.channel and after.channel.id in self.channels_create:
                await self.handle_create_channel(member, after)
            elif after.channel and after.channel.id == self.bot.config["channels_voice"]["afk"]:
                return

        if (
            before.channel
            and before.channel != after.channel
            and before.channel.type == discord.ChannelType.voice
            and len(before.channel.members) == 0
        ):
            await self.handle_channel_leave(before)

    async def handle_autokicks(self, member, channel):
        """Handle autokicks for a member joining a voice channel"""
        if channel.id == self.bot.config["channels_voice"]["afk"]:
            return

        # self.logger.info(f"Checking autokick for member {member.id} in channel {channel.id}")

        # Check if member should be autokicked using AutoKickManager
        should_kick, matching_owners = await self.autokick_manager.check_autokick(member, channel)
        # self.logger.info(f"Should kick member {member.id}: {should_kick}")

        if should_kick and matching_owners:
            try:
                # Get the first matching owner
                owner = None
                for owner_id in matching_owners:
                    potential_owner = channel.guild.get_member(owner_id)
                    if potential_owner and potential_owner in channel.members:
                        owner = potential_owner
                        self.logger.info(f"Found owner {owner.id} in channel members")
                        break

                if not owner:
                    self.logger.warning(f"No owner found for autokick of member {member.id}")
                    return

                # Move member to AFK channel
                afk_channel = self.guild.get_channel(self.bot.config["channels_voice"]["afk"])
                if afk_channel:
                    await member.move_to(afk_channel)
                    self.logger.info(f"Moved member {member.id} to AFK channel {afk_channel.id}")
                else:
                    await member.move_to(None)
                    self.logger.info(f"Disconnected member {member.id} (no AFK channel)")

                # Set connect permission to False
                current_perms = channel.overwrites_for(member) or discord.PermissionOverwrite()
                current_perms.connect = False
                await channel.set_permissions(member, overwrite=current_perms)
                self.logger.info(
                    f"Set connect=False permission for member {member.id} in channel {channel.id}"
                )

                # Send notification
                await self.message_sender.send_autokick_notification(channel, member, owner)
                self.logger.info(f"Sent autokick notification for member {member.id}")
            except discord.Forbidden:
                self.logger.warning(f"Failed to autokick {member.id} (no permission)")
            except Exception as e:
                self.logger.error(f"Failed to autokick {member.id}: {str(e)}")

    async def handle_create_channel(self, member, after):
        """
        Handle the creation of a new voice channel when a member joins a creation channel.

        :param member: Member object representing the joining member
        :param after: VoiceState object representing the state after the update
        """
        # Buforowanie kategorii - pobieramy informacje o kategorii tylko raz
        category = after.channel.category
        category_id = category.id if category else None

        # Sprawdź, czy w kategorii istnieje pusty kanał
        empty_channels = []
        if category:
            empty_channels = [
                channel
                for channel in category.voice_channels
                if len(channel.members) == 0
                and channel.id not in self.channels_create
                and channel.id != self.bot.config["channels_voice"]["afk"]
            ]

        # Determine channel name based on category
        channel_name = member.display_name

        logger.info(f"Creating channel in category: {category_id}")

        # Optymalizacja: Pobieramy konfigurację formatów tylko raz
        formats = self.bot.config.get("channel_name_formats", {})

        # Check if category has a custom format
        format_key = category_id  # próbuj najpierw jako int
        custom_format = None

        if format_key in formats:
            custom_format = formats[format_key]
        elif str(category_id) in formats:
            custom_format = formats[str(category_id)]

        if custom_format:
            # Get random emoji
            emoji = random.choice(self.bot.config.get("channel_emojis", ["🎮"]))
            # Apply the format
            channel_name = custom_format.format(emoji=emoji)
            logger.info(f"Using format for category {category_id}: {channel_name}")
        else:
            # Check if this is a git category
            git_categories = (
                self.bot.config.get("default_user_limits", {})
                .get("git_categories", {})
                .get("categories", [])
            )
            if category_id in git_categories:
                channel_name = f"- {channel_name}"
                logger.info(f"Added dash prefix for git category: {channel_name}")
            else:
                logger.info(
                    f"No format found for category {category_id}, using default name: {channel_name}"
                )

        # Get default permission overwrites
        permission_overwrites = self.permission_manager.get_default_permission_overwrites(
            self.guild, member
        )

        # Get user limit based on category
        user_limit = 0
        if category_id:
            # Optymalizacja: Buforujemy konfigurację limitów, pobierając ją tylko raz
            config = self.bot.config.get("default_user_limits", {})

            # Sprawdź kategorie git i public
            for cat_type in ["git_categories", "public_categories"]:
                cat_config = config.get(cat_type, {})
                if category_id in cat_config.get("categories", []):
                    user_limit = cat_config.get("limit", 0)
                    logger.info(f"Setting {cat_type} limit: {user_limit}")
                    break

            # Sprawdź kategorie max
            if user_limit == 0:  # jeśli nie znaleziono limitu w git/public
                max_categories = config.get("max_categories", {})
                for max_type, max_config in max_categories.items():
                    if category_id == max_config.get("id"):
                        user_limit = max_config.get("limit", 0)
                        logger.info(f"Setting max channel limit for {max_type}: {user_limit}")
                        break

        # Check if this is a clean permissions category (max/public)
        is_clean_perms = category_id in self.bot.config.get("clean_permission_categories", [])
        if is_clean_perms:
            # Set clean permissions for @everyone
            permission_overwrites[
                self.guild.default_role
            ] = self.permission_manager._get_clean_everyone_permissions()
            logger.info(f"Set clean permissions for @everyone in category {category_id}")

        # Add permissions from database (always, except @everyone for clean_perms categories)
        db_overwrites = await self.permission_manager.add_db_overwrites_to_permissions(
            self.guild, member.id, permission_overwrites, is_clean_perms=is_clean_perms
        )

        # Combine all overwrites
        if db_overwrites:
            for target, overwrite in db_overwrites.items():
                if target in permission_overwrites:
                    # Update existing overwrite
                    current = permission_overwrites[target]
                    for perm, value in overwrite._values.items():
                        if value is not None:
                            setattr(current, perm, value)
                else:
                    # Add new overwrite
                    permission_overwrites[target] = overwrite

        # Jeśli istnieje pusty kanał, użyj go zamiast tworzyć nowy
        if empty_channels:
            # Użyj pierwszego pustego kanału
            existing_channel = empty_channels[0]
            logger.info(f"Wykorzystuję istniejący pusty kanał: {existing_channel.name}")

            # Nie zmieniamy nazwy ani limitu, bo są już ustawione poprawnie
            # Nie resetujemy uprawnień, bo zostały już zresetowane przy opuszczaniu kanału

            # Dodaj tylko uprawnienia dla właściciela kanału
            owner_permissions = permission_overwrites.get(member, None)
            if owner_permissions:
                await existing_channel.set_permissions(member, overwrite=owner_permissions)
                logger.info(f"Dodano uprawnienia właściciela dla {member.display_name}")

            # Przenieś członka do kanału
            await member.move_to(existing_channel)

            # Utwórz fake context i wyślij informację o zajęciu kanału
            fake_ctx = FakeContext(self.bot, member.guild)
            await self.message_sender.send_channel_creation_info(
                existing_channel, fake_ctx, owner=member
            )

            return

        # Create the new channel with all permissions and limits (gdy nie znaleziono pustego kanału)
        # Optymalizacja: Tworzenie kanału z wszystkimi parametrami za jednym razem
        new_channel = await self.guild.create_voice_channel(
            channel_name,
            category=category,
            bitrate=self.guild.bitrate_limit,
            user_limit=user_limit,
            overwrites=permission_overwrites,
        )

        # Move member to the new channel
        await member.move_to(new_channel)

        # Create fake context and send channel creation info
        fake_ctx = FakeContext(self.bot, member.guild)
        await self.message_sender.send_channel_creation_info(new_channel, fake_ctx, owner=member)

    async def handle_channel_leave(self, before):
        """
        Handle the deletion of a voice channel when all members leave.

        :param before: VoiceState object representing the state before the update
        """
        # Nie usuwamy kanałów create ani AFK
        if (
            before.channel.id in self.channels_create
            or before.channel.id == self.bot.config["channels_voice"]["afk"]
        ):
            return

        # Usuwamy tylko kanały w kategoriach głosowych
        if before.channel.category and before.channel.category.id in self.vc_categories:
            # Sprawdź, czy kategoria jest jedną z tych, gdzie zachowujemy puste kanały
            preserve_categories = [
                id
                for key, id in {
                    "publ": self.bot.config.get("default_user_limits", {})
                    .get("public_categories", {})
                    .get("categories", [])[0]
                    if self.bot.config.get("default_user_limits", {})
                    .get("public_categories", {})
                    .get("categories", [])
                    else None,
                    "max2": self.bot.config.get("default_user_limits", {})
                    .get("max_categories", {})
                    .get("max2", {})
                    .get("id"),
                    "max3": self.bot.config.get("default_user_limits", {})
                    .get("max_categories", {})
                    .get("max3", {})
                    .get("id"),
                    "max4": self.bot.config.get("default_user_limits", {})
                    .get("max_categories", {})
                    .get("max4", {})
                    .get("id"),
                    "max5": self.bot.config.get("default_user_limits", {})
                    .get("max_categories", {})
                    .get("max5", {})
                    .get("id"),
                }.items()
                if id is not None
            ]

            if before.channel.category.id in preserve_categories:
                # Sprawdź ile pustych kanałów jest już w tej kategorii
                empty_channels = [
                    channel
                    for channel in before.channel.category.voice_channels
                    if len(channel.members) == 0
                    and channel.id not in self.channels_create
                    and channel.id != self.bot.config["channels_voice"]["afk"]
                ]

                self.logger.info(
                    f"Liczba pustych kanałów w kategorii {before.channel.category.name}: {len(empty_channels)}"
                )

                if len(empty_channels) <= 3:  # Zachowaj kanał, jeśli pustych jest 3 lub mniej
                    self.logger.info(
                        f"Zachowuję pusty kanał {before.channel.name} w kategorii {before.channel.category.name}"
                    )

                    # Zoptymalizacja: Przygotuj wszystkie zmiany uprawnień na raz
                    clean_perms = self.permission_manager._get_clean_everyone_permissions()

                    # Przygotuj słownik wszystkich uprawnień do ustawienia za jednym razem
                    new_overwrites = {}

                    # Dodaj czyste uprawnienia dla @everyone
                    new_overwrites[before.channel.guild.default_role] = clean_perms

                    # Zachowaj tylko uprawnienia dla ról wyciszających
                    mute_role_ids = [role["id"] for role in self.bot.config["mute_roles"]]
                    for target, overwrite in before.channel.overwrites.items():
                        if isinstance(target, discord.Role) and target.id in mute_role_ids:
                            new_overwrites[target] = overwrite

                    # Ustaw odpowiedni limit użytkowników
                    user_limit = self.permission_manager._get_default_user_limit(
                        before.channel.category.id
                    )

                    # Zastosuj wszystkie zmiany jednym wywołaniem API
                    await before.channel.edit(overwrites=new_overwrites, user_limit=user_limit)

                    # Zakończ funkcję, nie usuwając kanału
                    return

            # W pozostałych przypadkach usuń kanał
            await before.channel.delete()


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnVoiceStateUpdateEvent(bot))
