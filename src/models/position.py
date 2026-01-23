"""Position tracking models for portfolio monitoring."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class Position(BaseModel):
    """Position tracking for a specific token.

    Tracks shares held, average entry price, and unrealized PnL
    for a specific outcome token in a prediction market.
    """

    token_id: str
    market_id: Optional[str] = None
    question: Optional[str] = None  # Human-readable market question
    outcome: str  # "YES" or "NO"

    # Position data
    total_shares: float = 0.0
    avg_entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0

    # Metadata
    last_updated: datetime = Field(default_factory=datetime.now)

    def update_pnl(self, current_price: float) -> None:
        """Update unrealized PnL based on current price.

        Args:
            current_price: Current market price for the token
        """
        self.current_price = current_price
        if self.total_shares > 0:
            self.unrealized_pnl = (current_price - self.avg_entry_price) * self.total_shares
        else:
            self.unrealized_pnl = 0.0
        self.last_updated = datetime.now()

    def add_buy(self, shares: float, price: float) -> None:
        """Add a buy transaction to the position.

        Updates total shares and recalculates average entry price.

        Args:
            shares: Number of shares bought
            price: Price per share
        """
        if shares <= 0:
            return

        total_cost = self.total_shares * self.avg_entry_price
        new_cost = shares * price
        self.total_shares += shares

        if self.total_shares > 0:
            self.avg_entry_price = (total_cost + new_cost) / self.total_shares

        self.last_updated = datetime.now()

    def add_sell(self, shares: float) -> None:
        """Add a sell transaction to the position.

        Reduces total shares. Average entry price remains unchanged.

        Args:
            shares: Number of shares sold
        """
        if shares <= 0:
            return

        self.total_shares -= shares
        self.last_updated = datetime.now()

    def is_empty(self) -> bool:
        """Check if position is empty (no shares held).

        Returns:
            True if total_shares is zero or negative
        """
        return self.total_shares <= 0
