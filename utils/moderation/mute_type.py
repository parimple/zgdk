"""Definicje typów wyciszeń.

Moduł zawiera definicje typów wyciszeń i ich konfiguracji.
"""

import logging
from datetime import timedelta

logger = logging.getLogger(__name__)


class MuteType:
    """Klasa definiująca typy wyciszeń.

    Klasa zawiera stałe i konfigurację dla różnych typów wyciszeń
    oraz metody pomocnicze do obsługi tych typów.
    """

    NICK = "nick"
    IMG = "img"
    TXT = "txt"
    LIVE = "live"
    RANK = "rank"

    def __init__(self, type_name):
        """Inicjalizuje obiekt typu wyciszenia.

        :param type_name: Nazwa typu wyciszenia.
        :type type_name: str
        :raises ValueError: Gdy podany typ wyciszenia nie istnieje.
        """
        self.type_name = type_name
        self.config = self._get_config_for_type(type_name)

    def _get_config_for_type(self, type_name):
        """Pobiera konfigurację dla konkretnego typu.

        :param type_name: Nazwa typu wyciszenia.
        :type type_name: str
        :returns: Konfiguracja dla danego typu wyciszenia.
        :rtype: dict
        """
        all_configs = self.get_config()
        return all_configs.get(type_name)

    @property
    def role_index(self):
        """Zwraca indeks roli dla tego typu wyciszenia.

        :returns: Indeks roli.
        :rtype: int
        """
        return self.config["role_index"]

    @property
    def role_id_field(self):
        """Zwraca pole ID roli dla tego typu wyciszenia.

        :returns: Nazwa pola ID roli.
        :rtype: str
        """
        return self.config["role_id_field"]

    @property
    def display_name(self):
        """Zwraca nazwę wyświetlaną dla tego typu wyciszenia.

        :returns: Nazwa wyświetlana.
        :rtype: str
        """
        return self.config["display_name"]

    @property
    def action_name(self):
        """Zwraca nazwę akcji dla tego typu wyciszenia.

        :returns: Nazwa akcji.
        :rtype: str
        """
        return self.config["action_name"]

    @property
    def reason_add(self):
        """Zwraca powód dodania wyciszenia.

        :returns: Powód dodania wyciszenia.
        :rtype: str
        """
        return self.config["reason_add"]

    @property
    def reason_remove(self):
        """Zwraca powód usunięcia wyciszenia.

        :returns: Powód usunięcia wyciszenia.
        :rtype: str
        """
        return self.config["reason_remove"]

    @property
    def success_message_add(self):
        """Zwraca wiadomość sukcesu dla dodania wyciszenia.

        :returns: Wiadomość sukcesu.
        :rtype: str
        """
        return self.config["success_message_add"]

    @property
    def success_message_remove(self):
        """Zwraca wiadomość sukcesu dla usunięcia wyciszenia.

        :returns: Wiadomość sukcesu.
        :rtype: str
        """
        return self.config["success_message_remove"]

    @property
    def default_duration(self):
        """Zwraca domyślny czas trwania wyciszenia.

        :returns: Domyślny czas trwania wyciszenia.
        :rtype: timedelta or None
        """
        return self.config["default_duration"]

    @property
    def supports_duration(self):
        """Zwraca czy ten typ wyciszenia obsługuje określony czas trwania.

        :returns: Czy obsługuje czas trwania.
        :rtype: bool
        """
        return self.config["supports_duration"]

    @property
    def special_actions(self):
        """Zwraca listę specjalnych akcji dla tego typu wyciszenia.

        :returns: Lista specjalnych akcji.
        :rtype: list
        """
        return self.config["special_actions"]

    @staticmethod
    def get_config():
        """Zwraca konfigurację dla wszystkich typów wyciszeń.

        :returns: Konfiguracja dla wszystkich typów wyciszeń.
        :rtype: dict
        """
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

    @classmethod
    def from_name(cls, type_name):
        """Factory method do tworzenia instancji z nazwy typu.

        :param type_name: Nazwa typu wyciszenia.
        :type type_name: str
        :returns: Instancja klasy MuteType dla podanego typu.
        :rtype: MuteType
        :raises ValueError: Jeśli podany typ nie istnieje.
        """
        if type_name not in cls.get_config():
            raise ValueError(f"Nieznany typ wyciszenia: {type_name}")
        return cls(type_name)
