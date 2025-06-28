"""Pytest fixtures for the commands cog."""

import sys
import types
from unittest.mock import MagicMock, AsyncMock

# Mock Discord modules BEFORE any imports (gentler approach)
# Following your brilliant solution A - stub only what we need, leave commands alone
discord_mock = types.ModuleType("discord")          # bare module
discord_ext_mock = types.ModuleType("discord.ext")
discord_ui_mock = types.ModuleType("discord.ui")
discord_ui_mock.View = MagicMock()                   # shop_views needs it

# Add essential discord attributes
discord_mock.Member = MagicMock
discord_mock.User = MagicMock
discord_mock.Color = MagicMock()
discord_mock.Color.blue = MagicMock(return_value=MagicMock())
discord_mock.Color.green = MagicMock(return_value=MagicMock())
discord_mock.Color.red = MagicMock(return_value=MagicMock())
discord_mock.Color.yellow = MagicMock(return_value=MagicMock())
discord_mock.Embed = MagicMock
discord_mock.Forbidden = Exception
discord_mock.utils = MagicMock()
discord_mock.ui = discord_ui_mock

sys.modules["discord"] = discord_mock
sys.modules["discord.ext"] = discord_ext_mock
sys.modules["discord.ui"] = discord_ui_mock
# ← no sys.modules["discord.ext.commands"] assignment here!

# Mock other problematic modules
sys.modules['utils.permissions'] = MagicMock()
sys.modules['utils.currency'] = MagicMock()
sys.modules['core.interfaces.member_interfaces'] = MagicMock()
sys.modules['core.interfaces.premium_interfaces'] = MagicMock()
sys.modules['cogs.ui.shop_embeds'] = MagicMock()
sys.modules['cogs.views.shop_views'] = MagicMock()

# Mock datasources and its submodules properly
datasources_mod = types.ModuleType("datasources")

# Mock datasources.queries
queries_mod = types.ModuleType("datasources.queries")
class _HPQ:  # HandledPaymentQueries
    add_payment = AsyncMock()
    get_payment_by_id = AsyncMock()
    get_last_payments = AsyncMock()
queries_mod.HandledPaymentQueries = _HPQ

# Mock datasources.models
models_mod = types.ModuleType("datasources.models")
models_base_mod = types.ModuleType("datasources.models.base")
models_base_mod.Base = MagicMock()
models_mod.base = models_base_mod

# Mock all model classes
for model_name in ['Member', 'MemberRole', 'Activity', 'Role', 'HandledPayment', 
                   'Invite', 'AutoKick', 'ModerationLog', 'ChannelPermission', 
                   'Message', 'NotificationLog']:
    setattr(models_mod, model_name, MagicMock())

# Set up module hierarchy
datasources_mod.queries = queries_mod
datasources_mod.models = models_mod

sys.modules["datasources"] = datasources_mod
sys.modules["datasources.queries"] = queries_mod
sys.modules["datasources.models"] = models_mod
sys.modules["datasources.models.base"] = models_base_mod

# Mock utils.premium with working PaymentData
mock_premium = types.ModuleType('utils.premium')
class PaymentData:
    def __init__(self, name, amount, paid_at, payment_type):
        self.name = name
        self.amount = amount
        self.paid_at = paid_at
        self.payment_type = payment_type
mock_premium.PaymentData = PaymentData
mock_premium.PremiumManager = MagicMock()
mock_premium.TipplyDataProvider = MagicMock()
sys.modules['utils.premium'] = mock_premium

# Now safe to import
import discord
import pytest
# Note: discord.ext.commands is now stubbed per-test for flexibility

# Import fixture modules
from tests.fixtures.database_fixtures import *  # noqa
from tests.fixtures.service_fixtures import *  # noqa


@pytest.fixture
def bot() -> MagicMock:
    """Fixture for the Bot"""
    bot_mock = MagicMock()  # Remove spec since commands.Bot not available here
    # Dodaj podstawową konfigurację dla testów
    bot_mock.config = {
        "voice_permission_levels": {},
        "team": {},
        "premium_roles": [
            {"name": "zG50", "moderator_count": 1},
            {"name": "zG100", "moderator_count": 2},
            {"name": "zG500", "moderator_count": 5},
            {"name": "zG1000", "moderator_count": 10},
        ],
        "prefix": ",",
        "channels_voice": {"afk": 123456789},
        "voice_permissions": {
            "commands": {
                "speak": {"require_bypass_if_no_role": True},
                "view": {"require_bypass_if_no_role": True},
                "connect": {"require_bypass_if_no_role": True},
                "text": {"require_bypass_if_no_role": True},
                "live": {"require_bypass_if_no_role": True},
                "mod": {
                    "require_bypass_if_no_role": False,
                    "allowed_roles": ["zG50", "zG100", "zG500", "zG1000"],
                },
                "autokick": {
                    "require_bypass_if_no_role": False,
                    "allowed_roles": ["zG500", "zG1000"],
                },
            }
        },
    }
    return bot_mock


@pytest.fixture
def ctx() -> MagicMock:
    """Fixture for the Context"""
    ctx_mock = MagicMock()  # Remove spec since commands.Context not available here
    # Popraw kolor żeby był prawidłowym obiektem Discord Color
    ctx_mock.author.color = discord.Color.blue()
    return ctx_mock
