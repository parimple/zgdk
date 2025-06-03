"""Simplified role sale logic with better error handling and atomicity."""
import logging
from datetime import datetime, timezone
from typing import Optional, Tuple

import discord
from sqlalchemy import text

from datasources.queries import MemberQueries, RoleQueries
from utils.currency import CURRENCY_UNIT
from utils.refund import calculate_refund

logger = logging.getLogger(__name__)


class RoleSaleManager:
    """Manages role sales with improved error handling and atomicity."""

    def __init__(self, bot):
        self.bot = bot

    async def sell_role(
        self, member: discord.Member, role: discord.Role, interaction: discord.Interaction
    ) -> Tuple[bool, str, Optional[int]]:
        """
        Sell a role for a member.

        Returns:
            Tuple[bool, str, Optional[int]]: (success, message, refund_amount)
        """
        try:
            # 1. Validate inputs
            if not member or not role:
                return False, "Nieprawidłowe dane wejściowe.", None

            # 2. Check if user has the role on Discord
            user_role_ids = [r.id for r in member.roles]
            if role.id not in user_role_ids:
                return False, "Nie posiadasz tej roli na Discord.", None

            # 3. Get role price from config
            role_config = next(
                (r for r in self.bot.config["premium_roles"] if r["name"] == role.name),
                None,
            )
            if not role_config:
                return False, "Nie można znaleźć konfiguracji roli.", None

            # 4. Perform all operations in a single transaction
            async with self.bot.get_db() as session:
                try:
                    # Check if user has the role in database
                    db_role = await RoleQueries.get_member_role(session, member.id, role.id)
                    if not db_role:
                        return False, "Nie posiadasz tej roli w bazie danych.", None

                    # Calculate refund
                    refund_amount = calculate_refund(
                        db_role.expiration_date, role_config["price"], role.name
                    )

                    # Remove role from Discord first
                    await member.remove_roles(role)
                    logger.info(
                        f"[ROLE_SALE] Removed role {role.name} from Discord for {member.display_name}"
                    )

                    # Remove role from database
                    delete_sql = text(
                        "DELETE FROM member_roles WHERE member_id = :member_id AND role_id = :role_id"
                    )
                    result = await session.execute(
                        delete_sql, {"member_id": member.id, "role_id": role.id}
                    )

                    if result.rowcount == 0:
                        # Rollback Discord change if database operation failed
                        await member.add_roles(role)
                        return False, "Nie udało się usunąć roli z bazy danych.", None

                    # Add refund to wallet
                    if refund_amount > 0:
                        await MemberQueries.add_to_wallet_balance(session, member.id, refund_amount)

                    # Remove premium role privileges
                    await self._remove_premium_privileges(session, member.id)

                    # Commit all changes
                    await session.commit()

                    logger.info(
                        f"[ROLE_SALE] Successfully sold role {role.name} for {member.display_name}, "
                        f"refund: {refund_amount}G"
                    )

                    return (
                        True,
                        f"Sprzedano rolę {role.name} za {refund_amount}{CURRENCY_UNIT}.",
                        refund_amount,
                    )

                except Exception as e:
                    await session.rollback()
                    # Try to restore role on Discord if something went wrong
                    try:
                        await member.add_roles(role)
                    except:
                        pass
                    logger.error(f"[ROLE_SALE] Transaction failed: {e}")
                    return False, "Wystąpił błąd podczas sprzedaży roli.", None

        except Exception as e:
            logger.error(f"[ROLE_SALE] Unexpected error: {e}")
            return False, "Wystąpił nieoczekiwany błąd.", None

    async def _remove_premium_privileges(self, session, member_id: int):
        """Remove premium role privileges (teams, mod permissions)."""
        try:
            # Import here to avoid circular imports
            from cogs.commands.info import remove_premium_role_mod_permissions

            await remove_premium_role_mod_permissions(session, self.bot, member_id)
        except Exception as e:
            logger.warning(f"[ROLE_SALE] Failed to remove premium privileges: {e}")
            # Don't fail the entire transaction for this
