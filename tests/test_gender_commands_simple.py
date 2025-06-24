"""Simple tests for gender command logic."""

import pytest


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


MALE_ROLE = MockRole(960665311701528599, "♂")
FEMALE_ROLE = MockRole(960665311701528600, "♀")


def apply_male_role(user, male_role, female_role):
    if user.has_role(female_role):
        user.remove_role(female_role)
    if not user.has_role(male_role):
        user.add_role(male_role)
        return "added"
    return "already_has"


def apply_female_role(user, male_role, female_role):
    if user.has_role(male_role):
        user.remove_role(male_role)
    if not user.has_role(female_role):
        user.add_role(female_role)
        return "added"
    return "already_has"


def test_male_role_logic():
    user = MockUser()
    assert apply_male_role(user, MALE_ROLE, FEMALE_ROLE) == "added"
    assert user.has_role(MALE_ROLE)
    assert not user.has_role(FEMALE_ROLE)

    assert apply_male_role(user, MALE_ROLE, FEMALE_ROLE) == "already_has"

    user2 = MockUser()
    user2.add_role(FEMALE_ROLE)
    assert apply_male_role(user2, MALE_ROLE, FEMALE_ROLE) == "added"
    assert MALE_ROLE in user2.roles and FEMALE_ROLE not in user2.roles


def test_female_role_logic():
    user = MockUser()
    assert apply_female_role(user, MALE_ROLE, FEMALE_ROLE) == "added"
    assert user.has_role(FEMALE_ROLE)
    assert not user.has_role(MALE_ROLE)

    assert apply_female_role(user, MALE_ROLE, FEMALE_ROLE) == "already_has"

    user2 = MockUser()
    user2.add_role(MALE_ROLE)
    assert apply_female_role(user2, MALE_ROLE, FEMALE_ROLE) == "added"
    assert FEMALE_ROLE in user2.roles and MALE_ROLE not in user2.roles


def validate_gender_config(config):
    gender_roles = config.get("gender_roles", {})
    male_id = gender_roles.get("male")
    female_id = gender_roles.get("female")
    if not male_id:
        return "missing_male"
    if not female_id:
        return "missing_female"
    return "valid"


def test_config_validation():
    valid = {"gender_roles": {"male": 960665311701528599, "female": 960665311701528600}}
    assert validate_gender_config(valid) == "valid"

    missing_male = {"gender_roles": {"female": 960665311701528600}}
    assert validate_gender_config(missing_male) == "missing_male"

    missing_female = {"gender_roles": {"male": 960665311701528599}}
    assert validate_gender_config(missing_female) == "missing_female"

    empty = {}
    assert validate_gender_config(empty) == "missing_male"
