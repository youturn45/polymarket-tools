"""Test script to verify Polymarket API connection and authentication."""

import sys

from core.client import PolymarketClient

from config.settings import load_settings
from utils.logger import setup_logger


def test_connection() -> None:
    """Test connection to Polymarket API."""
    # Setup logger
    logger = setup_logger(level="INFO")
    logger.info("Starting Polymarket connection test...")

    try:
        # Load settings
        logger.info("Loading settings from .env file...")
        settings = load_settings()

        # Create client
        logger.info("Creating Polymarket client...")
        client = PolymarketClient(settings.polymarket)

        # Connect and authenticate
        logger.info("Connecting to Polymarket...")
        client.connect()

        # Test basic API calls
        logger.info("\n" + "=" * 60)
        logger.info("Testing basic API calls...")
        logger.info("=" * 60)

        # Get markets
        logger.info("\n1. Fetching available markets...")
        markets = client.get_markets()

        # Handle different response formats
        if isinstance(markets, dict):
            market_count = len(markets)
            logger.info("   ✓ Retrieved markets data (%d markets)", market_count)
            if market_count > 0:
                first_key = list(markets.keys())[0]
                first_market = markets[first_key]
                if isinstance(first_market, dict) and "question" in first_market:
                    logger.info("   Sample market: %s", first_market["question"][:50])
        elif isinstance(markets, list):
            logger.info("   ✓ Found %d markets", len(markets))
            if markets and isinstance(markets[0], dict) and "question" in markets[0]:
                logger.info("   Sample market: %s", markets[0]["question"][:50])
        else:
            logger.info("   ✓ Markets retrieved")

        # Get your trades and orders (works without token_id)
        logger.info("\n2. Fetching your trades...")
        trades = client.get_trades()
        logger.info("   ✓ Found %d trades", len(trades))

        # Get open orders
        logger.info("\n3. Fetching open orders...")
        orders = client.get_open_orders()
        logger.info("   ✓ Found %d open orders", len(orders))

        # Get order book for configured token (optional)
        if settings.strategy.token_id:
            logger.info("\n4. Testing order book for configured token...")
            token_id = settings.strategy.token_id
            try:
                _ = client.get_order_book(token_id)

                best_bid, best_ask = client.get_best_bid_ask(token_id)
                logger.info("   ✓ Order book retrieved")
                logger.info("   Best Bid: $%.4f", best_bid if best_bid else 0)
                logger.info("   Best Ask: $%.4f", best_ask if best_ask else 0)

                midpoint = client.get_midpoint(token_id)
                if midpoint:
                    logger.info("   Midpoint: $%.4f", midpoint)
            except Exception as e:
                logger.warning("   ⚠️  Token ID has no active order book: %s", token_id)
                logger.warning("   Error: %s", str(e))
                logger.info("\n   💡 To find valid token IDs:")
                logger.info("   1. Visit https://polymarket.com and find a market")
                logger.info("   2. Or leave TOKEN_ID empty in .env for now")

        logger.info("\n" + "=" * 60)
        logger.info("✓ All tests passed successfully!")
        logger.info("=" * 60)
        logger.info("\nYour Polymarket API connection is working correctly.")
        logger.info("You can now proceed with trading operations.")

        # Disconnect
        client.disconnect()

    except FileNotFoundError:
        logger.error("\n❌ Error: .env file not found!")
        logger.error("Please create a .env file based on .env.example")
        logger.error("Run: cp .env.example .env")
        logger.error("Then edit .env with your credentials")
        sys.exit(1)

    except ValueError as e:
        logger.error("\n❌ Configuration error: %s", e)
        logger.error("Please check your .env file settings")
        sys.exit(1)

    except RuntimeError as e:
        logger.error("\n❌ Connection error: %s", e)
        logger.error("Please check your API credentials")
        sys.exit(1)

    except Exception as e:
        logger.error("\n❌ Unexpected error: %s", e)
        logger.exception("Full error details:")
        sys.exit(1)


if __name__ == "__main__":
    test_connection()
