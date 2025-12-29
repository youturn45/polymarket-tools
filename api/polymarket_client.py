"""Polymarket API client wrapper with error handling and retry logic."""

import logging
import time
from typing import Optional

from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType

from config.settings import PolymarketConfig


class PolymarketClient:
    """Wrapper around py-clob-client with error handling and retry logic."""

    def __init__(
        self,
        config: PolymarketConfig,
        logger: Optional[logging.Logger] = None,
        max_retries: int = 3,
    ):
        """Initialize Polymarket client.

        Args:
            config: Polymarket configuration
            logger: Optional logger instance
            max_retries: Maximum number of retry attempts for API calls
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self.max_retries = max_retries

        # Initialize the underlying CLOB client
        self.client = self._initialize_client()

        # Generate API credentials on-the-fly
        try:
            creds = self.client.create_or_derive_api_creds()
            self.client.set_api_creds(creds)
            self.logger.info("API credentials generated successfully")
        except Exception as e:
            self.logger.error(f"Failed to generate API credentials: {e}")
            raise

    def _initialize_client(self) -> ClobClient:
        """Initialize the underlying ClobClient based on configuration."""
        client_kwargs = {
            "host": self.config.host,
            "chain_id": self.config.chain_id,
            "key": self.config.private_key,
        }

        # Add signature type and funder for proxy wallets
        if self.config.signature_type in (1, 2):
            client_kwargs["signature_type"] = self.config.signature_type
            client_kwargs["funder"] = self.config.funder_address

        return ClobClient(**client_kwargs)

    def place_order(
        self,
        token_id: str,
        price: float,
        size: float,
        side: str,
        order_type: OrderType = OrderType.GTC,
    ) -> dict:
        """Place an order on Polymarket with retry logic.

        Args:
            token_id: Token identifier
            price: Order price (0.0 to 1.0)
            size: Order size in shares
            side: "BUY" or "SELL"
            order_type: Order type (GTC, FOK, GTD)

        Returns:
            Order response from API

        Raises:
            Exception: If order placement fails after retries
        """
        order_args = OrderArgs(price=price, size=size, side=side, token_id=token_id)

        for attempt in range(1, self.max_retries + 1):
            try:
                # Create and sign order
                signed_order = self.client.create_order(order_args)

                # Post order
                response = self.client.post_order(signed_order, order_type)

                self.logger.info(
                    f"Order placed successfully: {side} {size} @ ${price}",
                    extra={"token_id": token_id, "order_response": response},
                )
                return response

            except Exception as e:
                self.logger.warning(
                    f"Order placement attempt {attempt}/{self.max_retries} failed: {e}"
                )

                if attempt < self.max_retries:
                    # Exponential backoff
                    wait_time = 2**attempt
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Failed to place order after {self.max_retries} attempts")
                    raise

    def cancel_order(self, order_id: str) -> dict:
        """Cancel an order with retry logic.

        Args:
            order_id: Order identifier to cancel

        Returns:
            Cancellation response from API

        Raises:
            Exception: If cancellation fails after retries
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.cancel(order_id)
                self.logger.info(f"Order cancelled: {order_id}")
                return response

            except Exception as e:
                self.logger.warning(f"Cancel attempt {attempt}/{self.max_retries} failed: {e}")

                if attempt < self.max_retries:
                    wait_time = 2**attempt
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Failed to cancel order after {self.max_retries} attempts")
                    raise

    def get_order_status(self, order_id: str) -> dict:
        """Get order status from exchange.

        Args:
            order_id: Order identifier

        Returns:
            Order status data

        Raises:
            Exception: If status check fails after retries
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.get_order(order_id)
                return response

            except Exception as e:
                self.logger.warning(
                    f"Status check attempt {attempt}/{self.max_retries} failed: {e}"
                )

                if attempt < self.max_retries:
                    wait_time = 1  # Shorter wait for status checks
                    time.sleep(wait_time)
                else:
                    self.logger.error(
                        f"Failed to get order status after {self.max_retries} attempts"
                    )
                    raise

    def get_order_book(self, token_id: str) -> dict:
        """Get order book for a token.

        Args:
            token_id: Token identifier

        Returns:
            Order book data with bids and asks

        Raises:
            Exception: If request fails after retries
        """
        for attempt in range(1, self.max_retries + 1):
            try:
                response = self.client.get_order_book(token_id)
                return response

            except Exception as e:
                self.logger.warning(
                    f"Order book fetch attempt {attempt}/{self.max_retries} failed: {e}"
                )

                if attempt < self.max_retries:
                    wait_time = 1
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"Failed to get order book after {self.max_retries} attempts")
                    raise

    def get_orders(self, token_id: Optional[str] = None) -> list:
        """Get open orders for the API key.

        Args:
            token_id: Optional token ID to filter orders

        Returns:
            List of open orders
        """
        try:
            from py_clob_client.clob_types import OpenOrderParams

            # Create params with optional token filter
            params = OpenOrderParams(asset_id=token_id) if token_id else None
            response = self.client.get_orders(params=params)
            return response if response else []

        except Exception as e:
            self.logger.warning(f"Failed to get orders: {e}")
            return []
