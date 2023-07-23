"""Handles conversion of datetime objects to Discord timestamp format."""

import datetime


class DiscordTimestamp:
    """Handles conversion of datetime objects to Discord timestamp format."""

    FORMATS = {
        "t": "Krótki format czasu",
        "T": "Długi format czasu",
        "d": "Krótki format daty",
        "D": "Długi format daty",
        "f": "Krótki format daty i czasu",
        "F": "Długi format daty i czasu",
        "R": "Czas względny",
    }

    @staticmethod
    def format(dt: datetime.datetime, frmt: str) -> str:
        """Formats a datetime object to Discord timestamp format."""
        if frmt not in DiscordTimestamp.FORMATS:
            raise ValueError("Invalid format. Choose from 't', 'T', 'd', 'D', 'f', 'F', 'R'.")
        return f"<t:{int(dt.timestamp())}:{format}>"
