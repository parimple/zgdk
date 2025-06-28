"""Premium payment processing service."""

import logging
import re
from typing import Any, Optional

import discord
from sqlalchemy.exc import IntegrityError

from core.interfaces.premium_interfaces import IPremiumService, PaymentData
from core.repositories.premium_repository import PaymentRepository
from core.services.base_service import BaseService
from datasources.queries import HandledPaymentQueries

logger = logging.getLogger(__name__)


class PremiumPaymentService(BaseService, IPremiumService):
    """Service for processing premium payments."""

    def __init__(
        self,
        payment_repository: PaymentRepository,
        bot: Any,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.payment_repository = payment_repository
        self.bot = bot
        self.guild: Optional[discord.Guild] = None
        self.config = bot.config

    async def validate_operation(self, *args, **kwargs) -> bool:
        """Validate payment operations."""
        return True

    def set_guild(self, guild: discord.Guild) -> None:
        """Set the guild for the service."""
        self.guild = guild
        logger.info(f"Guild set for PremiumPaymentService: {guild.name}")

    def extract_id(self, text: str) -> Optional[int]:
        """Extract Discord ID from text."""
        patterns = [
            r"<@!?(\d+)>",  # Discord mention
            r"(\d{17,19})",  # Raw Discord ID
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        return None

    async def get_banned_member(self, name_or_id: str) -> Optional[discord.User]:
        """Try to find a banned member by name or ID."""
        if not self.guild:
            return None
            
        try:
            # Try to extract ID first
            member_id = self.extract_id(name_or_id)
            
            # Get ban list
            bans = [ban async for ban in self.guild.bans()]
            
            for ban_entry in bans:
                user = ban_entry.user
                
                # Check by ID
                if member_id and user.id == member_id:
                    return user
                    
                # Check by exact name match
                if user.name.lower() == name_or_id.lower():
                    return user
                    
                # Check by display name
                if user.display_name.lower() == name_or_id.lower():
                    return user
                    
                # Check by name#discriminator
                if str(user).lower() == name_or_id.lower():
                    return user
                    
            return None
            
        except Exception as e:
            logger.error(f"Error checking banned members: {e}")
            return None

    async def get_member(self, name_or_id: str) -> Optional[discord.Member]:
        """Get a member by name or ID."""
        if not self.guild:
            return None
            
        # Try to extract ID first
        member_id = self.extract_id(name_or_id)
        if member_id:
            member = self.guild.get_member(member_id)
            if member:
                return member
                
        # Try exact name match
        name_lower = name_or_id.lower()
        for member in self.guild.members:
            if (
                member.name.lower() == name_lower
                or member.display_name.lower() == name_lower
                or str(member).lower() == name_lower
            ):
                return member
                
        # Try partial match
        for member in self.guild.members:
            if (
                name_lower in member.name.lower()
                or name_lower in member.display_name.lower()
            ):
                return member
                
        return None

    async def process_data(self, session, payment_data: PaymentData) -> None:
        """Process payment data and store in database."""
        try:
            # Check if already processed
            existing = await HandledPaymentQueries.get_payment_by_name_and_amount(
                session, payment_data.name, payment_data.amount
            )
            
            if existing:
                logger.info(f"Payment already processed: {payment_data}")
                return
                
            # Try to find member
            member = await self.get_member(payment_data.name)
            member_id = member.id if member else None
            
            # Create payment record
            await HandledPaymentQueries.add_payment(
                session,
                member_id=member_id,
                name=payment_data.name,
                amount=payment_data.amount,
                paid_at=payment_data.paid_at,
                payment_type=payment_data.payment_type,
            )
            
            # Commit to ensure payment is recorded
            await session.commit()
            
            # Process invite commission if applicable
            if member and payment_data.amount >= 15:
                await self._process_invite_commission(session, member, payment_data.amount)
                
            self._log_operation(
                "process_payment_data",
                payment_name=payment_data.name,
                amount=payment_data.amount,
                member_found=member is not None,
            )
            
        except IntegrityError:
            logger.warning(f"Payment already exists: {payment_data}")
            await session.rollback()
        except Exception as e:
            logger.error(f"Error processing payment data: {e}")
            await session.rollback()
            raise

    async def _process_invite_commission(
        self, session, member: discord.Member, amount: int
    ) -> None:
        """Process commission for the member's inviter."""
        try:
            from datasources.queries import MemberQueries
            
            # Get member's inviter
            db_member = await MemberQueries.get_or_add_member(
                session, member.id, wallet_balance=0, joined_at=member.joined_at
            )
            
            if not db_member.current_inviter_id:
                return
                
            # Get inviter
            inviter = self.guild.get_member(db_member.current_inviter_id)
            if not inviter:
                return
                
            # Calculate commission (10%)
            commission = int(amount * 0.1)
            if commission < 1:
                return
                
            # Add commission to inviter's wallet
            inviter_db = await MemberQueries.get_or_add_member(
                session, inviter.id, wallet_balance=0, joined_at=inviter.joined_at
            )
            inviter_db.wallet_balance += commission
            
            # Log commission
            logger.info(
                f"Added {commission} PLN commission to {inviter} for {member}'s payment"
            )
            
            # Send notification to inviter
            await self._notify_commission(inviter, member, commission)
            
        except Exception as e:
            logger.error(f"Error processing invite commission: {e}")

    async def _notify_commission(
        self, inviter: discord.Member, invited: discord.Member, amount: int
    ) -> None:
        """Send commission notification to inviter."""
        try:
            embed = discord.Embed(
                title="💰 Otrzymałeś prowizję!",
                description=(
                    f"Użytkownik {invited.mention}, którego zaprosiłeś, "
                    f"dokonał zakupu premium!\n\n"
                    f"Twoja prowizja: **{amount} PLN**"
                ),
                color=discord.Color.green(),
            )
            embed.set_footer(text="Prowizja została dodana do Twojego portfela")
            
            await inviter.send(embed=embed)
            
        except discord.Forbidden:
            logger.info(f"Cannot send commission notification to {inviter}")
        except Exception as e:
            logger.error(f"Error sending commission notification: {e}")

    async def notify_unban(self, member):
        """Notify staff about automatic unban."""
        try:
            # Get log channel
            log_channel_id = self.bot.config["channels"].get("modlogs")
            if not log_channel_id:
                return
                
            log_channel = self.bot.get_channel(log_channel_id)
            if not log_channel:
                return
                
            embed = discord.Embed(
                title="🔓 Automatyczne odbanowanie",
                description=f"Użytkownik {member} został automatycznie odbanowany po wpłacie.",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )
            embed.set_footer(text=f"ID: {member.id}")
            
            await log_channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending unban notification: {e}")

    async def notify_member_not_found(self, name: str):
        """Notify staff when payment member cannot be found."""
        try:
            # Get donation channel
            channel_id = self.bot.config["channels"]["donation"]
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
                
            embed = discord.Embed(
                title="❓ Nie znaleziono użytkownika",
                description=(
                    f"Otrzymano wpłatę od **{name}**, ale nie można znaleźć "
                    f"użytkownika na serwerze.\n\n"
                    f"Sprawdź czy użytkownik jest zbanowany lub użyj komendy "
                    f"`/przypisz_wplate` aby ręcznie przypisać wpłatę."
                ),
                color=discord.Color.orange(),
            )
            
            await channel.send(embed=embed)
            
        except Exception as e:
            logger.error(f"Error sending member not found notification: {e}")

    def calculate_premium_benefits(self, amount: int) -> Optional[tuple[str, int]]:
        """Calculate which premium role and duration to give based on payment amount."""
        # Legacy conversion if enabled
        if self.bot.config.get("legacy_system", {}).get("enabled", False):
            legacy_amounts = self.bot.config.get("legacy_system", {}).get("amounts", {})
            if amount in legacy_amounts:
                amount = legacy_amounts[amount]
                
        # Find matching premium role
        for role_config in self.bot.config.get("premium_roles", []):
            role_price = role_config["price"]
            role_name = role_config["name"]
            
            # Check exact match or +1 PLN
            if amount in [role_price, role_price + 1]:
                return role_name, 30  # Default 30 days
                
        return None