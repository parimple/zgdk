"""Configuration for command prefixes to avoid conflicts with other bots."""

# Commands that should have a unique prefix to avoid conflicts
PREFIXED_COMMANDS = {
    # Common commands that many bots use
    "help": "zg_help",
    "stats": "zg_stats", 
    "profile": "zg_profile",
    "shop": "zg_shop",
    "ranking": "zg_ranking",
    "mute": "zg_mute",
    "unmute": "zg_unmute",
    "timeout": "zg_timeout",
    "clear": "zg_clear",
    
    # Keep original aliases for user convenience
    "aliases": {
        "zg_help": ["help", "pomoc"],
        "zg_profile": ["profile", "p"],
        "zg_shop": ["shop", "sklep"],
        "zg_ranking": ["ranking", "top", "topka"],
    }
}

# Commands that are unique enough to not need prefixing
UNIQUE_COMMANDS = [
    "zagadka",
    "bypass",
    "addt",
    "checkroles",
    "przypisz_wplate",
    "games",
    "serverinfo",
    "createcategory",
    "deletecategory",
]

# Admin/owner commands that don't need prefixing
ADMIN_COMMANDS = [
    "reload",
    "reboot", 
    "sync",
    "eval",
    "sql",
]