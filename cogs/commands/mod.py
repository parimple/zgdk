import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Union

import discord
from discord import app_commands
from discord.ext import commands

from datasources.queries import MemberQueries, ModerationLogQueries, RoleQueries
from utils.message_sender import MessageSender
from utils.moderation import (
    GenderManager,
    GenderType,
    MessageCleaner,
    MuteManager,
    MuteType,
)
from utils.permissions import is_admin, is_mod_or_admin, is_owner_or_admin

logger = logging.getLogger(__name__)


class ModCog(commands.Cog):
    """Cog for moderation commands."""

    def __init__(self, bot):
        self.bot = bot
        self.config = bot.config
        self.message_sender = MessageSender(bot)
        self.mute_manager = MuteManager(bot)
        self.message_cleaner = MessageCleaner(bot)
        self.gender_manager = GenderManager(bot)

        # Ułatwia testowanie komend bez dodawania cogu do bota
        for command in self.get_commands():
            command.cog = self

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

    @commands.hybrid_command(
        name="clear", description="Usuwa wiadomości użytkownika z ostatnich X godzin."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, którego wiadomości mają być usunięte",
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
    )
    async def clear_messages(
        self, ctx: commands.Context, user: discord.Member, hours: Optional[int] = 1
    ):
        await self.message_cleaner.clear_messages(ctx, hours, user, all_channels=False)

    @commands.hybrid_command(
        name="clearall",
        description="Usuwa wiadomości użytkownika z ostatnich X godzin na wszystkich kanałach.",
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, którego wiadomości mają być usunięte",
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
    )
    async def clear_all_channels(
        self, ctx: commands.Context, user: discord.Member, hours: Optional[int] = 1
    ):
        await self.message_cleaner.clear_messages(ctx, hours, user, all_channels=True)

    @commands.hybrid_command(
        name="clearimg",
        description="Usuwa linki i obrazki użytkownika z ostatnich X godzin.",
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, którego linki i obrazki mają być usunięte",
        hours="Liczba godzin wstecz, z których usunąć wiadomości (domyślnie 1)",
    )
    async def clear_images(
        self, ctx: commands.Context, user: discord.Member, hours: Optional[int] = 1
    ):
        await self.message_cleaner.clear_messages(
            ctx, hours, user, all_channels=False, images_only=True
        )

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

    @commands.hybrid_group(
        name="mute", description="Komendy związane z wyciszaniem użytkowników."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik do wyciszenia (opcjonalnie, działa jak mute txt)",
        duration="Czas trwania blokady, np. 1h, 30m, 1d (puste = blokada stała)",
    )
    async def mute(
        self,
        ctx: commands.Context,
        user: Optional[discord.Member] = None,
        duration: str = "",
    ):
        """Komendy związane z wyciszaniem użytkowników.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do wyciszenia (opcjonalnie, działa jak mute txt)
        :param duration: Czas trwania blokady (opcjonalnie)
        """
        if ctx.invoked_subcommand is None:
            if user is not None:
                # Jeśli podano użytkownika, ale nie podkomendę, działa jak 'mute txt'
                await self.mute_txt(
                    ctx, user, duration
                )  # Przekazujemy parametr duration
            else:
                # Użyj wspólnej metody do wyświetlania pomocy
                await self.send_subcommand_help(ctx, "mute")

    @mute.command(
        name="nick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik z niewłaściwym nickiem")
    async def mute_nick(self, ctx: commands.Context, user: discord.Member):
        """Usuwa niewłaściwy nick użytkownika i nadaje karę."""
        await self.mute_manager.mute_user(ctx, user, MuteType.NICK)

    @mute.command(
        name="img", description="Blokuje możliwość wysyłania obrazków i linków."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość wysyłania obrazków",
        duration="Czas trwania blokady, np. 1h, 30m, 1d (puste = blokada stała)",
    )
    async def mute_img(
        self, ctx: commands.Context, user: discord.Member, duration: str = ""
    ):
        """Blokuje możliwość wysyłania obrazków i linków.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do zablokowania
        :param duration: Czas trwania blokady (opcjonalnie)
        """
        parsed_duration = self.mute_manager.parse_duration(duration)
        await self.mute_manager.mute_user(ctx, user, MuteType.IMG, parsed_duration)

    @mute.command(name="txt", description="Blokuje możliwość wysyłania wiadomości.")
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość wysyłania wiadomości",
        duration="Czas trwania blokady, np. 1h, 30m, 1d (puste = blokada stała)",
    )
    async def mute_txt(
        self, ctx: commands.Context, user: discord.Member, duration: str = ""
    ):
        """Blokuje możliwość wysyłania wiadomości.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do zablokowania
        :param duration: Czas trwania blokady (opcjonalnie)
        """
        parsed_duration = self.mute_manager.parse_duration(duration)
        await self.mute_manager.mute_user(ctx, user, MuteType.TXT, parsed_duration)

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
        await self.mute_manager.mute_user(ctx, user, MuteType.LIVE)

    @mute.command(
        name="rank", description="Blokuje możliwość zdobywania punktów rankingowych."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik, któremu chcesz zablokować możliwość zdobywania punktów"
    )
    async def mute_rank(self, ctx: commands.Context, user: discord.Member):
        """Blokuje możliwość zdobywania punktów rankingowych.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do zablokowania
        """
        await self.mute_manager.mute_user(ctx, user, MuteType.RANK)

    @commands.hybrid_group(
        name="unmute", description="Komendy związane z odwyciszaniem użytkowników."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik do odwyciszenia (opcjonalnie, działa jak unmute txt)"
    )
    async def unmute(
        self, ctx: commands.Context, user: Optional[discord.Member] = None
    ):
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

    @unmute.command(
        name="nick", description="Przywraca możliwość zmiany nicku użytkownikowi."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odmutowania nicku")
    async def unmute_nick(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość zmiany nicku użytkownikowi.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.mute_manager.unmute_user(ctx, user, MuteType.NICK)

    @unmute.command(
        name="img", description="Przywraca możliwość wysyłania obrazków i linków."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odblokowania wysyłania obrazków")
    async def unmute_img(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość wysyłania obrazków i linków.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.mute_manager.unmute_user(ctx, user, MuteType.IMG)

    @unmute.command(name="txt", description="Przywraca możliwość wysyłania wiadomości.")
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik do odblokowania wysyłania wiadomości"
    )
    async def unmute_txt(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość wysyłania wiadomości.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.mute_manager.unmute_user(ctx, user, MuteType.TXT)

    @unmute.command(name="live", description="Przywraca możliwość streamowania.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odblokowania streamowania")
    async def unmute_live(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość streamowania.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.mute_manager.unmute_user(ctx, user, MuteType.LIVE)

    @unmute.command(
        name="rank", description="Przywraca możliwość zdobywania punktów rankingowych."
    )
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik do odblokowania zdobywania punktów")
    async def unmute_rank(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość zdobywania punktów rankingowych.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do odblokowania
        """
        await self.mute_manager.unmute_user(ctx, user, MuteType.RANK)

    @commands.command(
        name="mutenick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę."
    )
    @is_mod_or_admin()
    async def mutenick_prefix(self, ctx: commands.Context, user: discord.Member):
        """Usuwa niewłaściwy nick użytkownika i nadaje karę (wersja prefiksowa)."""
        try:
            logger.info(
                f"mutenick command started for user {user.id} ({user.display_name}) by {ctx.author.id}"
            )

            # Sprawdź aktualny nick przed rozpoczęciem
            default_nick = self.config.get("default_mute_nickname", "random")
            original_nick = user.nick or user.name
            logger.info(
                f"User {user.id} original nick: '{original_nick}', target nick: '{default_nick}'"
            )

            # Wykonaj standardową logikę mutenick
            await self.mute_manager.mute_user(ctx, user, MuteType.NICK)

            # Dodatkowe sprawdzenie po 3 sekundach, czy nick został faktycznie ustawiony
            import asyncio

            await asyncio.sleep(3)

            # Pobierz świeży obiekt użytkownika
            updated_user = ctx.guild.get_member(user.id)
            if updated_user:
                current_nick = updated_user.nick or updated_user.name
                logger.info(f"After mutenick, user {user.id} nick is: '{current_nick}'")

                # Sprawdź czy nick to faktycznie "random"
                if current_nick != default_nick:
                    logger.warning(
                        f"Nick verification failed for user {user.id}: expected '{default_nick}', got '{current_nick}'. Attempting to fix..."
                    )
                    try:
                        await updated_user.edit(
                            nick=default_nick,
                            reason="Wymuszenie poprawnego nicku mutenick - weryfikacja",
                        )
                        logger.info(
                            f"Successfully enforced nick '{default_nick}' for user {user.id}"
                        )

                        # Wyślij dodatkową informację do moderatora
                        await ctx.send(
                            f"⚠️ **Dodatkowa weryfikacja**: Wymuszono poprawny nick `{default_nick}` dla {updated_user.mention}"
                        )

                    except discord.Forbidden:
                        logger.error(
                            f"Failed to enforce nick for user {user.id} - permission denied"
                        )
                        await ctx.send(
                            f"❌ **Ostrzeżenie**: Nie udało się wymusić nicku `{default_nick}` dla {updated_user.mention} - brak uprawnień!"
                        )

                    except Exception as nick_error:
                        logger.error(
                            f"Failed to enforce nick for user {user.id}: {nick_error}"
                        )
                        await ctx.send(
                            f"❌ **Ostrzeżenie**: Błąd podczas wymuszania nicku dla {updated_user.mention}: {nick_error}"
                        )
                else:
                    logger.info(
                        f"Nick verification successful for user {user.id}: '{current_nick}'"
                    )
            else:
                logger.warning(
                    f"Could not fetch updated user {user.id} for nick verification"
                )

            logger.info(f"mutenick command completed successfully for user {user.id}")

        except Exception as e:
            logger.error(
                f"Error in mutenick command for user {user.id}: {e}", exc_info=True
            )
            await ctx.send(f"Wystąpił błąd podczas wykonywania komendy mutenick: {e}")

    @commands.command(
        name="unmutenick", description="Przywraca możliwość zmiany nicku użytkownikowi."
    )
    @is_mod_or_admin()
    async def unmutenick_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość zmiany nicku użytkownikowi (wersja prefiksowa)."""
        await self.mute_manager.unmute_user(ctx, user, MuteType.NICK)

    @commands.command(
        name="muteimg", description="Blokuje możliwość wysyłania obrazków i linków."
    )
    @is_mod_or_admin()
    async def muteimg_prefix(
        self, ctx: commands.Context, user: discord.Member, duration: str = ""
    ):
        """Blokuje możliwość wysyłania obrazków i linków (wersja prefiksowa)."""
        parsed_duration = self.mute_manager.parse_duration(duration)
        await self.mute_manager.mute_user(ctx, user, MuteType.IMG, parsed_duration)

    @commands.command(
        name="unmuteimg", description="Przywraca możliwość wysyłania obrazków i linków."
    )
    @is_mod_or_admin()
    async def unmuteimg_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość wysyłania obrazków i linków (wersja prefiksowa)."""
        await self.mute_manager.unmute_user(ctx, user, MuteType.IMG)

    @commands.command(
        name="mutetxt", description="Blokuje możliwość wysyłania wiadomości."
    )
    @is_mod_or_admin()
    async def mutetxt_prefix(
        self, ctx: commands.Context, user: discord.Member, duration: str = ""
    ):
        """Blokuje możliwość wysyłania wiadomości (wersja prefiksowa)."""
        parsed_duration = self.mute_manager.parse_duration(duration)
        await self.mute_manager.mute_user(ctx, user, MuteType.TXT, parsed_duration)

    @commands.command(
        name="unmutetxt", description="Przywraca możliwość wysyłania wiadomości."
    )
    @is_mod_or_admin()
    async def unmutetxt_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość wysyłania wiadomości (wersja prefiksowa)."""
        await self.mute_manager.unmute_user(ctx, user, MuteType.TXT)

    @commands.command(name="mutelive", description="Blokuje możliwość streamowania.")
    @is_mod_or_admin()
    async def mutelive_prefix(self, ctx: commands.Context, user: discord.Member):
        """Blokuje możliwość streamowania (wersja prefiksowa)."""
        await self.mute_manager.mute_user(ctx, user, MuteType.LIVE)

    @commands.command(
        name="unmutelive", description="Przywraca możliwość streamowania."
    )
    @is_mod_or_admin()
    async def unmutelive_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość streamowania (wersja prefiksowa)."""
        await self.mute_manager.unmute_user(ctx, user, MuteType.LIVE)

    @commands.command(
        name="muterank",
        description="Blokuje możliwość zdobywania punktów rankingowych.",
    )
    @is_mod_or_admin()
    async def muterank_prefix(self, ctx: commands.Context, user: discord.Member):
        """Blokuje możliwość zdobywania punktów rankingowych (wersja prefiksowa)."""
        await self.mute_manager.mute_user(ctx, user, MuteType.RANK)

    @commands.command(
        name="unmuterank",
        description="Przywraca możliwość zdobywania punktów rankingowych.",
    )
    @is_mod_or_admin()
    async def unmuterank_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość zdobywania punktów rankingowych (wersja prefiksowa)."""
        await self.mute_manager.unmute_user(ctx, user, MuteType.RANK)

    @commands.command(name="male", description="Nadaje rolę mężczyzny użytkownikowi")
    @is_mod_or_admin()
    async def male(self, ctx: commands.Context, user: discord.Member):
        """Nadaje rolę mężczyzny użytkownikowi.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do nadania roli mężczyzny
        """
        await self.gender_manager.assign_gender_role(ctx, user, GenderType.MALE)

    @commands.command(name="female", description="Nadaje rolę kobiety użytkownikowi")
    @is_mod_or_admin()
    async def female(self, ctx: commands.Context, user: discord.Member):
        """Nadaje rolę kobiety użytkownikowi.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do nadania roli kobiety
        """
        await self.gender_manager.assign_gender_role(ctx, user, GenderType.FEMALE)

    @commands.command(
        name="userid", description="Wyświetla ID użytkownika o podanej nazwie"
    )
    @is_mod_or_admin()
    async def user_id(self, ctx: commands.Context, *, name: str):
        """Wyświetla ID użytkownika o podanej nazwie.

        :param ctx: Kontekst komendy
        :param name: Nazwa użytkownika (lub jej część)
        """
        matching_members = []

        # Szukaj wszystkich pasujących członków
        for member in ctx.guild.members:
            if name.lower() in member.name.lower() or (
                member.nick and name.lower() in member.nick.lower()
            ):
                matching_members.append(member)

        if not matching_members:
            await ctx.send(f"Nie znaleziono użytkowników pasujących do nazwy '{name}'.")
            return

        # Wyświetl wszystkie pasujące ID
        result = "Znaleziono następujących użytkowników:\n"
        for member in matching_members[:10]:  # Limit do 10 wyników
            result += f"- **{member.name}** (ID: `{member.id}`)\n"

        if len(matching_members) > 10:
            result += (
                f"\nPokazano 10 z {len(matching_members)} pasujących użytkowników."
            )

        await ctx.send(result)

    @commands.command(
        name="mutehistory", description="Wyświetla historię mute'ów użytkownika"
    )
    @is_mod_or_admin()
    async def mute_history(
        self, ctx: commands.Context, user: discord.Member, limit: int = 10
    ):
        """Wyświetla historię mute'ów użytkownika.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do sprawdzenia historii
        :param limit: Liczba ostatnich akcji do wyświetlenia (max 50)
        """
        if limit > 50:
            limit = 50

        try:
            async with self.bot.get_db() as session:
                # Pobierz historię mute'ów
                history = await ModerationLogQueries.get_user_mute_history(
                    session, user.id, limit
                )

                if not history:
                    embed = discord.Embed(
                        title="Historia mute'ów",
                        description=f"Użytkownik {user.mention} nie ma żadnych akcji moderatorskich w historii.",
                        color=discord.Color.green(),
                    )
                    await ctx.reply(embed=embed)
                    return

                # Stwórz embed z historią
                embed = discord.Embed(
                    title=f"Historia mute'ów - {user.display_name}",
                    description=f"Ostatnie {len(history)} akcji moderatorskich",
                    color=user.color or discord.Color.blue(),
                )
                embed.set_thumbnail(url=user.display_avatar.url)

                # Dodaj pola z historią (maksymalnie 25 pól na embed)
                for i, log in enumerate(history[:25]):
                    action_emoji = "🔇" if log.action_type == "mute" else "🔓"
                    moderator_name = "Nieznany"
                    if log.moderator:
                        moderator_name = (
                            log.moderator.id
                        )  # Będziemy pokazywać ID, bo nie mamy dostępu do nazwy

                    # Formatuj czas trwania
                    duration_text = "Permanentne"
                    if log.duration_seconds:
                        hours, remainder = divmod(log.duration_seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        if hours > 0:
                            duration_text = f"{hours}h {minutes}m"
                        elif minutes > 0:
                            duration_text = f"{minutes}m"
                        else:
                            duration_text = f"{seconds}s"

                    # Formatuj typ mute'a
                    mute_type_text = log.mute_type.upper() if log.mute_type else "N/A"

                    field_value = (
                        f"**Typ:** {mute_type_text}\n"
                        f"**Moderator:** <@{log.moderator_id}>\n"
                        f"**Czas:** {duration_text if log.action_type == 'mute' else 'N/A'}\n"
                        f"**Data:** {discord.utils.format_dt(log.created_at, 'f')}"
                    )

                    embed.add_field(
                        name=f"{action_emoji} {log.action_type.upper()} #{len(history) - i}",
                        value=field_value,
                        inline=True,
                    )

                if len(history) > 25:
                    embed.add_field(
                        name="ℹ️ Informacja",
                        value=f"Pokazano 25 z {len(history)} akcji. Użyj mniejszego limitu dla nowszych akcji.",
                        inline=False,
                    )

                await ctx.reply(embed=embed)

        except Exception as e:
            logger.error(
                f"Error retrieving mute history for user {user.id}: {e}", exc_info=True
            )
            await ctx.send("Wystąpił błąd podczas pobierania historii mute'ów.")

    @commands.command(
        name="mutestats", description="Wyświetla statystyki mute'ów z serwera"
    )
    @is_mod_or_admin()
    async def mute_stats(self, ctx: commands.Context, days: int = 30):
        """Wyświetla statystyki mute'ów z ostatnich X dni.

        :param ctx: Kontekst komendy
        :param days: Liczba dni wstecz do analizy (max 365)
        """
        if days > 365:
            days = 365

        try:
            async with self.bot.get_db() as session:
                stats = await ModerationLogQueries.get_mute_statistics(session, days)

                # Stwórz embed ze statystykami
                embed = discord.Embed(
                    title="📊 Statystyki mute'ów",
                    description=f"Podsumowanie z ostatnich {days} dni",
                    color=discord.Color.orange(),
                    timestamp=datetime.now(timezone.utc),
                )

                # Ogólne statystyki
                embed.add_field(
                    name="📋 Ogólne",
                    value=f"**Całkowite mute'y:** {stats['total_mutes']}",
                    inline=False,
                )

                # Statystyki według typu mute'a
                if stats["mute_types"]:
                    types_text = ""
                    for mute_type, count in stats["mute_types"].items():
                        types_text += f"**{mute_type.upper()}:** {count}\n"

                    embed.add_field(
                        name="🏷️ Według typu",
                        value=types_text or "Brak danych",
                        inline=True,
                    )

                # Top mutowani użytkownicy
                if stats["top_muted_users"]:
                    users_text = ""
                    for i, (user_id, count) in enumerate(
                        stats["top_muted_users"][:5], 1
                    ):
                        users_text += f"{i}. <@{user_id}> - {count} mute'ów\n"

                    embed.add_field(
                        name="👤 Najczęściej mutowani",
                        value=users_text or "Brak danych",
                        inline=True,
                    )

                # Top moderatorzy
                if stats["top_moderators"]:
                    mods_text = ""
                    for i, (mod_id, count) in enumerate(stats["top_moderators"][:5], 1):
                        mods_text += f"{i}. <@{mod_id}> - {count} akcji\n"

                    embed.add_field(
                        name="👮 Najaktywniejsi moderatorzy",
                        value=mods_text or "Brak danych",
                        inline=True,
                    )

                await ctx.reply(embed=embed)

        except Exception as e:
            logger.error(f"Error retrieving mute statistics: {e}", exc_info=True)
            await ctx.send("Wystąpił błąd podczas pobierania statystyk mute'ów.")

    @commands.command(
        name="mutecount", description="Sprawdza ile razy użytkownik był mutowany"
    )
    @is_mod_or_admin()
    async def mute_count(
        self, ctx: commands.Context, user: discord.Member, days: int = 30
    ):
        """Sprawdza ile razy użytkownik był mutowany w ostatnich X dniach.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do sprawdzenia
        :param days: Liczba dni wstecz do sprawdzenia (max 365)
        """
        if days > 365:
            days = 365

        try:
            async with self.bot.get_db() as session:
                mute_count = await ModerationLogQueries.get_user_mute_count(
                    session, user.id, days
                )

                # Stwórz embed z wynikiem
                color = (
                    discord.Color.green()
                    if mute_count == 0
                    else (
                        discord.Color.orange()
                        if mute_count < 5
                        else discord.Color.red()
                    )
                )

                embed = discord.Embed(
                    title="📊 Liczba mute'ów",
                    description=f"Użytkownik {user.mention} miał **{mute_count}** mute'ów w ostatnich {days} dniach.",
                    color=color,
                )
                embed.set_thumbnail(url=user.display_avatar.url)

                # Dodaj ocenę
                if mute_count == 0:
                    embed.add_field(
                        name="✅ Ocena",
                        value="Użytkownik nie ma żadnych mute'ów!",
                        inline=False,
                    )
                elif mute_count < 3:
                    embed.add_field(
                        name="⚠️ Ocena",
                        value="Niewiele mute'ów - dobry użytkownik",
                        inline=False,
                    )
                elif mute_count < 10:
                    embed.add_field(
                        name="⚠️ Ocena",
                        value="Średnio problematyczny użytkownik",
                        inline=False,
                    )
                else:
                    embed.add_field(
                        name="🚫 Ocena",
                        value="Bardzo problematyczny użytkownik!",
                        inline=False,
                    )

                await ctx.reply(embed=embed)

        except Exception as e:
            logger.error(
                f"Error retrieving mute count for user {user.id}: {e}", exc_info=True
            )
            await ctx.send("Wystąpił błąd podczas sprawdzania liczby mute'ów.")


async def setup(bot):
    await bot.add_cog(ModCog(bot))
