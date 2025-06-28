"""Fix premium role mapping to use config role IDs."""

# Create a simple mapping file that the bot can use
PREMIUM_ROLE_DISCORD_IDS = {
    "zG50": 1306588378829164565,
    "zG100": 1306588380141846528,
    "zG500": 1317129475271557221,
    "zG1000": 1321432424101576705
}

# Write this mapping to a file the bot can import
mapping_content = '''"""Premium role Discord ID mappings."""

# Discord role IDs for premium roles
PREMIUM_ROLE_DISCORD_IDS = {
    "zG50": 1306588378829164565,
    "zG100": 1306588380141846528,
    "zG500": 1317129475271557221,
    "zG1000": 1321432424101576705
}

def get_premium_role_discord_id(role_name: str) -> int:
    """Get Discord role ID for a premium role name."""
    return PREMIUM_ROLE_DISCORD_IDS.get(role_name)
'''

with open("premium_role_mapping.py", "w") as f:
    f.write(mapping_content)
    
print("Created premium_role_mapping.py file")
print("This file needs to be imported and used in the premium service")