"""Moduł do zarządzania rolami czasowymi.

Zawiera klasy i funkcje służące do zarządzania wszystkimi rolami czasowymi
na serwerze Discord, w tym rolami premium i wyciszeniami.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

import discord
from discord import AllowedMentions
from discord.ext import commands

from datasources.queries import MemberQueries, NotificationLogQueries, RoleQueries

logger = logging.getLogger(__name__)


class RoleManager:
    """Zarządza rolami czasowymi na serwerze Discord.

    Klasa odpowiedzialna za logikę dodawania, usuwania i sprawdzania
    wygasłych ról premium i wyciszeń.
    """

    # Zmienne statyczne do przechowywania ostatnich wyników
    _last_check_results = {}
    _last_check_timestamp = None

    def __init__(self, bot):
        """Inicjalizuje menedżera ról.

        :param bot: Instancja bota Discord.
        :type bot: discord.ext.commands.Bot
        """
        self.bot = bot
        self.config = bot.config
        self.notification_channel_id = self.bot.config.get("channels", {}).get("mute_notifications")

    @property
    def force_channel_notifications(self):
        """Zwraca ustawienie powiadomień na kanał.

        :return: True jeśli powiadomienia mają być wysyłane na kanał, False dla DM.
        :rtype: bool
        """
        return getattr(self.bot, "force_channel_notifications", True)

    async def check_expired_roles(
        self,
        role_type: Optional[str] = None,
        role_ids: Optional[List[int]] = None,
        notification_handler: Optional[Callable] = None,
    ):
        """Sprawdza i usuwa wygasłe role określonego typu lub o konkretnych ID.

        Usuwa tylko role, które:
        1. Istnieją w bazie danych z datą wygaśnięcia
        2. Wygasły zgodnie z datą w bazie
        3. Są aktualnie przypisane do użytkownika na serwerze

        Nie usuwa wpisów z bazy danych dla ról, które nie są już przypisane użytkownikom,
        co pozwala na współdziałanie z innymi botami zarządzającymi rolami.

        :param role_type: Opcjonalny typ roli do sprawdzenia (np. "premium", "mute")
        :type role_type: Optional[str]
        :param role_ids: Opcjonalna lista konkretnych ID ról do sprawdzenia
        :type role_ids: Optional[List[int]]
        :param notification_handler: Opcjonalna funkcja do obsługi powiadomień
        :type notification_handler: Optional[Callable]
        :return: Liczba usuniętych ról
        :rtype: int
        """
        start_time = datetime.now()
        now = datetime.now(timezone.utc)
        removed_count = 0

        # Utworzenie unikalnego klucza dla tego konkretnego sprawdzenia
        check_key = f"{role_type}_{str(role_ids)}"

        # Liczniki dla statystyk
        stats = {
            "non_existent_members": 0,
            "non_existent_roles": 0,
            "roles_not_assigned": 0,
            "skipped_member_ids": set(),  # Unikalne ID użytkowników
            "skipped_role_ids": set(),  # Unikalne ID ról
            "expired_roles_count": 0,  # Liczba wygasłych ról znalezionych w bazie
            "removed_count": 0,  # Liczba usuniętych ról
        }

        # Sprawdź czy serwer jest dostępny
        if not hasattr(self.bot, "guild") or self.bot.guild is None:
            logger.error("Guild not available - skipping expired roles check")
            return 0

        # Zmiana poziomu logowania z INFO na DEBUG
        logger.debug(f"Checking expired roles: type={role_type}, specific_ids={role_ids}")

        try:
            # Zapamiętaj poprzedni stan pominiętych członków dla tego klucza
            previous_skipped_ids = RoleManager._last_check_results.get(check_key, {}).get(
                "skipped_member_ids", set()
            )

            async with self.bot.get_db() as session:
                # Pobierz wygasłe role z bazy danych
                expired_roles = await RoleQueries.get_expired_roles(
                    session, now, role_type=role_type, role_ids=role_ids
                )

                if not expired_roles:
                    # Sprawdź czy poprzednio było coś do zrobienia
                    last_stats = RoleManager._last_check_results.get(check_key, {})
                    if last_stats.get("expired_roles_count", 0) > 0:
                        logger.info("No expired roles found (changed from previous check)")
                        RoleManager._last_check_results[check_key] = stats.copy()
                    return 0

                # Zapisz liczbę wygasłych ról
                stats["expired_roles_count"] = len(expired_roles)

                # Sprawdź czy zmieniła się liczba wygasłych ról
                last_expired_count = RoleManager._last_check_results.get(check_key, {}).get(
                    "expired_roles_count", -1
                )
                if last_expired_count != stats["expired_roles_count"]:
                    logger.info(
                        f"Found {stats['expired_roles_count']} expired roles to process (changed from {last_expired_count})"
                    )

                # Zidentyfikuj rolę mutenick (rola o indeksie 2 w konfiguracji)
                nick_mute_role_id = None
                for role_config in self.config["mute_roles"]:
                    if role_config["description"] == "attach_files_off":
                        nick_mute_role_id = role_config["id"]
                        break

                if not nick_mute_role_id:
                    logger.warning("Couldn't find mutenick role ID in config")

                # Grupuj role według użytkowników dla zoptymalizowanego przetwarzania
                # Słownik: {member_id: [(member_role, role_obj)]}
                member_roles = {}
                for member_role in expired_roles:
                    # Pobierz obiekt użytkownika
                    member = self.bot.guild.get_member(member_role.member_id)
                    if not member:
                        # Zamiast logować ostrzeżenie tutaj, dodajemy ID do statystyk
                        stats["non_existent_members"] += 1
                        stats["skipped_member_ids"].add(member_role.member_id)
                        continue

                    # Pobierz obiekt roli Discord
                    role = self.bot.guild.get_role(member_role.role_id)
                    if not role:
                        stats["non_existent_roles"] += 1
                        stats["skipped_role_ids"].add(member_role.role_id)
                        continue

                    # Sprawdź czy użytkownik faktycznie ma tę rolę
                    if role not in member.roles:
                        stats["roles_not_assigned"] += 1
                        continue

                    # Dodaj do słownika do przetwarzania
                    if member.id not in member_roles:
                        member_roles[member.id] = []
                    member_roles[member.id].append((member_role, role))

                # Przetwarzaj role pogrupowane według użytkowników
                for member_id, role_pairs in member_roles.items():
                    member = self.bot.guild.get_member(member_id)
                    if not member:
                        continue

                    roles_to_remove = []
                    role_objects = []

                    for member_role, role in role_pairs:
                        roles_to_remove.append((member_role.member_id, member_role.role_id))
                        role_objects.append(role)

                    # Sprawdź, czy użytkownik ma mutenick i czy ma domyślny nick przed usunięciem ról
                    has_nick_mute_before = nick_mute_role_id and discord.utils.get(
                        member.roles, id=nick_mute_role_id
                    )
                    default_nick = self.config.get("default_mute_nickname", "random")
                    is_default_nick = member.nick == default_nick

                    # Sprawdź, czy wygasające role zawierają mutenick
                    nick_mute_expiring = any(role.id == nick_mute_role_id for role in role_objects)

                    # Usuń role z użytkownika w jednej operacji
                    try:
                        if role_objects:
                            await member.remove_roles(*role_objects, reason="Role wygasły")

                            # Sprawdź, czy użytkownik nadal ma mutenick po usunięciu
                            has_nick_mute_after = False
                            if nick_mute_role_id and not nick_mute_expiring:
                                has_nick_mute_after = (
                                    discord.utils.get(member.roles, id=nick_mute_role_id)
                                    is not None
                                )

                            # Jeśli użytkownik miał mutenick z domyślnym nickiem, a ten wygasł,
                            # ale jednocześnie ma inne mutenick role, przywróć domyślny nick
                            if has_nick_mute_before and is_default_nick and has_nick_mute_after:
                                # Poczekaj chwilę na zastosowanie zmian ról
                                await asyncio.sleep(0.5)
                                await member.edit(
                                    nick=default_nick,
                                    reason="Zachowanie domyślnego nicku po wygaśnięciu roli",
                                )
                                logger.info(
                                    f"Preserved default nickname '{default_nick}' for {member.display_name} ({member.id}) with mutenick"
                                )

                            # Usuń role z bazy danych
                            for member_id, role_id in roles_to_remove:
                                await RoleQueries.delete_member_role(session, member_id, role_id)
                                removed_count += 1
                                stats["removed_count"] += 1

                                # Dodaj log powiadomienia
                                notification_tag = f"{role_type or 'role'}_expired"
                                await NotificationLogQueries.add_or_update_notification_log(
                                    session, member_id, notification_tag
                                )

                            logger.info(
                                f"Removed {len(role_objects)} expired roles from {member.display_name} ({member.id})"
                            )

                            # Wysyłaj powiadomienia
                            for i, (member_role, role) in enumerate(role_pairs):
                                try:
                                    if notification_handler:
                                        await notification_handler(member, member_role, role)
                                    else:
                                        # Użyj domyślnego powiadomienia, ale ogranicz liczbę
                                        if (
                                            i == 0 or len(role_pairs) <= 3
                                        ):  # Wyślij dla pierwszej i gdy max 3 role
                                            await self.send_default_notification(member, role)
                                except Exception as e:
                                    logger.error(f"Error sending role expiry notification: {e}")

                    except discord.Forbidden:
                        logger.error(
                            f"Permission error removing roles from {member.display_name} ({member.id})"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error removing roles from {member.display_name} ({member.id}): {e}"
                        )

                await session.commit()

                # Pobierz poprzednie statystyki i porównaj
                last_stats = RoleManager._last_check_results.get(check_key, {})

                # Loguj statystyki pominięć tylko jeśli coś się zmieniło
                stats_changed = False

                # Sprawdź czy zmieniła się liczba pominiętych ról dla nieistniejących użytkowników
                if stats["non_existent_members"] != last_stats.get("non_existent_members", -1):
                    stats_changed = True
                    if stats["non_existent_members"] > 0:
                        logger.info(
                            f"Skipped {stats['non_existent_members']} roles for {len(stats['skipped_member_ids'])} non-existent members"
                        )

                # Sprawdź czy zmieniła się liczba pominiętych nieistniejących ról
                if stats["non_existent_roles"] != last_stats.get("non_existent_roles", -1):
                    stats_changed = True
                    if stats["non_existent_roles"] > 0:
                        logger.info(
                            f"Skipped {stats['non_existent_roles']} non-existent roles for {len(stats['skipped_role_ids'])} unique IDs"
                        )

                # Sprawdź czy zmieniła się liczba pominiętych nieprzypisanych ról
                if stats["roles_not_assigned"] != last_stats.get("roles_not_assigned", -1):
                    stats_changed = True
                    if stats["roles_not_assigned"] > 0:
                        logger.info(
                            f"Skipped {stats['roles_not_assigned']} roles not actually assigned to members"
                        )

                # Sprawdź czy usunięto jakieś role lub czy zmieniła się liczba usuniętych ról
                if removed_count > 0 or stats["removed_count"] != last_stats.get(
                    "removed_count", -1
                ):
                    stats_changed = True

                # Rejestruj metryki wydajności tylko jeśli coś się zmieniło lub jeśli coś zostało usunięte
                if stats_changed or removed_count > 0:
                    end_time = datetime.now()
                    duration = (end_time - start_time).total_seconds()
                    logger.info(
                        f"Role expiry check completed in {duration:.2f}s - Processed {len(expired_roles)} roles, removed {removed_count}, skipped {stats['non_existent_members'] + stats['non_existent_roles'] + stats['roles_not_assigned']}"
                    )

                # Zapisz bieżące statystyki jako ostatnie
                RoleManager._last_check_results[check_key] = stats.copy()
                RoleManager._last_check_timestamp = now

                # Logowanie zagregowanych informacji o pominiętych członkach tylko jeśli lista się zmieniła
                current_skipped_ids = stats["skipped_member_ids"]
                if current_skipped_ids and current_skipped_ids != previous_skipped_ids:
                    logger.info(
                        f"RoleManager: Skipped processing for {stats['non_existent_members']} members not found in guild cache. IDs: {list(current_skipped_ids)}"
                    )

                return removed_count

        except Exception as e:
            logger.error(f"Error in check_expired_roles: {e}", exc_info=True)
            return 0

    async def send_default_notification(self, member: discord.Member, role: discord.Role):
        """Wysyła domyślne powiadomienie o wygaśnięciu roli.

        :param member: Użytkownik, któremu wygasła rola
        :type member: discord.Member
        :param role: Rola, która wygasła
        :type role: discord.Role
        """
        try:
            # Sprawdź, czy to rola wyciszenia
            is_mute_role = any(
                role.id == mute_role["id"] for mute_role in self.config.get("mute_roles", [])
            )

            if is_mute_role:
                message = (
                    f"Twoje wyciszenie ({role.name}) wygasło i zostało automatycznie usunięte."
                )
            else:
                message = f"Twoja rola {role.name} wygasła i została automatycznie usunięta."

            await self.send_notification(member, message)

        except Exception as e:
            logger.error(f"Error sending default notification: {e}")

    async def send_notification(self, member: discord.Member, message: str):
        """Wysyła powiadomienie do użytkownika przez DM lub na kanał.

        :param member: Użytkownik, do którego wysyłane jest powiadomienie
        :type member: discord.Member
        :param message: Treść powiadomienia
        :type message: str
        """
        try:
            if not self.force_channel_notifications:
                # Wysyłanie DM
                await member.send(message)
                logger.info(f"Sent DM notification to {member.display_name} ({member.id})")
            else:
                # Wysyłanie na kanał
                channel = self.bot.get_channel(self.notification_channel_id)
                if channel:
                    await channel.send(
                        f"[Kanał] {member.mention}, {message}",
                        allowed_mentions=AllowedMentions(users=False),
                    )
                    logger.info(f"Sent channel notification to {member.display_name} ({member.id})")
                else:
                    logger.error(f"Notification channel {self.notification_channel_id} not found")
        except discord.Forbidden:
            logger.warning(f"Could not send DM to {member.display_name} ({member.id})")
            # Fallback do powiadomienia na kanał
            if not self.force_channel_notifications:
                channel = self.bot.get_channel(self.notification_channel_id)
                if channel:
                    await channel.send(
                        f"[DM nie działa] {member.mention}, {message}",
                        allowed_mentions=AllowedMentions(users=False),
                    )
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
