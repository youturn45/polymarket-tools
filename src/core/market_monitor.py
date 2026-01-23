"""Market monitor for tracking order book and calculating micro-price."""

import logging
from datetime import datetime
from typing import Optional

from api.polymarket_client import PolymarketClient
from models.market import MarketSnapshot


class MarketMonitor:
    """Monitors market conditions and calculates micro-price.

    The micro-price is a more accurate measure of fair value than the mid-price,
    weighted by the depth on each side of the order book.

    Formula: micro_price = (best_bid × ask_size + best_ask × bid_size) / (bid_size + ask_size)
    """

    def __init__(
        self,
        client: PolymarketClient,
        token_id: str,
        band_width_bps: int = 50,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize market monitor.

        Args:
            client: Polymarket API client
            token_id: Token to monitor
            band_width_bps: Width of micro-price bands in basis points (default: 50 = 0.5%)
            logger: Optional logger instance
        """
        self.client = client
        self.token_id = token_id
        self.band_width_bps = band_width_bps
        self.logger = logger or logging.getLogger(__name__)

        # Cache for latest snapshot
        self._last_snapshot: Optional[MarketSnapshot] = None

    def calculate_micro_price(
        self,
        best_bid: float,
        best_ask: float,
        bid_depth: int,
        ask_depth: int,
    ) -> float:
        """Calculate micro-price from order book levels.

        The micro-price is a depth-weighted fair value that considers the size
        of orders on both sides of the book. It's more accurate than simple mid-price
        when there's imbalanced depth.

        Formula: (best_bid × ask_depth + best_ask × bid_depth) / (bid_depth + ask_depth)

        Args:
            best_bid: Best bid price
            best_ask: Best ask price
            bid_depth: Size at best bid
            ask_depth: Size at best ask

        Returns:
            Calculated micro-price
        """
        total_depth = bid_depth + ask_depth

        # Handle edge case where there's no depth
        if total_depth == 0:
            # Fall back to mid-price
            return (best_bid + best_ask) / 2

        # Depth-weighted price
        micro_price = (best_bid * ask_depth + best_ask * bid_depth) / total_depth

        return micro_price

    def calculate_bands(self, micro_price: float) -> tuple[float, float]:
        """Calculate upper and lower threshold bands around micro-price.

        Args:
            micro_price: Current micro-price

        Returns:
            Tuple of (lower_band, upper_band)
        """
        # Convert basis points to fraction
        band_fraction = self.band_width_bps / 10000

        # Calculate bands
        band_size = micro_price * band_fraction
        lower_band = micro_price - band_size
        upper_band = micro_price + band_size

        # Ensure bands stay within [0, 1] for prediction markets
        lower_band = max(0.0, lower_band)
        upper_band = min(1.0, upper_band)

        return lower_band, upper_band

    def get_market_snapshot(self, depth_levels: int = 5) -> MarketSnapshot:
        """Get current market snapshot with micro-price.

        Args:
            depth_levels: Number of order book levels to include (default: 5)

        Returns:
            MarketSnapshot with current market state

        Raises:
            Exception: If unable to fetch order book data
        """
        try:
            # Fetch order book from API
            order_book = self.client.get_order_book(self.token_id)

            # Extract and sort bids/asks correctly
            bids = order_book.bids or []
            asks = order_book.asks or []

            if not bids or not asks:
                raise ValueError(f"Empty order book for token {self.token_id}")

            # Sort order book correctly:
            # - Bids: highest to lowest (best bid = highest price)
            # - Asks: lowest to highest (best ask = lowest price)
            bids_sorted = sorted(bids, key=lambda b: float(b.price), reverse=True)
            asks_sorted = sorted(asks, key=lambda a: float(a.price))

            # Best prices and depths
            best_bid_price = float(bids_sorted[0].price)
            best_bid_size = int(float(bids_sorted[0].size))
            best_ask_price = float(asks_sorted[0].price)
            best_ask_size = int(float(asks_sorted[0].size))

            # Calculate spread
            spread = best_ask_price - best_bid_price

            # Calculate micro-price
            micro_price = self.calculate_micro_price(
                best_bid_price, best_ask_price, best_bid_size, best_ask_size
            )

            # Calculate threshold bands
            lower_band, upper_band = self.calculate_bands(micro_price)

            # Extract top N levels (already sorted)
            bid_levels = [(float(b.price), int(float(b.size))) for b in bids_sorted[:depth_levels]]
            ask_levels = [(float(a.price), int(float(a.size))) for a in asks_sorted[:depth_levels]]

            # Get our active orders (if any)
            our_orders = self._get_our_orders()

            # Create snapshot
            snapshot = MarketSnapshot(
                token_id=self.token_id,
                timestamp=datetime.now(),
                best_bid=best_bid_price,
                best_ask=best_ask_price,
                spread=spread,
                bid_depth=best_bid_size,
                ask_depth=best_ask_size,
                micro_price=micro_price,
                micro_price_upper_band=upper_band,
                micro_price_lower_band=lower_band,
                bids=bid_levels,
                asks=ask_levels,
                our_orders=our_orders,
            )

            # Cache snapshot
            self._last_snapshot = snapshot

            self.logger.debug(
                f"Market snapshot: bid={best_bid_price}, ask={best_ask_price}, "
                f"micro={micro_price:.4f}, spread={spread:.4f}"
            )

            return snapshot

        except Exception as e:
            self.logger.error(f"Failed to get market snapshot: {e}")
            raise

    def _get_our_orders(self) -> list[dict]:
        """Get our active orders for this token.

        Returns:
            List of our active orders
        """
        try:
            # Fetch our open orders
            orders = self.client.get_orders(self.token_id)

            # Filter for active orders
            active_orders = [
                {
                    "order_id": o.get("id"),
                    "price": float(o.get("price", 0)),
                    "size": int(o.get("size", 0)),
                    "side": o.get("side"),
                }
                for o in orders
                if o.get("status") == "OPEN"
            ]

            return active_orders

        except Exception as e:
            self.logger.warning(f"Failed to fetch our orders: {e}")
            return []

    def is_price_competitive(self, price: float, snapshot: Optional[MarketSnapshot] = None) -> bool:
        """Check if a price is within the micro-price threshold bands.

        Args:
            price: Price to check
            snapshot: Optional snapshot to use (uses cached if not provided)

        Returns:
            True if price is within threshold bands
        """
        if snapshot is None:
            snapshot = self._last_snapshot

        if snapshot is None:
            # No snapshot available, fetch fresh one
            snapshot = self.get_market_snapshot()

        return snapshot.is_price_in_bounds(price)

    def get_distance_from_fair_value(
        self, price: float, snapshot: Optional[MarketSnapshot] = None
    ) -> float:
        """Calculate how far a price is from micro-price (as fraction).

        Args:
            price: Price to check
            snapshot: Optional snapshot to use (uses cached if not provided)

        Returns:
            Distance from micro-price as fraction (e.g., 0.05 = 5% away)
        """
        if snapshot is None:
            snapshot = self._last_snapshot

        if snapshot is None:
            # No snapshot available, fetch fresh one
            snapshot = self.get_market_snapshot()

        return snapshot.distance_from_micro_price(price)

    def get_last_snapshot(self) -> Optional[MarketSnapshot]:
        """Get the last cached market snapshot.

        Returns:
            Last snapshot or None if no snapshot cached
        """
        return self._last_snapshot
