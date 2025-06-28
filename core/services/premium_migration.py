"""Migration helper for transitioning to consolidated premium service."""

import logging
from typing import Any

from core.services.consolidated_premium_service import ConsolidatedPremiumService
from utils.premium import PremiumManager
from utils.premium_logic import PremiumRoleManager
from utils.premium_checker import PremiumChecker

logger = logging.getLogger(__name__)


class PremiumServiceAdapter:
    """Adapter to make ConsolidatedPremiumService compatible with old interfaces."""
    
    def __init__(self, bot: Any):
        self.bot = bot
        self._service = None
        self._manager = None
        self._role_manager = None
        self._checker = None
        
    async def get_service(self):
        """Get the consolidated premium service."""
        if not self._service:
            from core.repositories.premium_repository import PremiumRepository, PaymentRepository
            # Create repositories (these might need session management)
            premium_repo = PremiumRepository(None)  # Will be injected with session
            payment_repo = PaymentRepository(None)
            self._service = ConsolidatedPremiumService(
                premium_repository=premium_repo,
                payment_repository=payment_repo,
                bot=self.bot
            )
        return self._service
    
    async def get_manager(self) -> PremiumManager:
        """Get PremiumManager-compatible interface."""
        if not self._manager:
            service = await self.get_service()
            # Create adapter that wraps service to look like PremiumManager
            self._manager = PremiumManagerAdapter(service, self.bot)
        return self._manager
    
    async def get_role_manager(self, guild) -> PremiumRoleManager:
        """Get PremiumRoleManager-compatible interface."""
        if not self._role_manager:
            service = await self.get_service()
            service.set_guild(guild)
            self._role_manager = PremiumRoleManagerAdapter(service, self.bot, guild)
        return self._role_manager
    
    async def get_checker(self) -> PremiumChecker:
        """Get PremiumChecker-compatible interface."""
        if not self._checker:
            service = await self.get_service()
            self._checker = PremiumCheckerAdapter(service, self.bot)
        return self._checker


class PremiumManagerAdapter:
    """Adapter to make ConsolidatedPremiumService look like PremiumManager."""
    
    def __init__(self, service: ConsolidatedPremiumService, bot: Any):
        self.service = service
        self.bot = bot
        self.guild = None
        self.config = bot.config
    
    def set_guild(self, guild):
        """Set the guild for operations."""
        self.guild = guild
        self.service.set_guild(guild)
    
    def extract_id(self, text: str):
        """Extract ID from text."""
        return self.service.extract_id(text)
    
    async def get_banned_member(self, name_or_id: str):
        """Get banned member."""
        return await self.service.get_banned_member(name_or_id)
    
    async def get_member(self, name_or_id: str):
        """Get member."""
        return await self.service.get_member(name_or_id)
    
    @staticmethod
    def add_premium_roles_to_embed(ctx, embed, premium_roles):
        """Add premium roles to embed."""
        ConsolidatedPremiumService.add_premium_roles_to_embed(ctx, embed, premium_roles)
    
    async def process_data(self, session, payment_data):
        """Process payment data."""
        await self.service.process_data(session, payment_data)
    
    async def notify_unban(self, member):
        """Notify about unban."""
        await self.service.notify_unban(member)
    
    async def notify_member_not_found(self, name: str):
        """Notify member not found."""
        await self.service.notify_member_not_found(name)


class PremiumRoleManagerAdapter:
    """Adapter to make ConsolidatedPremiumService look like PremiumRoleManager."""
    
    class ExtensionType:
        NORMAL = "normal"
        PARTIAL = "partial"
        UPGRADE = "upgrade"
    
    def __init__(self, service: ConsolidatedPremiumService, bot: Any, guild):
        self.service = service
        self.bot = bot
        self.guild = guild
        self.premium_roles = bot.config["premium_roles"]
        self.mute_roles = {role["name"]: role for role in bot.config.get("mute_roles", [])}
        
        # Copy class attributes
        self.MONTHLY_DURATION = service.MONTHLY_DURATION
        self.YEARLY_DURATION = service.YEARLY_DURATION
        self.BONUS_DAYS = service.BONUS_DAYS
        self.YEARLY_MONTHS = service.YEARLY_MONTHS
        self.PREMIUM_PRIORITY = service.PREMIUM_PRIORITY
    
    def has_mute_roles(self, member):
        """Check if member has mute roles."""
        return self.service.has_mute_roles(member)
    
    async def remove_mute_roles(self, member):
        """Remove mute roles."""
        await self.service.remove_mute_roles(member)
    
    def get_user_highest_role_priority(self, member):
        """Get user's highest role priority."""
        return self.service.get_user_highest_role_priority(member)
    
    def get_user_highest_role_name(self, member):
        """Get user's highest role name."""
        return self.service.get_user_highest_role_name(member)
    
    async def assign_or_extend_premium_role(self, session, member, role_name, amount, 
                                           duration_days=30, source="shop"):
        """Assign or extend premium role."""
        return await self.service.assign_or_extend_premium_role(
            session, member, role_name, amount, duration_days, source
        )
    
    async def assign_temporary_roles(self, session, member, amount):
        """Assign temporary roles."""
        await self.service.assign_temporary_roles(session, member, amount)


