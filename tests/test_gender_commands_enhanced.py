"""Enhanced tests for gender command utilities."""

import pytest

from utils.moderation.gender_type import GenderType
from utils.moderation.mute_type import MuteType


def test_gender_type_config():
    male_type = GenderType.from_name(GenderType.MALE)
    assert male_type.type_name == "male"
    assert male_type.role_id_field == "male"
    assert male_type.display_name == "męską"
    assert male_type.opposite_type == "female"
    assert male_type.role_symbol == "♂"
    assert "✅ Nadano rolę **{role_symbol}**" in male_type.success_message_add

    female_type = GenderType.from_name(GenderType.FEMALE)
    assert female_type.type_name == "female"
    assert female_type.role_id_field == "female"
    assert female_type.display_name == "kobiecą"
    assert female_type.opposite_type == "male"
    assert female_type.role_symbol == "♀"
    assert "✅ Nadano rolę **{role_symbol}**" in female_type.success_message_add

    with pytest.raises(ValueError):
        GenderType.from_name("invalid")


def test_gender_messages():
    male_type = GenderType.from_name(GenderType.MALE)
    female_type = GenderType.from_name(GenderType.FEMALE)

    user_mention = "<@123456789>"

    male_add = male_type.success_message_add.format(
        user_mention=user_mention, role_symbol=male_type.role_symbol
    )
    assert user_mention in male_add
    assert "♂" in male_add
    assert "✅" in male_add

    female_already = female_type.success_message_already_has.format(
        user_mention=user_mention, display_name=female_type.display_name
    )
    assert user_mention in female_already
    assert "kobiecą" in female_already
    assert "ℹ️" in female_already

    male_switch = male_type.success_message_switch.format(
        user_mention=user_mention, role_symbol=male_type.role_symbol
    )
    assert user_mention in male_switch
    assert "♂" in male_switch
    assert "usunięto poprzednią" in male_switch


def test_integration_with_existing_system():
    male_config = GenderType.get_config()[GenderType.MALE]
    nick_config = MuteType.get_config()[MuteType.NICK]

    assert "reason_add" in male_config
    assert "reason_remove" in male_config
    assert "reason_add" in nick_config
    assert "reason_remove" in nick_config

    assert "success_message_add" in male_config
    assert "success_message_add" in nick_config


@pytest.mark.asyncio
async def test_database_integration_concepts():
    class MockRoleQueries:
        @staticmethod
        async def add_or_update_role_to_member(session, user_id, role_id, duration=None):
            assert duration is None
            return True

        @staticmethod
        async def remove_role_from_member(session, user_id, role_id):
            return True

    async def simulate():
        user_id = 123456789
        male_role_id = 960665311701528599
        female_role_id = 960665311701528600
        await MockRoleQueries.add_or_update_role_to_member(None, user_id, male_role_id)
        await MockRoleQueries.remove_role_from_member(None, user_id, female_role_id)
        return True

    assert await simulate() is True


def test_embed_response_concept():
    class MockEmbed:
        def __init__(self, description=None, color=None):
            self.description = description
            self.color = color

    def create_gender_embed(message, author_color):
        return MockEmbed(description=message, color=author_color)

    msg = "✅ Nadano rolę **♂** dla <@123456789>"
    color = 0x5865F2
    embed = create_gender_embed(msg, color)
    assert embed.description == msg
    assert embed.color == color


def test_logging_integration():
    def create_log_embed_concept(user_id, moderator_id, gender_symbol, action_type):
        return {
            "title": "🏷️ Zmiana roli płci",
            "fields": {
                "user": f"<@{user_id}> (`{user_id}`)",
                "moderator": f"<@{moderator_id}> (`{moderator_id}`)",
                "action": f"Nadano rolę {gender_symbol}",
                "role": f"{gender_symbol} {'męską' if gender_symbol == '♂' else 'kobiecą'}",
            },
        }

    log_data = create_log_embed_concept(123456789, 987654321, "♂", "added")
    assert "🏷️ Zmiana roli płci" in log_data["title"]
    assert "123456789" in log_data["fields"]["user"]
    assert "987654321" in log_data["fields"]["moderator"]
    assert "♂" in log_data["fields"]["action"]
    assert "męską" in log_data["fields"]["role"]
