"""
Utility functions for creating mocks in tests
"""
from unittest.mock import AsyncMock, MagicMock


def make_async_cm(result):
    """Create async context manager that returns result"""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=result)
    cm.__aexit__ = AsyncMock(return_value=None)
    return cm


def make_mock_bot():
    """Create fully configured mock bot with all async services"""
    bot = MagicMock()

    # Database session with async commit (following your checklist)
    session = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()

    # Database context manager
    bot.get_db = MagicMock(return_value=make_async_cm(session))

    # Member service with async methods
    member_service = AsyncMock()
    member_service.get_or_create_member = AsyncMock(
        return_value=AsyncMock(wallet_balance=1000)
    )
    member_service.update_member_info = AsyncMock()

    # Premium service with async methods
    premium_service = AsyncMock()
    premium_service.get_member_premium_roles = AsyncMock(return_value=[])
    premium_service.assign_premium_role = AsyncMock()
    premium_service.remove_premium_role = AsyncMock()

    # Service mapping
    def get_service_mock(interface, session=None):
        interface_str = str(interface)
        if 'Member' in interface_str:
            return member_service
        elif 'Premium' in interface_str:
            return premium_service
        else:
            return AsyncMock()

    bot.get_service = AsyncMock(side_effect=get_service_mock)

    # Bot config for RoleShopView and other components
    bot.config = {
        "premium_roles": [
            {"name": "zG50", "price": 49, "duration": 30},
            {"name": "zG100", "price": 99, "duration": 30},
        ],
        "emojis": {
            "success": "✅",
            "error": "❌",
        },
        "channels": {
            "premium_info": 123456789,
        }
    }

    return bot


def make_mock_context():
    """Create mock Discord context with async methods (following your checklist)"""
    ctx = MagicMock()
    ctx.author = MagicMock()
    ctx.author.id = 123456789
    ctx.author.display_name = "TestUser"
    ctx.author.mention = "<@123456789>"

    ctx.guild = MagicMock()
    ctx.guild.id = 987654321
    ctx.guild.roles = []

    ctx.channel = MagicMock()
    ctx.channel.id = 111111111

    # Async methods - ensure ctx.reply is AsyncMock
    ctx.reply = AsyncMock()
    ctx.send = AsyncMock()
    ctx.defer = AsyncMock()

    return ctx


def make_mock_user(user_id=123456789):
    """Create mock Discord user with async methods"""
    user = MagicMock()
    user.id = user_id
    user.name = "TestUser"
    user.display_name = "TestUser"
    user.mention = f"<@{user_id}>"
    user.send = AsyncMock()

    return user


def make_mock_member(user_id=123456789):
    """Create mock Discord member (extends user)"""
    member = make_mock_user(user_id)
    member.roles = []
    member.add_roles = AsyncMock()
    member.remove_roles = AsyncMock()

    return member


def patch_shop_queries():
    """Return dict of common shop query patches"""
    return {
        'cogs.commands.shop.HandledPaymentQueries.add_payment': AsyncMock,
        'cogs.commands.shop.HandledPaymentQueries.get_payment_by_id': AsyncMock,
        'cogs.commands.shop.HandledPaymentQueries.get_last_payments': AsyncMock,
    }


def create_shop_cog_with_mocks():
    """Create ShopCog with all necessary mocks applied"""
    from cogs.commands.shop import ShopCog

    bot = make_mock_bot()
    shop_cog = ShopCog(bot)
    # Override bot to ensure our mock is used
    shop_cog.bot = bot

    return shop_cog, bot
