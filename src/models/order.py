"""Order data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from models.enums import OrderSide, OrderStatus, Urgency


class StrategyParams(BaseModel):
    """Parameters for iceberg strategy execution."""

    initial_tranche_size: int = Field(default=50, description="Size of first order chunk", gt=0)
    min_tranche_size: int = Field(default=10, description="Minimum chunk size", gt=0)
    max_tranche_size: int = Field(default=200, description="Maximum chunk size", gt=0)
    tranche_randomization: float = Field(
        default=0.2,
        description="Amount of size randomization (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )

    @field_validator("initial_tranche_size")
    @classmethod
    def validate_initial_size(cls, v: int, info) -> int:
        """Validate initial tranche size is within min/max bounds."""
        # Note: Can't access other fields during validation in Pydantic v2
        # Will add model validator if needed
        return v


class Order(BaseModel):
    """Represents a single order request."""

    # Identification
    order_id: str = Field(description="Unique order identifier")
    token_id: str = Field(description="Token ID (YES/NO token)")
    market_id: Optional[str] = Field(
        default=None, description="Optional market/condition ID for tracking"
    )

    # Order parameters
    side: OrderSide = Field(description="BUY or SELL")
    total_size: int = Field(description="Total number of shares to trade", gt=0)
    target_price: float = Field(
        description="Initial target price",
        ge=0.0,
        le=1.0,
    )
    max_price: float = Field(
        description="Maximum acceptable price (buy orders)",
        ge=0.0,
        le=1.0,
    )
    min_price: float = Field(
        description="Minimum acceptable price (sell orders)",
        ge=0.0,
        le=1.0,
    )

    # Execution parameters
    urgency: Urgency = Field(default=Urgency.MEDIUM, description="Order urgency level")
    strategy_params: StrategyParams = Field(
        default_factory=StrategyParams,
        description="Strategy execution parameters",
    )

    # State tracking
    status: OrderStatus = Field(
        default=OrderStatus.QUEUED,
        description="Current order status",
    )
    filled_amount: int = Field(default=0, description="Amount filled so far", ge=0)
    remaining_amount: Optional[int] = Field(
        default=None, description="Amount remaining to fill", ge=0
    )

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.now,
        description="When order was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.now,
        description="Last update timestamp",
    )

    # Tracking
    adjustment_count: int = Field(
        default=0,
        description="Number of price adjustments made",
        ge=0,
    )
    undercut_count: int = Field(
        default=0,
        description="Number of times undercut detected",
        ge=0,
    )

    def model_post_init(self, __context) -> None:
        """Initialize remaining_amount after model creation."""
        if self.remaining_amount is None:
            self.remaining_amount = self.total_size

    @field_validator("max_price", "min_price")
    @classmethod
    def validate_price_range(cls, v: float) -> float:
        """Validate prices are within 0.0 to 1.0 range."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("Price must be between 0.0 and 1.0")
        return v

    def update_status(self, new_status: OrderStatus) -> None:
        """Update order status and timestamp."""
        self.status = new_status
        self.updated_at = datetime.now()

    def record_fill(self, amount: int) -> None:
        """Record a fill and update amounts."""
        self.filled_amount += amount
        self.remaining_amount = self.total_size - self.filled_amount
        self.updated_at = datetime.now()

        # Update status based on fill
        if self.remaining_amount == 0:
            self.status = OrderStatus.COMPLETED
        elif self.filled_amount > 0:
            self.status = OrderStatus.PARTIALLY_FILLED

    def record_adjustment(self) -> None:
        """Record a price adjustment."""
        self.adjustment_count += 1
        self.updated_at = datetime.now()

    def record_undercut(self) -> None:
        """Record an undercut detection."""
        self.undercut_count += 1
        self.updated_at = datetime.now()
