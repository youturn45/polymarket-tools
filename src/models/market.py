"""Market conditions data models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MarketConditions(BaseModel):
    """Real-time market state snapshot."""

    token_id: str = Field(description="Token identifier")
    market_id: Optional[str] = Field(default=None, description="Optional market identifier")

    # Order book metrics
    best_bid: float = Field(description="Current best bid price")
    best_ask: float = Field(description="Current best ask price")
    spread: float = Field(description="Bid-ask spread")
    bid_depth: int = Field(description="Total size at best bid", default=0)
    ask_depth: int = Field(description="Total size at best ask", default=0)

    # Position tracking
    our_position_in_queue: Optional[int] = Field(
        default=None, description="Position in queue at our price level"
    )
    total_orders_at_price: Optional[int] = Field(
        default=None, description="Total orders at our price level"
    )

    # Competition metrics
    undercut_detected: bool = Field(default=False, description="Someone placed order ahead of us")
    undercut_margin: Optional[float] = Field(
        default=None, description="Price difference of undercut"
    )

    # Time tracking
    timestamp: datetime = Field(default_factory=datetime.now, description="When snapshot was taken")

    @property
    def mid_price(self) -> float:
        """Calculate mid-point between bid and ask."""
        return (self.best_bid + self.best_ask) / 2


class MarketSnapshot(BaseModel):
    """Complete snapshot of market state including order book and micro-price."""

    token_id: str = Field(description="Token identifier")
    timestamp: datetime = Field(default_factory=datetime.now, description="Snapshot timestamp")

    # Order book - best prices
    best_bid: float = Field(description="Best bid price")
    best_ask: float = Field(description="Best ask price")
    spread: float = Field(description="Bid-ask spread")

    # Order book - depth
    bid_depth: int = Field(description="Size at best bid", ge=0)
    ask_depth: int = Field(description="Size at best ask", ge=0)

    # Micro-price
    micro_price: float = Field(description="Calculated micro-price (fair value)")
    micro_price_upper_band: float = Field(description="Upper threshold band")
    micro_price_lower_band: float = Field(description="Lower threshold band")

    # Full order book (top N levels)
    bids: list[tuple[float, int]] = Field(
        default_factory=list, description="Bid levels [(price, size), ...]"
    )
    asks: list[tuple[float, int]] = Field(
        default_factory=list, description="Ask levels [(price, size), ...]"
    )

    # Our orders in this market
    our_orders: list[dict] = Field(default_factory=list, description="Our active orders")

    @property
    def mid_price(self) -> float:
        """Calculate mid-point between bid and ask."""
        return (self.best_bid + self.best_ask) / 2

    def is_price_in_bounds(self, price: float) -> bool:
        """Check if price is within micro-price threshold bands."""
        return self.micro_price_lower_band <= price <= self.micro_price_upper_band

    def distance_from_micro_price(self, price: float) -> float:
        """Calculate distance from micro-price as a fraction."""
        if self.micro_price == 0:
            return 0.0
        return abs(price - self.micro_price) / self.micro_price

    def get_spread_bps(self) -> int:
        """Get spread in basis points."""
        if self.mid_price == 0:
            return 0
        return int((self.spread / self.mid_price) * 10000)
