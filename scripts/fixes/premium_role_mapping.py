"""Premium role Discord ID mappings."""

# Discord role IDs for premium roles
PREMIUM_ROLE_DISCORD_IDS = {
    "zG50": 1306588378829164565,
    "zG100": 1306588380141846528,
    "zG500": 1317129475271557221,
    "zG1000": 1321432424101576705,
}


def get_premium_role_discord_id(role_name: str) -> int:
    """Get Discord role ID for a premium role name."""
    return PREMIUM_ROLE_DISCORD_IDS.get(role_name)
