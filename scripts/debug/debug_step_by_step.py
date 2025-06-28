"""
Debug step by step which await is failing
"""
import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock, patch

# Mock all imports
sys.modules['discord'] = MagicMock()
sys.modules['discord.ext'] = MagicMock()
sys.modules['discord.ext.commands'] = MagicMock()
sys.modules['utils.permissions'] = MagicMock()
sys.modules['utils.premium'] = MagicMock()
sys.modules['core.interfaces.member_interfaces'] = MagicMock()
sys.modules['core.interfaces.premium_interfaces'] = MagicMock()
sys.modules['datasources.queries'] = MagicMock()
sys.modules['cogs.ui.shop_embeds'] = MagicMock()
sys.modules['cogs.views.shop_views'] = MagicMock()

async def debug_each_await():
    print("Starting step-by-step debug...")
    
    # Create all the mocks similar to fixtures
    mock_bot = MagicMock()
    
    # Mock get_db with proper async context manager
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_bot.get_db = MagicMock(return_value=mock_context_manager)
    
    # Mock get_service
    mock_member_service = AsyncMock()
    mock_db_member = MagicMock()
    mock_db_member.wallet_balance = 1000
    mock_member_service.get_or_create_member = AsyncMock(return_value=mock_db_member)
    mock_member_service.update_member_info = AsyncMock()
    
    mock_bot.get_service = AsyncMock(return_value=mock_member_service)
    
    # Mock context and user
    mock_ctx = MagicMock()
    mock_ctx.author = MagicMock()
    mock_ctx.author.display_name = "TestUser"
    mock_ctx.reply = AsyncMock()
    
    mock_user = MagicMock()
    mock_user.id = 123456789
    mock_user.mention = "<@123456789>"
    
    amount = 500
    
    print("1. Testing bot.get_db()...")
    async with mock_bot.get_db() as session:
        print("✓ bot.get_db() works")
        
        print("2. Testing bot.get_service()...")
        member_service = await mock_bot.get_service("IMemberService", session)
        print("✓ bot.get_service() works")
        
        print("3. Testing HandledPaymentQueries.add_payment()...")
        with patch('datasources.queries.HandledPaymentQueries.add_payment', new_callable=AsyncMock) as mock_add_payment:
            await mock_add_payment(session, mock_user.id, "TestUser", amount, None, "command")
            print("✓ HandledPaymentQueries.add_payment() works")
        
        print("4. Testing member_service.get_or_create_member()...")
        db_member = await member_service.get_or_create_member(mock_user)
        print("✓ member_service.get_or_create_member() works")
        
        print("5. Testing member_service.update_member_info()...")
        new_balance = db_member.wallet_balance + amount
        await member_service.update_member_info(db_member, wallet_balance=new_balance)
        print("✓ member_service.update_member_info() works")
        
        print("6. Testing session.commit()...")
        await session.commit()
        print("✓ session.commit() works")
    
    print("7. Testing ctx.reply()...")
    await mock_ctx.reply(f"Dodano {amount} do portfela {mock_user.mention}.")
    print("✓ ctx.reply() works")
    
    print("All individual awaits work! Now testing actual ShopCog...")
    
    # Import and test ShopCog
    from cogs.commands.shop import ShopCog
    
    with patch('cogs.commands.shop.HandledPaymentQueries.add_payment', new_callable=AsyncMock):
        shop_cog = ShopCog(mock_bot)
        print("ShopCog created successfully")
        
        print("About to call add_balance...")
        await shop_cog.add_balance(mock_ctx, mock_user, amount)
        print("✓ ShopCog.add_balance() works!")

if __name__ == "__main__":
    asyncio.run(debug_each_await())