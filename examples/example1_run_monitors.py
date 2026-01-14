"""Example 1: Run portfolio and order monitor system.

This example demonstrates how to run both the PortfolioMonitor (for tracking all
orders and positions) and MarketMonitor (for tracking specific market conditions)
together in a real-time monitoring system.

Usage:
    python examples/example1_run_monitors.py --token-id <token_id>
"""

import argparse
import asyncio
import logging

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.market_monitor import MarketMonitor
from core.portfolio_monitor import PortfolioMonitor


def setup_logging():
    """Configure logging for the example."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


async def display_portfolio_status(monitor: PortfolioMonitor, logger: logging.Logger):
    """Display current portfolio status."""
    orders = monitor.get_orders_snapshot()
    positions = monitor.get_positions_snapshot()
    stats = monitor.get_stats()

    logger.info("=" * 80)
    logger.info("PORTFOLIO STATUS")
    logger.info("=" * 80)

    # Display statistics
    logger.info(f"Monitor Running: {stats['is_running']}")
    logger.info(f"Poll Interval: {stats['poll_interval']}s")
    logger.info(
        f"Last Update: {stats['last_orders_update'].strftime('%H:%M:%S') if stats['last_orders_update'] else 'Never'}"
    )
    logger.info("")

    # Display orders
    logger.info(f"OPEN ORDERS ({len(orders)})")
    logger.info("-" * 80)
    for order_id, order in orders.items():
        token_id = order.get("asset_id", "Unknown")
        side = order.get("side", "?")
        price = float(order.get("price", 0))
        size = int(order.get("original_size", 0))
        filled = int(order.get("size_matched", 0))
        fill_pct = (filled / size * 100) if size > 0 else 0

        # Get market question
        question = await monitor.get_market_question(token_id)

        logger.info(f"  Order ID: {order_id[:12]}...")
        logger.info(f"  Market: {question[:60]}")
        logger.info(f"  Side: {side} | Price: ${price:.4f} | Size: {size}")
        logger.info(f"  Filled: {filled} ({fill_pct:.1f}%)")
        logger.info("")

    # Display positions
    logger.info(f"POSITIONS ({len(positions)})")
    logger.info("-" * 80)
    for token_id, pos in positions.items():
        logger.info(f"  Token: {token_id[:12]}...")
        logger.info(f"  Market: {pos.question[:60]}")
        logger.info(f"  Outcome: {pos.outcome}")
        logger.info(f"  Shares: {pos.total_shares:.2f}")
        logger.info(f"  Avg Entry: ${pos.avg_entry_price:.4f} | Current: ${pos.current_price:.4f}")
        logger.info(f"  P&L: ${pos.unrealized_pnl:.2f}")
        logger.info("")


async def display_market_snapshot(market_monitor: MarketMonitor, logger: logging.Logger):
    """Display current market snapshot."""
    try:
        snapshot = market_monitor.get_market_snapshot()

        logger.info("=" * 80)
        logger.info("MARKET SNAPSHOT")
        logger.info("=" * 80)
        logger.info(f"Token ID: {snapshot.token_id[:16]}...")
        logger.info(f"Timestamp: {snapshot.timestamp.strftime('%H:%M:%S')}")
        logger.info("")

        # Price information
        logger.info("PRICES")
        logger.info(f"  Best Bid: ${snapshot.best_bid:.4f} (depth: {snapshot.bid_depth:,})")
        logger.info(f"  Best Ask: ${snapshot.best_ask:.4f} (depth: {snapshot.ask_depth:,})")
        logger.info(f"  Spread: ${snapshot.spread:.4f} ({snapshot.get_spread_bps():.1f} bps)")
        logger.info("")

        # Micro-price information
        logger.info("MICRO-PRICE (Depth-Weighted Fair Value)")
        logger.info(f"  Fair Value: ${snapshot.micro_price:.4f}")
        logger.info(f"  Lower Band: ${snapshot.micro_price_lower_band:.4f}")
        logger.info(f"  Upper Band: ${snapshot.micro_price_upper_band:.4f}")
        logger.info("")

        # Order book depth
        logger.info("ORDER BOOK (Top 5 Levels)")
        logger.info("  BIDS                    |  ASKS")
        logger.info("  Price      Size         |  Price      Size")
        logger.info("  " + "-" * 50)

        for i in range(min(5, len(snapshot.bids), len(snapshot.asks))):
            bid_price, bid_size = snapshot.bids[i] if i < len(snapshot.bids) else (0, 0)
            ask_price, ask_size = snapshot.asks[i] if i < len(snapshot.asks) else (0, 0)
            logger.info(f"  ${bid_price:.4f}  {bid_size:>8,}  |  ${ask_price:.4f}  {ask_size:>8,}")
        logger.info("")

        # Our orders in this market
        if snapshot.our_orders:
            logger.info(f"OUR ORDERS ({len(snapshot.our_orders)})")
            for order in snapshot.our_orders:
                side = order.get("side", "?")
                price = order.get("price", 0)
                size = order.get("size", 0)
                competitive = snapshot.is_price_in_bounds(price)
                status = "✓ COMPETITIVE" if competitive else "✗ OUTSIDE BANDS"
                logger.info(f"  {side:4} {size:>6} @ ${price:.4f} - {status}")
        logger.info("")

    except Exception as e:
        logger.error(f"Failed to get market snapshot: {e}")


async def main():
    """Main monitoring loop."""
    parser = argparse.ArgumentParser(description="Run portfolio and market monitors")
    parser.add_argument(
        "--token-id",
        type=str,
        help="Token ID to monitor (optional - will only show portfolio if not provided)",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=10.0,
        help="Portfolio monitor poll interval in seconds (default: 10.0)",
    )
    parser.add_argument(
        "--display-interval",
        type=float,
        default=30.0,
        help="Display update interval in seconds (default: 30.0)",
    )
    args = parser.parse_args()

    logger = setup_logging()

    try:
        # Load configuration
        logger.info("Loading configuration...")
        config = load_config()

        # Initialize client
        logger.info("Initializing Polymarket client...")
        client = PolymarketClient(config, logger=logger)

        # Initialize portfolio monitor
        logger.info(f"Starting portfolio monitor (poll interval: {args.poll_interval}s)...")
        portfolio_monitor = PortfolioMonitor(
            client=client, poll_interval=args.poll_interval, logger=logger
        )

        # Initialize market monitor if token provided
        market_monitor = None
        if args.token_id:
            logger.info(f"Initializing market monitor for token: {args.token_id[:16]}...")
            market_monitor = MarketMonitor(
                client=client, token_id=args.token_id, band_width_bps=50, logger=logger
            )

        # Start portfolio monitor
        await portfolio_monitor.start()

        logger.info("")
        logger.info("Monitors started successfully!")
        logger.info(f"Display interval: {args.display_interval}s")
        logger.info("Press Ctrl+C to stop")
        logger.info("")

        # Main monitoring loop
        while True:
            await asyncio.sleep(args.display_interval)

            # Display portfolio status
            await display_portfolio_status(portfolio_monitor, logger)

            # Display market snapshot if monitoring a specific token
            if market_monitor:
                await display_market_snapshot(market_monitor, logger)

    except KeyboardInterrupt:
        logger.info("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        if portfolio_monitor and portfolio_monitor.is_running():
            await portfolio_monitor.stop()
        logger.info("Monitors stopped")


if __name__ == "__main__":
    asyncio.run(main())
