import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)


class ModCog(commands.Cog):
    """Cog for moderation commands."""

    def __init__(self, bot):
        self.bot = bot

    async def get_target_user(
        self, ctx: commands.Context, user
    ) -> Optional[tuple[int, discord.Member]]:
        if user is None:
            return None, None

        if isinstance(user, (discord.User, discord.Member)):
            target_id = user.id
            target_member = ctx.guild.get_member(user.id)
        else:
            try:
                target_id = int(user)
                target_member = ctx.guild.get_member(target_id)
                if target_member is None:
                    target_member = await ctx.guild.fetch_member(target_id)
            except ValueError:
                await ctx.send("Nieprawidłowe ID użytkownika.")
                return None, None
            except discord.NotFound:
                await ctx.send("Nie znaleziono użytkownika o podanym ID na tym serwerze.")
                return None, None

        return target_id, target_member

    async def check_permissions(
        self, ctx: commands.Context, target_member: Optional[discord.Member]
    ) -> bool:
        if target_member and (
            target_member.guild_permissions.manage_messages
            or target_member.guild_permissions.administrator
        ):
            if not ctx.author.guild_permissions.administrator:
                await ctx.send("Nie możesz usuwać wiadomości moderatorów lub administratorów.")
                return False
        return True

    @commands.hybrid_command(
        name="clear", description="Usuwa wiadomości użytkownika z ostatnich X godzin."
    )
    @commands.has_role("✪")
    @discord.app_commands.describe(
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
        user="Użytkownik lub ID użytkownika, którego wiadomości mają być usunięte (opcjonalnie dla administratorów)",
    )
    async def clear_messages(
        self, ctx: commands.Context, hours: Optional[int] = 1, user: Optional[str] = None
    ):
        await self._clear_messages_base(ctx, hours, user, all_channels=False)

    @commands.hybrid_command(
        name="clearall",
        description="Usuwa wiadomości użytkownika z ostatnich X godzin na wszystkich kanałach.",
    )
    @commands.has_role("✪")
    @discord.app_commands.describe(
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
        user="Użytkownik lub ID użytkownika, którego wiadomości mają być usunięte (opcjonalnie dla administratorów)",
    )
    async def clear_all_channels(
        self, ctx: commands.Context, hours: Optional[int] = 1, user: Optional[str] = None
    ):
        await self._clear_messages_base(ctx, hours, user, all_channels=True)

    @commands.hybrid_command(
        name="clearimg", description="Usuwa linki i obrazki użytkownika z ostatnich X godzin."
    )
    @commands.has_role("✪")
    @discord.app_commands.describe(
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
        user="Użytkownik lub ID użytkownika, którego linki i obrazki mają być usunięte (opcjonalnie dla administratorów)",
    )
    async def clear_images(
        self, ctx: commands.Context, hours: Optional[int] = 1, user: Optional[str] = None
    ):
        await self._clear_messages_base(ctx, hours, user, all_channels=False, images_only=True)

    async def _clear_messages_base(
        self,
        ctx: commands.Context,
        hours: Optional[int] = 1,
        user: Optional[str] = None,
        all_channels: bool = False,
        images_only: bool = False,
    ):
        logger.info(
            f"clear_messages_base called with hours={hours}, user={user}, all_channels={all_channels}, images_only={images_only}"
        )

        if not ctx.author.guild_permissions.administrator:
            hours = min(hours, 24)
            if user is None:
                await ctx.send("Musisz podać użytkownika, którego wiadomości chcesz usunąć.")
                return

        target_id, target_member = await self.get_target_user(ctx, user)

        if user is not None and target_id is None:
            return  # Error message already sent in get_target_user

        if not await self.check_permissions(ctx, target_member):
            return

        if target_id is None and not ctx.author.guild_permissions.administrator:
            await ctx.send("Musisz podać użytkownika, którego wiadomości chcesz usunąć.")
            return

        if target_id is None:
            confirm_message = (
                "Czy na pewno chcesz usunąć wszystkie wiadomości"
                + (" na wszystkich kanałach" if all_channels else "")
                + "?"
            )
            confirm = await self.confirm_action(ctx, confirm_message)
            if not confirm:
                await ctx.send("Anulowano usuwanie wiadomości.")
                return

        if all_channels:
            deleted_count = await self._delete_messages_all_channels(
                ctx, hours, target_id, images_only
            )
        else:
            deleted_count = await self._delete_messages(ctx, hours, target_id, images_only)

        await ctx.send(
            f"Usunięto łącznie {deleted_count} wiadomości"
            + (" ze wszystkich kanałów" if all_channels else "")
            + "."
        )

    async def _delete_messages(
        self,
        ctx: commands.Context,
        hours: int,
        target_id: Optional[int] = None,
        images_only: bool = False,
    ):
        logger.info(
            f"_delete_messages called with hours={hours}, target_id={target_id}, images_only={images_only}"
        )
        time_threshold = ctx.message.created_at - timedelta(hours=hours)
        logger.info(f"Time threshold set to {time_threshold}")

        def is_message_to_delete(message):
            if message.id == ctx.message.id:
                return False
            if target_id is not None and message.author.id != target_id:
                return False
            if images_only:
                has_image = bool(message.attachments)
                has_link = bool(re.search(r"http[s]?://\S+", message.content))
                return has_image or has_link
            return True

        total_deleted = 0
        status_message = await ctx.send("Rozpoczynam usuwanie wiadomości...")

        try:
            # Najpierw usuwamy najnowsze wiadomości (ostatnie 100)
            deleted = await ctx.channel.purge(
                limit=100, check=is_message_to_delete, before=ctx.message, after=time_threshold
            )
            total_deleted += len(deleted)
            await status_message.edit(
                content=f"Szybko usunięto {total_deleted} najnowszych wiadomości. Kontynuuję usuwanie starszych..."
            )

            # Następnie usuwamy starsze wiadomości w tle
            async for message in ctx.channel.history(
                limit=None, before=ctx.message, after=time_threshold, oldest_first=False
            ):
                if is_message_to_delete(message):
                    try:
                        await message.delete()
                        total_deleted += 1
                        if total_deleted % 10 == 0:
                            await status_message.edit(
                                content=f"Usunięto łącznie {total_deleted} wiadomości. Kontynuuję usuwanie starszych..."
                            )
                    except discord.NotFound:
                        logger.warning(f"Message {message.id} not found, probably already deleted")
                    except discord.Forbidden:
                        logger.error(f"No permission to delete message {message.id}")
                    except Exception as e:
                        logger.error(f"Error deleting message {message.id}: {e}")

            await status_message.delete()
            await ctx.send(f"Zakończono. Usunięto łącznie {total_deleted} wiadomości.")
        except discord.Forbidden:
            await status_message.edit(
                content="Nie mam uprawnień do usuwania wiadomości na tym kanale."
            )
        except discord.HTTPException as e:
            await status_message.edit(content=f"Wystąpił błąd podczas usuwania wiadomości: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in _delete_messages: {e}", exc_info=True)
            await status_message.edit(content=f"Wystąpił nieoczekiwany błąd: {e}")

        return total_deleted

    async def _delete_messages_all_channels(
        self,
        ctx: commands.Context,
        hours: int,
        target_id: Optional[int] = None,
        images_only: bool = False,
    ):
        logger.info(
            f"_delete_messages_all_channels called with hours={hours}, target_id={target_id}, images_only={images_only}"
        )
        time_threshold = ctx.message.created_at - timedelta(hours=hours)
        total_deleted = 0
        status_message = await ctx.send("Rozpoczynam usuwanie wiadomości na wszystkich kanałach...")

        for channel in ctx.guild.text_channels:
            if not channel.permissions_for(ctx.guild.me).manage_messages:
                logger.info(f"Skipping channel {channel.id}: no manage messages permission")
                continue

            def is_message_to_delete(message):
                if message.created_at < time_threshold:
                    return False
                if target_id is not None and message.author.id != target_id:
                    return False
                if images_only:
                    has_image = bool(message.attachments)
                    has_link = bool(re.search(r"http[s]?://\S+", message.content))
                    return has_image or has_link
                return True

            try:
                # Najpierw usuwamy najnowsze wiadomości (ostatnie 100)
                deleted = await channel.purge(limit=100, check=is_message_to_delete)
                total_deleted += len(deleted)

                # Następnie usuwamy starsze wiadomości
                async for message in channel.history(
                    limit=None, after=time_threshold, oldest_first=False
                ):
                    if is_message_to_delete(message):
                        try:
                            await message.delete()
                            total_deleted += 1
                        except discord.NotFound:
                            logger.warning(
                                f"Message {message.id} not found in channel {channel.id}, probably already deleted"
                            )
                        except discord.Forbidden:
                            logger.error(
                                f"No permission to delete message {message.id} in channel {channel.id}"
                            )
                        except Exception as e:
                            logger.error(
                                f"Error deleting message {message.id} in channel {channel.id}: {e}"
                            )

                logger.info(f"Deleted {total_deleted} messages in channel {channel.id}")
                await status_message.edit(
                    content=f"Usunięto łącznie {total_deleted} wiadomości. Trwa sprawdzanie kolejnych kanałów..."
                )
            except discord.Forbidden:
                logger.error(f"Forbidden error while purging messages in channel {channel.id}")
                continue
            except discord.HTTPException as e:
                logger.error(f"HTTP exception while purging messages in channel {channel.id}: {e}")
                continue

        await status_message.delete()
        return total_deleted

    async def confirm_action(self, ctx: commands.Context, message: str):
        logger.info(f"Confirming action: {message}")
        view = discord.ui.View()
        view.add_item(
            discord.ui.Button(label="Tak", style=discord.ButtonStyle.danger, custom_id="confirm")
        )
        view.add_item(
            discord.ui.Button(label="Nie", style=discord.ButtonStyle.secondary, custom_id="cancel")
        )

        msg = await ctx.send(message, view=view)

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

    @commands.command()
    @commands.is_owner()
    async def modsync(self, ctx):
        logger.info("modsync command called")
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"Zsynchronizowano {len(synced)} komend ModCog.")
            logger.info(f"Synchronized {len(synced)} commands")
        except Exception as e:
            logger.error(f"Error during command synchronization: {e}", exc_info=True)
            await ctx.send(f"Wystąpił błąd podczas synchronizacji ModCog: {e}")


async def setup(bot):
    logging.basicConfig(level=logging.DEBUG)
    await bot.add_cog(ModCog(bot))
