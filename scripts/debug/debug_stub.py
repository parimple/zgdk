#!/usr/bin/env python3
"""Debug stub installation"""

import sys

print("=== BEFORE STUB ===")
print(f"discord.ext.commands in sys.modules: {'discord.ext.commands' in sys.modules}")
if "discord.ext.commands" in sys.modules:
    cmd_mod = sys.modules["discord.ext.commands"]
    print(f"Type: {type(cmd_mod)}")
    print(f"Cog: {getattr(cmd_mod, 'Cog', 'MISSING')}")

# Install stub
from tests.utils import install_commands_stub

stub = install_commands_stub()

print("\n=== AFTER STUB ===")
print(f"Stub returned: {stub}")
print(f"Stub Cog: {stub.Cog}")
print(f"sys.modules['discord.ext.commands']: {sys.modules['discord.ext.commands']}")
print(f"Same object? {stub is sys.modules['discord.ext.commands']}")

# Try importing ShopCog
print("\n=== IMPORTING SHOPCOG ===")
from cogs.commands.shop import ShopCog

print(f"ShopCog: {ShopCog}")
print(f"ShopCog.__bases__: {ShopCog.__bases__}")

if hasattr(ShopCog.__bases__[0], "__name__"):
    print(f"Base class name: {ShopCog.__bases__[0].__name__}")
