"""Market conditions data model."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class MarketConditions(BaseModel):
    """Real-time market state snapshot."""

    market_id: str = Field(description="Market identifier")
    token_id: str = Field(description="Token identifier")

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
