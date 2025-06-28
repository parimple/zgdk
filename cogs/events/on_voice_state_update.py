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

        # Queue dla operacji autokick
        self.autokick_queue = asyncio.Queue()
        self.autokick_worker_task = None

        # Cache dla kategorii i ich konfiguracji
        self._category_config_cache = {}
        self._empty_channels_cache = {}
        self._cache_refresh_time = 0

        # Performance metrics
        self.metrics = {
            "channels_created": 0,
            "channels_reused": 0,
            "autokicks_queued": 0,
            "autokicks_executed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
        }

    @commands.Cog.listener()
    async def on_ready(self):
        """Set guild when bot is ready"""
        self.guild = self.bot.get_guild(self.bot.guild_id)
        if not self.guild:
            logger.error("Cannot find guild with ID %d", self.bot.guild_id)
            return

        logger.info("Setting guild for VoicePermissionManager in OnVoiceStateUpdateEvent")
        self.permission_manager.guild = self.guild

        # Start autokick worker
        if self.autokick_worker_task is None:
            self.autokick_worker_task = asyncio.create_task(self._autokick_worker())
            logger.info("Started autokick worker task")

    async def _autokick_worker(self):
        """Worker task dla przetwarzania operacji autokick"""
        while True:
            try:
                # Pobierz zadanie z queue (czekaj max 1 sekundę)
                try:
                    autokick_data = await asyncio.wait_for(self.autokick_queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue

                member, channel, matching_owners = autokick_data

                # Sprawdź czy member nadal jest w kanale (może już wyszedł)
                if member not in channel.members:
                    continue

                # Wykonaj autokick
                await self._execute_autokick(member, channel, matching_owners)

            except Exception as e:
                self.logger.error(f"Error in autokick worker: {str(e)}")
                await asyncio.sleep(1)

    async def _execute_autokick(self, member, channel, matching_owners):
        """Wykonuje faktyczny autokick"""
        try:
            self.metrics["autokicks_executed"] += 1
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
            self.logger.info(f"Set connect=False permission for member {member.id} in channel {channel.id}")

            # Send notification
            await self.message_sender.send_autokick_notification(channel, member, owner)
            self.logger.info(f"Sent autokick notification for member {member.id}")
        except discord.Forbidden:
            self.logger.warning(f"Failed to autokick {member.id} (no permission)")
        except Exception as e:
            self.logger.error(f"Failed to autokick {member.id}: {str(e)}")

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        """Handle the event when a member joins or leaves a voice channel."""
        # Check for autokicks when a member joins a voice channel
        if after.channel and before.channel != after.channel:
            logger.info(f"Member {member.display_name} joined channel {after.channel.name} (ID: {after.channel.id})")

            if member.id != self.bot.config["owner_id"]:
                await self.handle_autokicks(member, after.channel)

            if after.channel and after.channel.id in self.channels_create:
                logger.info(f"Channel {after.channel.id} is a create channel, handling creation...")
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
            self.metrics["autokicks_queued"] += 1
            await self.autokick_queue.put((member, channel, matching_owners))
            logger.info(f"Queued autokick for {member.display_name} (owners: {len(matching_owners)})")

    async def _get_category_config(self, category_id):
        """Pobiera konfigurację kategorii z cache"""
        current_time = asyncio.get_event_loop().time()

        # Refresh cache co 60 sekund
        if current_time - self._cache_refresh_time > 60:
            self._category_config_cache.clear()
            self._empty_channels_cache.clear()
            self._cache_refresh_time = current_time
            logger.info("Cache refreshed - cleared category and empty channels cache")

        if category_id not in self._category_config_cache:
            self.metrics["cache_misses"] += 1
            config = self.bot.config.get("default_user_limits", {})

            # Sprawdź kategorie git i public
            user_limit = 0
            for cat_type in ["git_categories", "public_categories"]:
                cat_config = config.get(cat_type, {})
                if category_id in cat_config.get("categories", []):
                    user_limit = cat_config.get("limit", 0)
                    break

            # Sprawdź kategorie max
            if user_limit == 0:
                max_categories = config.get("max_categories", {})
                for max_type, max_config in max_categories.items():
                    if category_id == max_config.get("id"):
                        user_limit = max_config.get("limit", 0)
                        break

            # Cache formatów nazw
            formats = self.bot.config.get("channel_name_formats", {})
            custom_format = formats.get(category_id) or formats.get(str(category_id))

            # Cache czy to kategoria clean permissions
            is_clean_perms = category_id in self.bot.config.get("clean_permission_categories", [])

            self._category_config_cache[category_id] = {
                "user_limit": user_limit,
                "custom_format": custom_format,
                "is_clean_perms": is_clean_perms,
            }
            logger.info(
                f"Cached config for category {category_id}: limit={user_limit}, format={bool(custom_format)}, clean_perms={is_clean_perms}"
            )
        else:
            self.metrics["cache_hits"] += 1

        return self._category_config_cache[category_id]

    async def _get_empty_channels(self, category):
        """Pobiera puste kanały z cache"""
        if category.id not in self._empty_channels_cache:
            self.metrics["cache_misses"] += 1
            empty_channels = [
                channel
                for channel in category.voice_channels
                if len(channel.members) == 0
                and channel.id not in self.channels_create
                and channel.id != self.bot.config["channels_voice"]["afk"]
            ]
            self._empty_channels_cache[category.id] = empty_channels
            logger.info(f"Cached {len(empty_channels)} empty channels for category {category.name}")
        else:
            self.metrics["cache_hits"] += 1

        return self._empty_channels_cache[category.id]

    async def handle_create_channel(self, member, after):
        """
        Handle the creation of a new voice channel when a member joins a creation channel.
        Ulepszona wersja z cache i optymalizacjami.
        """
        category = after.channel.category
        category_id = category.id if category else None

        if not category_id:
            return

        # Pobierz konfigurację kategorii z cache
        config = await self._get_category_config(category_id)

        # Sprawdź puste kanały z cache
        empty_channels = await self._get_empty_channels(category)

        # Determine channel name based on category
        channel_name = member.display_name

        if config["custom_format"]:
            # Get random emoji
            emoji = random.choice(self.bot.config.get("channel_emojis", ["🎮"]))
            channel_name = config["custom_format"].format(emoji=emoji)
            logger.info(f"Using cached format for category {category_id}: {channel_name}")
        else:
            # Check if this is a git category
            git_categories = (
                self.bot.config.get("default_user_limits", {}).get("git_categories", {}).get("categories", [])
            )
            if category_id in git_categories:
                channel_name = f"- {channel_name}"
                logger.info(f"Added dash prefix for git category: {channel_name}")

        # Get default permission overwrites
        permission_overwrites = self.permission_manager.get_default_permission_overwrites(self.guild, member)

        # Use cached user limit
        user_limit = config["user_limit"]

        # Check if this is a clean permissions category (cached)
        is_clean_perms = config["is_clean_perms"]
        if is_clean_perms:
            permission_overwrites[self.guild.default_role] = self.permission_manager._get_clean_everyone_permissions()
            logger.info(f"Set clean permissions for @everyone in category {category_id}")

        # Add permissions from database
        db_overwrites = await self.permission_manager.add_db_overwrites_to_permissions(
            self.guild, member.id, permission_overwrites, is_clean_perms=is_clean_perms
        )

        # Combine all overwrites
        if db_overwrites:
            for target, overwrite in db_overwrites.items():
                if target in permission_overwrites:
                    current = permission_overwrites[target]
                    for perm, value in overwrite._values.items():
                        if value is not None:
                            setattr(current, perm, value)
                else:
                    permission_overwrites[target] = overwrite

        # Wykorzystaj istniejący pusty kanał jeśli dostępny
        if empty_channels:
            self.metrics["channels_reused"] += 1
            existing_channel = empty_channels[0]
            logger.info(f"Wykorzystuję istniejący pusty kanał: {existing_channel.name}")

            # Dodaj wszystkie uprawnienia do istniejącego kanału
            # Najpierw ustaw uprawnienia właściciela
            owner_permissions = permission_overwrites.get(member, None)
            if owner_permissions:
                await existing_channel.set_permissions(member, overwrite=owner_permissions)
                logger.info(f"Dodano uprawnienia właściciela dla {member.display_name}")

            # Następnie dodaj wszystkie inne uprawnienia z bazy danych
            for target, overwrite in permission_overwrites.items():
                if target != member and target != self.guild.default_role:
                    # Pomiń role wyciszające (już są na kanale) i @everyone (już jest ustawiony)
                    mute_role_ids = [role["id"] for role in self.bot.config["mute_roles"]]
                    if isinstance(target, discord.Role) and target.id in mute_role_ids:
                        continue

                    await existing_channel.set_permissions(target, overwrite=overwrite)
                    logger.info(f"Dodano uprawnienia z bazy danych dla {target}")

            # Dodaj uprawnienia z db_overwrites jeśli istnieją
            if db_overwrites:
                for target, overwrite in db_overwrites.items():
                    await existing_channel.set_permissions(target, overwrite=overwrite)
                    logger.info(f"Dodano dodatkowe uprawnienia z bazy danych dla {target}")

            # Przenieś członka do kanału
            await member.move_to(existing_channel)

            # Usuń z cache pustych kanałów
            self._empty_channels_cache[category_id].remove(existing_channel)

            # Wyślij informację o zajęciu kanału
            fake_ctx = FakeContext(self.bot, member.guild)
            try:
                logger.info(f"Sending channel creation info to existing channel {existing_channel.name}")
                await self.message_sender.send_channel_creation_info(fake_ctx, existing_channel)
                logger.info("Successfully sent channel creation info to existing channel")
            except Exception as e:
                logger.error(f"Failed to send channel creation info to existing channel: {e}", exc_info=True)
            return

        # Utwórz nowy kanał
        self.metrics["channels_created"] += 1
        new_channel = await self.guild.create_voice_channel(
            channel_name,
            category=category,
            bitrate=self.guild.bitrate_limit,
            user_limit=user_limit,
            overwrites=permission_overwrites,
        )
        logger.info(f"Created new channel: {channel_name} with limit={user_limit}")

        # Move member to the new channel
        await member.move_to(new_channel)

        # Send channel creation info
        fake_ctx = FakeContext(self.bot, member.guild)
        try:
            logger.info(f"Sending channel creation info to {new_channel.name}")
            await self.message_sender.send_channel_creation_info(fake_ctx, new_channel)
            logger.info("Successfully sent channel creation info")
        except Exception as e:
            logger.error(f"Failed to send channel creation info: {e}", exc_info=True)

    def cog_unload(self):
        """Cleanup when cog is unloaded"""
        if self.autokick_worker_task:
            self.autokick_worker_task.cancel()
            logger.info("Cancelled autokick worker task")

    async def handle_channel_leave(self, before):
        """
        Handle the deletion of a voice channel when all members leave.
        Ulepszona wersja z optymalizacjami.
        """
        # Nie usuwamy kanałów create ani AFK
        if before.channel.id in self.channels_create or before.channel.id == self.bot.config["channels_voice"]["afk"]:
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
                    if self.bot.config.get("default_user_limits", {}).get("public_categories", {}).get("categories", [])
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
                    user_limit = self.permission_manager._get_default_user_limit(before.channel.category.id)

                    # Zastosuj wszystkie zmiany jednym wywołaniem API
                    await before.channel.edit(overwrites=new_overwrites, user_limit=user_limit)

                    # Zakończ funkcję, nie usuwając kanału
                    return

            # W pozostałych przypadkach usuń kanał
            await before.channel.delete()


async def setup(bot: commands.Bot):
    """Setup Function"""
    await bot.add_cog(OnVoiceStateUpdateEvent(bot))