class PremiumCheckerAdapter:
    """Adapter to make ConsolidatedPremiumService look like PremiumChecker."""
    
    # Copy class constants
    COMMAND_TIERS = ConsolidatedPremiumService.COMMAND_TIERS
    BOOSTER_ROLE_ID = ConsolidatedPremiumService.BOOSTER_ROLE_ID
    INVITE_ROLE_ID = ConsolidatedPremiumService.INVITE_ROLE_ID
    PREMIUM_ROLE_LEVELS = {"zG50": 1, "zG100": 2, "zG500": 3, "zG1000": 4}
    
    def __init__(self, service: ConsolidatedPremiumService, bot: Any):
        self.service = service
        self.bot = bot
        self.config = bot.config.get("voice_permission_levels", {})
        # Import here to avoid circular imports
        from utils.message_sender import MessageSender
        self.message_sender = MessageSender()
    
    def get_command_tier(self, command_name: str):
        """Get command tier synchronously."""
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.service.get_command_tier(command_name))
    
    async def has_active_bypass(self, ctx):
        """Check if user has active bypass."""
        return await self.service.has_active_bypass(ctx.author)
    
    def has_booster_roles(self, ctx):
        """Check if user has booster roles."""
        return self.service.has_booster_roles(ctx.author)
    
    def has_discord_invite_in_status(self, ctx):
        """Check if user has invite in status."""
        return self.service.has_discord_invite_in_status(ctx.author)
    
    async def has_alternative_bypass_access(self, ctx):
        """Check alternative bypass access."""
        return await self.service.has_alternative_bypass_access(ctx.author)
    
    def has_premium_role(self, ctx, min_tier: str = "zG50"):
        """Check if user has premium role."""
        import asyncio
        loop = asyncio.get_event_loop()
        has_premium = loop.run_until_complete(self.service.has_premium_role(ctx.author))
        if not has_premium:
            return False
        
        # Check minimum tier
        if min_tier != "zG50":
            premium_level = loop.run_until_complete(self.service.get_member_premium_level(ctx.author))
            if not premium_level:
                return False
            min_level = self.PREMIUM_ROLE_LEVELS.get(min_tier, 0)
            user_level = self.PREMIUM_ROLE_LEVELS.get(premium_level, 0)
            return user_level >= min_level
        
        return has_premium
    
    # Static decorators - these need special handling
    @staticmethod
    def requires_premium_tier(command_name: str):
        """Decorator for premium tier checking."""
        # Import the original for now
        from utils.premium_checker import PremiumChecker
        return PremiumChecker.requires_premium_tier(command_name)
    
    @staticmethod  
    def requires_voice_access(command_name: str):
        """Decorator for voice access checking."""
        # Import the original for now
        from utils.premium_checker import PremiumChecker
        return PremiumChecker.requires_voice_access(command_name)
    
    @staticmethod
    def requires_premium(command_name: str):
        """Legacy decorator."""
        # Import the original for now
        from utils.premium_checker import PremiumChecker
        return PremiumChecker.requires_premium(command_name)
    
    @staticmethod
    def requires_specific_roles(required_roles: list[str]):
        """Decorator for specific roles."""
        # Import the original for now
        from utils.premium_checker import PremiumChecker
        return PremiumChecker.requires_specific_roles(required_roles)
    
    @staticmethod
    async def extend_bypass(bot, member_id: int, hours: int = 12):
        """Extend bypass."""
        from utils.premium_checker import PremiumChecker
        return await PremiumChecker.extend_bypass(bot, member_id, hours)


# Global adapter instance
_adapter = None

def get_premium_adapter(bot: Any) -> PremiumServiceAdapter:
    """Get the global premium service adapter."""
    global _adapter
    if not _adapter:
        _adapter = PremiumServiceAdapter(bot)
    return _adapter