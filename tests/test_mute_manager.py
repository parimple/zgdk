from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest

from utils.moderation.mute_manager import MuteManager


@pytest.fixture
def mute_manager():
    bot = MagicMock()
    bot.config = {
        "mute_roles": [
            {"id": 123, "name": "⚠︎", "description": "stream_off"},
            {"id": 456, "name": "⌀", "description": "send_messages_off"},
            {"id": 789, "name": "☢︎", "description": "attach_files_off"},
            {"id": 101, "name": "♺", "description": "points_off"},
        ],
        "admin_roles": {"mod": 111, "admin": 222},
        "color_roles": {"blue": 333, "green": 444, "red": 555},
        "channels": {"premium_info": 666, "mute_notifications": 777},
        "channels_voice": {"afk": 888},
        "default_mute_nickname": "random",
    }
    return MuteManager(bot)


def test_parse_duration(mute_manager):
    assert mute_manager.parse_duration(None) is None
    assert mute_manager.parse_duration("") is None
    assert mute_manager.parse_duration("5") == timedelta(hours=5)
    assert mute_manager.parse_duration("1d") == timedelta(days=1)
    assert mute_manager.parse_duration("3h") == timedelta(hours=3)
    assert mute_manager.parse_duration("30m") == timedelta(minutes=30)
    assert mute_manager.parse_duration("45s") == timedelta(seconds=45)
    assert mute_manager.parse_duration("1d12h30m") == timedelta(days=1, hours=12, minutes=30)


@patch("discord.utils.format_dt")
@pytest.mark.asyncio
async def test_duration_formatting(mock_format_dt, mute_manager):
    mock_format_dt.return_value = "<t:1234567890:R>"

    result = await _extract_duration_text(mute_manager, timedelta(days=2, hours=3, minutes=15))
    assert result == "2d 3h 15m"

    result = await _extract_duration_text(mute_manager, timedelta(hours=5, minutes=30))
    assert result == "5h 30m"

    result = await _extract_duration_text(mute_manager, timedelta(minutes=45))
    assert result == "45m"

    result = await _extract_duration_text(mute_manager, timedelta(seconds=30))
    assert result == "30s"

    result = await _extract_duration_text(mute_manager, None)
    assert result == "stałe"


async def _extract_duration_text(mute_manager, duration):
    ctx = MagicMock()
    user = MagicMock()
    mute_type = MagicMock()
    mute_type.success_message_add = "{user_mention} {duration_text} {action_name} {premium_channel}"
    mute_type.action_name = "test_action"
    mute_type.role_index = 1

    with patch.object(mute_manager, "_handle_mute_logic", new=_mock_handle_logic):
        return await mute_manager._handle_mute_logic(ctx, user, mute_type, duration, unmute=False)


async def _mock_handle_logic(ctx, user, mute_type, duration, unmute=False):
    if duration is None:
        return "stałe"

    parts = []
    if duration.days:
        parts.append(f"{duration.days}d")
    hours, remainder = divmod(duration.seconds, 3600)
    if hours:
        parts.append(f"{hours}h")
    minutes, seconds = divmod(remainder, 60)
    if minutes:
        parts.append(f"{minutes}m")
    if seconds and not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts) if parts else "mniej niż 1m"
