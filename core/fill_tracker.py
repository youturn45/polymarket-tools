"""Track order fills across multiple tranches."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class TrancheFill:
    """Record of a single tranche fill."""

    tranche_number: int
    size: int
    filled: int
    price: float
    timestamp: datetime


class FillTracker:
    """Tracks fills across multiple tranches of an iceberg order."""

    def __init__(self, total_size: int):
        """Initialize fill tracker.

        Args:
            total_size: Total order size to track
        """
        self.total_size = total_size
        self.fills: list[TrancheFill] = []

    def record_tranche_fill(
        self, tranche_number: int, size: int, filled: int, price: float
    ) -> None:
        """Record a tranche fill.

        Args:
            tranche_number: Tranche sequence number (1-indexed)
            size: Tranche size attempted
            filled: Amount actually filled
            price: Fill price
        """
        fill = TrancheFill(
            tranche_number=tranche_number,
            size=size,
            filled=filled,
            price=price,
            timestamp=datetime.now(),
        )
        self.fills.append(fill)

    @property
    def total_filled(self) -> int:
        """Calculate total filled amount across all tranches.

        Returns:
            Total shares filled
        """
        return sum(fill.filled for fill in self.fills)

    @property
    def total_remaining(self) -> int:
        """Calculate remaining unfilled amount.

        Returns:
            Shares remaining to fill
        """
        return max(0, self.total_size - self.total_filled)

    @property
    def average_fill_price(self) -> float:
        """Calculate volume-weighted average fill price.

        Returns:
            Average price, or 0.0 if no fills
        """
        if not self.fills or self.total_filled == 0:
            return 0.0

        total_value = sum(fill.filled * fill.price for fill in self.fills)
        return total_value / self.total_filled

    @property
    def fill_rate(self) -> float:
        """Calculate fill rate as percentage.

        Returns:
            Fill rate as decimal (0.0 to 1.0)
        """
        if self.total_size == 0:
            return 0.0
        return self.total_filled / self.total_size

    @property
    def tranche_count(self) -> int:
        """Get number of tranches executed.

        Returns:
            Number of tranches
        """
        return len(self.fills)

    def is_complete(self) -> bool:
        """Check if order is completely filled.

        Returns:
            True if all shares filled
        """
        return self.total_filled >= self.total_size

    def get_tranche_summary(self) -> list[dict]:
        """Get summary of all tranche fills.

        Returns:
            List of tranche summaries
        """
        return [
            {
                "tranche": fill.tranche_number,
                "size": fill.size,
                "filled": fill.filled,
                "price": fill.price,
                "timestamp": fill.timestamp.isoformat(),
                "fill_rate": fill.filled / fill.size if fill.size > 0 else 0.0,
            }
            for fill in self.fills
        ]
