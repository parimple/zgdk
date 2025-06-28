"""Utility functions for moderation commands."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)


def parse_duration(duration_str: str) -> Optional[int]:
    """
    Parse duration string to seconds.

    :param duration_str: Duration string (e.g., "1h", "30m", "1d")
    :return: Duration in seconds or None for permanent
    """
    if not duration_str:
        return None

    # Simple duration parsing
    matches = re.findall(r"(\d+)([dhm]?)", duration_str.lower())
    total_seconds = 0

    for amount, unit in matches:
        amount = int(amount)
        if unit == "d":
            total_seconds += amount * 24 * 60 * 60
        elif unit == "h":
            total_seconds += amount * 60 * 60
        elif unit == "m":
            total_seconds += amount * 60
        else:
            # Default to hours if no unit specified
            total_seconds += amount * 60 * 60

    return total_seconds if total_seconds > 0 else None
