"""Testy dla klasy MuteType."""

import unittest
from datetime import timedelta

from utils.moderation.mute_type import MuteType


class TestMuteType(unittest.TestCase):
    """Testy dla klasy MuteType."""

    def test_get_config(self):
        """Test metody get_config."""
        config = MuteType.get_config()
        self.assertIsInstance(config, dict)
        self.assertIn(MuteType.NICK, config)
        self.assertIn(MuteType.IMG, config)
        self.assertIn(MuteType.TXT, config)
        self.assertIn(MuteType.LIVE, config)
        self.assertIn(MuteType.RANK, config)

    def test_from_name(self):
        """Test metody from_name."""
        nick_type = MuteType.from_name(MuteType.NICK)
        self.assertIsInstance(nick_type, MuteType)
        self.assertEqual(nick_type.type_name, MuteType.NICK)

        img_type = MuteType.from_name(MuteType.IMG)
        self.assertIsInstance(img_type, MuteType)
        self.assertEqual(img_type.type_name, MuteType.IMG)

        with self.assertRaises(ValueError):
            MuteType.from_name("nieistniejący_typ")

    def test_properties(self):
        """Test właściwości klasy MuteType."""
        nick_type = MuteType.from_name(MuteType.NICK)

        self.assertEqual(nick_type.role_index, 2)
        self.assertEqual(nick_type.role_id_field, "id")
        self.assertEqual(nick_type.display_name, "nicku")
        self.assertEqual(nick_type.action_name, "zmiany nicku")
        self.assertEqual(nick_type.reason_add, "Niewłaściwy nick")
        self.assertEqual(nick_type.reason_remove, "Przywrócenie możliwości zmiany nicku")
        self.assertIsInstance(nick_type.success_message_add, str)
        self.assertIsInstance(nick_type.success_message_remove, str)
        self.assertEqual(nick_type.default_duration, timedelta(days=30))
        self.assertEqual(nick_type.supports_duration, False)
        self.assertIn("change_nickname", nick_type.special_actions)

    def test_live_and_rank_permanent(self):
        """Test czy typy LIVE i RANK są zawsze permanentne."""
        live_type = MuteType.from_name(MuteType.LIVE)
        self.assertEqual(live_type.supports_duration, False)
        self.assertIsNone(live_type.default_duration)

        rank_type = MuteType.from_name(MuteType.RANK)
        self.assertEqual(rank_type.supports_duration, False)
        self.assertIsNone(rank_type.default_duration)


if __name__ == "__main__":
    unittest.main()
