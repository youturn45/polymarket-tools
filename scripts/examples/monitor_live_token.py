"""Monitor a live Polymarket token in real-time.

This script demonstrates how to use MarketMonitor to track real market data
from Polymarket's API, including:
- Live order book updates
- Micro-price calculations (depth-weighted fair value)
- Price competitiveness checks
- Historical snapshot storage

Usage:
    # Monitor a specific token
    python scripts/examples/monitor_live_token.py --token-id <your_token_id>

    # With custom settings
    python scripts/examples/monitor_live_token.py \
        --token-id <your_token_id> \
        --interval 5 \
        --band-width 100

Example:
    python scripts/examples/monitor_live_token.py \
        --token-id 21742633143463906290569050155826241533067272736897614950488156847949938836455
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from api.polymarket_client import PolymarketClient  # noqa: E402
from config.settings import load_config  # noqa: E402
from core.market_monitor import MarketMonitor  # noqa: E402


def setup_logging(verbose: bool = False):
    """Configure logging."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    return logging.getLogger(__name__)


def display_snapshot(monitor: MarketMonitor, logger: logging.Logger):
    """Display current market snapshot in a readable format."""
    try:
        # Fetch fresh snapshot
        snapshot = monitor.get_market_snapshot(depth_levels=5)

        # Header
        logger.info("=" * 80)
        logger.info(f"MARKET SNAPSHOT - {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 80)

        # Basic prices
        logger.info("\n📊 MARKET PRICES")
        logger.info(
            f"  Best Bid:  ${snapshot.best_bid:.4f}  (depth: {snapshot.bid_depth:,} shares)"
        )
        logger.info(
            f"  Best Ask:  ${snapshot.best_ask:.4f}  (depth: {snapshot.ask_depth:,} shares)"
        )
        logger.info(f"  Spread:    ${snapshot.spread:.4f}  ({snapshot.get_spread_bps():.1f} bps)")
        logger.info(f"  Mid-Price: ${snapshot.get_mid_price():.4f}")

        # Micro-price (depth-weighted fair value)
        logger.info("\n💎 MICRO-PRICE (Depth-Weighted Fair Value)")
        logger.info(f"  Fair Value:  ${snapshot.micro_price:.4f}")
        logger.info(f"  Lower Band:  ${snapshot.micro_price_lower_band:.4f}")
        logger.info(f"  Upper Band:  ${snapshot.micro_price_upper_band:.4f}")
        logger.info(
            f"  Band Width:  {monitor.band_width_bps} bps ({monitor.band_width_bps/100:.2f}%)"
        )

        # Interpret what this means
        if snapshot.micro_price > snapshot.get_mid_price():
            bias = "ASK"
            reason = "more bid depth (buyers stronger)"
        else:
            bias = "BID"
            reason = "more ask depth (sellers stronger)"
        logger.info(f"\n  ℹ️  Micro-price is closer to {bias} side ({reason})")

        # Order book depth
        logger.info("\n📖 ORDER BOOK (Top 5 Levels)")
        logger.info("  " + "-" * 76)
        logger.info(f"  {'BIDS':^35} | {'ASKS':^35}")
        logger.info(
            f"  {'Price':>12}  {'Size':>12}  {'Total':>8} | {'Price':>12}  {'Size':>12}  {'Total':>8}"
        )
        logger.info("  " + "-" * 76)

        bid_total = 0
        ask_total = 0
        max_levels = max(len(snapshot.bids), len(snapshot.asks))

        for i in range(min(5, max_levels)):
            # Bid side
            if i < len(snapshot.bids):
                bid_price, bid_size = snapshot.bids[i]
                bid_total += bid_size
                bid_str = f"${bid_price:>11.4f}  {bid_size:>12,}  {bid_total:>8,}"
            else:
                bid_str = " " * 35

            # Ask side
            if i < len(snapshot.asks):
                ask_price, ask_size = snapshot.asks[i]
                ask_total += ask_size
                ask_str = f"${ask_price:>11.4f}  {ask_size:>12,}  {ask_total:>8,}"
            else:
                ask_str = " " * 35

            logger.info(f"  {bid_str} | {ask_str}")

        # Our orders (if any)
        if snapshot.our_orders:
            logger.info(f"\n🎯 OUR ORDERS ({len(snapshot.our_orders)})")
            logger.info("  " + "-" * 76)
            for order in snapshot.our_orders:
                order_id = order.get("order_id", "unknown")[:12]
                side = order.get("side", "?")
                price = order.get("price", 0)
                size = order.get("size", 0)

                # Check competitiveness
                is_competitive = snapshot.is_price_in_bounds(price)
                distance = snapshot.distance_from_micro_price(price)

                status = "✓ COMPETITIVE" if is_competitive else "✗ OUTSIDE BANDS"
                logger.info(
                    f"  {order_id}... | {side:4} {size:>6} @ ${price:.4f} | "
                    f"{distance:+.2%} from fair | {status}"
                )
        else:
            logger.info("\n🎯 OUR ORDERS: None")

        logger.info("\n" + "=" * 80 + "\n")

    except Exception as e:
        logger.error(f"Failed to get market snapshot: {e}", exc_info=True)


async def run_continuous_monitor(
    token_id: str,
    interval: float,
    band_width: int,
    logger: logging.Logger,
):
    """Run continuous market monitoring with async background updates."""
    logger.info("🚀 Starting continuous market monitor...")

    # Load config and initialize client
    config = load_config()
    client = PolymarketClient(config, logger=logger)

    # Create market monitor
    monitor = MarketMonitor(
        client=client,
        token_id=token_id,
        band_width_bps=band_width,
        poll_interval=interval,
        logger=logger,
    )

    logger.info(f"📡 Monitoring token: {token_id[:16]}...")
    logger.info(f"⏱️  Update interval: {interval} seconds")
    logger.info(f"📏 Band width: {band_width} bps ({band_width/100:.2f}%)")
    logger.info("\nPress Ctrl+C to stop\n")

    try:
        # Start background monitoring
        await monitor.start_monitoring()

        # Display loop
        while True:
            display_snapshot(monitor, logger)
            await asyncio.sleep(interval)

    except KeyboardInterrupt:
        logger.info("\n🛑 Stopping monitor...")
    finally:
        await monitor.stop_monitoring()
        logger.info("✅ Monitor stopped")


def run_single_snapshot(
    token_id: str,
    band_width: int,
    logger: logging.Logger,
):
    """Fetch and display a single market snapshot (non-async)."""
    logger.info("📸 Fetching single market snapshot...")

    # Load config and initialize client
    config = load_config()
    client = PolymarketClient(config, logger=logger)

    # Create market monitor
    monitor = MarketMonitor(
        client=client,
        token_id=token_id,
        band_width_bps=band_width,
        logger=logger,
    )

    # Display snapshot
    display_snapshot(monitor, logger)

    # Show DB info
    logger.info("💾 Snapshot saved to database:")
    latest = monitor.get_latest_snapshot_from_db()
    if latest:
        logger.info(f"  Token: {latest['token_id'][:16]}...")
        logger.info(f"  Time:  {latest['timestamp']}")
        logger.info(f"  Bid:   ${latest['best_bid']:.4f}")
        logger.info(f"  Ask:   ${latest['best_ask']:.4f}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor a live Polymarket token",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single snapshot
  python scripts/examples/monitor_live_token.py --token-id 21742633143463906290569050155826241533067272736897614950488156847949938836455

  # Continuous monitoring (updates every 10 seconds)
  python scripts/examples/monitor_live_token.py --token-id <token> --continuous --interval 10

  # Wider price bands (100 bps = 1%)
  python scripts/examples/monitor_live_token.py --token-id <token> --band-width 100
        """,
    )

    parser.add_argument(
        "--token-id",
        type=str,
        required=True,
        help="Token ID to monitor",
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuous monitoring (default: single snapshot)",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=10.0,
        help="Update interval in seconds for continuous mode (default: 10.0)",
    )
    parser.add_argument(
        "--band-width",
        type=int,
        default=50,
        help="Micro-price band width in basis points (default: 50 = 0.5%%)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    # Setup logging
    logger = setup_logging(args.verbose)

    # Run appropriate mode
    if args.continuous:
        asyncio.run(
            run_continuous_monitor(
                token_id=args.token_id,
                interval=args.interval,
                band_width=args.band_width,
                logger=logger,
            )
        )
    else:
        run_single_snapshot(
            token_id=args.token_id,
            band_width=args.band_width,
            logger=logger,
        )


if __name__ == "__main__":
    main()
