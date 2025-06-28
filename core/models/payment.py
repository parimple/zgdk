"""
Payment and premium-related Pydantic models.
"""

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Literal, Optional

from pydantic import Field, validator

from .base import BaseModel, DiscordID, Timestamp


class PaymentMethod(str, Enum):
    """Available payment methods."""
    TIPPLY = "tipply"
    PAYPAL = "paypal"
    CRYPTO = "crypto"
    BANK_TRANSFER = "bank_transfer"
    MANUAL = "manual"


class PremiumTier(str, Enum):
    """Premium subscription tiers."""
    ZG50 = "zG50"
    ZG100 = "zG100"
    ZG500 = "zG500"
    ZG1000 = "zG1000"


class Currency(str, Enum):
    """Supported currencies."""
    PLN = "PLN"
    USD = "USD"
    EUR = "EUR"


class PaymentRequest(BaseModel):
    """Base payment request model."""
    amount: Decimal = Field(..., gt=0, decimal_places=2)
    currency: Currency = Currency.PLN
    method: PaymentMethod
    description: str = Field(..., min_length=3, max_length=500)
    metadata: dict = Field(default_factory=dict)
    
    @validator('amount')
    def validate_amount(cls, v: Decimal) -> Decimal:
        """Ensure amount has max 2 decimal places."""
        if v.as_tuple().exponent < -2:
            raise ValueError("Amount can have maximum 2 decimal places")
        return v


class PremiumPurchaseRequest(BaseModel):
    """Request to purchase premium subscription."""
    user_id: DiscordID
    guild_id: DiscordID
    tier: PremiumTier
    payment_method: PaymentMethod
    amount: Decimal = Field(..., gt=0)
    currency: Currency = Currency.PLN
    duration_days: int = Field(default=30, gt=0)
    auto_renew: bool = False
    team_member_ids: list[DiscordID] = Field(default_factory=list)
    
    @validator('amount')
    def validate_tier_amount(cls, v: Decimal, values: dict) -> Decimal:
        """Validate amount matches the tier pricing."""
        tier_prices = {
            PremiumTier.ZG50: Decimal("49.00"),
            PremiumTier.ZG100: Decimal("99.00"),
            PremiumTier.ZG500: Decimal("499.00"),
            PremiumTier.ZG1000: Decimal("999.00")
        }
        
        tier = values.get('tier')
        currency = values.get('currency', Currency.PLN)
        
        if tier and currency == Currency.PLN:
            expected = tier_prices.get(tier)
            if expected and abs(v - expected) > Decimal("0.01"):
                raise ValueError(
                    f"Amount {v} doesn't match {tier.value} price {expected} PLN"
                )
        return v
    
    @validator('team_member_ids')
    def validate_team_size(cls, v: list[DiscordID], values: dict) -> list[DiscordID]:
        """Validate team size for tier."""
        tier_limits = {
            PremiumTier.ZG50: 0,
            PremiumTier.ZG100: 10,
            PremiumTier.ZG500: 20,
            PremiumTier.ZG1000: 30
        }
        
        tier = values.get('tier')
        if tier:
            limit = tier_limits.get(tier, 0)
            if len(v) > limit:
                raise ValueError(
                    f"Team size {len(v)} exceeds limit {limit} for {tier.value}"
                )
        return v


class PaymentValidation(BaseModel):
    """Payment validation result."""
    valid: bool
    payment_id: str | None = None
    error_message: str | None = None
    error_code: str | None = None
    timestamp: Timestamp = Field(default_factory=datetime.utcnow)
    
    @validator('error_message')
    def require_error_message_if_invalid(cls, v: str | None, values: dict) -> str | None:
        """Require error message if payment is invalid."""
        if not values.get('valid') and not v:
            raise ValueError("Error message required for invalid payment")
        return v


class PaymentStatus(BaseModel):
    """Payment status tracking."""
    payment_id: str = Field(..., min_length=1)
    user_id: DiscordID
    status: Literal["pending", "completed", "failed", "refunded"]
    amount: Decimal = Field(..., gt=0)
    currency: Currency
    method: PaymentMethod
    created_at: Timestamp
    updated_at: Timestamp
    completed_at: datetime | None = None
    error_details: dict | None = None
    
    @validator('completed_at')
    def validate_completed_at(cls, v: datetime | None, values: dict) -> datetime | None:
        """Ensure completed_at is set for completed payments."""
        status = values.get('status')
        if status == 'completed' and not v:
            return datetime.utcnow()
        return v


class PremiumSubscription(BaseModel):
    """Active premium subscription details."""
    id: int
    user_id: DiscordID
    guild_id: DiscordID
    tier: PremiumTier
    start_date: datetime
    end_date: datetime
    auto_renew: bool = False
    is_active: bool = True
    payment_id: str | None = None
    team_members: list[DiscordID] = Field(default_factory=list)
    
    @validator('end_date')
    def validate_end_date(cls, v: datetime, values: dict) -> datetime:
        """Ensure end date is after start date."""
        start = values.get('start_date')
        if start and v <= start:
            raise ValueError("End date must be after start date")
        return v
    
    @property
    def days_remaining(self) -> int:
        """Calculate days remaining in subscription."""
        if not self.is_active:
            return 0
        remaining = (self.end_date - datetime.utcnow()).days
        return max(0, remaining)
    
    @property
    def is_expired(self) -> bool:
        """Check if subscription is expired."""
        return datetime.utcnow() > self.end_date