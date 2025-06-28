import asyncio
import sys
from unittest.mock import AsyncMock, MagicMock, patch

# Mock Discord before any imports
sys.modules["discord"] = MagicMock()
sys.modules["discord.ext"] = MagicMock()
sys.modules["discord.ext.commands"] = MagicMock()
sys.modules["utils.permissions"] = MagicMock()
sys.modules["utils.premium"] = MagicMock()
sys.modules["core.interfaces.member_interfaces"] = MagicMock()
sys.modules["datasources.queries"] = MagicMock()

from cogs.commands.shop import ShopCog


async def debug_test():
    # Create mocks
    mock_bot = MagicMock()
    mock_bot.get_service = AsyncMock(return_value=AsyncMock())

    mock_session = AsyncMock()
    mock_context_manager = AsyncMock()
    mock_context_manager.__aenter__ = AsyncMock(return_value=mock_session)
    mock_context_manager.__aexit__ = AsyncMock(return_value=None)
    mock_bot.get_db = MagicMock(return_value=mock_context_manager)

    mock_ctx = MagicMock()
    mock_ctx.reply = AsyncMock()
    mock_ctx.author = MagicMock()
    mock_ctx.author.display_name = "TestUser"

    mock_user = MagicMock()
    mock_user.id = 123456789
    mock_user.mention = "<@123456789>"

    # Patch the database query
    with patch("cogs.commands.shop.HandledPaymentQueries.add_payment", new_callable=AsyncMock):
        try:
            shop_cog = ShopCog(mock_bot)
            print("ShopCog created successfully")

            print("About to call add_balance...")
            await shop_cog.add_balance(mock_ctx, mock_user, 500)
            print("add_balance completed successfully!")

        except Exception as e:
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()

            # Let's try to debug step by step
            print("\nDebugging step by step...")
            print("1. Creating PaymentData...")
            from datetime import datetime, timezone

            from datasources.models.payment_data import PaymentData

            payment_data = PaymentData(
                name=mock_ctx.author.display_name,
                amount=500,
                paid_at=datetime.now(timezone.utc),
                payment_type="command",
            )
            print("PaymentData created")

            print("2. Getting database session...")
            async with mock_bot.get_db() as session:
                print("Got database session")

                print("3. Getting member service...")
                member_service = await mock_bot.get_service("IMemberService", session)
                print("Got member service")

                print("4. Test finished - the issue is elsewhere")


if __name__ == "__main__":
    asyncio.run(debug_test())
