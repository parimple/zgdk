"""Moduł do zarządzania rolami czasowymi.

Zawiera klasy i funkcje służące do zarządzania wszystkimi rolami czasowymi
na serwerze Discord, w tym rolami premium i wyciszeniami.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

import discord
from discord import AllowedMentions

from core.interfaces.premium_interfaces import IPremiumService
from core.repositories import NotificationRepository, RoleRepository

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

        # Lista powiadomień do wysłania po commit
        notifications_to_send = []

        try:
            # Zapamiętaj poprzedni stan pominiętych członków dla tego klucza
            previous_skipped_ids = RoleManager._last_check_results.get(check_key, {}).get("skipped_member_ids", set())

            async with self.bot.get_db() as session:
                # Create repository instances for this session
                role_repo = RoleRepository(session)
                notification_repo = NotificationRepository(session)

                # Pobierz wygasłe role z bazy danych
                expired_roles_data = await role_repo.get_expired_roles(now, role_type=role_type, role_ids=role_ids)

                # Convert dict data to MemberRole objects for compatibility
                expired_roles = [item["member_role"] for item in expired_roles_data]

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
                last_expired_count = RoleManager._last_check_results.get(check_key, {}).get("expired_roles_count", -1)
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
                # Słownik: {member_id: {"member": discord.Member, "roles": [(member_role, role_obj)]}}
                member_data_map: Dict[int, Dict[str, Any]] = {}

                for member_role in expired_roles:
                    member: Optional[discord.Member] = None
                    # Sprawdź, czy już pobraliśmy tego użytkownika
                    if member_role.member_id in member_data_map:
                        member = member_data_map[member_role.member_id]["member"]
                    else:
                        try:
                            member = await self.bot.guild.fetch_member(member_role.member_id)
                            if not member:
                                logger.warning(f"Could not fetch member {member_role.member_id}")
                                continue
                            # Zapisz pobranego użytkownika, aby uniknąć wielokrotnego fetchowania
                            member_data_map[member_role.member_id] = {
                                "member": member,
                                "roles": [],
                            }
                        except discord.NotFound:
                            logger.info(
                                f"Member with ID {member_role.member_id} not found (left server?), skipping role {member_role.role_id} and cleaning DB."
                            )
                            stats["non_existent_members"] += 1
                            stats["skipped_member_ids"].add(member_role.member_id)
                            await role_repo.delete_member_role(member_role.member_id, member_role.role_id)
                            removed_count += 1  # Count DB removal as an action
                            stats["removed_count"] += 1

                            # Jeśli to była rola premium, wyczyść również teamy i uprawnienia
                            # nawet gdy użytkownik opuścił serwer (zombie teams cleanup)
                            if role_type == "premium":
                                try:
                                    from cogs.commands.info.admin.helpers import remove_premium_role_mod_permissions

                                    await remove_premium_role_mod_permissions(session, self.bot, member_role.member_id)
                                    logger.info(
                                        f"Removed premium privileges (teams, mod permissions) for departed member {member_role.member_id} to prevent zombie teams"
                                    )
                                except Exception as e_premium_cleanup:
                                    logger.error(
                                        f"Error removing premium privileges for departed member {member_role.member_id}: {e_premium_cleanup}",
                                        exc_info=True,
                                    )
                            continue
                        except Exception as e:
                            logger.error(f"Error fetching member {member_role.member_id}: {e}")
                            stats["non_existent_members"] += 1
                            stats["skipped_member_ids"].add(member_role.member_id)
                            # Don't delete from DB on unknown error, might be temporary
                            continue

                    if not member:  # Powinno być obsłużone przez wyjątki powyżej, ale jako dodatkowe zabezpieczenie
                        stats["non_existent_members"] += 1
                        stats["skipped_member_ids"].add(member_role.member_id)
                        logger.warning(
                            f"Member object is None for ID {member_role.member_id} despite fetch attempt, skipping role."
                        )
                        # Consider if DB cleanup is needed here too, though it implies an earlier fetch issue not caught by NotFound
                        continue

                    role = self.bot.guild.get_role(member_role.role_id)
                    if not role:
                        logger.info(
                            f"Role ID {member_role.role_id} not found on server for member {member_role.member_id}. Cleaning DB."
                        )
                        stats["non_existent_roles"] += 1
                        stats["skipped_role_ids"].add(member_role.role_id)
                        await role_repo.delete_member_role(member_role.member_id, member_role.role_id)
                        removed_count += 1  # Count DB removal
                        stats["removed_count"] += 1
                        continue

                    if role not in member.roles:
                        logger.info(
                            f"Role {role.name} (ID: {role.id}) was in DB for member {member.display_name} (ID: {member.id}) but not assigned on Discord. Cleaning DB and notifying user."
                        )
                        stats["roles_not_assigned"] += 1
                        await role_repo.delete_member_role(member_role.member_id, member_role.role_id)
                        removed_count += 1  # Count DB removal
                        stats["removed_count"] += 1

                        # Dodaj powiadomienie do wysłania po commit (tak jak w normalnym przypadku wygaśnięcia)
                        notification_tag = f"{role_type or 'role'}_expired"
                        await notification_repo.add_or_update_notification_log(member_role.member_id, notification_tag)

                        # Przygotuj powiadomienie do wysłania PO commit
                        if notification_handler:
                            notifications_to_send.append(
                                {
                                    "handler": notification_handler,
                                    "member": member,
                                    "member_role_db_entry": member_role,
                                    "role_obj": role,
                                }
                            )

                        # Jeśli to była rola premium, wyczyść również uprawnienia i teamy
                        if role_type == "premium":
                            try:
                                from cogs.commands.info.admin.helpers import remove_premium_role_mod_permissions

                                await remove_premium_role_mod_permissions(session, self.bot, member.id)
                                logger.info(
                                    f"Removed premium privileges (teams, mod permissions) for {member.display_name} ({member.id}) due to DB/Discord inconsistency"
                                )
                            except Exception as e_premium_cleanup:
                                logger.error(
                                    f"Error removing premium privileges for {member.display_name} ({member.id}): {e_premium_cleanup}",
                                    exc_info=True,
                                )
                        continue

                    # Dodaj parę (member_role, role) do listy ról użytkownika
                    # This part is reached only if member exists, role exists, and member has the role.
                    member_data_map[member_role.member_id]["roles"].append((member_role, role))

                # Przetwarzaj role pogrupowane według użytkowników
                for member_id, data in member_data_map.items():
                    member = data["member"]
                    role_pairs = data["roles"]

                    if not member or not role_pairs:
                        logger.warning(
                            f"Skipping member_id {member_id} due to missing member object or roles list in map."
                        )
                        continue

                    # Przygotuj listę obiektów ról discord.Role do usunięcia
                    discord_roles_to_remove_on_discord: List[discord.Role] = [rp[1] for rp in role_pairs]

                    # Sprawdź, czy użytkownik ma mutenick i czy ma domyślny nick przed usunięciem ról
                    default_nick = self.config.get("default_mute_nickname", "random")

                    if not discord_roles_to_remove_on_discord:  # Jeśli lista jest pusta, przejdź dalej
                        logger.debug(
                            f"No Discord roles to remove for member {member.display_name} ({member.id}), skipping Discord interaction."
                        )
                        continue

                    try:
                        # Krok 1: Spróbuj usunąć role na Discordzie
                        await member.remove_roles(*discord_roles_to_remove_on_discord, reason="Role wygasły")
                        logger.info(
                            f"Successfully removed {len(discord_roles_to_remove_on_discord)} roles from {member.display_name} ({member.id}) on Discord."
                        )

                        # Krok 2: Jeśli usunięcie na Discordzie się powiodło, usuń z bazy danych i przygotuj powiadomienia
                        for member_role_db_entry, role_obj in role_pairs:
                            try:
                                await role_repo.delete_member_role(
                                    member_role_db_entry.member_id, member_role_db_entry.role_id
                                )
                                removed_count += 1
                                stats["removed_count"] += 1
                                logger.debug(
                                    f"Successfully deleted role ID {member_role_db_entry.role_id} for member {member_role_db_entry.member_id} from DB."
                                )

                                notification_tag = f"{role_type or 'role'}_expired"
                                await notification_repo.add_or_update_notification_log(
                                    member_role_db_entry.member_id,
                                    notification_tag,
                                )

                                # Przygotuj powiadomienie do wysłania PO commit
                                if notification_handler:
                                    notifications_to_send.append(
                                        {
                                            "handler": notification_handler,
                                            "member": member,
                                            "member_role_db_entry": member_role_db_entry,
                                            "role_obj": role_obj,
                                        }
                                    )

                            except Exception as e_db_notify:
                                logger.error(
                                    f"Error during DB delete or notification preparation for role {role_obj.name} (member {member.id}): {e_db_notify}",
                                    exc_info=True,
                                )
                                # Kontynuuj z następną rolą, ale zaloguj błąd.
                                # Nie chcemy, aby błąd przy jednej roli zatrzymał przetwarzanie innych.

                        # Logika związana z mutenick po pomyślnym usunięciu ról
                        if nick_mute_role_id:  # Sprawdź tylko jeśli mutenick jest skonfigurowany
                            await asyncio.sleep(0.5)  # Daj Discordowi chwilę na przetworzenie usunięcia ról
                            # Pobierz świeży obiekt członka, aby mieć pewność co do aktualnych ról i nicku
                            try:
                                updated_member = await self.bot.guild.fetch_member(member.id)
                                if not updated_member:  # Na wypadek gdyby fetch_member zwrócił None
                                    logger.warning(
                                        f"Could not fetch updated member {member.id} after role removal, skipping nick logic."
                                    )
                                    continue  # Przejdź do następnego członka w pętli member_data_map
                            except discord.NotFound:
                                logger.info(
                                    f"Member {member.id} not found after role removal, likely left. Skipping nick logic."
                                )
                                continue
                            except Exception as e_fetch:
                                logger.error(
                                    f"Error fetching updated member {member.id}: {e_fetch}, skipping nick logic."
                                )
                                continue

                            current_nick = updated_member.nick
                            member_roles_after_removal = updated_member.roles

                            has_nick_mute_role_after_removal = (
                                discord.utils.get(member_roles_after_removal, id=nick_mute_role_id) is not None
                            )
                            was_nick_mute_role_removed = any(
                                role.id == nick_mute_role_id for role in discord_roles_to_remove_on_discord
                            )

                            # Scenariusz 1: Rola mutenick została właśnie usunięta
                            if was_nick_mute_role_removed:
                                if current_nick == default_nick:
                                    try:
                                        await updated_member.edit(
                                            nick=None,
                                            reason="Wyciszenie nicku wygasło, resetowanie nicku",
                                        )
                                        logger.info(
                                            f"Reset nickname for {updated_member.display_name} ({updated_member.id}) as their mute nick role expired."
                                        )
                                    except Exception as e_nick_reset:
                                        logger.error(
                                            f"Failed to reset nick for {updated_member.display_name} after mute nick expiry: {e_nick_reset}"
                                        )
                                # Jeśli nick nie był domyślnym nickiem wyciszenia, nie robimy nic - użytkownik mógł go zmienić.

                            # Scenariusz 2: Inna rola wygasła, ale użytkownik nadal ma mutenick i miał domyślny nick
                            elif has_nick_mute_role_after_removal and current_nick == default_nick:
                                # Ten warunek jest bardziej precyzyjny - sprawdzamy czy *nadal* ma mutenick
                                # i czy *nadal* ma domyślny nick. Jeśli tak, upewniamy się, że nick jest zachowany.
                                # Teoretycznie, jeśli nic się nie zmieniło z nickiem, ponowne edit nie jest konieczne,
                                # ale dla pewności można to zostawić, lub dodać warunek `member.nick != default_nick`
                                # (czyli `current_nick` przed `fetch_member` nie był `default_nick`), ale to komplikuje.
                                # Bezpieczniej jest po prostu próbować ustawić, jeśli warunki są spełnione.
                                try:
                                    await updated_member.edit(
                                        nick=default_nick,
                                        reason="Zachowanie domyślnego nicku po wygaśnięciu innej roli (nadal ma mutenick)",
                                    )
                                    logger.info(
                                        f"Ensured default nickname '{default_nick}' for {updated_member.display_name} ({updated_member.id}) as they still have a mute nick role."
                                    )
                                except Exception as e_nick:
                                    logger.error(
                                        f"Failed to ensure default nick for {updated_member.display_name}: {e_nick}"
                                    )

                    except discord.Forbidden:
                        logger.error(
                            f"PERMISSION ERROR removing roles from {member.display_name} ({member.id}). Roles NOT deleted from DB. Audit should catch this."
                        )
                        # WAŻNE: Nie usuwamy z DB, jeśli usunięcie z Discorda się nie powiodło z powodu braku uprawnień.
                    except discord.HTTPException as e_http:
                        logger.error(
                            f"HTTP ERROR {e_http.status} (code: {e_http.code}) removing roles from {member.display_name} ({member.id}): {e_http.text}. Roles NOT deleted from DB. Audit should catch this."
                        )
                        # WAŻNE: Nie usuwamy z DB, jeśli usunięcie z Discorda się nie powiodło z powodu błędu HTTP.
                    except Exception as e_main_remove:
                        logger.error(
                            f"GENERAL ERROR removing roles from {member.display_name} ({member.id}): {e_main_remove}. Roles NOT deleted from DB. Audit should catch this.",
                            exc_info=True,
                        )
                        # WAŻNE: Nie usuwamy z DB przy innych błędach.

                await session.commit()

                # Wyślij powiadomienia DOPIERO PO commit
                for notification_data in notifications_to_send:
                    try:
                        await notification_data["handler"](
                            notification_data["member"],
                            notification_data["member_role_db_entry"],
                            notification_data["role_obj"],
                        )
                    except Exception as e_notification:
                        logger.error(
                            f"Error sending notification for role {notification_data['role_obj'].name} (member {notification_data['member'].id}): {e_notification}",
                            exc_info=True,
                        )

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
                        logger.info(f"Skipped {stats['roles_not_assigned']} roles not actually assigned to members")

                # Sprawdź czy usunięto jakieś role lub czy zmieniła się liczba usuniętych ról
                if removed_count > 0 or stats["removed_count"] != last_stats.get("removed_count", -1):
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
            is_mute_role = any(role.id == mute_role["id"] for mute_role in self.config.get("mute_roles", []))

            if is_mute_role:
                message = f"Twoje wyciszenie ({role.name}) wygasło i zostało automatycznie usunięte."
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
