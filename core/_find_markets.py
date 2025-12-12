"""Helper script to find active markets and their token IDs."""

from core.client import PolymarketClient

from config.settings import load_settings
from utils.logger import setup_logger


def find_markets() -> None:
    """Display active markets with token IDs."""
    logger = setup_logger(level="INFO")

    try:
        settings = load_settings()
        client = PolymarketClient(settings.polymarket)
        client.connect()

        # Get your open orders to find active tokens
        logger.info("Fetching your open orders to find active markets...\n")
        orders = client.get_open_orders()

        if orders:
            logger.info("=" * 80)
            logger.info("YOUR ACTIVE MARKETS (from open orders)")
            logger.info("=" * 80)

            seen_tokens = set()
            for order in orders[:10]:  # Show first 10
                token_id = order.get("asset_id")
                if token_id and token_id not in seen_tokens:
                    seen_tokens.add(token_id)

                    # Get order book to verify it's active
                    try:
                        best_bid, best_ask = client.get_best_bid_ask(token_id)

                        logger.info(f"\nToken ID: {token_id}")
                        logger.info(f"  Market: {order.get('market', 'Unknown')}")
                        logger.info(
                            f"  Best Bid: ${best_bid:.4f}" if best_bid else "  Best Bid: None"
                        )
                        logger.info(
                            f"  Best Ask: ${best_ask:.4f}" if best_ask else "  Best Ask: None"
                        )
                        logger.info(
                            f"  Your Order: {order.get('side')} {order.get('size')} @ ${float(order.get('price', 0)):.4f}"
                        )

                        logger.info("\n  📝 To use this market, add to your .env:")
                        logger.info(f"     TOKEN_ID={token_id}")

                    except Exception as e:
                        logger.debug(f"  ⚠️  Token {token_id} error: {e}")

            logger.info("\n" + "=" * 80)

        else:
            logger.info("No open orders found. Showing recent markets...\n")

            # Fallback: show some markets
            markets = client.get_markets()
            if isinstance(markets, dict):
                logger.info("=" * 80)
                logger.info("AVAILABLE MARKETS")
                logger.info("=" * 80)

                for _market_id, market in list(markets.items())[:5]:
                    if isinstance(market, dict):
                        question = market.get("question", "Unknown")
                        tokens = market.get("tokens", [])

                        logger.info(f"\nQuestion: {question}")

                        for token in tokens[:2]:  # YES/NO tokens
                            if isinstance(token, dict):
                                token_id = token.get("token_id")
                                outcome = token.get("outcome", "Unknown")

                                logger.info(f"  {outcome} Token ID: {token_id}")

                logger.info("\n" + "=" * 80)

        client.disconnect()

    except Exception as e:
        logger.error(f"Error: {e}")
        logger.exception("Details:")


if __name__ == "__main__":
    find_markets()
