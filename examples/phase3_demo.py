"""Phase 3 Demo: Advanced Strategies and Order Daemon

This script demonstrates the Phase 3 features:
- Order daemon with asynchronous queue
- Micro-price adaptive strategy
- Kelly criterion position sizing
- Combined strategy usage

Usage:
    python examples/phase3_demo.py
"""

import asyncio
import logging

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.order_daemon import OrderDaemon
from models.enums import OrderSide
from models.order import StrategyParams
from models.order_request import KellyParams, MicroPriceParams, OrderRequest, StrategyType

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def demo_order_daemon():
    """Demonstrate order daemon with queue management."""
    logger.info("=== Order Daemon Demo ===")

    # Load configuration
    config = load_config()

    # Initialize client with config object
    client = PolymarketClient(config)

    logger.info("API credentials will be auto-derived from private key")

    # Create order daemon
    async with OrderDaemon(client, max_queue_size=10) as daemon:
        logger.info("Order daemon started")

        # Example 1: Submit iceberg order
        micro_request = OrderRequest(
            market_id="your-market-id",
            token_id="64115571112663071888929599027003715026866623388277198289581125847375946298399",
            side=OrderSide.SELL,
            strategy_type=StrategyType.MICRO_PRICE,
            total_size=3485,
            max_price=1,
            min_price=0.003,
            iceberg_params=StrategyParams(
                initial_tranche_size=200,
                min_tranche_size=50,
                max_tranche_size=300,
            ),
        )

        logger.info("Submitting iceberg order to daemon...")
        await daemon.submit_order(micro_request)

        # Wait for all orders to complete (with timeout)
        logger.info("Waiting for orders to complete...")
        completed = await daemon.wait_for_completion(timeout=300)  # 5 minute timeout

        if completed:
            logger.info("All orders completed!")
        else:
            logger.warning("Timeout waiting for orders")

        # Check results
        completed_orders = daemon.get_completed_orders()
        failed_orders = daemon.get_failed_orders()

        logger.info(f"Completed: {len(completed_orders)} orders")
        logger.info(f"Failed: {len(failed_orders)} orders")

        for order in completed_orders:
            logger.info(
                f"  {order.order_id}: {order.side.value} "
                f"{order.filled_amount}/{order.total_size} @ avg {order.get_average_price():.4f}"
            )

    logger.info("Order daemon stopped\n")


async def demo_micro_price_strategy():
    """Demonstrate micro-price adaptive strategy."""
    logger.info("=== Micro-Price Strategy Demo ===")

    # Load configuration
    config = load_config()

    # Initialize client with config object
    client = PolymarketClient(config)

    # Create order daemon
    async with OrderDaemon(client) as daemon:
        # Micro-price order with tight threshold
        request = OrderRequest(
            market_id="your-market-id",
            token_id="your-token-id",
            side=OrderSide.BUY,
            strategy_type=StrategyType.MICRO_PRICE,
            total_size=1000,
            max_price=0.52,
            min_price=0.48,
            micro_price_params=MicroPriceParams(
                threshold_bps=25,  # Very tight 0.25% threshold
                check_interval=1.0,  # Check every second
                max_adjustments=20,  # Allow more adjustments
                aggression_limit_bps=50,  # Stay within 0.5% of best
            ),
        )

        logger.info("Submitting micro-price order with tight threshold...")
        logger.info("  - Threshold: 25 bps (0.25%)")
        logger.info("  - Check interval: 1.0s")
        logger.info("  - Max adjustments: 20")
        logger.info("  - Aggression limit: 50 bps (0.5%)")

        await daemon.submit_order(request)
        await daemon.wait_for_completion(timeout=180)

        # Show results
        completed = daemon.get_completed_orders()
        if completed:
            order = completed[0]
            logger.info("Order completed:")
            logger.info(f"  Filled: {order.filled_amount}/{order.total_size}")
            logger.info(f"  Avg price: {order.get_average_price():.4f}")
            logger.info(f"  Adjustments: {order.adjustment_count}")

    logger.info("")


