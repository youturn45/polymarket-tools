"""Order request models for daemon submission."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field

from models.enums import OrderSide, Urgency
from models.order import StrategyParams


class StrategyType(str, Enum):
    """Available order execution strategies."""

    ICEBERG = "iceberg"
    MICRO_PRICE = "micro_price"
    KELLY = "kelly"


class MicroPriceParams(BaseModel):
    """Parameters for micro-price strategy execution."""

    threshold_bps: int = Field(
        default=50,
        description="Basis points from micro-price before replacing order",
        ge=1,
        le=10000,
    )
    check_interval: float = Field(
        default=2.0,
        description="Seconds between micro-price checks",
        ge=0.5,
        le=60.0,
    )
    max_adjustments: int = Field(
        default=10,
        description="Maximum number of order replacements",
        ge=1,
        le=100,
    )
    aggression_limit_bps: int = Field(
        default=100,
        description="Maximum basis points ahead of other orders",
        ge=1,
        le=1000,
    )

    def get_threshold_fraction(self) -> float:
        """Convert basis points to decimal fraction."""
        return self.threshold_bps / 10000

    def get_aggression_limit_fraction(self) -> float:
        """Convert aggression limit to decimal fraction."""
        return self.aggression_limit_bps / 10000


class KellyParams(BaseModel):
    """Parameters for Kelly criterion strategy."""

    win_probability: float = Field(
        description="Estimated probability of winning (0.0 to 1.0)",
        ge=0.0,
        le=1.0,
    )
    kelly_fraction: float = Field(
        default=0.25,
        description="Fraction of Kelly to use (0.25 = quarter Kelly)",
        ge=0.0,
        le=1.0,
    )
    max_position_size: int = Field(
        description="Maximum position size in shares",
        gt=0,
    )
    bankroll: int = Field(
        description="Available capital for position sizing",
        gt=0,
    )
    recalculate_interval: float = Field(
        default=5.0,
        description="Seconds between Kelly recalculations",
        ge=1.0,
        le=60.0,
    )
    recalc_threshold_pct: float = Field(
        default=0.05,
        description="Recalc when price changes by this %",
        ge=0.01,
        le=0.5,
    )

    # Kelly inherits micro-price for execution
    micro_price_params: MicroPriceParams = Field(
        default_factory=MicroPriceParams,
        description="Micro-price parameters for order execution",
    )


class OrderRequest(BaseModel):
    """Request to create and execute an order via daemon."""

    # Market identification
    token_id: str = Field(description="Token ID (YES or NO token)")
    side: OrderSide = Field(description="BUY or SELL")
    market_id: Optional[str] = Field(default=None, description="Optional market ID for tracking")

    # Strategy selection
    strategy_type: StrategyType = Field(description="Execution strategy to use")

    # Price bounds (required for all strategies)
    max_price: float = Field(
        description="Maximum acceptable price (buy limit)",
        ge=0.0,
        le=1.0,
    )
    min_price: float = Field(
        description="Minimum acceptable price (sell limit)",
        ge=0.0,
        le=1.0,
    )

    # Size specification (depends on strategy)
    total_size: Optional[int] = Field(
        default=None,
        description="Total shares for iceberg/micro-price (not used for Kelly)",
        gt=0,
    )

    # Strategy-specific parameters
    iceberg_params: Optional[StrategyParams] = Field(
        default=None,
        description="Parameters for iceberg strategy",
    )
    micro_price_params: Optional[MicroPriceParams] = Field(
        default=None,
        description="Parameters for micro-price strategy",
    )
    kelly_params: Optional[KellyParams] = Field(
        default=None,
        description="Parameters for Kelly criterion strategy",
    )

    # General settings
    urgency: Urgency = Field(
        default=Urgency.MEDIUM,
        description="Order urgency level",
    )
    timeout: float = Field(
        default=300.0,
        description="Maximum execution time in seconds",
        ge=10.0,
        le=3600.0,
    )

    def validate_strategy_params(self) -> None:
        """Validate that required params are provided for selected strategy."""
        if self.strategy_type == StrategyType.ICEBERG:
            if not self.iceberg_params:
                raise ValueError("iceberg_params required for ICEBERG strategy")
            if not self.total_size:
                raise ValueError("total_size required for ICEBERG strategy")

        elif self.strategy_type == StrategyType.MICRO_PRICE:
            if not self.micro_price_params:
                raise ValueError("micro_price_params required for MICRO_PRICE strategy")
            if not self.total_size:
                raise ValueError("total_size required for MICRO_PRICE strategy")

        elif self.strategy_type == StrategyType.KELLY:
            if not self.kelly_params:
                raise ValueError("kelly_params required for KELLY strategy")
            # Kelly calculates size dynamically, total_size should not be set
            if self.total_size is not None:
                raise ValueError("total_size should not be set for KELLY strategy")

    def model_post_init(self, __context) -> None:
        """Validate strategy parameters after initialization."""
        self.validate_strategy_params()

        # Validate price bounds
        if self.min_price >= self.max_price:
            raise ValueError("min_price must be less than max_price")

        # Set defaults for missing strategy params
        if self.strategy_type == StrategyType.ICEBERG and not self.iceberg_params:
            self.iceberg_params = StrategyParams()

        if self.strategy_type == StrategyType.MICRO_PRICE and not self.micro_price_params:
            self.micro_price_params = MicroPriceParams()
