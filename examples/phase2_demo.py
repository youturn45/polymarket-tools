"""Phase 2 Demo: Iceberg Order Execution

This script demonstrates the iceberg order strategy which splits large orders
into multiple smaller tranches to avoid market impact.

Example: A 1000 share order is split into ~5 tranches of varying sizes
"""

import sys
import uuid
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.order_executor import OrderExecutor
from models.enums import OrderSide, OrderStatus, Urgency
from models.order import Order, StrategyParams
from utils.logger import setup_logger


def main():
    """Run Phase 2 iceberg order demo."""
    print("=" * 60)
    print("Phase 2 Demo: Iceberg Order Execution")
    print("=" * 60)
    print()

    # Setup logger
    logger = setup_logger(
        name="phase2_demo",
        level="INFO",
        log_file=None,  # Console only for demo
        json_format=False,
    )

    logger.info("Loading configuration...")
    try:
        config = load_config()
        logger.info("Configuration loaded successfully")
        logger.info("API credentials will be auto-derived from private key")
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        return

    logger.info("Initializing Polymarket client...")
    try:
        client = PolymarketClient(config=config, logger=logger, max_retries=3)
        logger.info("Client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize client: {e}")
        return

    logger.info("Initializing order executor...")
    executor = OrderExecutor(
        client=client,
        logger=logger,
        poll_interval=2.0,
        timeout=60.0,
    )

    # Example: Create an iceberg order
    print()
    print("-" * 60)
    print("Creating Iceberg Order")
    print("-" * 60)

    # NOTE: Replace these with real values for actual trading
    market_id = "YOUR_MARKET_ID"
    token_id = "YOUR_TOKEN_ID"  # YES or NO token
    total_size = 1000  # Total shares to trade
    target_price = 0.45  # Target price

    order = Order(
        order_id=f"iceberg-{uuid.uuid4().hex[:8]}",
        market_id=market_id,
        token_id=token_id,
        side=OrderSide.BUY,
        total_size=total_size,
        target_price=target_price,
        max_price=0.50,
        min_price=0.40,
        urgency=Urgency.MEDIUM,
        strategy_params=StrategyParams(
            initial_tranche_size=200,  # First tranche: ~200 shares
            min_tranche_size=100,  # Minimum: 100 shares
            max_tranche_size=300,  # Maximum: 300 shares
            tranche_randomization=0.2,  # ±20% randomization
        ),
    )

    print(f"Order ID: {order.order_id}")
    print(f"Market: {market_id}")
    print(f"Token: {token_id}")
    print(f"Side: {order.side.value}")
    print(f"Total Size: {total_size} shares")
    print(f"Target Price: ${target_price}")
    print()
    print("Strategy Parameters:")
    print(f"  Initial Tranche: {order.strategy_params.initial_tranche_size} shares")
    print(f"  Min Tranche: {order.strategy_params.min_tranche_size} shares")
    print(f"  Max Tranche: {order.strategy_params.max_tranche_size} shares")
    print(f"  Randomization: ±{order.strategy_params.tranche_randomization * 100}%")
    print()

    # Preview tranches
    from strategies.iceberg import IcebergStrategy

    strategy = IcebergStrategy(order.strategy_params)
    tranches = strategy.calculate_all_tranches(total_size)

    print("Tranche Preview:")
    for i, tranche_size in enumerate(tranches, 1):
        print(f"  Tranche {i}: {tranche_size} shares")
    print(f"  Total: {sum(tranches)} shares across {len(tranches)} tranches")
    print()

    # Warn if using placeholder values
    if market_id == "YOUR_MARKET_ID" or token_id == "YOUR_TOKEN_ID":
        print("⚠️  WARNING: Using placeholder market/token IDs")
        print("⚠️  Update market_id and token_id with real values to execute trades")
        print()
        print("Demo completed (dry run - no actual trades placed)")
        return

    # Execute iceberg order
    print("-" * 60)
    print("Executing Iceberg Order")
    print("-" * 60)
    print()

    try:
        logger.info("Starting iceberg order execution...")
        result = executor.execute_iceberg_order(order)

        print()
        print("-" * 60)
        print("Execution Results")
        print("-" * 60)
        print(f"Status: {result.status.value}")
        print(f"Filled: {result.filled_amount}/{result.total_size} shares")
        print(f"Remaining: {result.remaining_amount} shares")

        if result.status == OrderStatus.COMPLETED:
            print()
            print("✅ Order completed successfully!")

        elif result.status == OrderStatus.PARTIALLY_FILLED:
            fill_rate = (result.filled_amount / result.total_size) * 100
            print()
            print(f"⚠️  Order partially filled ({fill_rate:.1f}%)")

        else:
            print()
            print("❌ Order failed")

    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        print()
        print(f"❌ Error: {e}")

    print()
    print("=" * 60)
    print("Demo Complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
