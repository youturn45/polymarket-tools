"""Standalone portfolio monitor daemon runner.

This script runs the portfolio monitoring daemon that continuously polls
the Polymarket API to maintain an in-memory cache of orders, positions,
and market metadata.

Usage:
    python scripts/examples/run_portfolio_monitor.py

The daemon will:
- Poll orders and positions every 10 seconds
- Display detailed order and position information
- Resolve market questions (human-readable names)
- Update display every 30 seconds
- Run until interrupted with Ctrl+C
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import logging  # noqa: E402
import sys  # noqa: E402
from datetime import datetime  # noqa: E402
from pathlib import Path  # noqa: E402

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.polymarket_client import PolymarketClient  # noqa: E402
from config.settings import load_config  # noqa: E402
from core.portfolio_monitor import PortfolioMonitor  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def display_portfolio_status(monitor: PortfolioMonitor):
    """Display detailed portfolio status with order and position information."""
    orders = monitor.get_orders_snapshot()
    positions = monitor.get_positions_snapshot()

    print("\n" + "=" * 70)
    print(f"PORTFOLIO STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # Display orders
    print(f"\n📋 OPEN ORDERS ({len(orders)})")
    print("-" * 70)

    if orders:
        for i, (order_id, order) in enumerate(orders.items(), 1):
            token_id = order.get("asset_id")
            side = order.get("side", "N/A")
            price = float(order.get("price", 0))
            original_size = float(order.get("original_size", 0))
            size_matched = float(order.get("size_matched", 0))
            status = order.get("status", "N/A")

            # Calculate fill percentage
            fill_pct = (size_matched / original_size * 100) if original_size > 0 else 0

            # Get market question (may trigger lazy load)
            question = await monitor.get_market_question(token_id)

            print(f"\n{i}. Order {order_id[:16]}...")
            print(f"   Side:     {side}")
            print(f"   Price:    ${price:.4f}")
            print(f"   Size:     {original_size:.0f} ({fill_pct:.1f}% filled)")
            print(f"   Status:   {status}")
            print(f"   Market:   {question[:60]}{'...' if len(question) > 60 else ''}")
    else:
        print("   No open orders")

    # Display positions
    print(f"\n💼 POSITIONS ({len(positions)})")
    print("-" * 70)

    if positions:
        # Sort by current value (shares * price) descending
        sorted_positions = sorted(
            positions.items(),
            key=lambda x: x[1].total_shares * x[1].current_price,
            reverse=True,
        )

        for i, (_token_id, pos) in enumerate(sorted_positions, 1):
            current_value = pos.total_shares * pos.current_price
            print(f"\n{i}. {pos.question[:108]}{'...' if len(pos.question) > 108 else ''}")
            print(f"   Position:  {pos.outcome}")
            print(f"   Shares:    {pos.total_shares:.2f}")
            print(f"   Avg Cost:  ${pos.avg_entry_price:.4f}")
            print(f"   Current:   ${pos.current_price:.4f}")
            print(f"   Value:     ${current_value:.2f}")
            print(f"   P&L:       ${pos.unrealized_pnl:.2f}")
    else:
        print("   No positions")

    print("\n" + "=" * 70 + "\n")


async def main():
    """Run portfolio monitor daemon with detailed display."""
    try:
        # Initialize client
        print("Initializing Polymarket client...")
        config = load_config()
        client = PolymarketClient(config=config, logger=logger)

        # Create monitor
        monitor = PortfolioMonitor(client=client, poll_interval=10.0, logger=logger)

        print("Starting portfolio monitor daemon...")
        print("Press Ctrl+C to stop\n")

        await monitor.start()

        # Wait for first poll to complete
        print("Waiting for first data fetch (11 seconds)...")
        await asyncio.sleep(11)

        # Display status immediately
        await display_portfolio_status(monitor)

        # Keep running and display periodic status
        try:
            while True:
                await asyncio.sleep(30)  # Display every 30s
                await display_portfolio_status(monitor)

        except KeyboardInterrupt:
            print("\nReceived shutdown signal...")

    except KeyboardInterrupt:
        print("Shutdown during initialization")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1
    finally:
        # Ensure clean shutdown
        if "monitor" in locals() and monitor.is_running():
            print("Shutting down monitor...")
            await monitor.stop()

    print("Portfolio monitor stopped")
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
