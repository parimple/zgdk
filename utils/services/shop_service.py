"""Shop service providing an interface to shop functionality."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import discord
from discord.ext.commands import Context

from utils.errors import ResourceNotFoundError, ZGDKError
from utils.managers.shop_manager import ShopManager
from utils.services import BaseService, ServiceResult


class ShopService(BaseService):
    """Service for handling shop operations."""

    def __init__(self, bot):
        """Initialize the shop service with a bot instance."""
        super().__init__(bot)
        self.shop_manager = ShopManager(bot)

    async def get_shop_data(self, viewer_id: int, target_member_id: int) -> Dict[str, Any]:
        """Get shop data including balance and premium roles.

        Args:
            viewer_id: The Discord ID of the viewer
            target_member_id: The Discord ID of the target member

        Returns:
            Dictionary containing shop data
        """
        return await self.shop_manager.get_shop_data(viewer_id, target_member_id)

    async def add_balance(
        self, admin: discord.Member, user: discord.User, amount: int
    ) -> Tuple[bool, str]:
        """Add balance to a user's wallet.

        Args:
            admin: The admin adding the balance
            user: The user to add balance to
            amount: The amount to add

        Returns:
            Tuple of (success, message)
        """
        return await self.shop_manager.add_balance(admin.display_name, user.id, amount)

    async def assign_payment(self, payment_id: int, user: discord.User) -> Tuple[bool, str]:
        """Assign a payment to a user.

        Args:
            payment_id: The ID of the payment to assign
            user: The user to assign the payment to

        Returns:
            Tuple of (success, message)
        """
        success, message = await self.shop_manager.assign_payment_to_user(payment_id, user.id)

        if success:
            # Try to send DM to the user
            try:
                await user.send(
                    "Proszę pamiętać o podawaniu swojego ID podczas dokonywania wpłat w przyszłości. Twoje ID to:"
                )
                await user.send(f"```{user.id}```")

                # Add to the success message
                message = f"{message}. DM sent to user."
            except discord.Forbidden:
                # Add to the success message
                message = f"{message}. Could not send DM to user."

        return success, message

    async def get_recent_payments(
        self, limit: int = 10, offset: int = 0
    ) -> Tuple[bool, str, Optional[List[Any]]]:
        """Get recent payments.

        Args:
            limit: The maximum number of payments to retrieve
            offset: The offset to start retrieving payments from

        Returns:
            Tuple of (success, message, payments)
        """
        try:
            payments = await self.shop_manager.get_recent_payments(limit, offset)
            return True, "Payments retrieved successfully", payments
        except Exception as e:
            return False, str(e), None

    async def set_role_expiry(
        self, member: discord.Member, hours: int, role_id: Optional[int] = None
    ) -> Tuple[bool, str, Optional[datetime]]:
        """Set the expiration time for a role.

        Args:
            member: The member whose role to set the expiry for
            hours: The number of hours until the role expires
            role_id: The ID of the role (optional, will use first premium role if not provided)

        Returns:
            Tuple of (success, message, new_expiry_date)
        """
        return await self.shop_manager.set_role_expiry(member.id, role_id, hours)

    async def check_expired_premium_roles(self, guild: discord.Guild) -> Tuple[bool, str, int]:
        """Check and remove expired premium roles.

        Args:
            guild: The Discord guild to check roles in

        Returns:
            Tuple of (success, message, count of removed roles)
        """
        try:
            count, errors = await self.shop_manager.check_expired_premium_roles(guild)

            if errors:
                return False, f"Removed {count} roles with {len(errors)} errors", count
            else:
                return True, f"Successfully removed {count} expired roles", count
        except Exception as e:
            return False, str(e), 0
