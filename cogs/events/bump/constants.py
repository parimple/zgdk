"""Constants for bump services."""

# Bot IDs and configurations
DISBOARD = {
    "id": 302050872383242240,
    "description": [
        "!",
        ":thumbsup:",
        ":sob:",
        "👍",
        "DISBOARD에서 확인하십시오",
        "Schau es dir auf DISBOARD",
        "Allez vérifier ça sur DISBOARD",
        "Zobacz aktualizację na stronie DISBOARD",
        "Check it on DISBOARD",
        "Échale un vistazo en DISBOARD",
        "Podbito serwer",
        "Server bumped",
    ],
    "ping_id": 764443772108013578,
    "message_bot": "Można już zbumpować kanał ❤️ Wpisz /bump ",
    "message_bump": "Można już zbumpować kanał ❤️ Wpisz /bump ",
    "command": "!d bump",
}

DZIK = {
    "id": 1270093920256393248,  # Top.gg bot ID
    "name": "Top.gg",
    "success_messages": ["głosujący", "głosów", "dziękujemy"],
}

DISCADIA = {
    "id": 1222548162741538938,
    "cooldown_messages": [
        "already bumped recently",
        "try again in",
        ":warning:",
        "can only bump every",
        "you must wait",
        "cooldown",
        "⏱️",
        "please wait",
        "❌",
    ],
    "success_messages": ["successfully", "✅", "congrats", "bump recorded", "thanks"],
}

DISCORDSERVERS = {
    "id": 1123608076092780615,
    "success_messages": [
        "successfully",
        "✅",
        "success",
        "confirmed",
        "Thanks for",
        "Good job!",
    ],
    "cooldown_messages": [
        "already bumped",
        "cooldown",
        "please wait",
        "try again in",
        ":warning:",
        "⏱️",
    ],
}

DSME = {
    "id": 830166826635509770,
    "success_messages": ["successfully", "✅", "voted", "thanks", "recorded"],
    "cooldown_messages": [
        "already voted",
        "cooldown",
        "please wait",
        "try again in",
        ":warning:",
        "⏱️",
    ],
}

# Service names for consistency
SERVICE_NAMES = {
    "disboard": "disboard",
    "dzik": "dzik",
    "discadia": "discadia",
    "discordservers": "discordservers",
    "dsme": "dsme",
}

# Bypass durations from config
BYPASS_DURATIONS = {
    "disboard": 3,  # 3T za bump na Disboard
    "dzik": 3,  # 3T za bump na Dziku
    "discadia": 6,  # 6T za głos na Discadia
    "discordservers": 6,  # 6T za głos na DiscordServers
    "dsme": 3,  # 3T za głos na DSME
}

# Cooldowns in hours
SERVICE_COOLDOWNS = {
    "disboard": 2,  # 2 hours global cooldown
    "dzik": 3,  # 3 hours per user cooldown
    "discadia": 24,  # 24 hours per user cooldown
    "discordservers": 12,  # 12 hours per user cooldown
    "dsme": 6,  # 6 hours per user cooldown
}