async def demo_kelly_strategy():
    """Demonstrate Kelly criterion position sizing."""
    logger.info("=== Kelly Criterion Strategy Demo ===")

    # Load configuration
    config = load_config()

    # Initialize client with config object
    client = PolymarketClient(config)

    # Create order daemon
    async with OrderDaemon(client) as daemon:
        # Kelly criterion order
        # Scenario: You think event has 65% chance of YES
        # Current market price is around 0.50
        # You have $10,000 bankroll
        request = OrderRequest(
            market_id="your-market-id",
            token_id="your-token-id",  # YES token
            side=OrderSide.BUY,
            strategy_type=StrategyType.KELLY,
            max_price=0.55,
            min_price=0.45,
            kelly_params=KellyParams(
                win_probability=0.65,  # Your estimated probability
                kelly_fraction=0.25,  # Quarter Kelly (conservative)
                max_position_size=5000,  # Cap at 5000 shares
                bankroll=10000,  # Total bankroll
                recalculate_interval=10.0,  # Recalc every 10 seconds
                micro_price_params=MicroPriceParams(
                    threshold_bps=50,
                    check_interval=2.0,
                    max_adjustments=15,
                ),
            ),
        )

        logger.info("Submitting Kelly criterion order...")
        logger.info("  - Win probability: 65%")
        logger.info("  - Kelly fraction: 0.25 (quarter Kelly)")
        logger.info("  - Bankroll: $10,000")
        logger.info("  - Max position: 5000 shares")
        logger.info("  - Position size will be calculated based on current price")

        await daemon.submit_order(request)
        await daemon.wait_for_completion(timeout=300)

        # Show results
        completed = daemon.get_completed_orders()
        if completed:
            order = completed[0]
            logger.info("Order completed:")
            logger.info(f"  Calculated size: {order.total_size} shares")
            logger.info(f"  Filled: {order.filled_amount}/{order.total_size}")
            logger.info(f"  Avg price: {order.get_average_price():.4f}")
            logger.info(f"  Total cost: ${order.filled_amount * order.get_average_price():.2f}")

    logger.info("")


async def demo_multiple_strategies():
    """Demonstrate running multiple strategies concurrently."""
    logger.info("=== Multiple Strategies Demo ===")

    # Load configuration
    config = load_config()

    # Initialize client with config object
    client = PolymarketClient(config)

    # Create order daemon with larger queue
    async with OrderDaemon(client, max_queue_size=20) as daemon:
        logger.info("Submitting multiple orders with different strategies...")

        # Order 1: Iceberg for large position
        await daemon.submit_order(
            OrderRequest(
                market_id="market-1",
                token_id="token-1",
                side=OrderSide.BUY,
                strategy_type=StrategyType.ICEBERG,
                total_size=2000,
                max_price=0.55,
                min_price=0.45,
                iceberg_params=StrategyParams(initial_tranche_size=300),
            )
        )
        logger.info("  1. Iceberg order: 2000 shares")

        # Order 2: Micro-price for best execution
        await daemon.submit_order(
            OrderRequest(
                market_id="market-2",
                token_id="token-2",
                side=OrderSide.SELL,
                strategy_type=StrategyType.MICRO_PRICE,
                total_size=500,
                max_price=0.60,
                min_price=0.50,
                micro_price_params=MicroPriceParams(threshold_bps=30),
            )
        )
        logger.info("  2. Micro-price order: 500 shares")

        # Order 3: Kelly for optimal sizing
        await daemon.submit_order(
            OrderRequest(
                market_id="market-3",
                token_id="token-3",
                side=OrderSide.BUY,
                strategy_type=StrategyType.KELLY,
                max_price=0.65,
                min_price=0.55,
                kelly_params=KellyParams(
                    win_probability=0.70,
                    kelly_fraction=0.5,
                    max_position_size=3000,
                    bankroll=5000,
                ),
            )
        )
        logger.info("  3. Kelly order: size TBD")

        logger.info(f"Queue size: {daemon.get_queue_size()}")
        logger.info("Processing orders concurrently...")

        # Wait for completion
        await daemon.wait_for_completion(timeout=600)

        # Summary
        completed = daemon.get_completed_orders()
        failed = daemon.get_failed_orders()

        logger.info("\nResults:")
        logger.info(f"  Completed: {len(completed)}")
        logger.info(f"  Failed: {len(failed)}")

        total_filled = sum(o.filled_amount for o in completed)
        total_cost = sum(o.filled_amount * o.get_average_price() for o in completed)

        logger.info(f"  Total filled: {total_filled} shares")
        logger.info(f"  Total cost: ${total_cost:.2f}")

    logger.info("")


async def main():
    """Run all Phase 3 demos."""
    logger.info("Phase 3 Advanced Strategies Demo")
    logger.info("=" * 50)
    logger.info("")

    # NOTE: These demos use placeholder market/token IDs
    # Replace with actual IDs from Polymarket before running
    logger.warning("IMPORTANT: Update market_id and token_id values before running!\n")

    try:
        # Run each demo
        await demo_order_daemon()
        # await demo_micro_price_strategy()
        # await demo_kelly_strategy()
        # await demo_multiple_strategies()

        logger.info("Demos commented out - uncomment after setting market/token IDs")

    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)

    logger.info("=" * 50)
    logger.info("Demo complete!")


if __name__ == "__main__":
    asyncio.run(main())
