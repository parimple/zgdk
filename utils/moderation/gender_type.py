"""Definicje typów ról płci.

Moduł zawiera definicje typów ról płci i ich konfiguracji.
"""

import logging

logger = logging.getLogger(__name__)


class GenderType:
    """Klasa definiująca typy ról płci.

    Klasa zawiera stałe i konfigurację dla różnych typów ról płci
    oraz metody pomocnicze do obsługi tych typów.
    """

    MALE = "male"
    FEMALE = "female"

    def __init__(self, type_name):
        """Inicjalizuje obiekt typu roli płci.

        :param type_name: Nazwa typu roli płci.
        :type type_name: str
        :raises ValueError: Gdy podany typ roli płci nie istnieje.
        """
        self.type_name = type_name
        self.config = self._get_config_for_type(type_name)

    def _get_config_for_type(self, type_name):
        """Pobiera konfigurację dla konkretnego typu.

        :param type_name: Nazwa typu roli płci.
        :type type_name: str
        :returns: Konfiguracja dla danego typu roli płci.
        :rtype: dict
        """
        all_configs = self.get_config()
        return all_configs.get(type_name)

    @property
    def role_id_field(self):
        """Zwraca pole ID roli dla tego typu płci.

        :returns: Nazwa pola ID roli.
        :rtype: str
        """
        return self.config["role_id_field"]

    @property
    def display_name(self):
        """Zwraca nazwę wyświetlaną dla tego typu płci.

        :returns: Nazwa wyświetlana.
        :rtype: str
        """
        return self.config["display_name"]

    @property
    def opposite_type(self):
        """Zwraca przeciwny typ płci.

        :returns: Przeciwny typ płci.
        :rtype: str
        """
        return self.config["opposite_type"]

    @property
    def role_symbol(self):
        """Zwraca symbol roli dla tego typu płci.

        :returns: Symbol roli.
        :rtype: str
        """
        return self.config["role_symbol"]

    @property
    def reason_add(self):
        """Zwraca powód dodania roli płci.

        :returns: Powód dodania roli płci.
        :rtype: str
        """
        return self.config["reason_add"]

    @property
    def reason_remove(self):
        """Zwraca powód usunięcia roli płci.

        :returns: Powód usunięcia roli płci.
        :rtype: str
        """
        return self.config["reason_remove"]

    @property
    def success_message_add(self):
        """Zwraca wiadomość sukcesu dla dodania roli płci.

        :returns: Wiadomość sukcesu.
        :rtype: str
        """
        return self.config["success_message_add"]

    @property
    def success_message_already_has(self):
        """Zwraca wiadomość dla przypadku gdy użytkownik już ma rolę.

        :returns: Wiadomość informacyjna.
        :rtype: str
        """
        return self.config["success_message_already_has"]

    @property
    def success_message_switch(self):
        """Zwraca wiadomość sukcesu dla przełączenia z przeciwnej roli.

        :returns: Wiadomość sukcesu.
        :rtype: str
        """
        return self.config["success_message_switch"]

    @staticmethod
    def get_config():
        """Zwraca konfigurację dla wszystkich typów ról płci.

        :returns: Konfiguracja dla wszystkich typów ról płci.
        :rtype: dict
        """
        return {
            GenderType.MALE: {
                "role_id_field": "male",
                "display_name": "męską",
                "opposite_type": GenderType.FEMALE,
                "role_symbol": "♂",
                "reason_add": "Nadanie roli męskiej",
                "reason_remove": "Usunięcie roli męskiej przy zmianie płci",
                "success_message_add": "✅ Nadano rolę **{role_symbol}** dla {user_mention}",
                "success_message_already_has": "ℹ️ {user_mention} już ma rolę {display_name}",
                "success_message_switch": "✅ Nadano rolę **{role_symbol}** dla {user_mention} (usunięto poprzednią rolę płci)",
            },
            GenderType.FEMALE: {
                "role_id_field": "female",
                "display_name": "kobiecą",
                "opposite_type": GenderType.MALE,
                "role_symbol": "♀",
                "reason_add": "Nadanie roli kobiecej",
                "reason_remove": "Usunięcie roli kobiecej przy zmianie płci",
                "success_message_add": "✅ Nadano rolę **{role_symbol}** dla {user_mention}",
                "success_message_already_has": "ℹ️ {user_mention} już ma rolę {display_name}",
                "success_message_switch": "✅ Nadano rolę **{role_symbol}** dla {user_mention} (usunięto poprzednią rolę płci)",
            },
        }

    @classmethod
    def from_name(cls, type_name):
        """Tworzy obiekt GenderType na podstawie nazwy typu.

        :param type_name: Nazwa typu roli płci.
        :type type_name: str
        :returns: Obiekt GenderType.
        :rtype: GenderType
        :raises ValueError: Gdy podany typ roli płci nie istnieje.
        """
        if type_name not in [cls.MALE, cls.FEMALE]:
            raise ValueError(f"Unknown gender type: {type_name}")
        return cls(type_name)

    @classmethod
    def get_all_types(cls):
        """Zwraca listę wszystkich dostępnych typów ról płci.

        :returns: Lista typów ról płci.
        :rtype: list
        """
        return [cls.MALE, cls.FEMALE]
