"""Example 3: Kelly-sized order with micro-price and automatic replacement.

This example demonstrates an advanced order placement system that:
1. Calculates order size using Kelly criterion
2. Determines price using micro-price (depth-weighted fair value)
3. Places the order on the exchange
4. Monitors market for price movement
5. Cancels and replaces order if price moves more than a tick

Usage:
    python examples/example3_kelly_micro_price_order.py \
        --token-id <token_id> \
        --side BUY \
        --win-prob 0.60 \
        --bankroll 1000 \
        --kelly-fraction 0.25
"""

import argparse
import asyncio
import logging
from datetime import datetime
from typing import Optional

from py_clob_client.clob_types import OrderType

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.market_monitor import MarketMonitor
from core.portfolio_monitor import PortfolioMonitor
from utils.kelly_calculator import calculate_kelly_fraction


def setup_logging():
    """Configure logging for the example."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


class KellyMicroPriceOrderManager:
    """Manages Kelly-sized orders with micro-price and automatic replacement."""

    # Tick size for Polymarket (0.01 = 1 cent)
    TICK_SIZE = 0.01

    def __init__(
        self,
        token_id: str,
        side: str,
        win_probability: float,
        bankroll: float,
        kelly_fraction: float,
        client: PolymarketClient,
        market_monitor: MarketMonitor,
        portfolio_monitor: PortfolioMonitor,
        logger: logging.Logger,
        max_position_size: Optional[int] = None,
    ):
        """Initialize order manager.

        Args:
            token_id: Token ID to trade
            side: Order side ("BUY" or "SELL")
            win_probability: Estimated probability of winning (0-1)
            bankroll: Available capital for position sizing
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly)
            client: Polymarket API client
            market_monitor: Market monitor instance
            portfolio_monitor: Portfolio monitor instance
            logger: Logger instance
            max_position_size: Maximum position size (None = unlimited)
        """
        self.token_id = token_id
        self.side = side.upper()
        self.win_probability = win_probability
        self.bankroll = bankroll
        self.kelly_fraction = kelly_fraction
        self.max_position_size = max_position_size or 999999

        self.client = client
        self.market_monitor = market_monitor
        self.portfolio_monitor = portfolio_monitor
        self.logger = logger

        # Current order state
        self.current_order_id: Optional[str] = None
        self.current_order_price: Optional[float] = None
        self.current_order_size: Optional[int] = None
        self.reference_micro_price: Optional[float] = None

        # Statistics
        self.total_fills = 0
        self.total_filled_size = 0
        self.replacements = 0
        self.start_time = datetime.now()

    def calculate_order_size(self, micro_price: float) -> int:
        """Calculate order size using Kelly criterion.

        Args:
            micro_price: Current micro-price

        Returns:
            Order size in shares
        """
        # Calculate full Kelly fraction
        kelly_full = calculate_kelly_fraction(self.win_probability, micro_price, self.side)

        # Apply Kelly fraction multiplier
        adjusted_kelly = kelly_full * self.kelly_fraction

        # Calculate position in dollars
        position_dollars = self.bankroll * adjusted_kelly

        # Convert to shares
        if micro_price == 0:
            shares = 0
        else:
            shares = int(position_dollars / micro_price)

        # Cap at max position size
        shares = min(shares, self.max_position_size)

        self.logger.info("Kelly calculation:")
        self.logger.info(f"  Full Kelly: {kelly_full:.4f} ({kelly_full*100:.2f}% of bankroll)")
        self.logger.info(f"  Adjusted ({self.kelly_fraction}x): {adjusted_kelly:.4f}")
        self.logger.info(f"  Position $: ${position_dollars:.2f}")
        self.logger.info(f"  Shares: {shares:,}")

        return shares

    async def get_current_position(self) -> int:
        """Get current position for this token.

        Returns:
            Number of shares currently held
        """
        try:
            positions = self.portfolio_monitor.get_positions_snapshot()
            if self.token_id in positions:
                return int(positions[self.token_id].total_shares)
        except Exception as e:
            self.logger.warning(f"Failed to get position: {e}")
        return 0

    async def place_order_at_micro_price(self) -> bool:
        """Place order at current micro-price.

        Returns:
            True if order placed successfully
        """
        try:
            # Get market snapshot
            snapshot = self.market_monitor.get_market_snapshot()
            micro_price = snapshot.micro_price

            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info("MARKET SNAPSHOT")
            self.logger.info("=" * 80)
            self.logger.info(f"Best Bid: ${snapshot.best_bid:.4f}")
            self.logger.info(f"Best Ask: ${snapshot.best_ask:.4f}")
            self.logger.info(
                f"Spread: ${snapshot.spread:.4f} ({snapshot.get_spread_bps():.1f} bps)"
            )
            self.logger.info(f"Micro-Price: ${micro_price:.4f}")
            self.logger.info(f"  Lower Band: ${snapshot.micro_price_lower_band:.4f}")
            self.logger.info(f"  Upper Band: ${snapshot.micro_price_upper_band:.4f}")
            self.logger.info("")

            # Calculate order size using Kelly
            self.logger.info("=" * 80)
            self.logger.info("KELLY POSITION SIZING")
            self.logger.info("=" * 80)
            self.logger.info(f"Win Probability: {self.win_probability:.2%}")
            self.logger.info(f"Bankroll: ${self.bankroll:,.2f}")
            self.logger.info(f"Kelly Fraction: {self.kelly_fraction} (Quarter Kelly)")
            self.logger.info("")

            order_size = self.calculate_order_size(micro_price)

            if order_size == 0:
                self.logger.warning("Kelly criterion suggests NOT to bet (size = 0)")
                return False

            # Get existing position
            existing_position = await self.get_current_position()
            if existing_position > 0:
                self.logger.info(f"Existing Position: {existing_position} shares")
                self.logger.info(f"Incremental Size: {order_size} shares")

            # Round price to tick size
            order_price = round(micro_price / self.TICK_SIZE) * self.TICK_SIZE

            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info("PLACING ORDER")
            self.logger.info("=" * 80)
            self.logger.info(f"Side: {self.side}")
            self.logger.info(f"Price: ${order_price:.4f} (rounded to tick)")
            self.logger.info(f"Size: {order_size:,} shares")
            self.logger.info(f"Notional: ${order_price * order_size:.2f}")
            self.logger.info("")

            # Place order
            response = await asyncio.to_thread(
                self.client.place_order,
                token_id=self.token_id,
                price=order_price,
                size=order_size,
                side=self.side,
                order_type=OrderType.GTC,
            )

            # Extract order ID
            order_id = response.get("orderID") or response.get("id")
            if not order_id:
                self.logger.error("Failed to get order ID from response")
                return False

            # Store order state
            self.current_order_id = order_id
            self.current_order_price = order_price
            self.current_order_size = order_size
            self.reference_micro_price = micro_price

            self.logger.info(f"✓ Order placed: {order_id[:16]}...")
            self.logger.info("")

            return True

        except Exception as e:
            self.logger.error(f"Failed to place order: {e}", exc_info=True)
            return False

    async def cancel_current_order(self) -> bool:
        """Cancel the current order.

        Returns:
            True if cancelled successfully
        """
        if not self.current_order_id:
            return True

        try:
            self.logger.info(f"Cancelling order: {self.current_order_id[:16]}...")
            await asyncio.to_thread(self.client.cancel_order, self.current_order_id)
            self.logger.info("✓ Order cancelled")
            return True

        except Exception as e:
            self.logger.error(f"Failed to cancel order: {e}")
            return False

    def should_replace_order(self, current_micro_price: float) -> bool:
        """Check if order should be replaced due to price movement.

        Args:
            current_micro_price: Current market micro-price

        Returns:
            True if order should be replaced
        """
        if self.reference_micro_price is None:
            return False

        # Calculate price change in ticks
        price_change = abs(current_micro_price - self.reference_micro_price)
        ticks_moved = price_change / self.TICK_SIZE

        # Replace if moved more than 1 tick
        if ticks_moved >= 1.0:
            self.logger.info(
                f"Price moved {ticks_moved:.1f} ticks "
                f"(${self.reference_micro_price:.4f} -> ${current_micro_price:.4f})"
            )
            return True

        return False

    async def monitor_and_replace(self, check_interval: float = 5.0, timeout: int = 300):
        """Monitor market and replace order when price moves.

        Args:
            check_interval: How often to check market (seconds)
            timeout: Maximum monitoring time (seconds)
        """
        self.logger.info("=" * 80)
        self.logger.info("MONITORING STARTED")
        self.logger.info("=" * 80)
        self.logger.info(f"Check Interval: {check_interval}s")
        self.logger.info(f"Timeout: {timeout}s")
        self.logger.info(f"Replace Trigger: Price moves >1 tick (${self.TICK_SIZE:.4f})")
        self.logger.info("")

        elapsed = 0
        while elapsed < timeout:
            await asyncio.sleep(check_interval)
            elapsed = (datetime.now() - self.start_time).total_seconds()

            # Check if order still exists
            orders = self.portfolio_monitor.get_orders_snapshot()

            if self.current_order_id not in orders:
                # Order filled or cancelled
                self.logger.info("Order no longer active (filled or cancelled)")
                break

            # Get current order status
            order = orders[self.current_order_id]
            filled = int(order.get("size_matched", 0))

            if filled > self.total_filled_size:
                # Partial fill detected
                new_fill = filled - self.total_filled_size
                self.total_filled_size = filled
                self.total_fills += 1
                self.logger.info(f"✓ Partial fill: +{new_fill} shares (total: {filled})")

            # Check if fully filled
            if filled >= self.current_order_size:
                self.logger.info("")
                self.logger.info("=" * 80)
                self.logger.info("ORDER FULLY FILLED")
                self.logger.info("=" * 80)
                self._display_final_summary()
                return

            # Get current market snapshot
            try:
                snapshot = self.market_monitor.get_market_snapshot()
                current_micro_price = snapshot.micro_price

                self.logger.info(
                    f"[{int(elapsed):3d}s] Market: Bid ${snapshot.best_bid:.4f} | "
                    f"Ask ${snapshot.best_ask:.4f} | Fair ${current_micro_price:.4f}"
                )

                # Check if order should be replaced
                if self.should_replace_order(current_micro_price):
                    self.logger.info("")
                    self.logger.info("🔄 REPLACING ORDER (price moved >1 tick)")
                    self.logger.info("-" * 80)

                    # Cancel current order
                    await self.cancel_current_order()
                    self.replacements += 1

                    # Place new order at new micro-price
                    success = await self.place_order_at_micro_price()

                    if not success:
                        self.logger.error("Failed to replace order, stopping monitoring")
                        break

                    self.logger.info("✓ Order replacement complete")
                    self.logger.info("")

            except Exception as e:
                self.logger.error(f"Error during monitoring: {e}")

        # Timeout or error
        if elapsed >= timeout:
            self.logger.info("")
            self.logger.info("=" * 80)
            self.logger.info("MONITORING TIMEOUT")
            self.logger.info("=" * 80)
            self._display_final_summary()

    def _display_final_summary(self):
        """Display final summary of order execution."""
        duration = (datetime.now() - self.start_time).total_seconds()

        self.logger.info("")
        self.logger.info("EXECUTION SUMMARY")
        self.logger.info("-" * 80)
        self.logger.info(f"Duration: {duration:.1f}s")
        self.logger.info(f"Total Fills: {self.total_fills}")
        self.logger.info(f"Total Filled: {self.total_filled_size} shares")
        if self.current_order_size:
            fill_rate = (self.total_filled_size / self.current_order_size) * 100
            self.logger.info(f"Fill Rate: {fill_rate:.1f}%")
        self.logger.info(f"Order Replacements: {self.replacements}")
        self.logger.info("")


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Place Kelly-sized order with micro-price and auto-replacement"
    )
    parser.add_argument("--token-id", type=str, required=True, help="Token ID to trade")
    parser.add_argument(
        "--side", type=str, required=True, choices=["BUY", "SELL"], help="Order side"
    )
    parser.add_argument(
        "--win-prob",
        type=float,
        required=True,
        help="Win probability (0.0-1.0 or 0-100 if percentage)",
    )
    parser.add_argument("--bankroll", type=float, required=True, help="Available bankroll ($)")
    parser.add_argument(
        "--kelly-fraction",
        type=float,
        default=0.25,
        help="Kelly fraction (0.25 = quarter Kelly, default: 0.25)",
    )
    parser.add_argument(
        "--max-position",
        type=int,
        help="Maximum position size in shares (optional)",
    )
    parser.add_argument(
        "--check-interval",
        type=float,
        default=5.0,
        help="Market check interval in seconds (default: 5.0)",
    )
    parser.add_argument(
        "--timeout", type=int, default=300, help="Maximum monitoring time in seconds (default: 300)"
    )
    args = parser.parse_args()

    logger = setup_logging()

    # Normalize win probability if given as percentage
    win_prob = args.win_prob / 100 if args.win_prob > 1 else args.win_prob
    if not 0 <= win_prob <= 1:
        logger.error("Error: win-prob must be between 0-1 or 0-100")
        return

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

        # Start portfolio monitor
        logger.info("Starting portfolio monitor...")
        portfolio_monitor = PortfolioMonitor(client=client, poll_interval=5.0, logger=logger)
        await portfolio_monitor.start()

        # Wait for initial data
        logger.info("Waiting for initial data...")
        await asyncio.sleep(3)

        # Initialize order manager
        logger.info("")
        logger.info("=" * 80)
        logger.info("KELLY MICRO-PRICE ORDER MANAGER")
        logger.info("=" * 80)
        logger.info(f"Token: {args.token_id[:24]}...")
        logger.info(f"Side: {args.side}")
        logger.info(f"Win Probability: {win_prob:.2%}")
        logger.info(f"Bankroll: ${args.bankroll:,.2f}")
        logger.info(f"Kelly Fraction: {args.kelly_fraction}x")
        if args.max_position:
            logger.info(f"Max Position: {args.max_position:,} shares")
        logger.info("")

        manager = KellyMicroPriceOrderManager(
            token_id=args.token_id,
            side=args.side,
            win_probability=win_prob,
            bankroll=args.bankroll,
            kelly_fraction=args.kelly_fraction,
            client=client,
            market_monitor=market_monitor,
            portfolio_monitor=portfolio_monitor,
            logger=logger,
            max_position_size=args.max_position,
        )

        # Place initial order
        success = await manager.place_order_at_micro_price()
        if not success:
            logger.error("Failed to place initial order")
            return

        # Monitor and replace as needed
        await manager.monitor_and_replace(check_interval=args.check_interval, timeout=args.timeout)

    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if portfolio_monitor and portfolio_monitor.is_running():
            await portfolio_monitor.stop()
        logger.info("Execution complete")


if __name__ == "__main__":
    asyncio.run(main())
