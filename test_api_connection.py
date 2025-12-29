"""Test API connection to diagnose Cloudflare issue."""

import logging

from api.polymarket_client import PolymarketClient
from config.settings import load_config

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Test basic API connection."""
    try:
        # Load config
        logger.info("Loading configuration...")
        config = load_config()
        logger.info(f"Using host: {config.host}")

        # Initialize client
        logger.info("Initializing client...")
        client = PolymarketClient(config)
        logger.info("Client initialized successfully")

        # Test fetching order book
        token_id = "64115571112663071888929599027003715026866623388277198289581125847375946298399"
        logger.info(f"Fetching order book for token {token_id[:20]}...")

        order_book = client.get_order_book(token_id)
        logger.info("Order book fetched successfully!")
        logger.info(f"Type: {type(order_book)}")
        logger.info(f"Bids: {len(order_book.bids) if order_book.bids else 0}")
        logger.info(f"Asks: {len(order_book.asks) if order_book.asks else 0}")

        if order_book.bids and order_book.asks:
            logger.info(f"Best bid: {order_book.bids[0].price}")
            logger.info(f"Best ask: {order_book.asks[0].price}")

    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
