from datetime import timedelta

import pytest

from utils.moderation.mute_type import MuteType


def test_get_config():
    config = MuteType.get_config()
    assert isinstance(config, dict)
    for key in [MuteType.NICK, MuteType.IMG, MuteType.TXT, MuteType.LIVE, MuteType.RANK]:
        assert key in config


def test_from_name():
    nick_type = MuteType.from_name(MuteType.NICK)
    assert isinstance(nick_type, MuteType)
    assert nick_type.type_name == MuteType.NICK

    img_type = MuteType.from_name(MuteType.IMG)
    assert isinstance(img_type, MuteType)
    assert img_type.type_name == MuteType.IMG

    with pytest.raises(ValueError):
        MuteType.from_name("nieistniejący_typ")


def test_properties():
    nick_type = MuteType.from_name(MuteType.NICK)

    assert nick_type.role_index == 2
    assert nick_type.role_id_field == "id"
    assert nick_type.display_name == "nicku"
    assert nick_type.action_name == "zmiany nicku"
    assert nick_type.reason_add == "Niewłaściwy nick"
    assert nick_type.reason_remove == "Przywrócenie możliwości zmiany nicku"
    assert isinstance(nick_type.success_message_add, str)
    assert isinstance(nick_type.success_message_remove, str)
    assert nick_type.default_duration == timedelta(days=30)
    assert nick_type.supports_duration is False
    assert "change_nickname" in nick_type.special_actions


def test_live_and_rank_permanent():
    live_type = MuteType.from_name(MuteType.LIVE)
    assert live_type.supports_duration is False
    assert live_type.default_duration is None

    rank_type = MuteType.from_name(MuteType.RANK)
    assert rank_type.supports_duration is False
    assert rank_type.default_duration is None
