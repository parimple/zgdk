import asyncio
import logging
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Union

import discord
from discord import app_commands
from discord.ext import commands

from datasources.queries import MemberQueries, RoleQueries
from utils.message_sender import MessageSender
from utils.permissions import is_admin, is_mod_or_admin, is_owner_or_admin

logger = logging.getLogger(__name__)


class MuteType:
    """Definicje typów wyciszeń."""

    NICK = "nick"
    IMG = "img"
    TXT = "txt"
    LIVE = "live"
    RANK = "rank"

    @staticmethod
    def get_config():
        """Zwraca konfigurację dla wszystkich typów wyciszeń."""
        return {
            MuteType.NICK: {
                "role_index": 2,  # ☢︎ role (attach_files_off)
                "role_id_field": "id",
                "display_name": "nicku",
                "action_name": "zmiany nicku",
                "reason_add": "Niewłaściwy nick",
                "reason_remove": "Przywrócenie możliwości zmiany nicku",
                "success_message_add": "Nałożono karę na {user_mention}. Aby odzyskać możliwość zmiany nicku, udaj się na <#{premium_channel}> i zakup dowolną rangę premium.",
                "success_message_remove": "Przywrócono możliwość {action_name} dla {user_mention}.",
                "default_duration": timedelta(days=30),
                "supports_duration": False,
                "special_actions": ["change_nickname"],
            },
            MuteType.IMG: {
                "role_index": 2,  # ☢︎ role (attach_files_off)
                "role_id_field": "id",
                "display_name": "obrazków i linków",
                "action_name": "wysyłania obrazków i linków",
                "reason_add": "Blokada wysyłania obrazków i linków",
                "reason_remove": "Przywrócenie możliwości wysyłania obrazków",
                "success_message_add": "Zablokowano możliwość {action_name} dla {user_mention} na {duration_text}.",
                "success_message_remove": "Przywrócono możliwość {action_name} dla {user_mention}.",
                "default_duration": None,  # Domyślnie permanentny
                "supports_duration": True,
                "special_actions": [],
            },
            MuteType.TXT: {
                "role_index": 1,  # ⌀ role (send_messages_off)
                "role_id_field": "id",
                "display_name": "wiadomości",
                "action_name": "wysyłania wiadomości",
                "reason_add": "Blokada wysyłania wiadomości",
                "reason_remove": "Przywrócenie możliwości wysyłania wiadomości",
                "success_message_add": "Zablokowano możliwość {action_name} dla {user_mention} na {duration_text}.",
                "success_message_remove": "Przywrócono możliwość {action_name} dla {user_mention}.",
                "default_duration": timedelta(hours=2),
                "supports_duration": True,
                "special_actions": [],
            },
            MuteType.LIVE: {
                "role_index": 0,  # ⚠︎ role (stream_off)
                "role_id_field": "id",
                "display_name": "streama",
                "action_name": "streamowania",
                "reason_add": "Blokada streamowania",
                "reason_remove": "Przywrócenie możliwości streamowania",
                "success_message_add": "Zablokowano możliwość {action_name} dla {user_mention} na stałe.",
                "success_message_remove": "Przywrócono możliwość {action_name} dla {user_mention}.",
                "default_duration": None,
                "supports_duration": False,  # Zawsze na stałe
                "special_actions": ["move_to_afk_and_back"],
            },
            MuteType.RANK: {
                "role_index": 3,  # ♺ role (points_off)
                "role_id_field": "id",
                "display_name": "rankingu",
                "action_name": "zdobywania punktów rankingowych",
                "reason_add": "Blokada zdobywania punktów",
                "reason_remove": "Przywrócenie możliwości zdobywania punktów",
                "success_message_add": "Zablokowano możliwość {action_name} dla {user_mention} na stałe.",
                "success_message_remove": "Przywrócono możliwość {action_name} dla {user_mention}.",
                "default_duration": None,
                "supports_duration": False,  # Zawsze na stałe
                "special_actions": [],
            },
        }


