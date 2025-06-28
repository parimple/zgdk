"""
Reusable lightweight Discord commands stub for testing.
Implements the user's brilliant pass-through decorator approach.
"""
import importlib
import sys
import types
from unittest.mock import AsyncMock, MagicMock


def install_commands_stub():
    """
    Install user's brilliant lightweight commands stub before importing cogs.

    This creates real classes that inherit from a lightweight _Cog instead of MagicMock,
    preserving coroutine nature with pass-through decorators.
    """
    # First ensure discord modules are properly mocked if not already done
    if "discord" not in sys.modules:
        discord_mock = types.ModuleType("discord")
        discord_mock.Member = MagicMock
        discord_mock.User = MagicMock
        discord_mock.Guild = MagicMock
        discord_mock.Role = MagicMock
        discord_mock.TextChannel = MagicMock
        discord_mock.VoiceChannel = MagicMock
        discord_mock.Message = MagicMock
        discord_mock.Interaction = MagicMock
        discord_mock.Color = MagicMock()
        discord_mock.Color.blue = MagicMock(return_value=MagicMock())
        discord_mock.Color.green = MagicMock(return_value=MagicMock())
        discord_mock.Color.red = MagicMock(return_value=MagicMock())
        discord_mock.Embed = MagicMock
        discord_mock.utils = MagicMock()
        discord_mock.Forbidden = Exception

        # Mock discord.ui
        discord_ui_mock = types.ModuleType("discord.ui")
        discord_ui_mock.View = MagicMock
        discord_ui_mock.Button = MagicMock
        discord_ui_mock.Select = MagicMock
        discord_ui_mock.button = lambda **kwargs: lambda func: func
        discord_ui_mock.select = lambda **kwargs: lambda func: func
        discord_mock.ui = discord_ui_mock

        sys.modules["discord"] = discord_mock
        sys.modules["discord.ui"] = discord_ui_mock

        if "discord.ext" not in sys.modules:
            sys.modules["discord.ext"] = types.ModuleType("discord.ext")

    # Ensure discord.ui is available even if discord was already mocked
    if not hasattr(sys.modules["discord"], "ui"):
        discord_ui_mock = types.ModuleType("discord.ui")
        discord_ui_mock.View = MagicMock
        discord_ui_mock.Button = MagicMock
        discord_ui_mock.Select = MagicMock
        discord_ui_mock.button = lambda **kwargs: lambda func: func
        discord_ui_mock.select = lambda **kwargs: lambda func: func
        sys.modules["discord"].ui = discord_ui_mock
        sys.modules["discord.ui"] = discord_ui_mock

    commands_stub = types.ModuleType("discord.ext.commands")

    def passthrough_decorator(*args, **kwargs):
        """Pass-through decorator that preserves coroutine nature"""
        def wrap(fn):
            return fn
        return wrap

    class _Cog:
        """Ultra-light Cog base class that keeps .bot attribute"""
        def __init__(self, bot):
            self.bot = bot

    # Essential commands module components
    commands_stub.Cog = _Cog
    commands_stub.Command = type("Command", (), {})
    commands_stub.Bot = MagicMock
    commands_stub.Context = MagicMock

    # Pass-through decorators that preserve coroutines
    commands_stub.hybrid_command = passthrough_decorator
    commands_stub.command = passthrough_decorator
    commands_stub.has_permissions = passthrough_decorator

    # Mock other required modules if not already mocked
    if 'utils.permissions' not in sys.modules:
        permissions_mock = MagicMock()
        permissions_mock.is_zagadka_owner = passthrough_decorator
        permissions_mock.is_admin = passthrough_decorator
        sys.modules['utils.permissions'] = permissions_mock

    if 'utils.premium' not in sys.modules:
        premium_mock = MagicMock()

        class PaymentData:
            def __init__(self, name, amount, paid_at, payment_type):
                self.name = name
                self.amount = amount
                self.paid_at = paid_at
                self.payment_type = payment_type
        premium_mock.PaymentData = PaymentData
        sys.modules['utils.premium'] = premium_mock

    if 'core.interfaces.member_interfaces' not in sys.modules:
        sys.modules['core.interfaces.member_interfaces'] = MagicMock()

    if 'core.interfaces.premium_interfaces' not in sys.modules:
        sys.modules['core.interfaces.premium_interfaces'] = MagicMock()

    if 'cogs.ui.shop_embeds' not in sys.modules:
        sys.modules['cogs.ui.shop_embeds'] = MagicMock()

    if 'cogs.views.shop_views' not in sys.modules:
        views_mock = MagicMock()
        views_mock.PaymentsView = MagicMock
        views_mock.RoleShopView = MagicMock
        sys.modules['cogs.views.shop_views'] = views_mock

    if 'datasources.queries' not in sys.modules:
        queries_mock = MagicMock()
        queries_mock.HandledPaymentQueries = MagicMock()
        queries_mock.HandledPaymentQueries.add_payment = AsyncMock()
        sys.modules['datasources.queries'] = queries_mock

    # Install the stub
    sys.modules["discord.ext.commands"] = commands_stub

    # Reload any modules that might have already imported the old mock
    modules_to_reload = [
        "cogs.commands.shop",
        "cogs.commands"
    ]
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            module = sys.modules[module_name]
            # Only reload real modules, not MagicMocks
            if hasattr(module, '__spec__') and hasattr(module, '__name__'):
                importlib.reload(module)
            else:
                # Remove mock module so it gets re-imported fresh
                del sys.modules[module_name]

    return commands_stub
