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
        self.message_sender = MessageSender(bot)

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
                target_id = int(user)
                logger.info(f"Converted input to target_id: {target_id}")

                # Pobierz i wypisz informacje o wszystkich członkach o podobnych nazwach
                guild_members = ctx.guild.members
                for member in guild_members:
                    if "drongale" in member.name.lower() or "1pow" in member.name.lower():
                        logger.info(f"Found similar member - Name: {member.name}, ID: {member.id}")

                target_member = ctx.guild.get_member(target_id)
                if target_member is None:
                    logger.info(f"Member not found in cache, trying to fetch from API")
                    try:
                        target_member = await ctx.guild.fetch_member(target_id)
                        logger.info(f"Found member from API: {target_member.name}")
                    except discord.NotFound:
                        logger.info(f"Member not found in API either, ID appears invalid")
                else:
                    logger.info(f"Found member in cache: {target_member.name}")
            except ValueError:
                logger.error(f"Invalid ID format: {user}")
                await ctx.send("Nieprawidłowe ID użytkownika.")
                return None, None
            except discord.NotFound:
                logger.error(f"User with ID {target_id} not found on the server")
                await ctx.send("Nie znaleziono użytkownika o podanym ID na tym serwerze.")
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
            await self.message_sender.send_error(ctx, "Musisz podać użytkownika, którego wiadomości chcesz usunąć.")
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
                await self.message_sender.send_info(ctx, "Anulowano usuwanie wiadomości.")
                return

        # Usuń wiadomości
        if all_channels:
            deleted_count = await self._delete_messages_all_channels(
                ctx, hours, target_id, images_only
            )
        else:
            deleted_count = await self._delete_messages(ctx, hours, target_id, images_only)

        # Wyślij potwierdzenie jako embed
        message = f"Usunięto łącznie {deleted_count} wiadomości{' ze wszystkich kanałów' if all_channels else ''}."
        await self.message_sender.send_success(ctx, message)

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

        def is_message_to_delete(message):
            # Skip command message
            if message.id == ctx.message.id:
                return False

            # Skip old messages
            if not is_bulk_delete and message.created_at < time_threshold:
                logger.info(f"Message too old, skipping: {message.created_at} < {time_threshold}")
                return False

            # Check if message is from target user
            if target_id is not None:
                if message.author.id == target_id:
                    logger.info(f"Found message from target user {target_id}")
                    return True
                    
                # Check if message mentions target user
                if f"<@{target_id}>" in message.content or f"<@!{target_id}>" in message.content:
                    logger.info(f"Found message mentioning target user {target_id}")
                    return True

                return False

            if images_only:
                has_image = bool(message.attachments)
                has_link = bool(re.search(r"http[s]?://\S+", message.content))
                return has_image or has_link
            return True

        total_deleted = 0
        status_message = await self.message_sender.send_info(ctx, "Rozpoczynam usuwanie wiadomości...")

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
                    color=discord.Color.blue()
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
                                    color=discord.Color.blue()
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
            await status_message.edit(embed=discord.Embed(
                description="Nie mam uprawnień do usuwania wiadomości na tym kanale.",
                color=discord.Color.red()
            ))
            return total_deleted
        except discord.HTTPException as e:
            logger.error(f"HTTP error while deleting messages: {e}")
            await status_message.edit(embed=discord.Embed(
                description=f"Wystąpił błąd podczas usuwania wiadomości: {e}",
                color=discord.Color.red()
            ))
            return total_deleted
        except Exception as e:
            logger.error(f"Unexpected error in _delete_messages: {e}", exc_info=True)
            await status_message.edit(embed=discord.Embed(
                description=f"Wystąpił nieoczekiwany błąd: {e}",
                color=discord.Color.red()
            ))
            return total_deleted
    
    async def _delete_messages_all_channels(
        self,
        ctx: commands.Context,
        hours: int,
        target_id: Optional[int] = None,
        images_only: bool = False,
    ) -> int:
        """Usuwa wiadomości na wszystkich kanałach."""
        time_threshold = ctx.message.created_at - timedelta(hours=hours)
        total_deleted = 0
        status_message = await self.message_sender.send_info(ctx, "Rozpoczynam usuwanie wiadomości na wszystkich kanałach...")

        for channel in ctx.guild.text_channels:
            if not channel.permissions_for(ctx.guild.me).manage_messages:
                continue

            def is_message_to_delete(message):
                # Skip messages older than threshold - but only for the second pass
                # In first pass (bulk delete) we check all recent 100 messages regardless of time
                if not is_bulk_delete and message.created_at < time_threshold:
                    return False

                if target_id is not None:
                    target_id_str = str(target_id)
                    target_member = ctx.guild.get_member(target_id)
                    target_name = target_member.name.lower() if target_member else None

                    # Sprawdź zwykłe wiadomości (nie webhook)
                    if not message.webhook_id:
                        # Sprawdź czy wiadomość jest od tego użytkownika
                        if message.author.id == target_id:
                            logger.info(f"Match: Message author ID {message.author.id} equals target ID {target_id}")
                            return True
                            
                        # Sprawdź czy wiadomość zawiera wzmiankę o użytkowniku
                        if f"<@{target_id}>" in message.content or f"<@!{target_id}>" in message.content:
                            logger.info(f"Match: Message contains mention of target user {target_id}")
                            return True

                        # Sprawdź czy to wiadomość od konkretnego bota
                        if (
                            message.author.id == 489377322042916885
                            and message.embeds
                            and target_name
                        ):
                            for embed in message.embeds:
                                if embed.title and target_name in embed.title.lower():
                                    logger.info(f"Match: Message from bot contains target user name {target_name}")
                                    return True
                        
                        # If Drongale's message, log debug info
                        if message.author.name.lower() == "drongale":
                            logger.info(f"No match: Drongale's message (ID: {message.author.id}) doesn't match target ID {target_id}")
                            
                        return False

                    # Check webhook messages and their content
                    else:
                        found_in_content = target_id_str in message.content
                        found_in_attachments = any(
                            target_id_str in attachment.url or target_id_str in attachment.filename
                            for attachment in message.attachments
                        )
                        found_in_webhook = target_id_str in str(message.author)

                        if not (found_in_content or found_in_attachments or found_in_webhook):
                            return False
                        return True

                if images_only:
                    has_image = bool(message.attachments)
                    has_link = bool(re.search(r"http[s]?://\S+", message.content))
                    return has_image or has_link
                return True

            try:
                # First bulk delete the last 100 messages, ignore time
                is_bulk_delete = True
                deleted = await channel.purge(limit=100, check=is_message_to_delete)
                total_deleted += len(deleted)

                # Then delete older messages with time limit
                is_bulk_delete = False
                async for message in channel.history(
                    limit=None, after=time_threshold, oldest_first=False
                ):
                    if is_message_to_delete(message):
                        try:
                            await message.delete()
                            total_deleted += 1
                        except discord.NotFound:
                            pass
                        except discord.Forbidden:
                            pass
                        except Exception as e:
                            pass

                await status_message.edit(
                    embed=discord.Embed(
                        description=f"Usunięto łącznie {total_deleted} wiadomości. Trwa sprawdzanie kolejnych kanałów...",
                        color=discord.Color.blue()
                    )
                )
            except discord.Forbidden:
                continue
            except discord.HTTPException:
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
            color=discord.Color.orange()
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
