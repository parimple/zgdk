"""
Ultra clean addbalance tests using the reusable commands stub.
Demonstrates user's brilliant pass-through decorator approach.
"""
import pytest
from tests.utils import make_mock_bot, make_mock_context, make_mock_user, install_commands_stub


@pytest.mark.asyncio
async def test_addbalance_ultraclean():
    """Test using user's brilliant approach - minimal green test"""
    # stub commands **before** importing the cog
    install_commands_stub()

    from cogs.commands.shop import ShopCog
    
    bot = make_mock_bot()
    ctx = make_mock_context()
    user = make_mock_user()

    shop = ShopCog(bot)
    await shop.add_balance(ctx, user, 500)

    ctx.reply.assert_awaited_once()
    bot.get_db.assert_called_once()


@pytest.mark.asyncio
async def test_addbalance_negative_ultraclean():
    """Test negative amount with ultra clean setup"""
    install_commands_stub()
    
    from cogs.commands.shop import ShopCog
    
    bot = make_mock_bot()
    ctx = make_mock_context()
    user = make_mock_user()
    
    shop = ShopCog(bot)
    await shop.add_balance(ctx, user, -100)
    
    ctx.reply.assert_awaited_once()
    reply_call = ctx.reply.call_args[0][0]
    assert "-100" in reply_call


def test_addbalance_signature_ultraclean():
    """Test command signature with ultra clean setup"""
    install_commands_stub()
    
    from cogs.commands.shop import ShopCog
    
    bot = make_mock_bot()
    shop = ShopCog(bot)
    assert hasattr(shop, 'add_balance')
    assert callable(shop.add_balance)
    
    # Bonus: verify it's a real coroutine function
    import inspect
    assert inspect.iscoroutinefunction(shop.add_balance)