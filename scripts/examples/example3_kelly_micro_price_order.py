"""Example 3: Kelly-sized order with 24-hour monitoring and automatic rebalancing.

This example demonstrates an advanced Kelly strategy system that:
1. Calculates order size using Kelly criterion
2. Determines price using micro-price (depth-weighted fair value)
3. Places the initial order on the exchange
4. Monitors position for 24 hours
5. Automatically rebalances when:
   - Price moves significantly (default: 5%)
   - Position deviates from optimal Kelly size (default: 10%)
   - Periodic check interval reached (default: 15 minutes)

Usage:
    python scripts/examples/example3_kelly_micro_price_order.py \
        --token-id <token_id> \
        --side BUY \
        --win-prob 0.60 \
        --bankroll 1000 \
        --kelly-fraction 0.25 \
        --monitor-hours 24.0
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.event_bus import EventBus
from core.kelly_monitor_daemon import KellyMonitorDaemon
from core.market_monitor import MarketMonitor
from core.order_daemon import OrderDaemon
from core.portfolio_monitor import PortfolioMonitor
from models.enums import OrderSide
from models.order_request import (
    KellyMonitorParams,
    KellyParams,
    MicroPriceParams,
    OrderRequest,
    StrategyType,
)


def setup_logging():
    """Configure logging for the example."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return logging.getLogger(__name__)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Place Kelly-sized order with 24-hour monitoring and rebalancing"
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
    parser.add_argument("--bankroll", type=int, required=True, help="Available bankroll ($)")
    parser.add_argument(
        "--kelly-fraction",
        type=float,
        default=0.25,
        help="Kelly fraction (0.25 = quarter Kelly, default: 0.25)",
    )
    parser.add_argument(
        "--max-position",
        type=int,
        default=10000,
        help="Maximum position size in shares (default: 10000)",
    )
    parser.add_argument(
        "--monitor-hours",
        type=float,
        default=24.0,
        help="Hours to monitor position (default: 24.0)",
    )
    parser.add_argument(
        "--price-threshold",
        type=float,
        default=0.05,
        help="Price change threshold for rebalancing (default: 0.05 = 5%%)",
    )
    args = parser.parse_args()

    logger = setup_logging()

    # Normalize win probability if given as percentage
    win_prob = args.win_prob / 100 if args.win_prob > 1 else args.win_prob
    if not 0 <= win_prob <= 1:
        logger.error("Error: win-prob must be between 0-1 or 0-100")
        return

    portfolio_monitor: Optional[PortfolioMonitor] = None
    order_daemon: Optional[OrderDaemon] = None
    kelly_monitor: Optional[KellyMonitorDaemon] = None

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
        logger.info("Waiting for initial portfolio data...")
        await asyncio.sleep(3)

        # Start event bus
        event_bus = EventBus(logger=logger)
        await event_bus.start()

        # Start order daemon
        logger.info("Starting order daemon...")
        order_daemon = OrderDaemon(
            client=client,
            portfolio_monitor=portfolio_monitor,
            event_bus=event_bus,
            logger=logger,
        )
        await order_daemon.start()

        # Start Kelly monitor daemon
        logger.info("Starting Kelly monitor daemon...")
        kelly_monitor = KellyMonitorDaemon(
            client=client,
            portfolio_monitor=portfolio_monitor,
            order_daemon=order_daemon,
            event_bus=event_bus,
            logger=logger,
        )
        await kelly_monitor.start()

        # Get initial micro-price
        snapshot = market_monitor.get_market_snapshot()
        initial_price = snapshot.micro_price

        logger.info("")
        logger.info("=" * 80)
        logger.info("KELLY 24-HOUR MONITORING SYSTEM")
        logger.info("=" * 80)
        logger.info(f"Token: {args.token_id[:24]}...")
        logger.info(f"Side: {args.side}")
        logger.info(f"Win Probability: {win_prob:.2%}")
        logger.info(f"Bankroll: ${args.bankroll:,}")
        logger.info(f"Kelly Fraction: {args.kelly_fraction}x")
        logger.info(f"Max Position: {args.max_position:,} shares")
        logger.info(f"Monitor Duration: {args.monitor_hours} hours")
        logger.info(f"Price Threshold: {args.price_threshold:.1%}")
        logger.info(f"Initial Micro-Price: ${initial_price:.4f}")
        logger.info("")

        # Create Kelly parameters
        kelly_params = KellyParams(
            win_probability=win_prob,
            kelly_fraction=args.kelly_fraction,
            max_position_size=args.max_position,
            bankroll=args.bankroll,
            micro_price_params=MicroPriceParams(),
        )

        # Create monitoring parameters
        kelly_monitor_params = KellyMonitorParams(
            monitor_duration_hours=args.monitor_hours,
            price_change_threshold_pct=args.price_threshold,
            kelly_params=kelly_params,
        )

        # Place initial order via order daemon
        logger.info("Placing initial Kelly-sized order...")
        side = OrderSide.BUY if args.side == "BUY" else OrderSide.SELL

        initial_request = OrderRequest(
            token_id=args.token_id,
            side=side,
            strategy_type=StrategyType.KELLY,
            max_price=initial_price,
            min_price=initial_price,
            kelly_params=kelly_params,
            timeout=300.0,
        )

        await order_daemon.submit_order(initial_request)
        logger.info("Initial order submitted to daemon")

        # Wait for initial order to be processed
        await asyncio.sleep(5)

        # Register token for 24-hour monitoring
        session_id = await kelly_monitor.add_token_monitor(
            token_id=args.token_id,
            side=side,
            params=kelly_monitor_params,
            initial_price=initial_price,
        )

        logger.info("")
        logger.info("=" * 80)
        logger.info(f"MONITORING SESSION STARTED (ID: {session_id})")
        logger.info("=" * 80)
        logger.info(f"Monitoring {args.token_id[:24]}... for {args.monitor_hours} hours")
        logger.info("Will automatically rebalance when:")
        logger.info(f"  - Price moves ≥{args.price_threshold:.1%}")
        logger.info("  - Position deviates ≥10% from optimal Kelly size")
        logger.info("  - Every 15 minutes (periodic check)")
        logger.info("")
        logger.info("Press Ctrl+C to stop monitoring early")
        logger.info("")

        # Wait for monitoring to complete or user interrupt
        try:
            await asyncio.sleep(args.monitor_hours * 3600)
            logger.info("")
            logger.info("=" * 80)
            logger.info("MONITORING DURATION COMPLETED")
            logger.info("=" * 80)
        except KeyboardInterrupt:
            logger.info("")
            logger.info("=" * 80)
            logger.info("MONITORING INTERRUPTED BY USER")
            logger.info("=" * 80)

        # Display final statistics
        stats = kelly_monitor.get_stats()
        logger.info("")
        logger.info("FINAL STATISTICS")
        logger.info("-" * 80)
        logger.info(f"Total Sessions: {stats['total_sessions']}")
        logger.info(f"Total Rebalances: {stats['total_rebalances']}")
        logger.info("")

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup
        if kelly_monitor and kelly_monitor.is_running():
            logger.info("Stopping Kelly monitor daemon...")
            await kelly_monitor.stop()

        if order_daemon and order_daemon.is_running():
            logger.info("Stopping order daemon...")
            await order_daemon.stop()

        if portfolio_monitor and portfolio_monitor.is_running():
            logger.info("Stopping portfolio monitor...")
            await portfolio_monitor.stop()

        logger.info("Execution complete")


if __name__ == "__main__":
    asyncio.run(main())
