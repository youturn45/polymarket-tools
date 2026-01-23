"""Test script for portfolio monitor API access and validation.

This script validates the portfolio monitor implementation by:
- Testing data access methods (orders, positions, metadata)
- Verifying market question resolution and caching
- Measuring cache performance
- Displaying formatted portfolio data

Usage:
    python scripts/examples/test_monitor_api.py

The script will run for ~30 seconds and display portfolio data
with market questions resolved.
"""

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
import logging
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.portfolio_monitor import PortfolioMonitor

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Test monitor data access and validation."""
    logger.info("Initializing portfolio monitor test...")

    try:
        # Initialize client and monitor
        config = load_config()
        client = PolymarketClient(config=config, logger=logger)

        async with PortfolioMonitor(client, poll_interval=5.0) as monitor:
            logger.info("Monitor started, waiting for first poll (6 seconds)...")
            await asyncio.sleep(6)

            # Test 1: Orders snapshot
            print("\n" + "=" * 70)
            print("TEST 1: Orders Snapshot")
            print("=" * 70)

            orders = monitor.get_orders_snapshot()
            print(f"\nFound {len(orders)} open orders")

            if orders:
                print("\nSample orders (up to 3):")
                for i, (order_id, order) in enumerate(list(orders.items())[:3]):
                    token_id = order.get("asset_id")
                    side = order.get("side", "N/A")
                    size = order.get("size", 0)
                    price = order.get("price", 0)

                    # Resolve market question
                    question = await monitor.get_market_question(token_id)

                    print(f"\n  Order {i+1}: {order_id[:16]}...")
                    print(f"    Side:   {side:4s}")
                    print(f"    Size:   {size}")
                    print(f"    Price:  ${float(price):.3f}")
                    print(f"    Market: {question[:60]}...")
            else:
                print("  No open orders found")

            # Test 2: Positions snapshot
            print("\n" + "=" * 70)
            print("TEST 2: Positions Snapshot")
            print("=" * 70)

            positions = monitor.get_positions_snapshot()
            print(f"\nFound {len(positions)} positions")

            if positions:
                print("\nPosition details:")
                for i, (token_id, pos) in enumerate(positions.items()):
                    print(f"\n  Position {i+1}:")
                    print(f"    Token:    {token_id[:16]}...")
                    print(f"    Outcome:  {pos.outcome}")
                    print(f"    Shares:   {pos.total_shares:.2f}")
                    print(f"    Avg Cost: ${pos.avg_entry_price:.4f}")
                    if pos.question:
                        print(f"    Market:   {pos.question[:60]}...")
            else:
                print("  No positions found")

            # Test 3: Cache performance
            print("\n" + "=" * 70)
            print("TEST 3: Cache Performance")
            print("=" * 70)

            if orders:
                token_id = next(iter(orders.values()))["asset_id"]
                print(f"\nTesting cache for token: {token_id[:16]}...")

                # First call (may fetch from API if not cached)
                start = time.time()
                q1 = await monitor.get_market_question(token_id)
                t1 = time.time() - start

                # Second call (should be cached)
                start = time.time()
                await monitor.get_market_question(token_id)
                t2 = time.time() - start

                print(f"\n  First call:  {t1*1000:.2f}ms")
                print(f"  Second call: {t2*1000:.2f}ms (cached)")
                print(f"  Speedup:     {t1/t2:.1f}x" if t2 > 0 else "  Speedup:     N/A")
                print(f"  Question:    {q1[:60]}...")

                if t2 < 0.001:
                    print("\n  ✓ Cache is working correctly")
                else:
                    print("\n  ⚠ Cache may not be working optimally")
            else:
                print("\n  Skipped: No orders available for testing")

            # Test 4: Monitor stats
            print("\n" + "=" * 70)
            print("TEST 4: Monitor Statistics")
            print("=" * 70)

            stats = monitor.get_stats()
            print(f"\n  Orders cached:    {stats['orders_count']}")
            print(f"  Positions cached: {stats['positions_count']}")
            print(f"  Markets cached:   {stats['metadata_count']}")
            print(f"  Poll interval:    {stats['poll_interval']}s")
            print(f"  Is running:       {stats['is_running']}")
            print(f"  Last order update: {stats['last_orders_update']}")
            print(f"  Last pos update:   {stats['last_positions_update']}")

            # Test 5: Data staleness
            print("\n" + "=" * 70)
            print("TEST 5: Data Freshness")
            print("=" * 70)

            is_stale = monitor.is_data_stale(max_age_seconds=10)
            print(f"\n  Data stale (10s threshold): {is_stale}")

            if not is_stale:
                print("  ✓ Data is fresh")
            else:
                print("  ⚠ Data may be stale")

            # Wait for another poll cycle
            print("\n" + "=" * 70)
            print("Waiting for next poll cycle (5 seconds)...")
            print("=" * 70)
            await asyncio.sleep(6)

            # Check if data updated
            new_stats = monitor.get_stats()
            if new_stats["last_orders_update"] != stats["last_orders_update"]:
                print("\n  ✓ Data updated successfully")
            else:
                print("\n  ⚠ Data did not update (may be an issue)")

            print("\n" + "=" * 70)
            print("TEST COMPLETED")
            print("=" * 70)
            print("\nAll tests finished. Monitor will now shut down.")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
