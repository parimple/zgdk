" test functions for client.py cog"
import pytest
from ...cogs.commands.client import add_numbers

class TestClient:
    def test_add_numbers(self):
        assert add_numbers(1, 2, 3) == 6, "Should be 6"

    def test_add_numbers2(self):
        assert add_numbers(1, 2, 5) == 8, "Should be 8"

    def test_add_numbers3(self):
        assert add_numbers(1, 2, 10) == 13, "Should be 13"
