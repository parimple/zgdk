"""
Test configuration for Discord bot testing.
"""

# Test user IDs (real users on the server)
TEST_USER_ID = "489328381972971520"  # Main test user
SECONDARY_TEST_USER_ID = "956602391891947592"  # Secondary test user

# Channel IDs
TEST_CHANNEL_ID = "1387864734002446407"

# Special user IDs
OWNER_ID = "956602391891947592"
BOT_ID = "1380757029420929136"  # deVelop bot ID

# API Configuration
API_BASE_URL = "http://localhost:8090"

# Test timeouts
COMMAND_TIMEOUT = 10  # seconds
CONNECTION_TIMEOUT = 5  # seconds

# Test data
TEST_MUTE_DURATIONS = ["1h", "2h", "1d", "30m"]
TEST_COLOR_CODES = ["#FF0000", "#00FF00", "#0000FF", "#FFFF00"]

# Expected role IDs (from config.yml)
MUTE_ROLE_IDS = {
    "stream_off": 1380907877874503742,  # ⚠︎
    "send_messages_off": 1380908038214389853,  # ⌀
    "attach_files_off": 1380908107852419156,  # ☢︎
    "points_off": 1380908187003183134,  # ♺
}