"""
Test constants for maintainability and consistency
Based on config.yml structure for realistic test data
"""

# Guild and Bot Configuration (based on config.yml)
GUILD_ID = 960665311701528596
PREFIX = ","
DESCRIPTION = "Hello, my name is zaGadka"

# Owner IDs (from config.yml)
MAIN_OWNER_ID = 956602391891947592
TEST_USER_OWNER_ID = 968632323916566579
CLAUDE_USER_ID = 1387857653748732046

# Additional Test User IDs
TEST_USER_1_ID = 968632323916566579
TEST_USER_2_ID = 987654321000000001
TEST_USER_3_ID = 987654321000000002
TEST_USER_4_ID = 987654321000000003
TEST_USER_5_ID = 987654321000000004
BOT_USER_ID = 987654321000000099

# Channel IDs (from config.yml)
CHANNEL_ON_JOIN = 1105588284555546634
CHANNEL_LOUNGE = 1143990867946913845
CHANNEL_DONATION = 960665312200626201
CHANNEL_PREMIUM_INFO = 960665316109713421
CHANNEL_BOTS = 960665312200626198
CHANNEL_MUTE_NOTIFICATIONS = 1336368306940018739
CHANNEL_MUTE_LOGS = 1379568677623562300
CHANNEL_UNMUTE_LOGS = 1379568677623562300

# Voice Channel IDs
CHANNEL_AFK = 1052997299233636402

# Test-specific Channel IDs
TEST_CHANNEL_ID = 1100000000000000001

# Message IDs for testing
MESSAGE_BASE_ID = 2000000000
BOT_MESSAGE_BASE_ID = 3000000000
WEBHOOK_MESSAGE_BASE_ID = 4000000000

# Role IDs (from config.yml)
ROLE_MOD_ID = 960665311953174564  # ✪ mod
ROLE_ADMIN_ID = 960665311953174565  # ✪ admin

# Premium Role IDs (from config.yml audit_settings)
ROLE_ZG50_ID = 1306588378829164565
ROLE_ZG100_ID = 1306588380141846528
ROLE_ZG500_ID = 1317129475271557221
ROLE_ZG1000_ID = 1321432424101576705

# Color Role IDs (from config.yml)
ROLE_BLUE_ID = 960665311730868235
ROLE_GREEN_ID = 960665311730868236
ROLE_RED_ID = 960665311730868237

# Gender Role IDs
ROLE_MALE_ID = 960665311701528599
ROLE_FEMALE_ID = 960665311701528600

# Mute Role IDs (from config.yml)
ROLE_STREAM_OFF_ID = 960665311760248873  # ⚠︎
ROLE_SEND_MESSAGES_OFF_ID = 960665311953174559  # ⌀
ROLE_ATTACH_FILES_OFF_ID = 960665311953174558  # ☢︎
ROLE_POINTS_OFF_ID = 960665311760248877  # ♺

# Test Role IDs
TEST_ROLE_1_ID = 1000000001
TEST_ROLE_2_ID = 1000000002
TEST_ROLE_3_ID = 1000000003
PREMIUM_ROLE_ID = 1000000004
VIP_ROLE_ID = 1000000005

# Emojis (from config.yml)
EMOJI_PROXY_BUNNY = "<a:bunnyProxy:1301144820349403157>"
EMOJI_MASTERCARD = "<:mastercard:1270433919233425545>"

# Test Emojis
EMOJI_SUCCESS = "✅"
EMOJI_ERROR = "❌"
EMOJI_STAR = "✪"

# Role Names
ROLE_NAMES = {
    "mod": "✪",
    "admin": "✪",
    "zg50": "zG50",
    "zg100": "zG100",
    "zg500": "zG500",
    "zg1000": "zG1000",
    "blue": "blue",
    "green": "green",
    "red": "red",
    "test1": "TestRole1",
    "test2": "TestRole2",
    "test3": "TestRole3",
    "premium": "Premium",
    "vip": "VIP",
    "nitro_booster": "♵",
    "server_booster": "♼"
}

