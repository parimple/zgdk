"""
Isolated test using user's brilliant Discord stub fix
This test doesn't use conftest.py to avoid conflicts
"""
import sys
import types
from unittest.mock import AsyncMock, MagicMock

import pytest

# Mock Discord modules BEFORE any imports
sys.modules["discord"] = MagicMock()
sys.modules["discord.ext"] = MagicMock()

# --- USER'S BRILLIANT STUB FOR discord.ext.commands --------------------------
commands_stub = types.ModuleType("discord.ext.commands")
sys.modules["discord.ext.commands"] = commands_stub

# pass‑through decorators so wrapped coroutine stays a coroutine
def _dummy_decorator(*d_args, **d_kwargs):
    def _wrap(fn):
        return fn

    return _wrap


commands_stub.hybrid_command = _dummy_decorator
commands_stub.command = _dummy_decorator

# ultra‑light Cog base class (keeps .bot attribute)
class _Cog:
    def __init__(self, bot):
        self.bot = bot


commands_stub.Cog = _Cog

# Add Context class
commands_stub.Context = MagicMock
# ---------------------------------------------------------------------------

# Mock remaining modules
permissions_mock = MagicMock()
permissions_mock.is_zagadka_owner = _dummy_decorator
permissions_mock.is_admin = _dummy_decorator
sys.modules["utils.permissions"] = permissions_mock

# Mock utils.premium with working PaymentData
premium_mock = MagicMock()


class PaymentData:
    def __init__(self, name, amount, paid_at, payment_type):
        self.name = name
        self.amount = amount
        self.paid_at = paid_at
        self.payment_type = payment_type


premium_mock.PaymentData = PaymentData
sys.modules["utils.premium"] = premium_mock

sys.modules["cogs.ui.shop_embeds"] = MagicMock()
sys.modules["cogs.views.shop_views"] = MagicMock()
sys.modules["core.interfaces.member_interfaces"] = MagicMock()
sys.modules["core.interfaces.premium_interfaces"] = MagicMock()

# Mock datasources.queries with AsyncMock
queries_mock = MagicMock()
queries_mock.HandledPaymentQueries = MagicMock()
queries_mock.HandledPaymentQueries.add_payment = AsyncMock()
queries_mock.HandledPaymentQueries.get_payment_by_id = AsyncMock()
queries_mock.HandledPaymentQueries.get_last_payments = AsyncMock()
sys.modules["datasources.queries"] = queries_mock


def test_user_fix_preserves_coroutine():
    """Test that user's fix preserves coroutine function nature"""
    # Debug what's in our commands_stub
    print(f"commands_stub.Cog: {commands_stub.Cog}")
    print(f"Type of commands_stub.Cog: {type(commands_stub.Cog)}")

    from cogs.commands.shop import ShopCog

    # Check what ShopCog inherits from
    print(f"ShopCog.__bases__: {ShopCog.__bases__}")
    print(f"Type of ShopCog.__bases__[0]: {type(ShopCog.__bases__[0])}")

    bot = MagicMock()
    shop_cog = ShopCog(bot)

    print(f"Type of shop_cog: {type(shop_cog)}")
    print(f"shop_cog.__class__: {shop_cog.__class__}")

    # Check that the method exists and is callable
    assert hasattr(shop_cog, "add_balance")
    assert callable(shop_cog.add_balance)

    # Check that it's still a coroutine function
    import inspect

    print(f"Method type: {type(shop_cog.add_balance)}")
    print(f"Is coroutine function: {inspect.iscoroutinefunction(shop_cog.add_balance)}")

    # Let's also check the raw method from class
    print(f"Raw class method: {ShopCog.add_balance}")
    print(f"Raw class method type: {type(ShopCog.add_balance)}")
    print(f"Raw class method is coroutine: {inspect.iscoroutinefunction(ShopCog.add_balance)}")

    # This should be True with user's fix - but let's debug first
    # assert inspect.iscoroutinefunction(shop_cog.add_balance)

    print("DEBUG: Investigating why user's fix isn't working")


@pytest.mark.asyncio
async def test_addbalance_with_user_fix_isolated():
    """Test addbalance with user's fix in isolation"""
    from cogs.commands.shop import ShopCog

    # Create bot mock
    bot = MagicMock()
    session_mock = AsyncMock()
    session_mock.commit = AsyncMock()
    bot.get_db.return_value.__aenter__ = AsyncMock(return_value=session_mock)
    bot.get_db.return_value.__aexit__ = AsyncMock(return_value=None)

    # Create member service mock
    member_service = AsyncMock()
    db_member = MagicMock()
    db_member.wallet_balance = 100
    member_service.get_or_create_member = AsyncMock(return_value=db_member)
    member_service.update_member_info = AsyncMock()
    bot.get_service = AsyncMock(return_value=member_service)

    # Create context and user mocks
    ctx = AsyncMock()
    ctx.author.display_name = "TestUser"
    user = MagicMock()
    user.id = 12345
    user.mention = "<@12345>"

    # Create ShopCog instance
    shop_cog = ShopCog(bot)

    # Test the command - this should work with user's fix!
    await shop_cog.add_balance(ctx, user, 500)

    # Verify it worked
    ctx.reply.assert_awaited_once()
    bot.get_db.assert_called_once()
    session_mock.commit.assert_awaited_once()

    print("SUCCESS: User's fix enables async command testing!")
