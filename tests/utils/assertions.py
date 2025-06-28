"""
Custom assertions for Discord bot testing.
"""

import re
from typing import Any, Dict


def assert_user_mentioned(response: Dict[str, Any], user_id: str) -> bool:
    """Assert that a user is mentioned in the response."""
    mention_pattern = f"<@{user_id}>"

    # Check in content
    content = response.get("content") or ""
    if mention_pattern in content:
        return True

    # Check in embeds
    embeds = response.get("embeds", [])
    for embed in embeds:
        # Check description
        if mention_pattern in embed.get("description", ""):
            return True

        # Check fields
        fields = embed.get("fields", [])
        for field in fields:
            if mention_pattern in field.get("value", ""):
                return True

    return False


def assert_has_timestamp(response: Dict[str, Any]) -> bool:
    """Assert that response contains a Discord timestamp."""
    # Discord timestamp pattern: <t:1234567890:R>
    timestamp_pattern = r"<t:\d+:[RFDTf]>"

    # Check in content
    content = response.get("content") or ""
    if re.search(timestamp_pattern, content):
        return True

    # Check in embeds
    embeds = response.get("embeds", [])
    for embed in embeds:
        # Check description
        if re.search(timestamp_pattern, embed.get("description", "")):
            return True

        # Check fields
        fields = embed.get("fields", [])
        for field in fields:
            if re.search(timestamp_pattern, field.get("value", "")):
                return True

    return False


def assert_premium_info(response: Dict[str, Any]) -> bool:
    """Assert that response contains premium information."""
    premium_indicators = [
        "<#960665316109713421>",  # Premium channel
        "<:mastercard:",  # Mastercard emoji
        "premium",
        "Wybierz swój"
    ]

    # Check in content
    content = response.get("content") or ""
    for indicator in premium_indicators:
        if indicator in content.lower():
            return True

    # Check in embeds
    embeds = response.get("embeds", [])
    for embed in embeds:
        # Check description
        desc = embed.get("description", "")
        for indicator in premium_indicators:
            if indicator in desc or indicator.lower() in desc.lower():
                return True

    return False


def extract_embed_info(response: Dict[str, Any]) -> Dict[str, Any]:
    """Extract key information from embed response."""
    embeds = response.get("embeds", [])
    if not embeds:
        return {}

    embed = embeds[0]  # Take first embed

    info = {
        "title": embed.get("title"),
        "description": embed.get("description"),
        "color": embed.get("color"),
        "fields": {}
    }

    # Extract fields
    fields = embed.get("fields", [])
    for field in fields:
        name = field.get("name", "")
        value = field.get("value", "")
        info["fields"][name] = value

    return info


def assert_mute_response_valid(response: Dict[str, Any], user_id: str,
                             mute_type: str, is_unmute: bool = False) -> bool:
    """Assert that a mute/unmute response is valid."""
    if not response.get("embeds"):
        return False

    # Check user mention
    if not assert_user_mentioned(response, user_id):
        return False

    # Check premium info
    if not assert_premium_info(response):
        return False

    embed_desc = response["embeds"][0].get("description", "")

    # Check action text based on type
    action_texts = {
        "txt": "wysyłania wiadomości",
        "img": "wysyłania obrazków i linków",
        "nick": "zmiany nicku",
        "live": "streamowania",
        "rank": "zdobywania punktów rankingowych"
    }

    expected_action = action_texts.get(mute_type)
    if not expected_action:
        return False

    if is_unmute:
        return f"Przywrócono możliwość {expected_action}" in embed_desc
    else:
        return f"Zablokowano możliwość {expected_action}" in embed_desc or \
               "Nałożono karę" in embed_desc  # For nick mute


