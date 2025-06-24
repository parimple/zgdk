"""Shop manager for business logic related to the shop."""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple, Union

import discord
from discord.ext.commands import Context

from datasources.queries import HandledPaymentQueries, MemberQueries, RoleQueries
from utils.errors import BusinessRuleViolationError, ResourceNotFoundError
from utils.managers import BaseManager
from utils.premium import PaymentData


class ShopManager(BaseManager):
    """Manager for shop business logic."""

    def __init__(self, bot):
        """Initialize the shop manager with a bot instance."""
        super().__init__(bot)

    async def assign_payment_to_user(self, payment_id: int, user_id: int) -> Tuple[bool, str]:
        """Assign a payment to a user and update their wallet balance.

        Args:
            payment_id: The ID of the payment to assign
            user_id: The Discord ID of the user to assign the payment to

        Returns:
            Tuple of (success, message)
        """
        try:
            async with self.bot.get_db() as session:
                payment = await HandledPaymentQueries.get_payment_by_id(session, payment_id)

                if not payment:
                    return False, f"Payment with ID {payment_id} not found"

                payment.member_id = user_id
                await MemberQueries.add_to_wallet_balance(session, user_id, payment.amount)
                await session.commit()

                return True, f"Payment assigned to user {user_id}"

        except Exception as e:
            return False, str(e)

    async def add_balance(self, admin_name: str, user_id: int, amount: int) -> Tuple[bool, str]:
        """Add balance to a user's wallet.

        Args:
            admin_name: The name of the admin adding the balance
            user_id: The Discord ID of the user to add balance to
            amount: The amount to add to the user's wallet

        Returns:
            Tuple of (success, message)
        """
        try:
            payment_data = PaymentData(
                name=admin_name,
                amount=amount,
                paid_at=datetime.now(timezone.utc),
                payment_type="command",
            )

            async with self.bot.get_db() as session:
                await HandledPaymentQueries.add_payment(
                    session,
                    user_id,
                    payment_data.name,
                    payment_data.amount,
                    payment_data.paid_at,
                    payment_data.payment_type,
                )
                await MemberQueries.get_or_add_member(session, user_id)
                await MemberQueries.add_to_wallet_balance(session, user_id, payment_data.amount)
                await session.commit()

            return True, f"Added {amount} to user's wallet"

        except Exception as e:
            return False, str(e)

    async def get_shop_data(self, viewer_id: int, target_member_id: int) -> Dict[str, Any]:
        """Get shop data including balance and premium roles.

        Args:
            viewer_id: The Discord ID of the viewer
            target_member_id: The Discord ID of the target member

        Returns:
            Dictionary containing shop data
        """
        async with self.bot.get_db() as session:
            db_viewer = await MemberQueries.get_or_add_member(session, viewer_id)
            balance = db_viewer.wallet_balance
            premium_roles = await RoleQueries.get_member_premium_roles(session, target_member_id)
            await session.commit()

        return {
            "balance": balance,
            "premium_roles": premium_roles,
        }

    async def get_recent_payments(self, limit: int = 10, offset: int = 0) -> List[Any]:
        """Get recent payments.

        Args:
            limit: The maximum number of payments to retrieve
            offset: The offset to start retrieving payments from

        Returns:
            List of payment objects
        """
        async with self.bot.get_db() as session:
            payments = await HandledPaymentQueries.get_last_payments(
                session, limit=limit, offset=offset
            )
            return payments

    async def set_role_expiry(
        self, member_id: int, role_id: Optional[int] = None, hours: int = 0
    ) -> Tuple[bool, str, Optional[datetime]]:
        """Set the expiration time for a role.

        Args:
            member_id: The Discord ID of the member
            role_id: The Discord ID of the role (optional, will use first premium role if not provided)
            hours: The number of hours until the role expires

        Returns:
            Tuple of (success, message, new_expiry_date)
        """
        try:
            async with self.bot.get_db() as session:
                premium_roles = await RoleQueries.get_member_premium_roles(session, member_id)

                if not premium_roles:
                    return False, "User has no premium roles", None

                # Get the first role if role_id is not specified
                if not role_id:
                    member_role, role = premium_roles[0]
                    role_id = role.id
                else:
                    # Verify the specified role exists for this member
                    role_found = False
                    for mr, r in premium_roles:
                        if r.id == role_id:
                            role_found = True
                            break

                    if not role_found:
                        return False, f"Role ID {role_id} not found for this member", None

                new_expiry = datetime.now(timezone.utc) + timedelta(hours=hours)

                await RoleQueries.update_role_expiration_date_direct(
                    session, member_id, role_id, new_expiry
                )
                await session.commit()

                return True, "Role expiry updated successfully", new_expiry

        except Exception as e:
            return False, str(e), None

    async def check_expired_premium_roles(self, guild: discord.Guild) -> Tuple[int, List[str]]:
        """Check and remove expired premium roles.

        Args:
            guild: The Discord guild to check roles in

        Returns:
            Tuple of (count of removed roles, list of error messages)
        """
        now = datetime.now(timezone.utc)
        count = 0
        errors = []

        # Get premium role configuration
        premium_role_names = {role["name"]: role for role in self.bot.config["premium_roles"]}

        # Find premium roles on the server
        premium_roles = [role for role in guild.roles if role.name in premium_role_names]

        # For each premium role
        for role in premium_roles:
            # Check members with this role
            for member in role.members:
                async with self.bot.get_db() as session:
                    db_role = await RoleQueries.get_member_role(session, member.id, role.id)

                    if not db_role or db_role.expiration_date <= now:
                        try:
                            await member.remove_roles(role)
                            count += 1

                            # If there was a DB entry, remove it
                            if db_role:
                                await RoleQueries.delete_member_role(session, member.id, role.id)

                        except Exception as e:
                            error_msg = f"Error removing role {role.name} from {member.display_name}: {str(e)}"
                            errors.append(error_msg)

        return count, errors
