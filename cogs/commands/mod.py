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

    def has_mod_admin_perms():
        async def predicate(ctx):
            # Check if user has moderator or admin role
            has_mod_role = discord.utils.get(
                ctx.author.roles, id=ctx.bot.config["admin_roles"]["mod"]
            )
            has_admin_role = discord.utils.get(
                ctx.author.roles, id=ctx.bot.config["admin_roles"]["admin"]
            )
            return bool(has_mod_role or has_admin_role)

        return commands.check(predicate)

    @commands.hybrid_group(name="mute", description="Komendy związane z wyciszaniem użytkowników.")
    @has_mod_admin_perms()
    async def mute(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Użyj jednej z podkomend: nick")

    @mute.command(name="nick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę.")
    @discord.app_commands.describe(user="Użytkownik z niewłaściwym nickiem")
    async def mute_nick(self, ctx: commands.Context, user: discord.Member):
        """Handle inappropriate nickname by removing color roles and applying punishment."""
        await self.handle_bad_nickname_logic(ctx, user)

    @commands.hybrid_group(
        name="unmute", description="Komendy związane z odwyciszaniem użytkowników."
    )
    @has_mod_admin_perms()
    async def unmute(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send("Użyj jednej z podkomend: nick")

    @unmute.command(name="nick", description="Przywraca możliwość zmiany nicku użytkownikowi.")
    @discord.app_commands.describe(user="Użytkownik do odmutowania nicku")
    async def unmute_nick(self, ctx: commands.Context, user: discord.Member):
        """Handle unmuting nickname."""
        await self.handle_unmute_nickname_logic(ctx, user)

    @commands.command(
        name="mutenick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę."
    )
    @has_mod_admin_perms()
    async def mutenick_prefix(self, ctx: commands.Context, user: discord.Member):
        """Handle inappropriate nickname by removing color roles and applying punishment."""
        await self.handle_bad_nickname_logic(ctx, user)

    @commands.command(
        name="unmutenick", description="Przywraca możliwość zmiany nicku użytkownikowi."
    )
    @has_mod_admin_perms()
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

            await ctx.send(
                f"Nałożono karę na {user.mention}. "
                f"Aby odzyskać możliwość zmiany nicku, udaj się na <#{self.config['channels']['premium_info']}> "
                f"i zakup dowolną rangę premium."
            )

            # Wait 5 seconds before changing nickname
            await asyncio.sleep(5)
            try:
                await user.edit(nick="random", reason="Niewłaściwy nick")
            except discord.Forbidden:
                await ctx.send("Nie mogę zmienić nicku tego użytkownika.")
            except Exception as e:
                logger.error(f"Error changing nickname for user {user.id}: {e}")
                await ctx.send("Wystąpił błąd podczas zmiany nicku.")

        except Exception as e:
            logger.error(f"Error handling bad nickname for user {user.id}: {e}", exc_info=True)
            await ctx.send("Wystąpił błąd podczas nakładania kary.")

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

    @commands.hybrid_command(name="giveaway", description="Losuje użytkownika z wybranych ról.")
    @commands.has_role("✪")
    @discord.app_commands.describe(
        role1="Pierwsza rola do losowania (wymagana)",
        role2="Druga rola do losowania (opcjonalna)",
        role3="Trzecia rola do losowania (opcjonalna)",
        mode="Tryb sprawdzania ról: 'or' (dowolna z ról) lub 'and' (wszystkie role)",
    )
    async def giveaway(
        self,
        ctx: commands.Context,
        role1: str,
        role2: str = None,
        role3: str = None,
        mode: str = "and",
    ):
        """Losuje użytkownika z wybranych ról.

        Przykład użycia:
        ,giveaway "Nazwa Roli 1" "Nazwa Roli 2" "Nazwa Roli 3" or  # Losuje użytkownika z dowolną z tych ról
        ,giveaway "Nazwa Roli 1" "Nazwa Roli 2"                    # Losuje użytkownika z obiema rolami (domyślnie and)
        """
        # Sprawdź czy użytkownik ma rolę administratora
        if not discord.utils.get(ctx.author.roles, id=self.config["admin_roles"]["admin"]):
            await ctx.send("Ta komenda jest dostępna tylko dla administratorów.")
            return

        # Konwertuj nazwy ról na obiekty ról
        roles = []
        for role_name in [role1, role2, role3]:
            if role_name:
                # Dla slash command, role_name będzie już obiektem Role
                if isinstance(role_name, discord.Role):
                    roles.append(role_name)
                else:
                    # Dla wersji z prefixem, szukamy roli po nazwie
                    role = discord.utils.get(ctx.guild.roles, name=role_name)
                    if role:
                        roles.append(role)
                    else:
                        await ctx.send(f"Nie znaleziono roli o nazwie: {role_name}")
                        return

        # Sprawdź poprawność trybu
        mode = mode.lower()
        if mode not in ["or", "and"]:
            mode = "and"  # Domyślnie używamy AND jeśli podano nieprawidłowy tryb

        # Zbierz wszystkich członków serwera
        eligible_members = []
        for member in ctx.guild.members:
            if not member.bot:  # Pomijamy boty
                if mode == "or":
                    # Tryb OR - wystarczy mieć jedną z ról
                    if any(role in member.roles for role in roles):
                        eligible_members.append(member)
                else:
                    # Tryb AND - musi mieć wszystkie role
                    if all(role in member.roles for role in roles):
                        eligible_members.append(member)

        if not eligible_members:
            role_names = ", ".join(f"'{role.name}'" for role in roles)
            await ctx.send(
                f"Nie znaleziono żadnych użytkowników z wymaganymi rolami ({role_names}) "
                f"w trybie {mode.upper()}."
            )
            return

        # Wylosuj zwycięzcę
        winner = random.choice(eligible_members)

        # Przygotuj wiadomość z informacją o rolach (bez pingowania)
        role_info = " ".join(f"'{role.name}'" for role in roles)
        mode_info = "dowolnej z" if mode == "or" else "wszystkich"

        await ctx.send(
            f"🎉 Wylosowano zwycięzcę spośród użytkowników z {mode_info} ról: {role_info}\n"
            f"Zwycięzca: {winner.mention}\n"
            f"Liczba uprawnionych użytkowników: {len(eligible_members)}"
        )

    # Osobna wersja dla slash command
    @giveaway.app_command.error
    async def giveaway_app_command_error(
        self, interaction: discord.Interaction, error: app_commands.CommandInvokeError
    ):
        # Konwertuj parametry z discord.Role na str dla wersji z prefixem
        if isinstance(error.original, commands.CommandInvokeError):
            ctx = await self.bot.get_context(interaction)
            roles = []
            for param in interaction.namespace:
                if isinstance(param, discord.Role):
                    roles.append(param.name)
                else:
                    roles.append(param)
            await self.giveaway(ctx, *roles)


async def setup(bot):
    logging.basicConfig(level=logging.DEBUG)
    await bot.add_cog(ModCog(bot))
