"""Moduł do zarządzania usuwaniem wiadomości.

Moduł zawiera klasy i funkcje umożliwiające usuwanie wiadomości z kanałów Discord
według różnych kryteriów, takich jak autor, czas, czy zawartość wiadomości.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple, Union

import discord
from discord.ext import commands

from utils.message_sender import MessageSender

logger = logging.getLogger(__name__)


class MessageCleaner:
    """Zarządza usuwaniem wiadomości.

    Klasa odpowiedzialna za usuwanie wiadomości z kanałów Discord
    według różnych filtrów i kryteriów.
    """

    def __init__(self, bot):
        """Inicjalizuje czyszczenie wiadomości.

        :param bot: Instancja bota Discord.
        :type bot: discord.ext.commands.Bot
        """
        self.bot = bot
        self.config = bot.config
        self.message_sender = MessageSender()
        # ID bota, który obsługuje komendy avatara
        self.avatar_bot_id = 489377322042916885

    async def get_target_user(
        self, ctx: commands.Context, user
    ) -> Tuple[Optional[int], Optional[discord.Member]]:
        """Pobiera ID użytkownika i obiekt Member z podanego użytkownika."""
        if user is None:
            return None, None

        logger.info(f"Trying to get target user from: {user} (type: {type(user)})")

        if isinstance(user, (discord.User, discord.Member)):
            target_id = user.id
            target_member = ctx.guild.get_member(user.id)
            logger.info(f"User is discord.User/Member with ID: {target_id} and name: {user.name}")
        else:
            try:
                # Próbuj najpierw przekonwertować na int (jeśli to ID)
                try:
                    target_id = int(user)
                    logger.info(f"Converted input to target_id: {target_id}")
                
                    # Pobierz informacje o wszystkich członkach serwera dla debugowania
                    logger.info(f"Server has {len(ctx.guild.members)} members")
                    logger.info(f"Looking for member with ID: {target_id}")
                    
                    # Najpierw sprawdź, czy użytkownik jest w pamięci podręcznej
                    target_member = ctx.guild.get_member(target_id)
                    
                    if target_member is None:
                        logger.info(f"Member not found in cache, trying to fetch from API")
                        try:
                            target_member = await ctx.guild.fetch_member(target_id)
                            logger.info(f"Found member from API: {target_member.name} (ID: {target_member.id})")
                        except discord.NotFound:
                            logger.warning(f"Member with ID {target_id} not found in API")
                            
                            # Szukaj użytkownika po ID w wiadomościach kanału
                            logger.info(f"Trying to find messages from user with ID {target_id} in current channel")
                            found_messages = False
                            async for message in ctx.channel.history(limit=50):
                                if message.author.id == target_id:
                                    logger.info(f"Found message from user ID {target_id}: {message.author.name}")
                                    found_messages = True
                                    break
                            
                            if not found_messages:
                                logger.warning(f"No messages found from user ID {target_id} in current channel")
                    else:
                        logger.info(f"Found member in cache: {target_member.name} (ID: {target_member.id})")
                
                except ValueError:
                    # Jeśli to nie ID, spróbuj znaleźć użytkownika po nazwie lub części nazwy
                    logger.info(f"Input '{user}' is not a valid ID, trying to find by name")
                    
                    user_str = str(user).lower()
                    found_members = []
                    
                    for member in ctx.guild.members:
                        if (user_str in member.name.lower() or 
                            (member.nick and user_str in member.nick.lower())):
                            found_members.append(member)
                            logger.info(f"Found member by name: {member.name} (ID: {member.id})")
                    
                    if found_members:
                        target_member = found_members[0]  # Weź pierwszego znalezionego
                        target_id = target_member.id
                        logger.info(f"Using first found member: {target_member.name} (ID: {target_id})")
                        
                        if len(found_members) > 1:
                            await ctx.send(f"Znaleziono {len(found_members)} użytkowników pasujących do '{user}'. Używam: {target_member.name} (ID: {target_id})")
                    else:
                        logger.warning(f"No members found matching '{user}'")
                        await ctx.send(f"Nie znaleziono użytkownika pasującego do '{user}'.")
                        return None, None
            except Exception as e:
                logger.error(f"Error finding user: {e}", exc_info=True)
                await ctx.send(f"Błąd podczas wyszukiwania użytkownika: {e}")
                return None, None

        return target_id, target_member

    async def check_permissions(
        self, ctx: commands.Context, target_member: Optional[discord.Member]
    ) -> bool:
        """Sprawdza, czy użytkownik ma uprawnienia do usuwania wiadomości.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param target_member: Obiekt Member, którego wiadomości będą usuwane.
        :type target_member: Optional[discord.Member]
        :returns: Czy użytkownik ma uprawnienia.
        :rtype: bool
        """
        if target_member and (
            target_member.guild_permissions.manage_messages
            or target_member.guild_permissions.administrator
        ):
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("Nie możesz usuwać wiadomości moderatorów lub administratorów.")
                return False
        return True

    async def clear_messages(
        self,
        ctx: commands.Context,
        hours: int = 1,
        user: Optional[str] = None,
        all_channels: bool = False,
        images_only: bool = False,
    ):
        """Usuwa wiadomości z określonego czasu."""
        logger.info(
            f"clear_messages called with hours={hours}, user={user}, all_channels={all_channels}, images_only={images_only}"
        )

        # Konwertuj user na target_id
        target_id, target_member = await self.get_target_user(ctx, user)
        logger.info(f"Converted user {user} to target_id: {target_id}")

        # Jeśli podano usera ale nie znaleziono ID, zakończ
        if user is not None and target_id is None:
            return  # Error message already sent in get_target_user

        # Sprawdź uprawnienia
        if not await self.check_permissions(ctx, target_member):
            return

        # Jeśli nie podano ID i nie jest się adminem, wymagaj podania użytkownika
        if target_id is None and not ctx.author.guild_permissions.administrator:
            embed = discord.Embed(
                description="Musisz podać użytkownika, którego wiadomości chcesz usunąć.",
                color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.red(),
            )
            await ctx.send(embed=embed)
            return

        # Jeśli nie podano ID i jest się adminem, pytaj o potwierdzenie
        if target_id is None and ctx.author.guild_permissions.administrator:
            confirm_message = (
                "Czy na pewno chcesz usunąć wszystkie wiadomości"
                + (" na wszystkich kanałach" if all_channels else "")
                + "?"
            )
            confirm = await self.confirm_action(ctx, confirm_message)
            if not confirm:
                embed = discord.Embed(
                    description="Anulowano usuwanie wiadomości.",
                    color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.blue(),
                )
                await ctx.send(embed=embed)
                return

        # Usuń wiadomości - najpierw z bieżącego kanału, a dopiero potem z innych
        deleted_count = 0
        
        # Zawsze zaczynamy od kanału, w którym została wywołana komenda
        deleted_count = await self._delete_messages(ctx, hours, target_id, images_only)
        
        # Jeśli flagę all_channels jest True, to dodatkowo usuwamy z pozostałych kanałów
        if all_channels:
            all_channels_deleted = await self._delete_messages_all_channels(
                ctx, hours, target_id, images_only, exclude_channel=ctx.channel
            )
            deleted_count += all_channels_deleted

        # Wyślij potwierdzenie
        # Pobierz emoji proxy_bunny z konfiguracji
        proxy_bunny = self.config.get("emojis", {}).get(
            "proxy_bunny", "<a:bunnyProxy:1301144820349403157>"
        )
        # Pobierz ID kanału premium_info
        premium_info_id = self.config.get("channels", {}).get("premium_info", 960665316109713421)

        message = f"Usunięto łącznie {deleted_count} wiadomości{' ze wszystkich kanałów' if all_channels else ''}.\nWybierz swój {proxy_bunny} <#{premium_info_id}>"
        embed = discord.Embed(
            description=message,
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.green(),
        )
        await ctx.send(embed=embed)

    async def _delete_messages(
        self,
        ctx: commands.Context,
        hours: int,
        target_id: Optional[int] = None,
        images_only: bool = False,
    ) -> int:
        """Usuwa wiadomości na jednym kanale."""
        time_threshold = ctx.message.created_at - timedelta(hours=hours)
        logger.info(f"Deleting messages before {ctx.message.created_at} and after {time_threshold}")
        logger.info(f"images_only={images_only}, target_id={target_id}")

        def is_message_to_delete(message):
            # Skip command message
            if message.id == ctx.message.id:
                return False

            # Skip old messages
            if not is_bulk_delete and message.created_at < time_threshold:
                logger.info(f"Message too old, skipping: {message.created_at} < {time_threshold}")
                return False

            # Sprawdź czy wiadomość ma obrazki/linki jeśli images_only=True
            if images_only:
                has_image = bool(message.attachments)
                has_link = bool(re.search(r"http[s]?://\S+", message.content))
                has_embeds = bool(message.embeds)
                has_media = has_image or has_link or has_embeds

                logger.info(
                    f"Checking message ID {message.id} for media: has_image={has_image}, has_link={has_link}, has_embeds={has_embeds}"
                )

                if not has_media:
                    logger.info(f"Message {message.id} rejected - no media found")
                    return False

                logger.info(
                    f"Message {message.id} has media: {message.content if not has_image else '<with image>'}"
                )

                # Jeśli ma media i nie ma target_id, możemy zwrócić True
                if target_id is None:
                    logger.info(
                        f"Message {message.id} accepted - has media and no target_id specified"
                    )
                    return True

            # Jeśli dotarliśmy tutaj i mamy target_id, sprawdzamy czy wiadomość jest od tego użytkownika
            if target_id is not None:
                # Pobierzmy informację o użytkowniku, aby sprawdzić jego nazwę
                target_member = ctx.guild.get_member(target_id)
                target_name = target_member.name.lower() if target_member else None
                target_id_str = str(target_id)
                
                # Log każdą wiadomość do sprawdzenia
                logger.info(f"Checking message ID {message.id} from {message.author.name} ({message.author.id}) against target_id: {target_id}")
                logger.info(f"Message content: {message.content[:50]}{'...' if len(message.content) > 50 else ''}")
                
                # Sprawdź content wiadomości
                if target_id_str in message.content:
                    logger.info(f"Message {message.id} contains user ID in content")
                    return True
                
                # Sprawdź czy to wiadomość od użytkownika
                if message.author.id == target_id:
                    logger.info(f"Found message {message.id} from target user {target_id}")
                    # Jeśli images_only, weryfikujemy czy wiadomość ma media
                    if images_only:
                        has_media = (
                            bool(message.attachments)
                            or bool(re.search(r"http[s]?://\S+", message.content))
                            or bool(message.embeds)
                        )
                        logger.info(f"Target message {message.id} has media: {has_media}")
                        return has_media
                    return True

                # Check if message mentions target user
                if f"<@{target_id}>" in message.content or f"<@!{target_id}>" in message.content:
                    logger.info(f"Found message {message.id} mentioning target user {target_id}")
                    # Jeśli images_only, weryfikujemy czy wiadomość ma media
                    if images_only:
                        has_media = (
                            bool(message.attachments)
                            or bool(re.search(r"http[s]?://\S+", message.content))
                            or bool(message.embeds)
                        )
                        logger.info(f"Mention message {message.id} has media: {has_media}")
                        return has_media
                    return True

                # Sprawdź czy to wiadomość od bota avatara
                if message.author.id == self.avatar_bot_id:
                    logger.info(f"Checking avatar bot message {message.id}: {message.content}")

                    # Sprawdź czy wiadomość zawiera nazwę użytkownika (jeśli dostępna)
                    avatar_message_match = False
                    if target_name and message.content.lower().startswith(target_name.lower()):
                        logger.info(
                            f"Avatar bot message {message.id} matches username {target_name}"
                        )
                        avatar_message_match = True

                    # Sprawdź czy w wiadomości jest ID użytkownika (w URL lub tekście)
                    if target_id_str in message.content:
                        logger.info(
                            f"Avatar bot message {message.id} contains target ID {target_id}"
                        )
                        avatar_message_match = True

                    # Sprawdzamy czy to wiadomość z avatarem (druga linia zawiera "avatar url")
                    message_lines = message.content.split("\n")
                    if len(message_lines) > 1 and "avatar url" in message_lines[1].lower():
                        logger.info(f"Avatar bot message {message.id} contains 'avatar url'")
                        # To jest wiadomość od bota avatara, czyli odpowiedź na komendę .a
                        # Jeśli nazwa użytkownika jest pierwszą linią, prawdopodobnie to wiadomość dla tego użytkownika
                        if target_name:
                            logger.info(
                                f"Checking if first line '{message_lines[0].lower()}' matches target name '{target_name.lower()}'"
                            )
                            if message_lines[0].lower() == target_name.lower():
                                logger.info(
                                    f"Avatar bot message {message.id} first line matches target name {target_name}"
                                )
                                avatar_message_match = True

                    # Sprawdź czy embedy zawierają informacje o użytkowniku
                    if message.embeds:
                        for embed in message.embeds:
                            logger.info(
                                f"Checking embed: title={embed.title}, description={embed.description}"
                            )
                            if embed.title:
                                if target_name and target_name.lower() in embed.title.lower():
                                    logger.info(
                                        f"Avatar bot message {message.id} embed title contains target name {target_name}"
                                    )
                                    avatar_message_match = True
                                if target_id_str in embed.title:
                                    logger.info(
                                        f"Avatar bot message {message.id} embed title contains target ID {target_id_str}"
                                    )
                                    avatar_message_match = True

                    if avatar_message_match:
                        logger.info(f"Avatar bot message {message.id} matches target user!")
                        if images_only:
                            has_media = (
                                bool(message.attachments)
                                or bool(re.search(r"http[s]?://\S+", message.content))
                                or bool(message.embeds)
                            )
                            logger.info(f"Avatar bot message {message.id} has media: {has_media}")
                            return has_media
                        return True

                # Dla wiadomości webhooków, sprawdź czy zawierają ID użytkownika
                if message.webhook_id:
                    found_in_content = target_id_str in message.content
                    found_in_attachments = any(
                        target_id_str in attachment.url or target_id_str in attachment.filename
                        for attachment in message.attachments
                    )
                    found_in_webhook = target_id_str in str(message.author)

                    webhook_match = found_in_content or found_in_attachments or found_in_webhook
                    logger.info(
                        f"Webhook message {message.id} contains target ID {target_id}: {webhook_match}"
                    )
                    logger.info(f"  - found_in_content: {found_in_content}")
                    logger.info(f"  - found_in_attachments: {found_in_attachments}")
                    logger.info(f"  - found_in_webhook: {found_in_webhook}")
                    logger.info(f"  - webhook author: {message.author}")

                    if webhook_match:
                        logger.info(
                            f"Found webhook message {message.id} containing target ID {target_id}"
                        )
                        return True

                # Dodatkowe sprawdzenie dla powiązanych wiadomości po treści
                if target_name:
                    # Sprawdź czy wiadomość zawiera nazwę użytkownika
                    if target_name.lower() in message.content.lower():
                        logger.info(f"Message {message.id} contains username {target_name}")
                        return True
                    
                    # Sprawdź czy wiadomość jest odpowiedzią na wiadomość użytkownika
                    if message.reference and message.reference.resolved:
                        ref_msg = message.reference.resolved
                        if hasattr(ref_msg, 'author') and ref_msg.author.id == target_id:
                            logger.info(f"Message {message.id} is a reply to target user {target_id}")
                            return True

                logger.info(f"Message {message.id} rejected - not from target user {target_id}")
                return False

            # Jeśli nie ma target_id i images_only=False, zwracamy True
            result = not images_only
            logger.info(f"Message {message.id} accepted: {result}")
            return result

        total_deleted = 0
        user_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.blue()
        status_message = await ctx.send(
            embed=discord.Embed(description="Rozpoczynam usuwanie wiadomości...", color=user_color)
        )

        try:
            # First bulk delete - for the last 100 messages, ignore time limit
            is_bulk_delete = True
            deleted = await ctx.channel.purge(
                limit=100, check=is_message_to_delete, before=ctx.message
            )
            total_deleted += len(deleted)
            logger.info(f"Bulk deleted {len(deleted)} messages")

            await status_message.edit(
                embed=discord.Embed(
                    description=f"Szybko usunięto {total_deleted} najnowszych wiadomości. Kontynuuję usuwanie starszych...",
                    color=user_color,
                )
            )

            # Then delete older messages with time limit
            is_bulk_delete = False
            async for message in ctx.channel.history(
                limit=None, before=ctx.message, after=time_threshold, oldest_first=False
            ):
                if is_message_to_delete(message):
                    try:
                        await message.delete()
                        total_deleted += 1
                        if total_deleted % 10 == 0:
                            await status_message.edit(
                                embed=discord.Embed(
                                    description=f"Usunięto łącznie {total_deleted} wiadomości. Kontynuuję usuwanie starszych...",
                                    color=user_color,
                                )
                            )
                    except discord.NotFound:
                        logger.warning(f"Message {message.id} not found, probably already deleted")
                    except discord.Forbidden:
                        logger.error(f"No permission to delete message {message.id}")
                    except Exception as e:
                        logger.error(f"Error deleting message {message.id}: {e}")

            await status_message.delete()
            return total_deleted

        except discord.Forbidden:
            logger.error("No permission to delete messages in this channel")
            await status_message.edit(
                embed=discord.Embed(
                    description="Nie mam uprawnień do usuwania wiadomości na tym kanale.",
                    color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.red(),
                )
            )
            return total_deleted
        except discord.HTTPException as e:
            logger.error(f"HTTP error while deleting messages: {e}")
            await status_message.edit(
                embed=discord.Embed(
                    description=f"Wystąpił błąd podczas usuwania wiadomości: {e}",
                    color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.red(),
                )
            )
            return total_deleted
        except Exception as e:
            logger.error(f"Unexpected error in _delete_messages: {e}", exc_info=True)
            await status_message.edit(
                embed=discord.Embed(
                    description=f"Wystąpił nieoczekiwany błąd: {e}",
                    color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.red(),
                )
            )
            return total_deleted

    async def _delete_messages_all_channels(
        self,
        ctx: commands.Context,
        hours: int,
        target_id: Optional[int] = None,
        images_only: bool = False,
        exclude_channel: Optional[discord.TextChannel] = None,
    ) -> int:
        """Usuwa wiadomości na wszystkich kanałach."""
        time_threshold = ctx.message.created_at - timedelta(hours=hours)
        total_deleted = 0
        user_color = ctx.author.color if ctx.author.color.value != 0 else discord.Color.blue()
        status_message = await ctx.send(
            embed=discord.Embed(
                description="Rozpoczynam usuwanie wiadomości na pozostałych kanałach...",
                color=user_color,
            )
        )

        # Pobierz listę ID kategorii do pominięcia
        excluded_categories = self.config.get("excluded_categories", [
            1127590722015604766,  # Dodane domyślne ID kategorii do pominięcia
            960665312200626199,
            960665312376807530,
            960665315895836698,
            960665316109713423
        ])
        
        logger.info(f"Excluded categories: {excluded_categories}")

        for channel in ctx.guild.text_channels:
            # Pomijamy kanał, na którym wywołano komendę (jeśli podano)
            if exclude_channel and channel.id == exclude_channel.id:
                logger.info(f"Skipping current channel {channel.name} ({channel.id})")
                continue
                
            # Pomijamy kanały z wykluczonych kategorii
            if channel.category_id and channel.category_id in excluded_categories:
                logger.info(f"Skipping channel {channel.name} ({channel.id}) from excluded category {channel.category_id}")
                continue
                
            # Pomijamy kanały, do których nie mamy uprawnień
            if not channel.permissions_for(ctx.guild.me).manage_messages:
                logger.info(f"No permission to delete messages in channel {channel.name} ({channel.id})")
                continue

            logger.info(f"Processing channel {channel.name} ({channel.id})")

            def is_message_to_delete(message):
                # Skip messages older than threshold - but only for the second pass
                # In first pass (bulk delete) we check all recent 100 messages regardless of time
                if not is_bulk_delete and message.created_at < time_threshold:
                    return False

                # Sprawdź czy wiadomość ma obrazki/linki jeśli images_only=True
                if images_only:
                    has_image = bool(message.attachments)
                    has_link = bool(re.search(r"http[s]?://\S+", message.content))
                    has_embeds = bool(message.embeds)
                    has_media = has_image or has_link or has_embeds

                    if not has_media:
                        return False

                    # Jeśli ma media i nie ma target_id, możemy zwrócić True
                    if target_id is None:
                        return True

                # Jeśli dotarliśmy tutaj i mamy target_id, sprawdzamy czy wiadomość jest od tego użytkownika
                if target_id is not None:
                    target_id_str = str(target_id)
                    target_member = ctx.guild.get_member(target_id)
                    target_name = target_member.name.lower() if target_member else None
                    
                    # Log każdą wiadomość do sprawdzenia
                    logger.info(f"Checking message ID {message.id} from {message.author.name} ({message.author.id}) against target_id: {target_id}")
                    logger.info(f"Message content: {message.content[:50]}{'...' if len(message.content) > 50 else ''}")
                    
                    # Sprawdź content wiadomości
                    if target_id_str in message.content:
                        logger.info(f"Message {message.id} contains user ID in content")
                        return True

                    # Sprawdź zwykłe wiadomości (nie webhook)
                    if not message.webhook_id:
                        # Sprawdź czy wiadomość jest od tego użytkownika
                        if message.author.id == target_id:
                            logger.info(
                                f"Match: Message author ID {message.author.id} equals target ID {target_id}"
                            )
                            return True

                        # Sprawdź czy wiadomość zawiera wzmiankę o użytkowniku
                        if (
                            f"<@{target_id}>" in message.content
                            or f"<@!{target_id}>" in message.content
                        ):
                            logger.info(
                                f"Match: Message contains mention of target user {target_id}"
                            )
                            return True

                        # Sprawdź czy to wiadomość od bota sprawdzającego avatar
                        if message.author.id == self.avatar_bot_id:
                            logger.info(
                                f"Checking all-channels avatar bot message: {message.content}"
                            )

                            # Sprawdź czy wiadomość zawiera nazwę użytkownika (jeśli dostępna)
                            if target_name and message.content.lower().startswith(
                                target_name.lower()
                            ):
                                logger.info(
                                    f"Match: Avatar bot message contains target username {target_name}"
                                )
                                return True

                            # Sprawdź czy w wiadomości jest ID użytkownika
                            if target_id_str in message.content:
                                logger.info(
                                    f"Match: Avatar bot message contains target ID {target_id}"
                                )
                                return True

                            # Sprawdź treść wiadomości (zwykle ma format "nazwa użytkownika\navatar url || invite bot")
                            message_lines = message.content.split("\n")
                            if len(message_lines) > 1 and "avatar url" in message_lines[1].lower():
                                logger.info(f"Avatar bot message contains 'avatar url'")
                                if target_name:
                                    logger.info(
                                        f"Checking if first line '{message_lines[0].lower()}' matches target name '{target_name.lower()}'"
                                    )
                                    if message_lines[0].lower() == target_name.lower():
                                        logger.info(
                                            f"Avatar bot message first line matches target name {target_name}"
                                        )
                                        return True

                            # Sprawdź embedy
                            if message.embeds:
                                for embed in message.embeds:
                                    logger.info(
                                        f"Checking all-channels embed: title={embed.title}, description={embed.description}"
                                    )
                                    if embed.title:
                                        if (
                                            target_name
                                            and target_name.lower() in embed.title.lower()
                                        ):
                                            logger.info(
                                                f"Avatar bot message embed title contains target name {target_name}"
                                            )
                                            return True
                                        if target_id_str in embed.title:
                                            logger.info(
                                                f"Avatar bot message embed title contains target ID {target_id_str}"
                                            )
                                            return True
                        
                        # Dodatkowe sprawdzenie dla powiązanych wiadomości po treści
                        if target_name:
                            # Sprawdź czy wiadomość zawiera nazwę użytkownika
                            if target_name.lower() in message.content.lower():
                                logger.info(f"Message {message.id} contains username {target_name}")
                                return True
                            
                            # Sprawdź czy wiadomość jest odpowiedzią na wiadomość użytkownika
                            if message.reference and message.reference.resolved:
                                ref_msg = message.reference.resolved
                                if hasattr(ref_msg, 'author') and ref_msg.author.id == target_id:
                                    logger.info(f"Message {message.id} is a reply to target user {target_id}")
                                    return True

                        # If Drongale's message, log debug info
                        if "drongale" in message.author.name.lower():
                            logger.info(
                                f"Checking Drongale's message (ID: {message.author.id}, name: {message.author.name})"
                            )
                            logger.info(f"Message content: {message.content[:100]}...")
                            if target_id == 1347753042417684491:
                                logger.info("Target ID is for Drongale - this message should match!")
                                return True

                    # Check webhook messages and their content
                    else:
                        found_in_content = target_id_str in message.content
                        found_in_attachments = any(
                            target_id_str in attachment.url or target_id_str in attachment.filename
                            for attachment in message.attachments
                        )
                        found_in_webhook = target_id_str in str(message.author)

                        if found_in_content or found_in_attachments or found_in_webhook:
                            logger.info(f"Found webhook message containing target ID {target_id}")
                            return True
                        
                        return False

                # Jeśli nie ma target_id i images_only=False, zwracamy True
                return not images_only

            try:
                # First bulk delete the last 100 messages, ignore time
                is_bulk_delete = True
                deleted = await channel.purge(limit=100, check=is_message_to_delete)
                total_deleted += len(deleted)
                
                if len(deleted) > 0:
                    logger.info(f"Bulk deleted {len(deleted)} messages from {channel.name}")

                # Then delete older messages with time limit
                is_bulk_delete = False
                channel_deleted = 0
                async for message in channel.history(
                    limit=None, after=time_threshold, oldest_first=False
                ):
                    if is_message_to_delete(message):
                        try:
                            await message.delete()
                            total_deleted += 1
                            channel_deleted += 1
                        except discord.NotFound:
                            pass
                        except discord.Forbidden:
                            pass
                        except Exception as e:
                            logger.error(f"Error deleting message: {e}")
                            pass
                
                if channel_deleted > 0:
                    logger.info(f"Deleted {channel_deleted} older messages from {channel.name}")

                await status_message.edit(
                    embed=discord.Embed(
                        description=f"Usunięto łącznie {total_deleted} wiadomości. Trwa sprawdzanie kolejnych kanałów...",
                        color=user_color,
                    )
                )
            except discord.Forbidden:
                logger.warning(f"Forbidden to delete messages in {channel.name}")
                continue
            except discord.HTTPException as e:
                logger.error(f"HTTP error in {channel.name}: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error in {channel.name}: {e}", exc_info=True)
                continue

        await status_message.delete()
        return total_deleted

    async def confirm_action(self, ctx: commands.Context, message: str) -> bool:
        """Prosi użytkownika o potwierdzenie akcji za pomocą przycisków.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param message: Wiadomość z prośbą o potwierdzenie.
        :type message: str
        :returns: Czy akcja została potwierdzona.
        :rtype: bool
        """
        logger.info(f"Confirming action: {message}")

        embed = discord.Embed(
            title="Potwierdzenie",
            description=message,
            color=ctx.author.color if ctx.author.color.value != 0 else discord.Color.orange(),
        )

        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(label="Tak", style=discord.ButtonStyle.danger, custom_id="confirm")
        )
        view.add_item(
            discord.ui.Button(label="Nie", style=discord.ButtonStyle.secondary, custom_id="cancel")
        )

        msg = await ctx.send(embed=embed, view=view)

        try:
            interaction = await self.bot.wait_for(
                "interaction",
                check=lambda i: i.message.id == msg.id and i.user.id == ctx.author.id,
                timeout=30.0,
            )

            await msg.delete()
            result = interaction.data["custom_id"] == "confirm"
            logger.info(f"Action confirmed: {result}")
            return result
        except asyncio.TimeoutError:
            await msg.delete()
            logger.info("Action confirmation timed out")
            return False
