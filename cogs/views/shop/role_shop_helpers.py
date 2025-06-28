"""Helper functions and utilities for RoleShopView."""
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import discord

from .constants import MONTHLY_DURATION, YEARLY_DURATION, YEARLY_MONTHS

logger = logging.getLogger(__name__)


class RoleShopPricing:
    """Helper class for role shop pricing calculations."""
    
    @staticmethod
    def get_price_map(premium_roles: List[Dict], page: int) -> Dict[str, int]:
        """Get price map based on current page (monthly/yearly)."""
        price_map = {}
        for role in premium_roles:
            if page == 1:  # Monthly prices
                price_map[role["name"]] = role["price"]
            else:  # Yearly prices (10 months)
                price_map[role["name"]] = role["price"] * YEARLY_MONTHS
        return price_map
    
    @staticmethod
    def calculate_subscription_days(page: int) -> int:
        """Calculate subscription duration in days based on page."""
        return MONTHLY_DURATION if page == 1 else YEARLY_DURATION


class RoleShopFormatting:
    """Helper class for formatting role shop text."""
    
    @staticmethod
    def add_premium_text_to_description(description: str) -> str:
        """Add premium text formatting to role description."""
        if "Role:" in description:
            return description.replace("Role:", "**Role:**")
        return description
    
    @staticmethod
    def format_duration_text(page: int) -> str:
        """Get formatted duration text based on page."""
        return "miesięczna" if page == 1 else "roczna"
    
    @staticmethod
    def format_price_info(page: int, role_name: str, price: int) -> str:
        """Format price information for role."""
        if page == 1:
            return f"Cena: {price} zł/miesiąc"
        else:
            monthly_price = price // YEARLY_MONTHS
            return f"Cena: {price} zł/rok ({monthly_price} zł/miesiąc x 10 miesięcy + 2 miesiące gratis)"


class RoleValidation:
    """Helper class for role validation."""
    
    @staticmethod
    def get_highest_premium_role(member: discord.Member, premium_roles: List[Dict]) -> Optional[str]:
        """Get the highest premium role a member has."""
        member_role_names = {role.name for role in member.roles}
        
        # Check roles in order (assuming they're ordered from highest to lowest)
        for role_config in premium_roles:
            if role_config["name"] in member_role_names:
                return role_config["name"]
        return None
    
    @staticmethod
    def is_role_upgrade(current_role: str, new_role: str, premium_roles: List[Dict]) -> bool:
        """Check if new role is an upgrade from current role."""
        if not current_role:
            return False
            
        current_index = next(
            (i for i, r in enumerate(premium_roles) if r["name"] == current_role), 
            -1
        )
        new_index = next(
            (i for i, r in enumerate(premium_roles) if r["name"] == new_role), 
            -1
        )
        
        # Higher index = higher tier role (config is ordered from lowest to highest)
        return new_index > current_index
    
    @staticmethod
    def is_role_downgrade(current_role: str, new_role: str, premium_roles: List[Dict]) -> bool:
        """Check if new role is a downgrade from current role."""
        if not current_role:
            return False
            
        current_index = next(
            (i for i, r in enumerate(premium_roles) if r["name"] == current_role), 
            -1
        )
        new_index = next(
            (i for i, r in enumerate(premium_roles) if r["name"] == new_role), 
            -1
        )
        
        # Lower index = lower tier role (config is ordered from lowest to highest)
        return new_index < current_index