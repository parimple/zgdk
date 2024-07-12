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

    @commands.hybrid_command(
        name="clear", description="Usuwa wiadomości użytkownika z ostatnich X godzin."
    )
    @commands.has_role("✪")
    @discord.app_commands.describe(
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
        user="Użytkownik, którego wiadomości mają być usunięte (opcjonalnie dla administratorów)",
    )
    async def clear_messages(
        self,
        ctx: commands.Context,
        hours: Optional[int] = 1,
        user: Optional[discord.User] = None,
    ):
        logger.info(f"clear_messages called with hours={hours}, user={user}")
        if not ctx.author.guild_permissions.administrator:
            hours = min(hours, 24)
            if not user:
                await ctx.send("Musisz podać użytkownika, którego wiadomości chcesz usunąć.")
                return

        target_id = None
        if user:
            target_id = user.id
            # Sprawdzenie czy user jest moderatorem lub administratorem
            member = ctx.guild.get_member(user.id)
            if member and (
                member.guild_permissions.manage_messages or member.guild_permissions.administrator
            ):
                await ctx.send("Nie możesz usuwać wiadomości moderatorów lub administratorów.")
                return
        elif not ctx.author.guild_permissions.administrator:
            await ctx.send("Musisz podać użytkownika, którego wiadomości chcesz usunąć.")
            return
        else:
            confirm = await self.confirm_action(
                ctx, "Czy na pewno chcesz usunąć wszystkie wiadomości na tym kanale?"
            )
            if not confirm:
                await ctx.send("Anulowano usuwanie wiadomości.")
                return

        await self._delete_messages(ctx, hours, target_id)

    @commands.hybrid_command(
        name="clearall",
        description="Usuwa wiadomości użytkownika z ostatnich X godzin na wszystkich kanałach.",
    )
    @commands.has_role("✪")
    @discord.app_commands.describe(
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
        user="Użytkownik, którego wiadomości mają być usunięte (opcjonalnie dla administratorów)",
    )
    async def clear_all_channels(
        self,
        ctx: commands.Context,
        hours: Optional[int] = 1,
        user: Optional[discord.User] = None,
    ):
        logger.info(f"clear_all_channels called with hours={hours}, user={user}")
        if not ctx.author.guild_permissions.administrator:
            hours = min(hours, 24)
            if not user:
                await ctx.send("Musisz podać użytkownika, którego wiadomości chcesz usunąć.")
                return

        target_id = user.id if user else None
        # Sprawdzenie czy user jest moderatorem lub administratorem
        member = ctx.guild.get_member(user.id) if user else None
        if member and (
            member.guild_permissions.manage_messages or member.guild_permissions.administrator
        ):
            await ctx.send("Nie możesz usuwać wiadomości moderatorów lub administratorów.")
            return
        elif not ctx.author.guild_permissions.administrator and not user:
            await ctx.send("Musisz podać użytkownika, którego wiadomości chcesz usunąć.")
            return
        else:
            confirm = await self.confirm_action(
                ctx, "Czy na pewno chcesz usunąć wszystkie wiadomości na wszystkich kanałach?"
            )
            if not confirm:
                await ctx.send("Anulowano usuwanie wiadomości.")
                return

        await self._delete_messages_all_channels(ctx, hours, target_id)

    @commands.hybrid_command(
        name="clearimg", description="Usuwa linki i obrazki użytkownika z ostatnich X godzin."
    )
    @commands.has_role("✪")
    @discord.app_commands.describe(
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
        user="Użytkownik, którego linki i obrazki mają być usunięte (opcjonalnie dla administratorów)",
    )
    async def clear_images(
        self,
        ctx: commands.Context,
        hours: Optional[int] = 1,
        user: Optional[discord.User] = None,
    ):
        logger.info(f"clear_images called with hours={hours}, user={user}")
        if not ctx.author.guild_permissions.administrator:
            hours = min(hours, 24)
            if not user:
                await ctx.send("Musisz podać użytkownika, którego obrazy i linki chcesz usunąć.")
                return

        target_id = user.id if user else None
        # Sprawdzenie czy user jest moderatorem lub administratorem
        member = ctx.guild.get_member(user.id) if user else None
        if member and (
            member.guild_permissions.manage_messages or member.guild_permissions.administrator
        ):
            await ctx.send("Nie możesz usuwać wiadomości moderatorów lub administratorów.")
            return
        elif not ctx.author.guild_permissions.administrator and not user:
            await ctx.send("Musisz podać użytkownika, którego obrazy i linki chcesz usunąć.")
            return
        else:
            confirm = await self.confirm_action(
                ctx, "Czy na pewno chcesz usunąć wszystkie obrazy i linki na tym kanale?"
            )
            if not confirm:
                await ctx.send("Anulowano usuwanie obrazów i linków.")
                return

        await self._delete_messages(ctx, hours, target_id, images_only=True)

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
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        logger.info(f"Time threshold set to {time_threshold}")

        def is_message_to_delete(message):
            if message.webhook_id:
                attachment_pattern = (
                    rf"discord-gg-zagadka_{target_id}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{6}}\.\d+\.\w+"
                )
                return any(
                    re.match(attachment_pattern, attachment.filename)
                    for attachment in message.attachments
                )

            if target_id is not None and message.author.id != target_id:
                return False

            if images_only:
                has_image = any(
                    attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif"))
                    for attachment in message.attachments
                )
                has_link = bool(
                    re.search(
                        r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+",
                        message.content,
                    )
                )
                return has_image or has_link

            return True

        total_deleted = 0
        status_message = await ctx.send("Rozpoczynam usuwanie wiadomości...")

        try:
            recent_threshold = datetime.now(timezone.utc) - timedelta(minutes=5)
            recent_deleted = await ctx.channel.purge(
                limit=100, check=is_message_to_delete, after=max(time_threshold, recent_threshold)
            )
            total_deleted += len(recent_deleted)
            logger.info(f"Deleted {total_deleted} recent messages")
            await status_message.edit(
                content=f"Usunięto {total_deleted} najnowszych wiadomości. Kontynuuję usuwanie starszych..."
            )

            if time_threshold < recent_threshold:
                older_deleted = await ctx.channel.purge(
                    limit=None,
                    check=is_message_to_delete,
                    before=recent_threshold,
                    after=time_threshold,
                )
                total_deleted += len(older_deleted)
                logger.info(f"Deleted {len(older_deleted)} older messages")

            await status_message.edit(
                content=f"Zakończono. Łącznie usunięto {total_deleted} wiadomości."
            )
        except discord.Forbidden:
            await status_message.edit(
                content="Nie mam uprawnień do usuwania wiadomości na tym kanale."
            )
        except discord.HTTPException as e:
            await status_message.edit(content=f"Wystąpił błąd podczas usuwania wiadomości: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in _delete_messages: {e}", exc_info=True)
            await status_message.edit(content=f"Wystąpił nieoczekiwany błąd: {e}")

    async def _delete_messages_all_channels(
        self, ctx: commands.Context, hours: int, target_id: Optional[int] = None
    ):
        logger.info(
            f"_delete_messages_all_channels called with hours={hours}, target_id={target_id}"
        )
        time_threshold = datetime.now(timezone.utc) - timedelta(hours=hours)
        total_deleted = 0
        status_message = await ctx.send("Rozpoczynam usuwanie wiadomości na wszystkich kanałach...")

        for channel in ctx.guild.text_channels:
            if not channel.permissions_for(ctx.guild.me).manage_messages:
                logger.info(f"Skipping channel {channel.id}: no manage messages permission")
                continue

            def is_message_to_delete(message):
                if message.webhook_id:
                    attachment_pattern = (
                        rf"discord-gg-zagadka_{target_id}_\d{{4}}-\d{{2}}-\d{{2}}_\d{{6}}\.\d+\.\w+"
                    )
                    return any(
                        re.match(attachment_pattern, attachment.filename)
                        for attachment in message.attachments
                    )
                return (
                    target_id is None or message.author.id == target_id
                ) and message.created_at >= time_threshold

            try:
                deleted = await channel.purge(limit=100, check=is_message_to_delete)
                total_deleted += len(deleted)
                logger.info(f"Deleted {len(deleted)} messages in channel {channel.id}")
                await status_message.edit(
                    content=f"Usunięto łącznie {total_deleted} wiadomości. Trwa sprawdzanie kolejnych kanałów..."
                )
            except discord.Forbidden:
                logger.error(f"Forbidden error while purging messages in channel {channel.id}")
                continue
            except discord.HTTPException as e:
                logger.error(f"HTTP exception while purging messages in channel {channel.id}: {e}")
                continue

        await status_message.edit(
            content=f"Zakończono. Usunięto łącznie {total_deleted} wiadomości ze wszystkich kanałów."
        )

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
