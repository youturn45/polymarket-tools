"""Example 2: Place an order and track it until filled.

This example demonstrates how to:
1. Place an order on Polymarket
2. Add it to a monitoring system
3. Track its fill status in real-time
4. Display progress updates until the order is filled or cancelled

Usage:
    python examples/example2_track_order.py --token-id <token_id> --side BUY --price 0.50 --size 100
"""

import argparse
import asyncio
import logging
from datetime import datetime
from typing import Optional

from py_clob_client.clob_types import OrderType

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.fill_tracker import FillTracker
from core.market_monitor import MarketMonitor
from core.portfolio_monitor import PortfolioMonitor


def setup_logging():
    """Configure logging for the example."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


class OrderTracker:
    """Tracks a specific order until it's filled or cancelled."""

    def __init__(
        self,
        order_id: str,
        total_size: int,
        client: PolymarketClient,
        portfolio_monitor: PortfolioMonitor,
        market_monitor: MarketMonitor,
        logger: logging.Logger,
    ):
        """Initialize order tracker.

        Args:
            order_id: Order ID to track
            total_size: Total order size
            client: Polymarket client
            portfolio_monitor: Portfolio monitoring daemon
            market_monitor: Market monitoring instance
            logger: Logger instance
        """
        self.order_id = order_id
        self.client = client
        self.portfolio_monitor = portfolio_monitor
        self.market_monitor = market_monitor
        self.logger = logger

        # Initialize fill tracker
        self.fill_tracker = FillTracker(total_size=total_size)

        # Tracking state
        self.last_filled_amount = 0
        self.is_complete = False
        self.start_time = datetime.now()

    async def track_until_complete(self, check_interval: float = 5.0, timeout: int = 300):
        """Track order until it's filled, cancelled, or times out.

        Args:
            check_interval: How often to check order status (seconds)
            timeout: Maximum time to track order (seconds)

        Returns:
            True if order completed successfully, False otherwise
        """
        self.logger.info(f"Starting to track order: {self.order_id[:16]}...")
        self.logger.info(f"Target size: {self.fill_tracker.total_size} shares")
        self.logger.info(f"Check interval: {check_interval}s | Timeout: {timeout}s")
        self.logger.info("")

        elapsed = 0
        while elapsed < timeout and not self.is_complete:
            await asyncio.sleep(check_interval)
            elapsed = (datetime.now() - self.start_time).total_seconds()

            # Update order status
            await self._check_order_status()

            # Display progress
            self._display_progress(elapsed)

            # Check if order is complete
            if self.fill_tracker.is_complete():
                self.is_complete = True
                self.logger.info("")
                self.logger.info("=" * 80)
                self.logger.info("ORDER FILLED SUCCESSFULLY!")
                self.logger.info("=" * 80)
                self._display_final_summary()
                return True

        if elapsed >= timeout:
            self.logger.warning("")
            self.logger.warning("=" * 80)
            self.logger.warning(f"ORDER TRACKING TIMEOUT ({timeout}s)")
            self.logger.warning("=" * 80)
            self._display_final_summary()
            return False

        return False

    async def _check_order_status(self):
        """Check order status and update fill tracker if needed."""
        try:
            # Get order from portfolio monitor cache (faster than API call)
            orders = self.portfolio_monitor.get_orders_snapshot()

            if self.order_id not in orders:
                # Order not in cache - might be filled or cancelled
                # Check via API
                order_status = await asyncio.to_thread(self.client.get_order_status, self.order_id)

                status = order_status.get("status", "UNKNOWN")
                if status in ["MATCHED", "FILLED"]:
                    # Order fully filled
                    filled = int(order_status.get("size_matched", 0))
                    if filled > self.last_filled_amount:
                        price = float(order_status.get("price", 0))
                        new_fill = filled - self.last_filled_amount
                        self.fill_tracker.record_tranche_fill(
                            tranche_number=self.fill_tracker.tranche_count + 1,
                            size=new_fill,
                            filled=new_fill,
                            price=price,
                        )
                        self.last_filled_amount = filled
                        self.logger.info(f"  ✓ Fill detected: +{new_fill} shares @ ${price:.4f}")
                elif status == "CANCELLED":
                    self.logger.warning("  Order was cancelled")
                    self.is_complete = True
                return

            # Order is still open
            order = orders[self.order_id]
            filled = int(order.get("size_matched", 0))

            # Check if there's a new fill
            if filled > self.last_filled_amount:
                price = float(order.get("price", 0))
                new_fill = filled - self.last_filled_amount

                # Record the fill
                self.fill_tracker.record_tranche_fill(
                    tranche_number=self.fill_tracker.tranche_count + 1,
                    size=new_fill,
                    filled=new_fill,
                    price=price,
                )

                self.last_filled_amount = filled
                self.logger.info(f"  ✓ Fill detected: +{new_fill} shares @ ${price:.4f}")

        except Exception as e:
            self.logger.error(f"Error checking order status: {e}")

    def _display_progress(self, elapsed: float):
        """Display current tracking progress."""
        # Get market snapshot
        try:
            snapshot = self.market_monitor.get_market_snapshot()
        except Exception:
            snapshot = None

        # Calculate progress
        fill_rate = self.fill_tracker.fill_rate
        filled = self.fill_tracker.total_filled
        remaining = self.fill_tracker.total_remaining
        avg_price = self.fill_tracker.average_fill_price

        # Build progress bar
        bar_width = 30
        filled_width = int(bar_width * fill_rate)
        bar = "█" * filled_width + "░" * (bar_width - filled_width)

        self.logger.info(
            f"[{int(elapsed):3d}s] {bar} {fill_rate*100:5.1f}% | {filled}/{self.fill_tracker.total_size} shares"
        )

        # Show average fill price if we have fills
        if filled > 0:
            self.logger.info(f"        Avg Fill Price: ${avg_price:.4f} | Remaining: {remaining}")

        # Show market context if available
        if snapshot:
            self.logger.info(
                f"        Market: Bid ${snapshot.best_bid:.4f} | Ask ${snapshot.best_ask:.4f} | "
                f"Fair ${snapshot.micro_price:.4f}"
            )

    def _display_final_summary(self):
        """Display final order summary."""
        filled = self.fill_tracker.total_filled
        remaining = self.fill_tracker.total_remaining
        avg_price = self.fill_tracker.average_fill_price
        fill_rate = self.fill_tracker.fill_rate
        duration = (datetime.now() - self.start_time).total_seconds()

        self.logger.info("")
        self.logger.info("FINAL SUMMARY")
        self.logger.info("-" * 80)
        self.logger.info(f"Order ID: {self.order_id}")
        self.logger.info(f"Duration: {duration:.1f}s")
        self.logger.info(
            f"Filled: {filled}/{self.fill_tracker.total_size} shares ({fill_rate*100:.1f}%)"
        )
        self.logger.info(f"Remaining: {remaining} shares")

        if filled > 0:
            self.logger.info(f"Avg Fill Price: ${avg_price:.4f}")
            total_cost = filled * avg_price
            self.logger.info(f"Total Cost: ${total_cost:.2f}")
            self.logger.info("")

            # Show tranche details
            self.logger.info("FILL DETAILS")
            self.logger.info("-" * 80)
            for tranche in self.fill_tracker.get_tranche_summary():
                self.logger.info(
                    f"  Tranche {tranche['tranche']}: {tranche['filled']} shares @ "
                    f"${tranche['price']:.4f} at {tranche['timestamp']}"
                )


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Place an order and track it until filled")
    parser.add_argument("--token-id", type=str, required=True, help="Token ID to trade")
    parser.add_argument(
        "--side", type=str, required=True, choices=["BUY", "SELL"], help="Order side"
    )
    parser.add_argument("--price", type=float, required=True, help="Order price (0.0 to 1.0)")
    parser.add_argument("--size", type=int, required=True, help="Order size in shares")
    parser.add_argument(
        "--check-interval",
        type=float,
        default=5.0,
        help="How often to check order status (seconds)",
    )
    parser.add_argument("--timeout", type=int, default=300, help="Maximum tracking time (seconds)")
    parser.add_argument(
        "--skip-place",
        type=str,
        help="Skip placing order and track existing order ID instead",
    )
    args = parser.parse_args()

    logger = setup_logging()

    # Initialize components
    portfolio_monitor: Optional[PortfolioMonitor] = None

    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config()

        # Initialize client
        logger.info("Initializing Polymarket client...")
        client = PolymarketClient(config, logger=logger)

        # Initialize market monitor
        logger.info(f"Initializing market monitor for token: {args.token_id[:16]}...")
        market_monitor = MarketMonitor(
            client=client, token_id=args.token_id, band_width_bps=50, logger=logger
        )

        # Get initial market snapshot
        logger.info("Fetching market snapshot...")
        snapshot = market_monitor.get_market_snapshot()
        logger.info(f"Current market: Bid ${snapshot.best_bid:.4f} | Ask ${snapshot.best_ask:.4f}")
        logger.info(f"Micro-price (fair value): ${snapshot.micro_price:.4f}")
        logger.info("")

        # Check if price is competitive
        if not args.skip_place:
            competitive = snapshot.is_price_in_bounds(args.price)
            distance = snapshot.distance_from_micro_price(args.price)
            logger.info(f"Your price: ${args.price:.4f}")
            logger.info(
                f"Status: {'✓ COMPETITIVE' if competitive else '✗ OUTSIDE FAIR VALUE BANDS'}"
            )
            logger.info(f"Distance from fair value: {distance*100:+.2f}%")
            logger.info("")

        # Start portfolio monitor
        logger.info("Starting portfolio monitor...")
        portfolio_monitor = PortfolioMonitor(client=client, poll_interval=5.0, logger=logger)
        await portfolio_monitor.start()

        # Wait for initial data
        await asyncio.sleep(2)

        # Place order or use existing
        if args.skip_place:
            order_id = args.skip_place
            logger.info(f"Tracking existing order: {order_id[:16]}...")
        else:
            logger.info("=" * 80)
            logger.info(f"PLACING ORDER: {args.side} {args.size} @ ${args.price:.4f}")
            logger.info("=" * 80)

            response = await asyncio.to_thread(
                client.place_order,
                token_id=args.token_id,
                price=args.price,
                size=args.size,
                side=args.side,
                order_type=OrderType.GTC,
            )

            order_id = response.get("orderID") or response.get("id")
            if not order_id:
                logger.error("Failed to get order ID from response")
                logger.error(f"Response: {response}")
                return

            logger.info(f"Order placed successfully! ID: {order_id[:16]}...")
            logger.info("")

        # Initialize order tracker
        logger.info("Initializing order tracker...")
        tracker = OrderTracker(
            order_id=order_id,
            total_size=args.size,
            client=client,
            portfolio_monitor=portfolio_monitor,
            market_monitor=market_monitor,
            logger=logger,
        )

        # Track order until complete
        logger.info("=" * 80)
        logger.info("TRACKING ORDER")
        logger.info("=" * 80)
        success = await tracker.track_until_complete(
            check_interval=args.check_interval, timeout=args.timeout
        )

        if success:
            logger.info("")
            logger.info("✓ Order tracking completed successfully")
        else:
            logger.info("")
            logger.info("✗ Order tracking incomplete (timeout or cancelled)")

    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if portfolio_monitor and portfolio_monitor.is_running():
            await portfolio_monitor.stop()
        logger.info("Tracking stopped")


if __name__ == "__main__":
    asyncio.run(main())
