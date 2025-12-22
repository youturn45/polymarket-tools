"""Phase 1 Demo: Single order execution.

This script demonstrates the Phase 1 functionality:
- Creating an Order with all required fields
- Using the PolymarketClient to interact with the API
- Using the OrderExecutor to place and monitor a single order
- Structured logging of the entire lifecycle

Usage:
    python examples/phase1_demo.py
"""

import uuid

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.order_executor import OrderExecutor
from models.enums import OrderSide, Urgency
from models.order import Order, StrategyParams
from utils.logger import setup_logger


def main():
    """Run Phase 1 demonstration."""
    # Set up logging
    logger = setup_logger(
        name="phase1_demo",
        level="INFO",
        log_file="logs/phase1_demo.log",
        json_format=False,  # Use human-readable format for demo
    )

    logger.info("=== Phase 1 Demo: Single Order Execution ===")

    # Load configuration
    logger.info("Loading configuration...")
    config = load_config()
    logger.info("Configuration loaded successfully")

    # Initialize client
    logger.info("Initializing Polymarket client...")
    client = PolymarketClient(config=config, logger=logger)

    # Create an order
    # NOTE: Replace these values with actual market/token IDs
    # This example uses placeholder values
    order = Order(
        order_id=f"demo-{uuid.uuid4().hex[:8]}",
        market_id="market-demo",
        token_id="114304586861386186441621124384163963092522056897081085884483958561365015034812",
        side=OrderSide.BUY,
        total_size=10,  # Small size for demo
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
        urgency=Urgency.MEDIUM,
        strategy_params=StrategyParams(
            initial_tranche_size=10,
            min_tranche_size=5,
            max_tranche_size=20,
        ),
    )

    logger.info(f"Created order: {order.order_id}")
    logger.info(f"  Side: {order.side.value}")
    logger.info(f"  Size: {order.total_size} shares")
    logger.info(f"  Target Price: ${order.target_price}")
    logger.info(f"  Max Price: ${order.max_price}")

    # Initialize executor
    logger.info("Initializing order executor...")
    executor = OrderExecutor(
        client=client,
        logger=logger,
        poll_interval=2.0,  # Check every 2 seconds
        timeout=60.0,  # Wait up to 60 seconds
    )

    # Execute the order
    logger.info("Executing order...")
    try:
        result = executor.execute_single_order(order)

        # Display results
        logger.info("=== Execution Complete ===")
        logger.info(f"Final Status: {result.status.value}")
        logger.info(f"Filled: {result.filled_amount}/{result.total_size} shares")
        logger.info(f"Remaining: {result.remaining_amount} shares")

        if result.status.value == "completed":
            logger.info("✅ Order completed successfully!")
        elif result.status.value == "partially_filled":
            logger.info("⚠️  Order partially filled")
        else:
            logger.info("❌ Order did not fill")

    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        logger.info("❌ Demo failed")

    logger.info("=== Demo Complete ===")


if __name__ == "__main__":
    main()