class ModCog(commands.Cog):
    """Cog for moderation commands."""

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.message_sender = MessageSender(bot)

    # Nowa metoda pomocnicza do wyświetlania pomocy dla komend
    async def send_subcommand_help(self, ctx, command_name):
        """Wyświetla pomoc dla komend grupowych z informacją o premium.

        :param ctx: Kontekst komendy
        :param command_name: Nazwa komendy (używana w logach)
        """
        base_text = "Użyj jednej z podkomend: nick, img, txt, live, rank"

        # Dodaj informację o premium
        _, premium_text = MessageSender._get_premium_text(ctx)
        if premium_text:
            base_text = f"{base_text}\n{premium_text}"

        embed = MessageSender._create_embed(description=base_text, ctx=ctx)
        await MessageSender._send_embed(ctx, embed, reply=True)
        logger.debug(f"Sent subcommand help for {command_name}")

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
    @discord.app_commands.describe(
        user="Użytkownik do wyciszenia (opcjonalnie, działa jak mute txt)"
    )
    async def mute(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Komendy związane z wyciszaniem użytkowników.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do wyciszenia (opcjonalnie, działa jak mute txt)
        """
        if ctx.invoked_subcommand is None:
            if user is not None:
                # Jeśli podano użytkownika, ale nie podkomendę, działa jak 'mute txt'
                await self.mute_txt(ctx, user)
            else:
                # Użyj wspólnej metody do wyświetlania pomocy
                await self.send_subcommand_help(ctx, "mute")

    @mute.command(name="nick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik z niewłaściwym nickiem")
    async def mute_nick(self, ctx: commands.Context, user: discord.Member):
        """Usuwa niewłaściwy nick użytkownika i nadaje karę."""
        await self.handle_mute_logic(ctx, user, MuteType.NICK)

    @mute.command(name="img", description="Blokuje możliwość wysyłania obrazków i linków.")
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość wysyłania obrazków",
        duration="Czas trwania blokady, np. 1h, 30m, 1d (puste = blokada stała)",
    )
    async def mute_img(self, ctx: commands.Context, user: discord.Member, duration: str = ""):
        """Blokuje możliwość wysyłania obrazków i linków.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do zablokowania
        :param duration: Czas trwania blokady (opcjonalnie)
        """
        parsed_duration = self.parse_duration(duration)
        await self.handle_mute_logic(ctx, user, MuteType.IMG, parsed_duration)

    @mute.command(name="txt", description="Blokuje możliwość wysyłania wiadomości.")
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość wysyłania wiadomości",
        duration="Czas trwania blokady, np. 1h, 30m, 1d (puste = blokada stała)",
    )
    async def mute_txt(self, ctx: commands.Context, user: discord.Member, duration: str = ""):
        """Blokuje możliwość wysyłania wiadomości.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do zablokowania
        :param duration: Czas trwania blokady (opcjonalnie)
        """
        parsed_duration = self.parse_duration(duration)
        await self.handle_mute_logic(ctx, user, MuteType.TXT, parsed_duration)

    @mute.command(name="live", description="Blokuje możliwość streamowania.")
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość streamowania"
    )
    async def mute_live(self, ctx: commands.Context, user: discord.Member):
        """Blokuje możliwość streamowania.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do zablokowania
        """
        await self.handle_mute_logic(ctx, user, MuteType.LIVE)

    @mute.command(name="rank", description="Blokuje możliwość zdobywania punktów rankingowych.")
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość zdobywania punktów"
    )
    async def mute_rank(self, ctx: commands.Context, user: discord.Member):
        """Blokuje możliwość zdobywania punktów rankingowych.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do zablokowania
        """
        await self.handle_mute_logic(ctx, user, MuteType.RANK)

    @commands.hybrid_group(
        name="unmute", description="Komendy związane z odwyciszaniem użytkowników."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik do odwyciszenia (opcjonalnie, działa jak unmute txt)"
    )
    async def unmute(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Komendy związane z odwyciszaniem użytkowników.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odwyciszenia (opcjonalnie, działa jak unmute txt)
        """
        if ctx.invoked_subcommand is None:
            if user is not None:
                # Jeśli podano użytkownika, ale nie podkomendę, działa jak 'unmute txt'
                await self.unmute_txt(ctx, user)
            else:
                # Użyj wspólnej metody do wyświetlania pomocy
                await self.send_subcommand_help(ctx, "unmute")

    @unmute.command(name="nick", description="Przywraca możliwość zmiany nicku użytkownikowi.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odmutowania nicku")
    async def unmute_nick(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość zmiany nicku użytkownikowi.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.handle_mute_logic(ctx, user, MuteType.NICK, unmute=True)

    @unmute.command(name="img", description="Przywraca możliwość wysyłania obrazków i linków.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odblokowania wysyłania obrazków")
    async def unmute_img(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość wysyłania obrazków i linków.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.handle_mute_logic(ctx, user, MuteType.IMG, unmute=True)

    @unmute.command(name="txt", description="Przywraca możliwość wysyłania wiadomości.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odblokowania wysyłania wiadomości")
    async def unmute_txt(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość wysyłania wiadomości.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.handle_mute_logic(ctx, user, MuteType.TXT, unmute=True)

    @unmute.command(name="live", description="Przywraca możliwość streamowania.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odblokowania streamowania")
    async def unmute_live(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość streamowania.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.handle_mute_logic(ctx, user, MuteType.LIVE, unmute=True)

    @unmute.command(name="rank", description="Przywraca możliwość zdobywania punktów rankingowych.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odblokowania zdobywania punktów")
    async def unmute_rank(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość zdobywania punktów rankingowych.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.handle_mute_logic(ctx, user, MuteType.RANK, unmute=True)

    @commands.command(
        name="mutenick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę."
    )
    @is_mod_or_admin()
    async def mutenick_prefix(self, ctx: commands.Context, user: discord.Member):
        """Usuwa niewłaściwy nick użytkownika i nadaje karę (wersja prefiksowa)."""
        await self.handle_mute_logic(ctx, user, MuteType.NICK)

    @commands.command(
        name="unmutenick", description="Przywraca możliwość zmiany nicku użytkownikowi."
    )
    @is_mod_or_admin()
    async def unmutenick_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość zmiany nicku użytkownikowi (wersja prefiksowa)."""
        await self.handle_mute_logic(ctx, user, MuteType.NICK, unmute=True)

    @commands.command(name="muteimg", description="Blokuje możliwość wysyłania obrazków i linków.")
    @is_mod_or_admin()
    async def muteimg_prefix(self, ctx: commands.Context, user: discord.Member, duration: str = ""):
        """Blokuje możliwość wysyłania obrazków i linków (wersja prefiksowa)."""
        parsed_duration = self.parse_duration(duration)
        await self.handle_mute_logic(ctx, user, MuteType.IMG, parsed_duration)

    @commands.command(
        name="unmuteimg", description="Przywraca możliwość wysyłania obrazków i linków."
    )
    @is_mod_or_admin()
    async def unmuteimg_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość wysyłania obrazków i linków (wersja prefiksowa)."""
        await self.handle_mute_logic(ctx, user, MuteType.IMG, unmute=True)

    @commands.command(name="mutetxt", description="Blokuje możliwość wysyłania wiadomości.")
    @is_mod_or_admin()
    async def mutetxt_prefix(self, ctx: commands.Context, user: discord.Member, duration: str = ""):
        """Blokuje możliwość wysyłania wiadomości (wersja prefiksowa)."""
        parsed_duration = self.parse_duration(duration)
        await self.handle_mute_logic(ctx, user, MuteType.TXT, parsed_duration)

    @commands.command(name="unmutetxt", description="Przywraca możliwość wysyłania wiadomości.")
    @is_mod_or_admin()
    async def unmutetxt_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość wysyłania wiadomości (wersja prefiksowa)."""
        await self.handle_mute_logic(ctx, user, MuteType.TXT, unmute=True)

    @commands.command(name="mutelive", description="Blokuje możliwość streamowania.")
    @is_mod_or_admin()
    async def mutelive_prefix(self, ctx: commands.Context, user: discord.Member):
        """Blokuje możliwość streamowania (wersja prefiksowa)."""
        await self.handle_mute_logic(ctx, user, MuteType.LIVE)

    @commands.command(name="unmutelive", description="Przywraca możliwość streamowania.")
    @is_mod_or_admin()
    async def unmutelive_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość streamowania (wersja prefiksowa)."""
        await self.handle_mute_logic(ctx, user, MuteType.LIVE, unmute=True)

    @commands.command(
        name="muterank", description="Blokuje możliwość zdobywania punktów rankingowych."
    )
    @is_mod_or_admin()
    async def muterank_prefix(self, ctx: commands.Context, user: discord.Member):
        """Blokuje możliwość zdobywania punktów rankingowych (wersja prefiksowa)."""
        await self.handle_mute_logic(ctx, user, MuteType.RANK)

    @commands.command(
        name="unmuterank", description="Przywraca możliwość zdobywania punktów rankingowych."
    )
    @is_mod_or_admin()
    async def unmuterank_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość zdobywania punktów rankingowych (wersja prefiksowa)."""
        await self.handle_mute_logic(ctx, user, MuteType.RANK, unmute=True)

    async def handle_mute_logic(
        self,
        ctx: commands.Context,
        user: discord.Member,
        mute_type: str,
        duration: Optional[timedelta] = None,
        unmute: bool = False,
    ):
        """Wspólna logika do obsługi różnych typów wyciszeń.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do wyciszenia/odciszenia
        :param mute_type: Typ wyciszenia (z MuteType)
        :param duration: Czas trwania wyciszenia (None dla permanentnego)
        :param unmute: Czy to jest operacja odciszenia
        """
        try:
            # Pobierz konfigurację dla tego typu wyciszenia
            mute_configs = MuteType.get_config()
            if mute_type not in mute_configs:
                await ctx.send(f"Nieznany typ wyciszenia: {mute_type}")
                return

            config = mute_configs[mute_type]

            # Check if target is a moderator or admin
            has_mod_role = discord.utils.get(user.roles, id=self.config["admin_roles"]["mod"])
            has_admin_role = discord.utils.get(user.roles, id=self.config["admin_roles"]["admin"])

            # Only admins can mute mods, and nobody can mute admins
            if has_admin_role:
                action = "zarządzać" if unmute else "zablokować"
                await ctx.send(f"Nie możesz {action} uprawnień administratora.")
                return

            if has_mod_role and not discord.utils.get(
                ctx.author.roles, id=self.config["admin_roles"]["admin"]
            ):
                action = "zarządzać" if unmute else "zablokować"
                await ctx.send(f"Tylko administrator może {action} uprawnienia moderatora.")
                return

            # Get role ID based on config
            role_index = config["role_index"]
            mute_role_id = self.config["mute_roles"][role_index]["id"]
            mute_role = discord.Object(id=mute_role_id)

            if unmute:
                # Remove mute role
                await user.remove_roles(mute_role, reason=config["reason_remove"])

                # Remove role from database
                async with self.bot.get_db() as session:
                    # Upewnij się, że użytkownik istnieje w tabeli members
                    await MemberQueries.get_or_add_member(session, user.id)

                    await RoleQueries.delete_member_role(session, user.id, mute_role_id)
                    await session.commit()

                # Format success message
                message = config["success_message_remove"].format(
                    user_mention=user.mention,
                    action_name=config["action_name"],
                    premium_channel=self.config["channels"]["premium_info"],
                )
            else:
                # Apply mute

                # Remove color roles if present
                color_roles = [
                    discord.Object(id=role_id) for role_id in self.config["color_roles"].values()
                ]
                await user.remove_roles(*color_roles, reason=config["reason_add"])

                # Add mute role
                await user.add_roles(mute_role, reason=config["reason_add"])

                # Set default duration if not specified and the mute type supports it
                if duration is None and config["supports_duration"]:
                    duration = config["default_duration"]

                # Save punishment in database
                async with self.bot.get_db() as session:
                    # Upewnij się, że użytkownik istnieje w tabeli members
                    await MemberQueries.get_or_add_member(session, user.id)

                    # Check if there's an existing mute with longer duration
                    existing_role = await RoleQueries.get_member_role(
                        session, user.id, mute_role_id
                    )

                    if existing_role and existing_role.expiration_date and duration is not None:
                        time_left = existing_role.expiration_date - datetime.now(timezone.utc)
                        if time_left > duration:
                            # Keep the existing longer duration
                            message = f"Użytkownik {user.mention} posiada już dłuższą blokadę. Obecna kara wygaśnie za {time_left.days}d {time_left.seconds//3600}h {(time_left.seconds//60)%60}m."
                            await ctx.send(message)
                            return

                    await RoleQueries.add_or_update_role_to_member(
                        session, user.id, mute_role_id, duration=duration
                    )
                    await session.commit()

                # Format duration text
                if duration is None:
                    duration_text = "stałe"
                else:
                    # Format duration for user-friendly display
                    duration_text = ""
                    if duration.days > 0:
                        duration_text += f"{duration.days}d "
                    hours, remainder = divmod(duration.seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)
                    if hours > 0:
                        duration_text += f"{hours}h "
                    if minutes > 0:
                        duration_text += f"{minutes}m "
                    if seconds > 0 or not duration_text:
                        duration_text += f"{seconds}s"

                # Format success message
                message = config["success_message_add"].format(
                    user_mention=user.mention,
                    duration_text=duration_text,
                    action_name=config["action_name"],
                    premium_channel=self.config["channels"]["premium_info"],
                )

                # Execute special actions for this mute type
                if "change_nickname" in config["special_actions"]:
                    # Wait 5 seconds before changing nickname
                    await asyncio.sleep(5)
                    try:
                        await user.edit(nick="random", reason="Niewłaściwy nick")
                    except discord.Forbidden:
                        await ctx.reply("Nie mogę zmienić nicku tego użytkownika.")
                    except Exception as e:
                        logger.error(f"Error changing nickname for user {user.id}: {e}")
                        await ctx.reply("Wystąpił błąd podczas zmiany nicku.")

                # Check if user needs to be moved to AFK and back to force stream permission update
                if (
                    "move_to_afk_and_back" in config["special_actions"]
                    and user.voice
                    and user.voice.channel
                ):
                    try:
                        # Get the AFK channel ID from config
                        afk_channel_id = self.config["channels_voice"]["afk"]
                        afk_channel = self.bot.get_channel(afk_channel_id)

                        if afk_channel:
                            # Remember original channel
                            original_channel = user.voice.channel

                            # Move to AFK
                            await user.move_to(
                                afk_channel,
                                reason=f"Wymuszenie aktualizacji uprawnień {config['action_name']}",
                            )
                            logger.info(
                                f"Moved user {user.id} to AFK channel for stream permission update"
                            )

                            # Wait a moment for Discord to register the move
                            await asyncio.sleep(1)

                            # Move back to original channel
                            await user.move_to(
                                original_channel,
                                reason=f"Powrót po aktualizacji uprawnień {config['action_name']}",
                            )
                            logger.info(
                                f"Moved user {user.id} back to original channel {original_channel.id}"
                            )
                    except discord.Forbidden:
                        logger.warning(
                            f"No permission to move user {user.id} between voice channels"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error moving user {user.id} for stream permission update: {e}"
                        )

            # Add premium info to message
            _, premium_text = MessageSender._get_premium_text(ctx)
            if premium_text:
                message = f"{message}\n{premium_text}"

            # Send response
            if mute_type == MuteType.NICK and not unmute:
                # For nick mute, use reply instead of embed
                await ctx.reply(message)
            else:
                # For other mutes, use embed
                embed = discord.Embed(description=message, color=ctx.author.color)
                await ctx.reply(embed=embed)

        except Exception as e:
            action = "odblokowania" if unmute else "blokowania"
            logger.error(
                f"Error handling {action} {mute_type} for user {user.id}: {e}", exc_info=True
            )
            await ctx.send(f"Wystąpił błąd podczas {action}.")

    def parse_duration(self, duration_str: str) -> Optional[timedelta]:
        """
        Parse a duration string into a timedelta.

        Formats supported:
        - Empty string or None - treated as permanent (returns None)
        - Plain number (e.g., "1") - treated as hours
        - Time units (e.g., "1h", "30m", "1d")
        - Combined (e.g., "1h30m")

        Returns a timedelta object or None for permanent duration.
        """
        if duration_str is None or duration_str.strip() == "":
            return None  # None indicates permanent mute

        # If it's just a number, treat as hours
        if duration_str.isdigit():
            return timedelta(hours=int(duration_str))

        # Try to parse complex duration
        total_seconds = 0
        pattern = r"(\d+)([dhms])"
        matches = re.findall(pattern, duration_str.lower())

        if not matches:
            # If no valid format found, default to 1 hour
            logger.warning(f"Invalid duration format: {duration_str}, using default 1 hour")
            return timedelta(hours=1)

        for value, unit in matches:
            if unit == "d":
                total_seconds += int(value) * 86400  # days to seconds
            elif unit == "h":
                total_seconds += int(value) * 3600  # hours to seconds
            elif unit == "m":
                total_seconds += int(value) * 60  # minutes to seconds
            elif unit == "s":
                total_seconds += int(value)  # seconds

        return timedelta(seconds=total_seconds)


async def setup(bot):
    logging.basicConfig(level=logging.DEBUG)
    await bot.add_cog(ModCog(bot))
