import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Union

import discord
from discord import app_commands
from discord.ext import commands

from datasources.queries import MemberQueries, RoleQueries
from utils.message_sender import MessageSender
from utils.moderation import MessageCleaner, MuteManager, MuteType
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
        name="clearimg", description="Usuwa linki i obrazki użytkownika z ostatnich X godzin."
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

    @commands.hybrid_group(name="mute", description="Komendy związane z wyciszaniem użytkowników.")
    @is_mod_or_admin()
    @discord.app_commands.describe(
        user="Użytkownik do wyciszenia (opcjonalnie, działa jak mute txt)",
        duration="Czas trwania blokady, np. 1h, 30m, 1d (puste = blokada stała)",
    )
    async def mute(
        self, ctx: commands.Context, user: Optional[discord.Member] = None, duration: str = ""
    ):
        """Komendy związane z wyciszaniem użytkowników.

        :param ctx: Kontekst komendy
        :param user: Użytkownik do wyciszenia (opcjonalnie, działa jak mute txt)
        :param duration: Czas trwania blokady (opcjonalnie)
        """
        if ctx.invoked_subcommand is None:
            if user is not None:
                # Jeśli podano użytkownika, ale nie podkomendę, działa jak 'mute txt'
                await self.mute_txt(ctx, user, duration)  # Przekazujemy parametr duration
            else:
                # Użyj wspólnej metody do wyświetlania pomocy
                await self.send_subcommand_help(ctx, "mute")

    @mute.command(name="nick", description="Usuwa niewłaściwy nick użytkownika i nadaje karę.")
    @is_mod_or_admin()
    @discord.app_commands.describe(user="Użytkownik z niewłaściwym nickiem")
    async def mute_nick(self, ctx: commands.Context, user: discord.Member):
        """Usuwa niewłaściwy nick użytkownika i nadaje karę."""
        await self.mute_manager.mute_user(ctx, user, MuteType.NICK)

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
        parsed_duration = self.mute_manager.parse_duration(duration)
        await self.mute_manager.mute_user(ctx, user, MuteType.IMG, parsed_duration)

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
        await self.mute_manager.mute_user(ctx, user, MuteType.RANK)

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
        await self.mute_manager.unmute_user(ctx, user, MuteType.NICK)

    @unmute.command(name="img", description="Przywraca możliwość wysyłania obrazków i linków.")
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
    @discord.app_commands.describe(user="Użytkownik do odblokowania wysyłania wiadomości")
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

    @unmute.command(name="rank", description="Przywraca możliwość zdobywania punktów rankingowych.")
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
                        logger.error(f"Failed to enforce nick for user {user.id}: {nick_error}")
                        await ctx.send(
                            f"❌ **Ostrzeżenie**: Błąd podczas wymuszania nicku dla {updated_user.mention}: {nick_error}"
                        )
                else:
                    logger.info(
                        f"Nick verification successful for user {user.id}: '{current_nick}'"
                    )
            else:
                logger.warning(f"Could not fetch updated user {user.id} for nick verification")

            logger.info(f"mutenick command completed successfully for user {user.id}")

        except Exception as e:
            logger.error(f"Error in mutenick command for user {user.id}: {e}", exc_info=True)
            await ctx.send(f"Wystąpił błąd podczas wykonywania komendy mutenick: {e}")

    @commands.command(
        name="unmutenick", description="Przywraca możliwość zmiany nicku użytkownikowi."
    )
    @is_mod_or_admin()
    async def unmutenick_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość zmiany nicku użytkownikowi (wersja prefiksowa)."""
        await self.mute_manager.unmute_user(ctx, user, MuteType.NICK)

    @commands.command(name="muteimg", description="Blokuje możliwość wysyłania obrazków i linków.")
    @is_mod_or_admin()
    async def muteimg_prefix(self, ctx: commands.Context, user: discord.Member, duration: str = ""):
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

    @commands.command(name="mutetxt", description="Blokuje możliwość wysyłania wiadomości.")
    @is_mod_or_admin()
    async def mutetxt_prefix(self, ctx: commands.Context, user: discord.Member, duration: str = ""):
        """Blokuje możliwość wysyłania wiadomości (wersja prefiksowa)."""
        parsed_duration = self.mute_manager.parse_duration(duration)
        await self.mute_manager.mute_user(ctx, user, MuteType.TXT, parsed_duration)

    @commands.command(name="unmutetxt", description="Przywraca możliwość wysyłania wiadomości.")
    @is_mod_or_admin()
    async def unmutetxt_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość wysyłania wiadomości (wersja prefiksowa)."""
        await self.mute_manager.unmute_user(ctx, user, MuteType.TXT)

    @commands.command(name="mutelive", description="Blokuje możliwość streamowania.")
    @is_mod_or_admin()
    async def mutelive_prefix(self, ctx: commands.Context, user: discord.Member):
        """Blokuje możliwość streamowania (wersja prefiksowa)."""
        await self.mute_manager.mute_user(ctx, user, MuteType.LIVE)

    @commands.command(name="unmutelive", description="Przywraca możliwość streamowania.")
    @is_mod_or_admin()
    async def unmutelive_prefix(self, ctx: commands.Context, user: discord.Member):
        """Przywraca możliwość streamowania (wersja prefiksowa)."""
        await self.mute_manager.unmute_user(ctx, user, MuteType.LIVE)

    @commands.command(
        name="muterank", description="Blokuje możliwość zdobywania punktów rankingowych."
    )
    @is_mod_or_admin()
    async def muterank_prefix(self, ctx: commands.Context, user: discord.Member):
        """Blokuje możliwość zdobywania punktów rankingowych (wersja prefiksowa)."""
        await self.mute_manager.mute_user(ctx, user, MuteType.RANK)

    @commands.command(
        name="unmuterank", description="Przywraca możliwość zdobywania punktów rankingowych."
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
        try:
            male_role_id = self.config.get("gender_roles", {}).get("male")
            female_role_id = self.config.get("gender_roles", {}).get("female")
            
            if not male_role_id:
                await ctx.send("❌ Role płci nie są skonfigurowane.", ephemeral=True)
                return
                
            male_role = ctx.guild.get_role(male_role_id)
            female_role = ctx.guild.get_role(female_role_id) if female_role_id else None
            
            if not male_role:
                await ctx.send("❌ Nie znaleziono roli męskiej na serwerze.", ephemeral=True)
                return
            
            # Usuń rolę kobiecą jeśli ją ma
            roles_to_remove = []
            if female_role and female_role in user.roles:
                roles_to_remove.append(female_role)
            
            # Sprawdź czy już ma rolę męską
            if male_role in user.roles:
                if roles_to_remove:
                    await user.remove_roles(*roles_to_remove, reason=f"Zmiana płci na męską - komenda przez {ctx.author}")
                    await ctx.send(f"✅ Usunięto rolę kobiecą dla {user.mention} (już miał rolę męską)")
                else:
                    await ctx.send(f"ℹ️ {user.mention} już ma rolę męską")
                return
            
            # Dodaj rolę męską i usuń kobiecą jeśli trzeba
            await user.add_roles(male_role, reason=f"Nadanie roli męskiej - komenda przez {ctx.author}")
            if roles_to_remove:
                await user.remove_roles(*roles_to_remove, reason=f"Zmiana płci na męską - komenda przez {ctx.author}")
            
            await ctx.send(f"✅ Nadano rolę **{male_role.name}** dla {user.mention}")
            logger.info(f"Nadano rolę męską ({male_role.name}) użytkownikowi {user.id} przez {ctx.author.id}")
            
        except discord.Forbidden:
            await ctx.send("❌ Brak uprawnień do zarządzania rolami tego użytkownika.")
        except Exception as e:
            logger.error(f"Błąd podczas nadawania roli męskiej użytkownikowi {user.id}: {e}")
            await ctx.send(f"❌ Wystąpił błąd podczas nadawania roli: {e}")

    @commands.command(name="female", description="Nadaje rolę kobiety użytkownikowi")
    @is_mod_or_admin()
    async def female(self, ctx: commands.Context, user: discord.Member):
        """Nadaje rolę kobiety użytkownikowi.
        
        :param ctx: Kontekst komendy
        :param user: Użytkownik do nadania roli kobiety
        """
        try:
            male_role_id = self.config.get("gender_roles", {}).get("male")
            female_role_id = self.config.get("gender_roles", {}).get("female")
            
            if not female_role_id:
                await ctx.send("❌ Role płci nie są skonfigurowane.", ephemeral=True)
                return
                
            female_role = ctx.guild.get_role(female_role_id)
            male_role = ctx.guild.get_role(male_role_id) if male_role_id else None
            
            if not female_role:
                await ctx.send("❌ Nie znaleziono roli kobiecej na serwerze.", ephemeral=True)
                return
            
            # Usuń rolę męską jeśli ją ma
            roles_to_remove = []
            if male_role and male_role in user.roles:
                roles_to_remove.append(male_role)
            
            # Sprawdź czy już ma rolę kobiecą
            if female_role in user.roles:
                if roles_to_remove:
                    await user.remove_roles(*roles_to_remove, reason=f"Zmiana płci na kobiecą - komenda przez {ctx.author}")
                    await ctx.send(f"✅ Usunięto rolę męską dla {user.mention} (już miał rolę kobiecą)")
                else:
                    await ctx.send(f"ℹ️ {user.mention} już ma rolę kobiecą")
                return
            
            # Dodaj rolę kobiecą i usuń męską jeśli trzeba
            await user.add_roles(female_role, reason=f"Nadanie roli kobiecej - komenda przez {ctx.author}")
            if roles_to_remove:
                await user.remove_roles(*roles_to_remove, reason=f"Zmiana płci na kobiecą - komenda przez {ctx.author}")
            
            await ctx.send(f"✅ Nadano rolę **{female_role.name}** dla {user.mention}")
            logger.info(f"Nadano rolę kobiecą ({female_role.name}) użytkownikowi {user.id} przez {ctx.author.id}")
            
        except discord.Forbidden:
            await ctx.send("❌ Brak uprawnień do zarządzania rolami tego użytkownika.")
        except Exception as e:
            logger.error(f"Błąd podczas nadawania roli kobiecej użytkownikowi {user.id}: {e}")
            await ctx.send(f"❌ Wystąpił błąd podczas nadawania roli: {e}")

    @commands.command(name="userid", description="Wyświetla ID użytkownika o podanej nazwie")
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
            result += f"\nPokazano 10 z {len(matching_members)} pasujących użytkowników."

        await ctx.send(result)


async def setup(bot):
    logging.basicConfig(level=logging.DEBUG)
    await bot.add_cog(ModCog(bot))
