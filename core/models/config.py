"""
Configuration schema validation using Pydantic.
"""

from typing import Any, Dict, List, Optional

from pydantic import Field, validator
from pydantic_settings import BaseSettings

from .base import BaseModel, DiscordID


class ChannelConfig(BaseModel):
    """Channel configuration."""
    on_join: DiscordID
    lounge: DiscordID
    donation: DiscordID
    premium_info: DiscordID
    bots: DiscordID
    mute_notifications: DiscordID
    mute_logs: DiscordID
    unmute_logs: DiscordID
    test_channel: DiscordID


class VoicePermissionCommand(BaseModel):
    """Voice command permission configuration."""
    require_bypass_if_no_role: bool = True
    description: str
    allowed_roles: List[str] = Field(default_factory=list)


class BypassDuration(BaseModel):
    """Bypass duration configuration."""
    bump: int = Field(12, description="Hours added for bump")
    activity: int = Field(6, description="Hours added for activity")


class PremiumRoleConfig(BaseModel):
    """Premium role configuration."""
    name: str
    premium: str
    price: int = Field(..., gt=0)
    usd: int = Field(..., gt=0)
    features: List[str]
    team_size: int = Field(..., ge=0)
    moderator_count: int = Field(..., ge=0)
    points_multiplier: int = Field(..., ge=0)
    emojis_access: bool = False
    override_limit: bool = True
    auto_kick: int = Field(default=0, ge=0)
    
    @validator('name')
    def validate_role_name(cls, v: str) -> str:
        """Validate premium role name format."""
        valid_names = ["zG50", "zG100", "zG500", "zG1000"]
        if v not in valid_names:
            raise ValueError(f"Role name must be one of: {', '.join(valid_names)}")
        return v
    
    @validator('price')
    def validate_price_matches_name(cls, v: int, values: dict) -> int:
        """Validate price matches role name."""
        name = values.get('name')
        expected_prices = {
            "zG50": 49,
            "zG100": 99,
            "zG500": 499,
            "zG1000": 999
        }
        if name and name in expected_prices:
            if v != expected_prices[name]:
                raise ValueError(f"Price {v} doesn't match expected {expected_prices[name]} for {name}")
        return v


class MuteRoleConfig(BaseModel):
    """Mute role configuration."""
    id: DiscordID
    name: str
    description: str


class ColorRoleConfig(BaseModel):
    """Color role system configuration."""
    blue: DiscordID
    green: DiscordID
    red: DiscordID


class AdminRoleConfig(BaseModel):
    """Admin role configuration."""
    mod: DiscordID
    admin: DiscordID


class GenderRoleConfig(BaseModel):
    """Gender role configuration."""
    male: DiscordID
    female: DiscordID


class TeamConfig(BaseModel):
    """Team system configuration."""
    symbol: str = Field(default="☫", max_length=5)
    base_role_id: DiscordID
    category_id: DiscordID


class ColorConfig(BaseModel):
    """Color system configuration."""
    role_name: str = Field(default="✎", max_length=5)
    base_role_id: DiscordID


class BotConfig(BaseSettings):
    """Main bot configuration with validation."""
    # Basic settings
    prefix: str = Field(default=",", min_length=1, max_length=5)
    description: str = Field(default="zaGadka Bot", max_length=200)
    guild_id: DiscordID
    donate_url: str = Field(default="", pattern=r'^https?://.*$|^$')
    
    # Owner configuration
    owner_ids: List[DiscordID] = Field(default_factory=list)
    owner_id: DiscordID  # Backward compatibility
    
    # Channels
    channels: ChannelConfig
    channels_voice: Dict[str, DiscordID] = Field(default_factory=dict)
    
    # Voice system
    channels_create: List[DiscordID] = Field(default_factory=list)
    vc_categories: List[DiscordID] = Field(default_factory=list)
    clean_permission_categories: List[DiscordID] = Field(default_factory=list)
    max_channels_categories: List[DiscordID] = Field(default_factory=list)
    
    # Roles
    premium_roles: List[PremiumRoleConfig]
    mute_roles: List[MuteRoleConfig]
    color_roles: ColorRoleConfig
    admin_roles: AdminRoleConfig
    gender_roles: GenderRoleConfig
    
    # Voice permissions
    voice_permissions: Dict[str, Any] = Field(default_factory=dict)
    
    # Bypass system
    bypass: Dict[str, Any] = Field(default_factory=dict)
    
    # Module configs
    color: ColorConfig
    team: TeamConfig
    
    # Excluded categories
    excluded_categories: List[DiscordID] = Field(default_factory=list)
    
    # Audit settings
    audit_settings: Dict[str, List[DiscordID]] = Field(default_factory=dict)
    
    # Legacy system
    legacy_system: Dict[str, Any] = Field(default_factory=dict)
    
    # Emojis
    emojis: Dict[str, str] = Field(default_factory=dict)
    
    # GIFs
    gifs: Dict[str, str] = Field(default_factory=dict)
    
    # Channel emojis
    channel_emojis: List[str] = Field(default_factory=list)
    
    # Channel name formats
    channel_name_formats: Dict[DiscordID, str] = Field(default_factory=dict)
    
    # Default user limits
    default_user_limits: Dict[str, Any] = Field(default_factory=dict)
    
    # Default mute nickname
    default_mute_nickname: str = Field(default="random", min_length=1)
    
    @validator('owner_ids')
    def ensure_owner_id_in_list(cls, v: List[DiscordID], values: dict) -> List[DiscordID]:
        """Ensure owner_id is in owner_ids for backward compatibility."""
        owner_id = values.get('owner_id')
        if owner_id and owner_id not in v:
            v.append(owner_id)
        return v
    
    @validator('donate_url')
    def validate_donate_url(cls, v: str) -> str:
        """Validate donation URL format."""
        if v and not v.startswith(('http://', 'https://')):
            raise ValueError("Donate URL must start with http:// or https://")
        return v
    
    @validator('premium_roles')
    def validate_premium_roles_order(cls, v: List[PremiumRoleConfig]) -> List[PremiumRoleConfig]:
        """Ensure premium roles are in correct order."""
        # Sort by price to ensure correct hierarchy
        return sorted(v, key=lambda r: r.price)
    
    def is_owner(self, user_id: str | int) -> bool:
        """Check if user is bot owner."""
        user_id_str = str(user_id)
        return user_id_str in self.owner_ids or user_id_str == self.owner_id
    
    def get_premium_role_config(self, role_name: str) -> Optional[PremiumRoleConfig]:
        """Get premium role configuration by name."""
        for role in self.premium_roles:
            if role.name == role_name:
                return role
        return None
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False