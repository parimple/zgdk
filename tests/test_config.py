"""
Test configuration for Discord bot integration tests
"""

# Test Environment Configuration
TEST_CONFIG = {
    "guild_id": 960665311701528596,
    "test_channel_id": 1387864734002446407,
    "test_user_id": 968632323916566579,
    "bot_token_env": "CLAUDE_BOT",
    "main_bot_token_env": "ZAGADKA_TOKEN",
}

# Test Data
TEST_SCENARIOS = {
    "balance_test": {
        "initial_amount": 1000,
        "expected_balance": 1000,
    },
    "role_purchase": {
        "role_name": "zG50",
        "role_price": 49,
        "expected_balance_after": 1000 - 49,
    },
    "shop_display": {
        "expected_roles": ["zG50", "zG100", "zG500", "zG1000"],
    }
}

# Commands to Test
COMMANDS_TO_TEST = [
    {
        "name": "addbalance",
        "type": "owner_only", 
        "description": "Add balance to user wallet",
        "test_params": ["@user", "1000"],
    },
    {
        "name": "profile",
        "type": "public",
        "description": "Display user profile with balance",
        "test_params": [],
    },
    {
        "name": "shop", 
        "type": "admin",
        "description": "Display premium shop",
        "test_params": [],
    },
    {
        "name": "ping",
        "type": "public", 
        "description": "Basic connectivity test",
        "test_params": [],
    },
]

# Expected Error Scenarios
ERROR_SCENARIOS = [
    {
        "name": "insufficient_balance",
        "description": "Try to buy role with insufficient balance",
        "setup": {"balance": 10, "role_price": 49},
        "expected_error": "insufficient funds",
    },
    {
        "name": "invalid_role",
        "description": "Try to buy non-existent role", 
        "expected_error": "role not found",
    },
]