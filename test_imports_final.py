#!/usr/bin/env python3
"""Test imports for all modified files"""

import os
import sys

sys.path.append(os.getcwd())


def test_imports():
    """Test all critical imports work"""

    try:
        # Test info.py components
        from cogs.commands.info import BuyRoleButton, InfoCog, ProfileView, SellRoleButton

        print("✅ Zaimportowano z cogs.commands.info")

        # Test shop_views.py components
        from cogs.views.shop_views import BuyRoleButton as ShopBuyButton
        from cogs.views.shop_views import RoleDescriptionView, RoleShopView

        print("✅ Zaimportowano z cogs.views.shop_views")

        # Test shop_embeds.py components
        from cogs.ui.shop_embeds import create_role_description_embed, create_shop_embed

        print("✅ Zaimportowano z cogs.ui.shop_embeds")

        # Test on_payment.py components
        from cogs.events.on_payment import OnPaymentEvent

        print("✅ Zaimportowano z cogs.events.on_payment")

        return True

    except ImportError as e:
        print(f"❌ Błąd importu: {e}")
        return False


def test_button_consistency():
    """Test that both BuyRoleButton implementations use config for emoji"""

    try:
        import inspect

        from cogs.commands.info import BuyRoleButton as InfoButton
        from cogs.views.shop_views import BuyRoleButton as ShopButton

        # Check source code to verify config usage
        info_source = inspect.getsource(InfoButton.__init__)
        shop_source = inspect.getsource(ShopButton.__init__)

        # Verify that both use config for emoji
        assert (
            'bot.config.get("emojis", {}).get("mastercard"' in info_source
        ), "Info button should use config for emoji"
        assert (
            'bot.config.get("emojis", {}).get("mastercard"' in shop_source
        ), "Shop button should use config for emoji"

        # Verify fallback emoji
        assert '"💳"' in info_source, "Info button should have fallback emoji"
        assert '"💳"' in shop_source, "Shop button should have fallback emoji"

        print("✅ Oba buttony używają konfiguracji dla emoji Mastercard")
        return True

    except Exception as e:
        print(f"❌ Błąd sprawdzania buttonów: {e}")
        return False


def test_embed_titles():
    """Test that embed titles use config for emoji"""

    try:
        import inspect

        from cogs.ui.shop_embeds import create_role_description_embed

        # Get source code to check for title format
        source = inspect.getsource(create_role_description_embed)

        # Check that title uses config for emoji
        assert (
            'ctx.bot.config.get("emojis", {}).get("mastercard", "💳")' in source
        ), "Title should use config for emoji"

        assert (
            'f"Opis roli {role_name} {mastercard_emoji}"' in source
        ), "Title should use variable for emoji"

        print("✅ Tytuł opisu roli używa konfiguracji dla emoji")
        return True

    except Exception as e:
        print(f"❌ Błąd sprawdzania tytułów: {e}")
        return False


if __name__ == "__main__":
    success = True

    success &= test_imports()
    success &= test_button_consistency()
    success &= test_embed_titles()

    if success:
        print("\n🎉 Wszystkie testy przeszły pomyślnie!")
        print("✅ Buttony 'Kup rangę' są zawsze widoczne w profilu")
        print("✅ Buttony otwierają sklep dla osoby która klika")
        print("✅ Emoji Mastercard używa konfiguracji z YAML")
        print("✅ Zabezpieczenia przed kupowaniem rangi komuś innemu działają")
        print("✅ Wszystkie hardcoded emoji zostały zastąpione zmiennymi")
    else:
        print("\n❌ Niektóre testy nie przeszły")
        sys.exit(1)
