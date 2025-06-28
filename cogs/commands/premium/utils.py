"""Utility functions for premium commands."""

import httpx


def emoji_validator(emoji_str: str) -> bool:
    """
    Check if the string is a valid Discord server emoji.

    :param emoji_str: String to check
    :return: True if string is a valid emoji, False otherwise
    """
    # Check if string is in format <:name:id> or <a:name:id>
    if not emoji_str.startswith("<") or not emoji_str.endswith(">"):
        return False

    parts = emoji_str.strip("<>").split(":")

    # Check if we have the right number of parts
    if len(parts) != 3 and len(parts) != 2:
        return False

    # If we have 3 parts, check if the first is 'a' (animated) or empty
    if len(parts) == 3 and parts[0] not in ["", "a"]:
        return False

    # Check if the last part (ID) is a number
    try:
        int(parts[-1])
        return True
    except ValueError:
        return False


async def emoji_to_icon(emoji_str: str) -> bytes:
    """
    Convert emoji to icon bytes.

    :param emoji_str: Emoji string to convert
    :return: Icon bytes
    """
    # Extract emoji ID from format <:name:id> or <a:name:id>
    emoji_id = emoji_str.split(":")[-1].rstrip(">")

    # Create URL for emoji icon
    # If emoji is animated (format <a:name:id>), use GIF extension
    is_animated = emoji_str.startswith("<a:")
    extension = "gi" if is_animated else "png"
    url = f"https://cdn.discordapp.com/emojis/{emoji_id}.{extension}"

    # Download icon
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code == 200:
            return response.content
        else:
            raise ValueError(f"Cannot download emoji. Status: {response.status_code}")
