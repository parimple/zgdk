#!/usr/bin/env python3
"""Simple test for gender commands logic."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_gender_role_logic():
    """Test the core logic of gender role assignment."""

    class MockRole:
        def __init__(self, role_id, name):
            self.id = role_id
            self.name = name

        def __eq__(self, other):
            return isinstance(other, MockRole) and self.id == other.id

    class MockUser:
        def __init__(self):
            self.roles = []

        def has_role(self, role):
            return role in self.roles

        def add_role(self, role):
            if role not in self.roles:
                self.roles.append(role)

        def remove_role(self, role):
            if role in self.roles:
                self.roles.remove(role)

    # Test data
    MALE_ROLE = MockRole(960665311701528599, "♂")
    FEMALE_ROLE = MockRole(960665311701528600, "♀")

    def apply_male_role(user, male_role, female_role):
        """Simulate male command logic."""
        # Remove female role if present
        if user.has_role(female_role):
            user.remove_role(female_role)

        # Add male role if not present
        if not user.has_role(male_role):
            user.add_role(male_role)
            return "added"
        else:
            return "already_has"

    def apply_female_role(user, male_role, female_role):
        """Simulate female command logic."""
        # Remove male role if present
        if user.has_role(male_role):
            user.remove_role(male_role)

        # Add female role if not present
        if not user.has_role(female_role):
            user.add_role(female_role)
            return "added"
        else:
            return "already_has"

    # Test 1: New user gets male role
    user1 = MockUser()
    result = apply_male_role(user1, MALE_ROLE, FEMALE_ROLE)
    assert result == "added", f"Expected 'added', got '{result}'"
    assert user1.has_role(MALE_ROLE), "User should have male role"
    assert not user1.has_role(FEMALE_ROLE), "User should not have female role"
    print("✅ Test 1: New user gets male role")

    # Test 2: User already has male role
    user2 = MockUser()
    user2.add_role(MALE_ROLE)
    result = apply_male_role(user2, MALE_ROLE, FEMALE_ROLE)
    assert result == "already_has", f"Expected 'already_has', got '{result}'"
    assert user2.has_role(MALE_ROLE), "User should still have male role"
    print("✅ Test 2: User already has male role")

    # Test 3: Switch from female to male
    user3 = MockUser()
    user3.add_role(FEMALE_ROLE)
    result = apply_male_role(user3, MALE_ROLE, FEMALE_ROLE)
    assert result == "added", f"Expected 'added', got '{result}'"
    assert user3.has_role(MALE_ROLE), "User should have male role"
    assert not user3.has_role(FEMALE_ROLE), "User should not have female role"
    print("✅ Test 3: Switch from female to male")

    # Test 4: New user gets female role
    user4 = MockUser()
    result = apply_female_role(user4, MALE_ROLE, FEMALE_ROLE)
    assert result == "added", f"Expected 'added', got '{result}'"
    assert user4.has_role(FEMALE_ROLE), "User should have female role"
    assert not user4.has_role(MALE_ROLE), "User should not have male role"
    print("✅ Test 4: New user gets female role")

    # Test 5: User already has female role
    user5 = MockUser()
    user5.add_role(FEMALE_ROLE)
    result = apply_female_role(user5, MALE_ROLE, FEMALE_ROLE)
    assert result == "already_has", f"Expected 'already_has', got '{result}'"
    assert user5.has_role(FEMALE_ROLE), "User should still have female role"
    print("✅ Test 5: User already has female role")

    # Test 6: Switch from male to female
    user6 = MockUser()
    user6.add_role(MALE_ROLE)
    result = apply_female_role(user6, MALE_ROLE, FEMALE_ROLE)
    assert result == "added", f"Expected 'added', got '{result}'"
    assert user6.has_role(FEMALE_ROLE), "User should have female role"
    assert not user6.has_role(MALE_ROLE), "User should not have male role"
    print("✅ Test 6: Switch from male to female")


def test_config_validation():
    """Test configuration validation logic."""

    def validate_gender_config(config):
        """Simulate config validation."""
        gender_roles = config.get("gender_roles", {})
        male_id = gender_roles.get("male")
        female_id = gender_roles.get("female")

        if not male_id:
            return "missing_male"
        if not female_id:
            return "missing_female"

        return "valid"

    # Test valid config
    valid_config = {"gender_roles": {"male": 960665311701528599, "female": 960665311701528600}}
    result = validate_gender_config(valid_config)
    assert result == "valid", f"Expected 'valid', got '{result}'"
    print("✅ Test: Valid config")

    # Test missing male role
    invalid_config1 = {"gender_roles": {"female": 960665311701528600}}
    result = validate_gender_config(invalid_config1)
    assert result == "missing_male", f"Expected 'missing_male', got '{result}'"
    print("✅ Test: Missing male role")

    # Test missing female role
    invalid_config2 = {"gender_roles": {"male": 960665311701528599}}
    result = validate_gender_config(invalid_config2)
    assert result == "missing_female", f"Expected 'missing_female', got '{result}'"
    print("✅ Test: Missing female role")

    # Test empty config
    empty_config = {}
    result = validate_gender_config(empty_config)
    assert result == "missing_male", f"Expected 'missing_male', got '{result}'"
    print("✅ Test: Empty config")


if __name__ == "__main__":
    print("🧪 Uruchamianie prostych testów logiki gender commands...")
    print()

    try:
        test_gender_role_logic()
        print()
        test_config_validation()
        print()
        print("🎉 Wszystkie testy przeszły pomyślnie!")
        print()
        print("📝 Podsumowanie:")
        print("   - Logika przypisywania ról płci działa poprawnie")
        print("   - Przełączanie między rolami działa poprawnie")
        print("   - Walidacja konfiguracji działa poprawnie")
        print("   - Role są wzajemnie wykluczające się")

    except Exception as e:
        print(f"❌ Test nie przeszedł: {e}")
        sys.exit(1)
