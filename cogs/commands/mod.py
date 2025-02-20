import asyncio
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from datasources.queries import RoleQueries
from utils.permissions import is_admin, is_mod_or_admin, is_owner_or_admin

logger = logging.getLogger(__name__)


class ModCog(commands.Cog):
    """Cog for moderation commands."""

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config

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
    @is_mod_or_admin()
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
    @is_mod_or_admin()
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
    @is_mod_or_admin()
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
        time_threshold = ctx.message.created_at - timedelta(hours=hours)

        def is_message_to_delete(message):
            if message.id == ctx.message.id:
                return False

            if target_id is not None:
                target_id_str = str(target_id)
                target_member = ctx.guild.get_member(target_id)
                target_name = target_member.name.lower() if target_member else None

                # Check regular messages
                if not message.webhook_id:
                    if message.author.id != target_id:
                        # Check if it's the specific bot with embeds
                        if (
                            message.author.id == 489377322042916885
                            and message.embeds
                            and target_name
                        ):
                            for embed in message.embeds:
                                if embed.title and target_name in embed.title.lower():
                                    return True
                        return False
                    return True

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
        time_threshold = ctx.message.created_at - timedelta(hours=hours)
        total_deleted = 0
        status_message = await ctx.send("Rozpoczynam usuwanie wiadomości na wszystkich kanałach...")

        for channel in ctx.guild.text_channels:
            if not channel.permissions_for(ctx.guild.me).manage_messages:
                continue

            def is_message_to_delete(message):
                if message.created_at < time_threshold:
                    return False
                if target_id is not None:
                    target_id_str = str(target_id)
                    target_member = ctx.guild.get_member(target_id)
                    target_name = target_member.name.lower() if target_member else None

                    # Check regular messages
                    if not message.webhook_id:
                        if message.author.id != target_id:
                            # Check if it's the specific bot with embeds
                            if (
                                message.author.id == 489377322042916885
                                and message.embeds
                                and target_name
                            ):
                                for embed in message.embeds:
                                    if embed.title and target_name in embed.title.lower():
                                        return True
                            return False
                        return True

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
                            pass
                        except discord.Forbidden:
                            pass
                        except Exception as e:
                            pass

                await status_message.edit(
                    content=f"Usunięto łącznie {total_deleted} wiadomości. Trwa sprawdzanie kolejnych kanałów..."
                )
            except discord.Forbidden:
                continue
            except discord.HTTPException:
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
    @is_owner_or_admin()
    async def modsync(self, ctx):
        logger.info("modsync command called")
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"Zsynchronizowano {len(synced)} komend ModCog.")
            logger.info(f"Synchronized {len(synced)} commands")
        except Exception as e:
            logger.error(f"Error during command synchronization: {e}", exc_info=True)
            await ctx.send(f"Wystąpił błąd podczas synchronizacji ModCog: {e}")

    @commands.hybrid_group(name="mute", description="Komendy związane z wyciszaniem użytkowników.")
    @is_mod_or_admin()
    async def mute(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Użyj jednej z podkomend: nick")

    @mute.command(name="nick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik z niewłaściwym nickiem")
    async def mute_nick(self, ctx: commands.Context, user: discord.Member):
        """Handle inappropriate nickname by removing color roles and applying punishment."""
        await self.handle_bad_nickname_logic(ctx, user)

    @commands.hybrid_group(
        name="unmute", description="Komendy związane z odwyciszaniem użytkowników."
    )
    @is_mod_or_admin()
    async def unmute(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Użyj jednej z podkomend: nick")

    @unmute.command(name="nick", description="Przywraca możliwość zmiany nicku użytkownikowi.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odmutowania nicku")
    async def unmute_nick(self, ctx: commands.Context, user: discord.Member):
        """Handle unmuting nickname."""
        await self.handle_unmute_nickname_logic(ctx, user)

    @commands.command(
        name="mutenick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę."
    )
    @is_mod_or_admin()
    async def mutenick_prefix(self, ctx: commands.Context, user: discord.Member):
        """Handle inappropriate nickname by removing color roles and applying punishment."""
        await self.handle_bad_nickname_logic(ctx, user)

    @commands.command(
        name="unmutenick", description="Przywraca możliwość zmiany nicku użytkownikowi."
    )
    @is_mod_or_admin()
    async def unmutenick_prefix(self, ctx: commands.Context, user: discord.Member):
        """Handle unmuting nickname."""
        await self.handle_unmute_nickname_logic(ctx, user)

    async def handle_bad_nickname_logic(self, ctx: commands.Context, user: discord.Member):
        """Common logic for handling inappropriate nicknames."""
        try:
            # Check if target is a moderator or admin
            has_mod_role = discord.utils.get(user.roles, id=self.config["admin_roles"]["mod"])
            has_admin_role = discord.utils.get(user.roles, id=self.config["admin_roles"]["admin"])

            # Only admins can mute mods, and nobody can mute admins
            if has_admin_role:
                await ctx.send("Nie możesz zmienić nicku administratorowi.")
                return

            if has_mod_role and not discord.utils.get(
                ctx.author.roles, id=self.config["admin_roles"]["admin"]
            ):
                await ctx.send("Tylko administrator może zmienić nick moderatorowi.")
                return

            # Remove color roles if present
            color_roles = [
                discord.Object(id=role_id) for role_id in self.config["color_roles"].values()
            ]
            await user.remove_roles(*color_roles, reason="Niewłaściwy nick")

            # Add mute role
            mute_role = discord.Object(id=self.config["mute_roles"][2]["id"])  # ☢︎ role
            await user.add_roles(mute_role, reason="Niewłaściwy nick")

            # Save punishment in database
            async with self.bot.get_db() as session:
                # Check if there's an existing mute
                existing_role = await RoleQueries.get_member_role(
                    session, user.id, self.config["mute_roles"][2]["id"]
                )

                new_duration = timedelta(days=30)
                if existing_role and existing_role.expiration_date:
                    time_left = existing_role.expiration_date - datetime.now(timezone.utc)
                    if time_left > new_duration:
                        # Keep the existing longer duration
                        new_duration = time_left

                await RoleQueries.add_or_update_role_to_member(
                    session, user.id, self.config["mute_roles"][2]["id"], duration=new_duration
                )
                await session.commit()

            await ctx.reply(
                f"Nałożono karę na {user.mention}. "
                f"Aby odzyskać możliwość zmiany nicku, udaj się na <#{self.config['channels']['premium_info']}> "
                f"i zakup dowolną rangę premium."
            )

            # Wait 5 seconds before changing nickname
            await asyncio.sleep(5)
            try:
                await user.edit(nick="random", reason="Niewłaściwy nick")
            except discord.Forbidden:
                await ctx.reply("Nie mogę zmienić nicku tego użytkownika.")
            except Exception as e:
                logger.error(f"Error changing nickname for user {user.id}: {e}")
                await ctx.reply("Wystąpił błąd podczas zmiany nicku.")

        except Exception as e:
            logger.error(f"Error handling bad nickname for user {user.id}: {e}", exc_info=True)
            await ctx.reply("Wystąpił błąd podczas nakładania kary.")

    async def handle_unmute_nickname_logic(self, ctx: commands.Context, user: discord.Member):
        """Common logic for handling nickname unmuting."""
        try:
            # Check if target is a moderator or admin
            has_mod_role = discord.utils.get(user.roles, id=self.config["admin_roles"]["mod"])
            has_admin_role = discord.utils.get(user.roles, id=self.config["admin_roles"]["admin"])

            # Only admins can unmute mods, and nobody can unmute admins
            if has_admin_role:
                await ctx.send("Nie możesz zarządzać nickiem administratora.")
                return

            if has_mod_role and not discord.utils.get(
                ctx.author.roles, id=self.config["admin_roles"]["admin"]
            ):
                await ctx.send("Tylko administrator może zarządzać nickiem moderatora.")
                return

            # Remove mute role
            mute_role = discord.Object(id=self.config["mute_roles"][2]["id"])  # ☢︎ role
            await user.remove_roles(mute_role, reason="Przywrócenie możliwości zmiany nicku")

            # Remove role from database
            async with self.bot.get_db() as session:
                await RoleQueries.delete_member_role(
                    session, user.id, self.config["mute_roles"][2]["id"]
                )
                await session.commit()

            await ctx.send(f"Przywrócono możliwość zmiany nicku dla {user.mention}.")

        except Exception as e:
            logger.error(f"Error handling nickname unmute for user {user.id}: {e}", exc_info=True)
            await ctx.send("Wystąpił błąd podczas odmutowywania nicku.")


async def setup(bot):
    logging.basicConfig(level=logging.DEBUG)
    await bot.add_cog(ModCog(bot))
