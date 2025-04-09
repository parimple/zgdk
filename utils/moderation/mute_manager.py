"""Moduł do zarządzania wyciszeniami użytkowników.

Moduł zawiera klasy i funkcje służące do zarządzania wyciszeniami użytkowników
na serwerze Discord.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands

from datasources.queries import MemberQueries, RoleQueries
from utils.message_sender import MessageSender
from utils.moderation.mute_type import MuteType

logger = logging.getLogger(__name__)


class MuteManager:
    """Zarządza wyciszeniami użytkowników.

    Klasa odpowiedzialna za logikę wyciszania i odciszania użytkowników,
    w tym zarządzanie rolami wyciszenia i bazą danych.
    """

    def __init__(self, bot):
        """Inicjalizuje menedżera wyciszeń.

        :param bot: Instancja bota Discord.
        :type bot: discord.ext.commands.Bot
        """
        self.bot = bot
        self.config = bot.config
        self.message_sender = MessageSender(bot)

    async def mute_user(self, ctx, user, mute_type_name, duration=None):
        """Wycisza użytkownika.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param user: Użytkownik do wyciszenia.
        :type user: discord.Member
        :param mute_type_name: Nazwa typu wyciszenia.
        :type mute_type_name: str
        :param duration: Czas trwania wyciszenia (opcjonalnie).
        :type duration: Optional[timedelta]
        """
        mute_type = MuteType.from_name(mute_type_name)

        # Ensure we have the most up-to-date user object
        # This is important to handle users with changed nicknames correctly
        user = ctx.guild.get_member(user.id)
        if not user:
            logger.error(f"Could not find user with ID {user.id} in guild. Aborting mute.")
            await ctx.send("Nie można znaleźć tego użytkownika na serwerze.")
            return

        logger.info(f"Muting user {user.id} ({user.display_name}) with type {mute_type_name}")
        await self._handle_mute_logic(ctx, user, mute_type, duration, unmute=False)

    async def unmute_user(self, ctx, user, mute_type_name):
        """Odcisza użytkownika.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param user: Użytkownik do odciszenia.
        :type user: discord.Member
        :param mute_type_name: Nazwa typu wyciszenia.
        :type mute_type_name: str
        """
        mute_type = MuteType.from_name(mute_type_name)

        # Ensure we have the most up-to-date user object
        # This is important to handle users with changed nicknames correctly
        user = ctx.guild.get_member(user.id)
        if not user:
            logger.error(f"Could not find user with ID {user.id} in guild. Aborting unmute.")
            await ctx.send("Nie można znaleźć tego użytkownika na serwerze.")
            return

        logger.info(f"Unmuting user {user.id} ({user.display_name}) with type {mute_type_name}")
        await self._handle_mute_logic(ctx, user, mute_type, unmute=True)

    async def _handle_mute_logic(
        self,
        ctx: commands.Context,
        user: discord.Member,
        mute_type: MuteType,
        duration: Optional[timedelta] = None,
        unmute: bool = False,
    ):
        """Wspólna logika do obsługi różnych typów wyciszeń.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param user: Użytkownik do wyciszenia/odciszenia.
        :type user: discord.Member
        :param mute_type: Obiekt typu wyciszenia.
        :type mute_type: MuteType
        :param duration: Czas trwania wyciszenia (None dla permanentnego).
        :type duration: Optional[timedelta]
        :param unmute: Czy to jest operacja odciszenia.
        :type unmute: bool
        """
        try:
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
            role_index = mute_type.role_index
            mute_role_id = self.config["mute_roles"][role_index]["id"]
            mute_role = discord.Object(id=mute_role_id)

            if unmute:
                # Remove mute role
                await user.remove_roles(mute_role, reason=mute_type.reason_remove)

                # Remove role from database
                async with self.bot.get_db() as session:
                    # Usuwamy rolę z bazy danych
                    await RoleQueries.delete_member_role(session, user.id, mute_role_id)
                    await session.commit()

                # Format success message
                message = mute_type.success_message_remove.format(
                    user_mention=user.mention,
                    action_name=mute_type.action_name,
                    premium_channel=self.config["channels"]["premium_info"],
                )
            else:
                # Apply mute - Optymalizacja operacji na rolach

                # Sprawdź czy użytkownik ma już rolę mutenick (rola o indeksie 2 w konfiguracji)
                nick_mute_role_id = self.config["mute_roles"][2]["id"]  # ID roli mutenick (☢︎)
                has_nick_mute = discord.utils.get(user.roles, id=nick_mute_role_id) is not None
                default_nick = self.config.get("default_mute_nickname", "random")

                # Sprawdź aktualny nick użytkownika
                current_nick = user.nick or user.name
                preserve_nick = has_nick_mute and current_nick == default_nick
                is_default_nick = current_nick == default_nick

                # Przygotuj role do modyfikacji
                roles_to_remove = []
                for role_id in self.config["color_roles"].values():
                    # Sprawdź, czy użytkownik ma rolę koloru przed próbą jej usunięcia
                    if discord.utils.get(user.roles, id=role_id):
                        roles_to_remove.append(discord.Object(id=role_id))

                if roles_to_remove:
                    # Jeśli są role do usunięcia, usuń je
                    await user.remove_roles(*roles_to_remove, reason=mute_type.reason_add)

                # Dodaj rolę wyciszenia jako osobną operację (by uniknąć błędów API)
                await user.add_roles(mute_role, reason=mute_type.reason_add)

                # Jeśli użytkownik ma włączone mutenick i już ma domyślny nick, upewnij się,
                # że nick nie zostanie zmieniony przez dodanie/usunięcie ról
                if has_nick_mute and is_default_nick and mute_type.type_name != MuteType.NICK:
                    # Sprawdź, czy nick został zmieniony przez dodanie roli i natychmiast przywróć
                    current_name = user.nick
                    if current_name != default_nick:
                        await user.edit(
                            nick=default_nick,
                            reason="Zachowanie domyślnego nicku przy nałożeniu innej kary",
                        )
                        logger.info(
                            f"Natychmiast przywrócono domyślny nick {default_nick} dla użytkownika {user.id}"
                        )

                # Set default duration if not specified and the mute type supports it
                if duration is None and mute_type.supports_duration:
                    duration = mute_type.default_duration

                # Zoptymalizowana obsługa bazy danych - jedna transakcja
                async with self.bot.get_db() as session:
                    # Sprawdź istniejącą rolę i zapisz nową w jednej transakcji
                    existing_role = await RoleQueries.get_member_role(
                        session, user.id, mute_role_id
                    )
                    override_info = ""

                    if existing_role and existing_role.expiration_date:
                        now = datetime.now(timezone.utc)

                        # Check if expiration time is in the past
                        if existing_role.expiration_date <= now:
                            # Role already expired but not removed yet
                            logger.info(
                                f"Nadpisuję wygasłą blokadę dla {user.id} (wygasła {now - existing_role.expiration_date} temu)"
                            )
                            override_info = (
                                "\nNadpisano wygasłą blokadę, która już powinna zostać usunięta."
                            )
                        else:
                            # Role still active, format with Discord timestamp
                            discord_timestamp = discord.utils.format_dt(
                                existing_role.expiration_date, "R"
                            )
                            logger.info(
                                f"Nadpisuję istniejącą blokadę dla {user.id}: stara kończy się {discord_timestamp}, nowa będzie trwać {duration}"
                            )
                            override_info = f"\nNadpisano istniejącą blokadę, która wygasłaby {discord_timestamp}."

                    # Dodaj użytkownika i rolę w jednej operacji
                    await MemberQueries.get_or_add_member(session, user.id)
                    await RoleQueries.add_or_update_role_to_member(
                        session, user.id, mute_role_id, duration=duration
                    )
                    await session.commit()

                # Format duration text
                if duration is None:
                    duration_text = "stałe"
                else:
                    # Calculate the expiration date for Discord timestamp
                    now = datetime.now(timezone.utc)
                    expiration_date = now + duration

                    # Use Discord's relative timestamp format
                    duration_text = discord.utils.format_dt(expiration_date, "R")

                    # For logging purposes, still format the duration as text
                    parts = []
                    if duration.days > 0:
                        parts.append(f"{duration.days}d")
                    hours, remainder = divmod(duration.seconds, 3600)
                    if hours > 0:
                        parts.append(f"{hours}h")
                    minutes, seconds = divmod(remainder, 60)
                    if minutes > 0:
                        parts.append(f"{minutes}m")
                    if seconds > 0 and not parts:
                        parts.append(f"{seconds}s")
                    log_duration = " ".join(parts) if parts else "mniej niż 1m"
                    logger.info(
                        f"Applying mute to user {user.id} for {log_duration}, expires {duration_text}"
                    )

                # Format success message
                message = mute_type.success_message_add.format(
                    user_mention=user.mention,
                    duration_text=duration_text,
                    action_name=mute_type.action_name,
                    premium_channel=self.config["channels"]["premium_info"],
                )

                # Dodaj informację o nadpisaniu blokady jeśli istnieje
                if "override_info" in locals():
                    message += override_info

                # Specjalne akcje uruchamiamy asynchronicznie, aby nie opóźniać głównej odpowiedzi
                # Tworzenie zadania, które wykona się niezależnie
                if mute_type.special_actions:
                    # Używamy run_in_executor dla specjalnych akcji, by uniknąć mieszania kontekstów
                    # między różnymi użytkownikami
                    special_task = asyncio.create_task(
                        self._execute_special_actions(ctx, user, mute_type)
                    )
                    # Dodaj identyfikator użytkownika do nazwy zadania dla lepszego debugowania
                    special_task.set_name(f"special_actions_{user.id}_{mute_type.type_name}")

            # Add premium info to message
            _, premium_text = MessageSender._get_premium_text(ctx)
            if premium_text:
                message = f"{message}\n{premium_text}"

            # Send response - Always use embed for consistency
            embed = discord.Embed(description=message, color=ctx.author.color)
            await ctx.reply(embed=embed)

        except discord.Forbidden as e:
            action = "odblokowania" if unmute else "blokowania"
            logger.error(
                f"Permission error during {action} {mute_type.type_name} for user {user.id}: {e}",
                exc_info=True,
            )
            await ctx.send(f"Brak uprawnień do {action} użytkownika.")
        except discord.HTTPException as e:
            action = "odblokowania" if unmute else "blokowania"
            logger.error(
                f"Discord API error during {action} {mute_type.type_name} for user {user.id}: {e}",
                exc_info=True,
            )
            await ctx.send(f"Wystąpił błąd Discord API podczas {action}.")
        except Exception as e:
            action = "odblokowania" if unmute else "blokowania"
            logger.error(
                f"Error handling {action} {mute_type.type_name} for user {user.id}: {e}",
                exc_info=True,
            )
            await ctx.send(f"Wystąpił błąd podczas {action}.")

    async def _execute_special_actions(self, ctx, user, mute_type):
        """Wykonuje specjalne akcje dla danego typu wyciszenia.

        :param ctx: Kontekst komendy.
        :type ctx: discord.ext.commands.Context
        :param user: Użytkownik, na którym wykonywane są akcje.
        :type user: discord.Member
        :param mute_type: Obiekt typu wyciszenia.
        :type mute_type: MuteType
        """
        # Pobierz świeży obiekt użytkownika, aby upewnić się, że mamy aktualne dane
        # This is critical to prevent actions on one user from affecting another
        try:
            # Get a fresh user object from the guild to ensure we have the most up-to-date data
            # and we're not reusing any cached data from previous operations
            user = ctx.guild.get_member(user.id)
            if not user:
                logger.error(
                    f"Could not find user with ID {user.id} in guild. Aborting special actions."
                )
                return

            special_actions = mute_type.special_actions
            logger.info(
                f"Executing special actions for user {user.id} ({user.display_name}): {special_actions}"
            )

            if "change_nickname" in special_actions:
                # Zmniejszamy opóźnienie z 5 sekund do 1 sekundy
                await asyncio.sleep(1)
                try:
                    default_nick = self.config.get("default_mute_nickname", "random")
                    # Sprawdź czy nickname już jest ustawiony na domyślny
                    current_nick = user.nick
                    if current_nick != default_nick:
                        logger.info(
                            f"Changing nickname for user {user.id} ({user.display_name}) from '{current_nick}' to '{default_nick}'"
                        )
                        await user.edit(nick=default_nick, reason="Niewłaściwy nick")
                        logger.info(
                            f"Pomyślnie zmieniono nick użytkownika {user.id} na {default_nick}"
                        )
                    else:
                        logger.info(
                            f"Użytkownik {user.id} już ma ustawiony domyślny nick {default_nick}"
                        )
                except discord.Forbidden:
                    logger.warning(f"Nie mogę zmienić nicku użytkownika {user.id}")
                except Exception as e:
                    logger.error(f"Error changing nickname for user {user.id}: {e}")

            # Check if user needs to be moved to AFK and back to force stream permission update
            if "move_to_afk_and_back" in special_actions and user.voice and user.voice.channel:
                # Get the AFK channel ID from config
                afk_channel_id = self.config["channels_voice"]["afk"]
                afk_channel = self.bot.get_channel(afk_channel_id)

                if (
                    afk_channel and afk_channel != user.voice.channel
                ):  # Dodajemy sprawdzenie, czy użytkownik nie jest już w kanale AFK
                    # Remember original channel
                    original_channel = user.voice.channel

                    # Move to AFK and back w jednej operacji asynchronicznej
                    try:
                        # Move to AFK
                        await user.move_to(
                            afk_channel,
                            reason=f"Wymuszenie aktualizacji uprawnień {mute_type.action_name}",
                        )
                        logger.info(
                            f"Moved user {user.id} to AFK channel for stream permission update"
                        )

                        # Zmniejszam opóźnienie z 1 sekundy do 0.5 sekundy
                        await asyncio.sleep(0.5)

                        # Move back to original channel
                        await user.move_to(
                            original_channel,
                            reason=f"Powrót po aktualizacji uprawnień {mute_type.action_name}",
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
        except Exception as e:
            logger.error(f"Error during special actions for user {user.id}: {e}", exc_info=True)

    def parse_duration(self, duration_str: str) -> Optional[timedelta]:
        """Parsuje ciąg znakowy reprezentujący czas trwania do obiektu timedelta.

        Obsługiwane formaty:
        - Pusty ciąg lub None - traktowany jako permanentny (zwraca None)
        - Sama liczba (np. "1") - traktowana jako godziny
        - Jednostki czasu (np. "1h", "30m", "1d")
        - Kombinacja (np. "1h30m")

        :param duration_str: String reprezentujący czas trwania.
        :type duration_str: str
        :returns: Obiekt timedelta lub None dla permanentnego.
        :rtype: Optional[timedelta]
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

    async def _preserve_nickname(self, user, default_nick):
        """Przywraca domyślny nickname dla użytkownika z mutenick.

        Ta metoda jest używana jako zabezpieczenie dla przypadków brzegowych,
        gdy nickname zmieni się w wyniku innych operacji.

        :param user: Użytkownik, któremu należy przywrócić nick.
        :type user: discord.Member
        :param default_nick: Domyślny nickname do ustawienia.
        :type default_nick: str
        """
        try:
            # Minimalne opóźnienie, tylko aby pozwolić na zakończenie innych operacji
            await asyncio.sleep(0.2)

            # Sprawdź, czy nickname się zmienił i przywróć domyślny
            current_nick = user.nick
            if current_nick != default_nick:
                await user.edit(
                    nick=default_nick,
                    reason="Przywrócenie domyślnego nicku po nałożeniu innej kary",
                )
                logger.info(
                    f"Przywrócono domyślny nick {default_nick} dla użytkownika {user.id} (aktualny był: {current_nick})"
                )
        except discord.Forbidden:
            logger.warning(f"Nie mogę przywrócić domyślnego nicku dla użytkownika {user.id}")
        except Exception as e:
            logger.error(
                f"Błąd podczas przywracania domyślnego nicku dla użytkownika {user.id}: {e}"
            )
