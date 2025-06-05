"""Role service providing an interface to role management functionality."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple, Callable

import discord

from utils.managers.role_manager import RoleManager
from utils.errors import ZGDKError, ResourceNotFoundError
from utils.services import BaseService


class RoleService(BaseService):
    """Service for handling role operations."""
    
    def __init__(self, bot):
        """Initialize the role service with a bot instance."""
        super().__init__(bot)
        self.role_manager = RoleManager(bot)
    
    async def check_expired_roles(
        self,
        role_type: Optional[str] = None,
        role_ids: Optional[List[int]] = None,
        notification_handler: Optional[Callable] = None
    ) -> Tuple[bool, str, int]:
        """Check and remove expired roles of the specified type or IDs.
        
        Args:
            role_type: Optional role type to check (e.g. "premium", "mute")
            role_ids: Optional list of specific role IDs to check
            notification_handler: Optional function to handle notifications
            
        Returns:
            Tuple of (success, message, number of removed roles)
        """
        try:
            removed_count = await self.role_manager.check_expired_roles(
                role_type=role_type,
                role_ids=role_ids,
                notification_handler=notification_handler
            )
            
            return True, f"Checked expired roles, removed {removed_count}", removed_count
        except Exception as e:
            return False, f"Error checking expired roles: {str(e)}", 0
    
    async def add_role_with_expiry(
        self,
        member: discord.Member,
        role_id: int,
        expiry_hours: int
    ) -> Tuple[bool, str, Optional[datetime]]:
        """Add a role with an expiration time to a member.
        
        Args:
            member: The Discord member
            role_id: The Discord ID of the role to add
            expiry_hours: Hours until the role expires
            
        Returns:
            Tuple of (success, message, expiry_date)
        """
        try:
            success = await self.role_manager.add_role_with_expiry(
                member.id, role_id, expiry_hours
            )
            
            if success:
                expiry_date = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
                return True, "Role added successfully", expiry_date
            else:
                return False, "Failed to add role", None
                
        except ResourceNotFoundError as e:
            return False, str(e), None
        except Exception as e:
            return False, f"Error adding role: {str(e)}", None
    
    async def remove_role(self, member: discord.Member, role_id: int) -> Tuple[bool, str]:
        """Remove a role from a member and from the database.
        
        Args:
            member: The Discord member
            role_id: The Discord ID of the role to remove
            
        Returns:
            Tuple of (success, message)
        """
        try:
            success = await self.role_manager.remove_role(member.id, role_id)
            
            if success:
                return True, "Role removed successfully"
            else:
                return False, "Failed to remove role"
                
        except Exception as e:
            return False, f"Error removing role: {str(e)}"
    
    async def get_member_roles(self, member: discord.Member) -> Tuple[bool, str, Optional[List[Dict[str, Any]]]]:
        """Get all roles for a member from the database.
        
        Args:
            member: The Discord member
            
        Returns:
            Tuple of (success, message, roles_data)
        """
        try:
            success, info = await self.role_manager.get_role_info(member.id)
            
            if not success:
                return False, info.get("error", "Failed to get roles"), None
            
            if "roles" in info:
                return True, "Roles retrieved successfully", info["roles"]
            else:
                return False, "Unexpected response format", None
                
        except Exception as e:
            return False, f"Error retrieving roles: {str(e)}", None
    
    async def get_role_info(self, member: discord.Member, role_id: int) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
        """Get information about a specific role for a member.
        
        Args:
            member: The Discord member
            role_id: The Discord ID of the role
            
        Returns:
            Tuple of (success, message, role_data)
        """
        try:
            success, info = await self.role_manager.get_role_info(member.id, role_id)
            
            if not success:
                return False, info.get("error", "Failed to get role info"), None
            
            if "error" in info:
                return False, info["error"], None
            
            return True, "Role info retrieved successfully", info
                
        except Exception as e:
            return False, f"Error retrieving role info: {str(e)}", None
    
    async def extend_role_expiry(
        self,
        member: discord.Member,
        role_id: int,
        additional_hours: int
    ) -> Tuple[bool, str, Optional[datetime]]:
        """Extend the expiration time of a role.
        
        Args:
            member: The Discord member
            role_id: The Discord ID of the role
            additional_hours: Additional hours to add to the current expiry
            
        Returns:
            Tuple of (success, message, new_expiry_date)
        """
        try:
            # First get the current role info
            success, message, role_info = await self.get_role_info(member, role_id)
            
            if not success:
                return False, message, None
            
            # Then remove and re-add the role with the new expiry
            current_expiry = role_info.get("expiry_date")
            if not current_expiry:
                # If no expiry date, set a new one from now
                new_hours = additional_hours
            else:
                # Calculate new expiry based on current expiry
                now = datetime.now(timezone.utc)
                remaining_hours = max(0, (current_expiry - now).total_seconds() / 3600)
                new_hours = remaining_hours + additional_hours
            
            # Remove the old role entry
            await self.role_manager.remove_role(member.id, role_id)
            
            # Add the role with the new expiry
            success = await self.role_manager.add_role_with_expiry(member.id, role_id, new_hours)
            
            if success:
                new_expiry = datetime.now(timezone.utc) + timedelta(hours=new_hours)
                return True, "Role expiry extended successfully", new_expiry
            else:
                return False, "Failed to extend role expiry", None
                
        except Exception as e:
            return False, f"Error extending role expiry: {str(e)}", None