# Premium Roles Configuration (from config.yml)
PREMIUM_ROLES_CONFIG = [
    {
        "name": "zG50",
        "premium": "Git",
        "usd": 14,
        "price": 49,
        "team_size": 0,
        "moderator_count": 1,
        "points_multiplier": 50,
        "emojis_access": False,
        "override_limit": True,
        "features": [
            "Dowolny kolor dostępny za pomocą komendy ?color",
            "Dostęp do kanału głosowego Git",
            "Dostęp do emotek i stickerów z każdego serwera",
            "50% więcej punktów do aktywności"
        ]
    },
    {
        "name": "zG100",
        "premium": "Git Plus",
        "price": 99,
        "usd": 29,
        "team_size": 10,
        "moderator_count": 2,
        "points_multiplier": 100,
        "emojis_access": False,
        "override_limit": True,
        "features": [
            "Rola na samej górze serwera",
            "Kanał drużynowy dla 15 osób",
            "Kanał Git Plus do tworzenia kanałów głosowych",
            "Moderator kanału głosowego",
            "Dostęp do emotek i stickerów z każdego serwera",
            "100% więcej punktów do aktywności"
        ]
    },
    {
        "name": "zG500",
        "premium": "Git Pro",
        "price": 499,
        "usd": 149,
        "team_size": 20,
        "moderator_count": 3,
        "points_multiplier": 200,
        "emojis_access": False,
        "override_limit": False,
        "auto_kick": 1,
        "features": [
            "Rola wyżej niż top1",
            "Kanał Git Pro nad lounge do tworzenia kanałów głosowych",
            "Drużyna do 30 osób",
            "3 moderatorów kanału głosowego",
            "Wszyscy w drużynie mają kolor klanu na serwerze",
            "Dostęp do emotek i stickerów z każdego serwera",
            "200% więcej punktów do aktywności",
            "Autokick 1 osoby na każdym kanale"
        ]
    },
    {
        "name": "zG1000",
        "premium": "Git Ultra",
        "price": 999,
        "usd": 299,
        "team_size": 30,
        "moderator_count": 5,
        "points_multiplier": 400,
        "emojis_access": False,
        "override_limit": False,
        "auto_kick": 3,
        "features": [
            "Moderator na serwerze",
            "Kanał Git Ultra nad info do tworzenia kanałów głosowych",
            "Drużyna do 50 osób",
            "6 moderatorów kanału głosowego",
            "Wszyscy w drużynie mają kolor klanu na serwerze",
            "Moliwość dodania emotki na serwer raz w miesiącu",
            "Moliwość dodania odznaki emotki całej drużynie",
            "300% więcej punktów do aktywności",
            "Autokick 3 osób na każdym kanale"
        ]
    }
]

# Bot Configuration for Tests
BOT_CONFIG = {
    "guild_id": GUILD_ID,
    "prefix": PREFIX,
    "owner_ids": [MAIN_OWNER_ID, TEST_USER_OWNER_ID, CLAUDE_USER_ID],
    "admin_roles": {
        "mod": ROLE_MOD_ID,
        "admin": ROLE_ADMIN_ID
    },
    "premium_roles": PREMIUM_ROLES_CONFIG,
    "emojis": {
        "proxy_bunny": EMOJI_PROXY_BUNNY,
        "mastercard": EMOJI_MASTERCARD,
        "success": EMOJI_SUCCESS,
        "error": EMOJI_ERROR
    },
    "channels": {
        "on_join": CHANNEL_ON_JOIN,
        "lounge": CHANNEL_LOUNGE,
        "donation": CHANNEL_DONATION,
        "premium_info": CHANNEL_PREMIUM_INFO,
        "bots": CHANNEL_BOTS
    }
}

# Wallet Balances for Testing
WALLET_BALANCES = {
    "empty": 0,
    "low": 100,
    "medium": 1000,
    "high": 5000,
    "zg50_price": 49,
    "zg100_price": 99,
    "zg500_price": 499,
    "zg1000_price": 999,
    "maximum": 999999999
}

# Sample Payment Data
SAMPLE_PAYMENT_DATA = {
    "id": "payment_123",
    "member_id": TEST_USER_1_ID,
    "name": "TestUser Payment",
    "amount": 500,
    "payment_type": "role_purchase",
    "role_name": "zG50",
    "duration_days": 30,
    "paid_at": "2024-01-01T00:00:00Z"
}

# Error Messages
ERROR_MESSAGES = {
    "no_balance": "Brak środków",
    "no_permission": "Brak uprawnień",
    "invalid_amount": "Nieprawidłowa kwota",
    "role_not_found": "Nie znaleziono roli",
    "database_error": "Błąd bazy danych",
    "no_premium_role": "nie ma żadnej roli premium",
    "admin_only": "administratorów",
    "no_messages": "Brak wiadomości do wylosowania",
    "no_eligible_users": "Nie znaleziono żadnych użytkowników"
}

# Legacy System Configuration (from config.yml)
LEGACY_SYSTEM = {
    "enabled": True,
    "amounts": {
        15: 49,   # zG50
        25: 99,   # zG100
        45: 499,  # zG500
        85: 999   # zG1000
    }
}

# Voice Channel Categories (from config.yml)
VC_CATEGORIES = [
    1325436667359662100,  # git ultra
    1325436219714441267,  # git pro
    1325435639260516442,  # git plus
    960665318475325454,   # git
    1325439014488117278,  # priv
    1325439940351229962,  # publ
    1325440354648068206,  # max2
    1325440407605346335,  # max3
    1325440479499649075,  # max4
    1325440557161648160   # max5
]

# Channel Creation IDs
CHANNELS_CREATE = [
    1325445547586359307,  # git ultra
    1057676020209168436,  # git pro
    1325445609074987100,  # git plus
    1325445576946614274,  # git
    1325445737206513727,  # priv
    1325445679706935296,  # publ
    1325445657858670622,  # max2
    1325445711436714095,  # max3
    1325445884967780442,  # max4
    1325445638002970684   # max5
]