class ModAssertions:
    """Assertions for moderation commands."""

    @staticmethod
    def assert_user_muted(response, user, mute_type, duration=None):
        """Assert user was muted successfully."""
        assert f"{user.mention} został wyciszony" in response.content
        if duration:
            assert str(duration) in response.content
        assert mute_type.upper() in response.content

    @staticmethod
    def assert_user_unmuted(response, user, mute_type):
        """Assert user was unmuted successfully."""
        assert f"{user.mention}" in response.content
        assert "odciszony" in response.content
        assert mute_type.upper() in response.content

    @staticmethod
    def assert_user_warned(response, user, reason=None):
        """Assert user was warned successfully."""
        assert f"{user.mention}" in response.content
        assert "ostrzeżenie" in response.content.lower()
        if reason:
            assert reason in response.content


class VoiceAssertions:
    """Assertions for voice commands."""

    @staticmethod
    def assert_permission_updated(response, permission_name, value):
        """Assert voice permission was updated."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        # Check permission name (handle both English and Polish names)
        permission_map = {
            "speak": "mówienia",
            "view_channel": "widzenia",
            "connect": "połączenia",
            "send_messages": "pisania",
            "stream": "streamowania",
            "manage_messages": "moderatora"
        }

        polish_name = permission_map.get(permission_name, permission_name)
        assert polish_name in content.lower() or permission_name in content.lower()

        # Check value set
        if value is True:
            assert "nadano" in content or "włączono" in content or "dodano" in content
        elif value is False:
            assert "odebrano" in content or "wyłączono" in content or "usunięto" in content

    @staticmethod
    def assert_mod_updated(response, user, added):
        """Assert channel moderator was added/removed."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert user.mention in content
        if added:
            assert "dodano" in content or "moderator" in content
        else:
            assert "usunięto" in content or "odebrano" in content

    @staticmethod
    def assert_channel_limit_set(response, limit):
        """Assert channel limit was set."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert "limit" in content.lower()
        assert str(limit) in content

    @staticmethod
    def assert_autokick_updated(response, user, added):
        """Assert user was added/removed from autokick list."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert user.mention in content
        assert "autokick" in content.lower()
        if added:
            assert "dodano" in content
        else:
            assert "usunięto" in content


class ShopAssertions:
    """Assertions for shop commands."""

    @staticmethod
    def assert_balance_updated(response, user, amount):
        """Assert user balance was updated."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert user.mention in content
        assert str(amount) in content
        assert "G" in content  # Currency symbol

    @staticmethod
    def assert_role_purchased(response, user, role_name):
        """Assert role was purchased successfully."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert "zakupiono" in content.lower() or "kupiono" in content.lower()
        assert role_name in content

    @staticmethod
    def assert_role_sold(response, user, role_name, refund_amount):
        """Assert role was sold successfully."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert "sprzedano" in content.lower() or "zwrócono" in content.lower()
        assert role_name in content
        assert str(refund_amount) in content

    @staticmethod
    def assert_shop_displayed(response, balance):
        """Assert shop is displayed with correct balance."""
        assert hasattr(response, 'title') or hasattr(response, 'embeds')

        if hasattr(response, 'title'):
            assert "sklep" in response.title.lower()

        if hasattr(response, 'footer'):
            assert f"Portfel: {balance} G" in response.footer.text


class PremiumAssertions:
    """Assertions for premium features."""

    @staticmethod
    def assert_premium_required(response):
        """Assert premium access is required."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert "premium" in content.lower() or "wymagana" in content.lower()

    @staticmethod
    def assert_color_changed(response, color):
        """Assert color was changed successfully."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert "kolor" in content.lower()
        assert "zmieniono" in content.lower() or "ustawiono" in content.lower()

    @staticmethod
    def assert_team_created(response, team_name):
        """Assert team was created successfully."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert "utworzono" in content.lower()
        assert "team" in content.lower()
        assert team_name in content or f"☫ {team_name}" in content

    @staticmethod
    def assert_payment_assigned(response, payment_id, user):
        """Assert payment was assigned to user."""
        if hasattr(response, 'content'):
            content = response.content
        else:
            content = response.description if hasattr(response, 'description') else str(response)

        assert str(payment_id) in content
        assert user.mention in content
        assert "przypisano" in content.lower() or "assigned" in content.lower()
