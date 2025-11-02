"""Polymarket client wrapper."""

import logging
from typing import Any, Optional

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import (
    ApiCreds,
    OpenOrderParams,
    OrderArgs,
    OrderType,
)

from config.settings import PolymarketConfig, Side

logger = logging.getLogger(__name__)


class PolymarketClient:
    """Wrapper around py-clob-client with error handling and convenience methods."""

    def __init__(self, config: PolymarketConfig) -> None:
        """Initialize Polymarket client.

        Args:
            config: Polymarket configuration
        """
        self.config = config
        self._client: Optional[ClobClient] = None
        self._authenticated = False

    def connect(self) -> None:
        """Initialize connection and authenticate."""
        logger.info("Connecting to Polymarket at %s", self.config.polymarket_host)

        try:
            self._client = ClobClient(
                host=self.config.polymarket_host,
                key=self.config.private_key,
                chain_id=self.config.chain_id,
                signature_type=self.config.signature_type,
                funder=self.config.funder_address,
            )

            # Derive or create API credentials (this also sets them on the client)
            logger.info("Deriving API credentials...")
            creds = self._client.create_or_derive_api_creds()

            # Verify credentials were set
            if not self._client.creds:
                logger.warning("Credentials not automatically set, setting manually...")
                self._client.set_api_creds(creds)

            self._log_credentials(creds)

            self._authenticated = True
            logger.info("Successfully connected and authenticated")

        except Exception as e:
            logger.error("Failed to connect to Polymarket: %s", e)
            raise

    def _log_credentials(self, creds: ApiCreds) -> None:
        """Log API credentials (safely)."""
        logger.info("API Key: %s", creds.api_key)
        logger.info("API Passphrase: %s", creds.api_passphrase[:4] + "****")
        logger.debug("API Secret: %s****", creds.api_secret[:8])

    @property
    def client(self) -> ClobClient:
        """Get underlying client, ensuring it's initialized."""
        if self._client is None:
            raise RuntimeError("Client not connected. Call connect() first.")
        return self._client

    def get_order_book(self, token_id: str) -> dict[str, Any]:
        """Get order book for a market.

        Args:
            token_id: Market token ID

        Returns:
            Order book data with bids and asks
        """
        logger.debug("Getting order book for token %s", token_id)
        try:
            book = self.client.get_order_book(token_id)
            return book
        except Exception as e:
            logger.error("Failed to get order book: %s", e)
            raise

    def get_best_bid_ask(self, token_id: str) -> tuple[Optional[float], Optional[float]]:
        """Get best bid and ask prices.

        Args:
            token_id: Market token ID

        Returns:
            Tuple of (best_bid, best_ask), None if no orders
        """
        try:
            book = self.get_order_book(token_id)

            best_bid = None
            best_ask = None

            # Handle OrderBookSummary object (has bids/asks attributes)
            if hasattr(book, "bids") and book.bids and len(book.bids) > 0:
                best_bid = float(book.bids[0].price)

            if hasattr(book, "asks") and book.asks and len(book.asks) > 0:
                best_ask = float(book.asks[0].price)

            return best_bid, best_ask

        except Exception as e:
            logger.error("Failed to get best bid/ask: %s", e)
            raise

    def get_price(self, token_id: str, side: Side) -> Optional[float]:
        """Get best price for a given side.

        Args:
            token_id: Market token ID
            side: BUY or SELL

        Returns:
            Best price for the side, or None if no orders
        """
        try:
            response = self.client.get_price(token_id, side.value)
            if response and "price" in response:
                return float(response["price"])
            return None
        except Exception as e:
            logger.error("Failed to get price: %s", e)
            raise

    def get_midpoint(self, token_id: str) -> Optional[float]:
        """Get midpoint price.

        Args:
            token_id: Market token ID

        Returns:
            Midpoint price or None
        """
        try:
            response = self.client.get_midpoint(token_id)
            if response and "mid" in response:
                return float(response["mid"])
            return None
        except Exception as e:
            logger.error("Failed to get midpoint: %s", e)
            raise

    def place_limit_order(
        self,
        token_id: str,
        side: Side,
        price: float,
        size: int,
    ) -> dict[str, Any]:
        """Place a limit order.

        Args:
            token_id: Market token ID
            side: BUY or SELL
            price: Limit price (0-1)
            size: Number of shares

        Returns:
            Order response from API
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        logger.info(
            "Placing %s limit order: %d shares @ $%.4f (token: %s)",
            side.value,
            size,
            price,
            token_id,
        )

        try:
            # Create the order
            order_args = OrderArgs(
                token_id=token_id,
                price=price,
                size=float(size),
                side=side.value,
            )

            # Sign the order
            signed_order = self.client.create_order(order_args)

            # Post the order
            response = self.client.post_order(signed_order, OrderType.GTC)

            logger.info("Order placed successfully: %s", response.get("orderID"))
            return response

        except Exception as e:
            logger.error("Failed to place order: %s", e)
            raise

    def cancel_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a specific order.

        Args:
            order_id: Order ID to cancel

        Returns:
            Cancellation response
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        logger.info("Cancelling order: %s", order_id)

        try:
            response = self.client.cancel(order_id)
            logger.info("Order cancelled successfully")
            return response
        except Exception as e:
            logger.error("Failed to cancel order: %s", e)
            raise

    def cancel_all_orders(self) -> dict[str, Any]:
        """Cancel all open orders.

        Returns:
            Cancellation response
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        logger.warning("Cancelling ALL open orders")

        try:
            response = self.client.cancel_all()
            logger.info("All orders cancelled successfully")
            return response
        except Exception as e:
            logger.error("Failed to cancel all orders: %s", e)
            raise

    def get_open_orders(self, token_id: Optional[str] = None) -> list[dict[str, Any]]:
        """Get open orders.

        Args:
            token_id: Optional filter by token ID

        Returns:
            List of open orders
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        try:
            params = OpenOrderParams()
            if token_id:
                # Filter by asset_id if provided
                params.asset_id = token_id

            orders = self.client.get_orders(params)
            logger.debug("Retrieved %d open orders", len(orders) if orders else 0)
            return orders if orders else []

        except Exception as e:
            logger.error("Failed to get open orders: %s", e)
            raise

    def get_trades(self) -> list[dict[str, Any]]:
        """Get trade history.

        Returns:
            List of trades
        """
        if not self._authenticated:
            raise RuntimeError("Not authenticated. Call connect() first.")

        try:
            trades = self.client.get_trades()
            logger.debug("Retrieved %d trades", len(trades) if trades else 0)
            return trades if trades else []

        except Exception as e:
            logger.error("Failed to get trades: %s", e)
            raise

    def get_markets(self) -> list[dict[str, Any]]:
        """Get all available markets.

        Returns:
            List of markets
        """
        try:
            markets = self.client.get_simplified_markets()
            logger.debug("Retrieved %d markets", len(markets) if markets else 0)
            return markets if markets else []

        except Exception as e:
            logger.error("Failed to get markets: %s", e)
            raise

    def disconnect(self) -> None:
        """Clean up client connection."""
        logger.info("Disconnecting from Polymarket")
        self._authenticated = False
        self._client = None
