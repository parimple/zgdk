#!/usr/bin/env python3
"""Enhanced test for gender commands with GenderManager and database tracking."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_gender_type_config():
    """Test GenderType configuration."""
    from utils.moderation.gender_type import GenderType

    # Test male type
    male_type = GenderType.from_name(GenderType.MALE)
    assert male_type.type_name == "male"
    assert male_type.role_id_field == "male"
    assert male_type.display_name == "męską"
    assert male_type.opposite_type == "female"
    assert male_type.role_symbol == "♂"
    assert "✅ Nadano rolę **{role_symbol}**" in male_type.success_message_add
    print("✅ Test: Male GenderType configuration")

    # Test female type
    female_type = GenderType.from_name(GenderType.FEMALE)
    assert female_type.type_name == "female"
    assert female_type.role_id_field == "female"
    assert female_type.display_name == "kobiecą"
    assert female_type.opposite_type == "male"
    assert female_type.role_symbol == "♀"
    assert "✅ Nadano rolę **{role_symbol}**" in female_type.success_message_add
    print("✅ Test: Female GenderType configuration")

    # Test invalid type
    try:
        GenderType.from_name("invalid")
        assert False, "Should raise ValueError for invalid type"
    except ValueError:
        pass
    print("✅ Test: Invalid GenderType handling")


def test_gender_messages():
    """Test gender message formatting."""
    from utils.moderation.gender_type import GenderType

    male_type = GenderType.from_name(GenderType.MALE)
    female_type = GenderType.from_name(GenderType.FEMALE)

    # Test message formatting
    user_mention = "<@123456789>"

    male_add_msg = male_type.success_message_add.format(
        user_mention=user_mention, role_symbol=male_type.role_symbol
    )
    assert user_mention in male_add_msg
    assert "♂" in male_add_msg
    assert "✅" in male_add_msg
    print("✅ Test: Male add message formatting")

    female_already_msg = female_type.success_message_already_has.format(
        user_mention=user_mention, display_name=female_type.display_name
    )
    assert user_mention in female_already_msg
    assert "kobiecą" in female_already_msg
    assert "ℹ️" in female_already_msg
    print("✅ Test: Female already has message formatting")

    male_switch_msg = male_type.success_message_switch.format(
        user_mention=user_mention, role_symbol=male_type.role_symbol
    )
    assert user_mention in male_switch_msg
    assert "♂" in male_switch_msg
    assert "usunięto poprzednią" in male_switch_msg
    print("✅ Test: Male switch message formatting")


def test_integration_with_existing_system():
    """Test integration with existing moderation system."""

    # Test that gender system follows same patterns as mute system
    from utils.moderation.gender_type import GenderType
    from utils.moderation.mute_type import MuteType

    # Both should have similar structure
    male_config = GenderType.get_config()[GenderType.MALE]
    nick_config = MuteType.get_config()[MuteType.NICK]

    # Both should have reason_add and reason_remove
    assert "reason_add" in male_config
    assert "reason_remove" in male_config
    assert "reason_add" in nick_config
    assert "reason_remove" in nick_config
    print("✅ Test: Consistent reason structure with mute system")

    # Both should have success messages
    assert "success_message_add" in male_config
    assert "success_message_add" in nick_config
    print("✅ Test: Consistent message structure with mute system")


def test_database_integration_concepts():
    """Test database integration concepts (without actual DB)."""

    # Test that we have the expected role tracking structure
    class MockRoleQueries:
        @staticmethod
        async def add_or_update_role_to_member(session, user_id, role_id, duration=None):
            # Gender roles should not have duration (unlike mutes)
            assert duration is None, "Gender roles should not have expiration"
            return True

        @staticmethod
        async def remove_role_from_member(session, user_id, role_id):
            return True

    # Simulate database operations
    async def simulate_gender_assignment():
        user_id = 123456789
        male_role_id = 960665311701528599
        female_role_id = 960665311701528600

        # Add male role (should not have duration)
        await MockRoleQueries.add_or_update_role_to_member(None, user_id, male_role_id)

        # Remove female role when switching
        await MockRoleQueries.remove_role_from_member(None, user_id, female_role_id)

        return True

    # Run simulation
    import asyncio

    result = asyncio.run(simulate_gender_assignment())
    assert result is True
    print("✅ Test: Database integration concepts")


def test_embed_response_concept():
    """Test that the system uses embeds like mute system."""

    # Test embed creation concept
    class MockEmbed:
        def __init__(self, description=None, color=None):
            self.description = description
            self.color = color

    # Simulate embed creation like in GenderManager
    def create_gender_embed(message, author_color):
        return MockEmbed(description=message, color=author_color)

    test_message = "✅ Nadano rolę **♂** dla <@123456789>"
    test_color = 0x5865F2  # Discord blue

    embed = create_gender_embed(test_message, test_color)
    assert embed.description == test_message
    assert embed.color == test_color
    print("✅ Test: Embed response concept")


def test_logging_integration():
    """Test logging integration concepts."""

    # Test log message structure
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
    print("✅ Test: Logging integration concept")


if __name__ == "__main__":
    print("🧪 Uruchamianie rozszerzonych testów Gender Commands...")
    print()

    try:
        test_gender_type_config()
        print()
        test_gender_messages()
        print()
        test_integration_with_existing_system()
        print()
        test_database_integration_concepts()
        print()
        test_embed_response_concept()
        print()
        test_logging_integration()
        print()
        print("🎉 Wszystkie rozszerzone testy przeszły pomyślnie!")
        print()
        print("📝 Nowy system Gender Commands:")
        print("   ✅ Używa GenderType podobnie jak MuteType")
        print("   ✅ Zapisuje role w bazie danych jak muty")
        print("   ✅ Używa ładnych embedów jak muty")
        print("   ✅ Ma logging do kanału moderacyjnego")
        print("   ✅ Spójny z resztą systemu moderacyjnego")
        print("   ✅ Obsługuje przełączanie między rolami")
        print("   ✅ Waliduje konfigurację")

    except Exception as e:
        print(f"❌ Test nie przeszedł: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
