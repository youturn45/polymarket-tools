"""Simple demo: Single micro-price order via daemon."""

import asyncio
import logging

from config.settings import load_config
from core.order_daemon import OrderDaemon
from models.enums import OrderSide
from models.order_request import MicroPriceParams, OrderRequest, StrategyType

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def main():
    """Run a single micro-price order through the daemon."""
    # Load configuration
    config = load_config()

    # Initialize client
    from api.polymarket_client import PolymarketClient

    client = PolymarketClient(config)

    # Initialize daemon
    logger.info("Starting order daemon...")
    daemon = OrderDaemon(client, logger=logger)

    try:
        # Start daemon
        await daemon.start()
        logger.info("Daemon started successfully")

        # Create micro-price order request
        order_request = OrderRequest(
            # Market identification
            token_id="64115571112663071888929599027003715026866623388277198289581125847375946298399",
            side=OrderSide.SELL,
            # Strategy
            strategy_type=StrategyType.MICRO_PRICE,
            # Size
            total_size=3485,
            # Price bounds
            min_price=0.002,
            max_price=0.005,
            # Micro-price parameters
            micro_price_params=MicroPriceParams(
                threshold_bps=5000,  # Replace order if 50 bps from micro-price
                check_interval=2.0,  # Check every 2 seconds
                max_adjustments=10,  # Max 10 order replacements
                aggression_limit_bps=100,  # Don't place more than 100 bps ahead
            ),
            # Execution settings
            timeout=3000.0,  # 60 second timeout for demo
        )

        logger.info(
            f"Submitting micro-price order: {order_request.side.value} "
            f"{order_request.total_size} @ {order_request.min_price}-{order_request.max_price}"
        )

        # Submit to daemon
        order = await daemon.submit_order(order_request)
        logger.info(f"Order submitted: {order.order_id}")

        # Wait for completion (timeout + buffer)
        logger.info("Waiting for order to complete...")
        await asyncio.sleep(order_request.timeout + 5)

        # Get final status
        final_order = daemon.get_order_status(order.order_id)
        if final_order:
            logger.info(
                f"Order completed: {final_order.status.value}, "
                f"filled {final_order.filled_amount}/{final_order.total_size}, "
                f"{final_order.adjustment_count} adjustments made"
            )
        else:
            logger.warning(f"Order {order.order_id} not found")

    except Exception as e:
        logger.error(f"Demo failed: {e}", exc_info=True)

    finally:
        # Shutdown daemon
        logger.info("Shutting down daemon...")
        await daemon.shutdown()
        logger.info("Demo complete")


if __name__ == "__main__":
    asyncio.run(main())
