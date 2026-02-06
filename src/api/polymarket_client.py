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

    def _with_retries(
        self,
        action,
        *,
        action_name: str,
        retry_wait_fn,
        on_fail=None,
    ):
        """Run an action with retries and consistent logging."""
        for attempt in range(1, self.max_retries + 1):
            try:
                return action()
            except Exception as e:
                self.logger.warning(
                    f"{action_name} attempt {attempt}/{self.max_retries} failed: {e}"
                )

                if attempt < self.max_retries:
                    wait_time = retry_wait_fn(attempt)
                    self.logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    if on_fail:
                        return on_fail(e)
                    self.logger.error(f"Failed to {action_name} after {self.max_retries} attempts")
                    raise

    def extract_order_id(self, response: dict) -> str:
        """Extract order ID from API response."""
        if isinstance(response, dict):
            return response.get("orderID", response.get("id", "unknown"))
        return str(response)

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

        def _action():
            signed_order = self.client.create_order(order_args)
            response = self.client.post_order(signed_order, order_type)
            self.logger.info(
                f"Order placed successfully: {side} {size} @ ${price}",
                extra={"token_id": token_id, "order_response": response},
            )
            return response

        return self._with_retries(
            _action,
            action_name="place order",
            retry_wait_fn=lambda attempt: 2**attempt,
        )

    def cancel_order(self, order_id: str) -> dict:
        """Cancel an order with retry logic.

        Args:
            order_id: Order identifier to cancel

        Returns:
            Cancellation response from API

        Raises:
            Exception: If cancellation fails after retries
        """

        def _action():
            response = self.client.cancel(order_id)
            self.logger.info(f"Order cancelled: {order_id}")
            return response

        return self._with_retries(
            _action,
            action_name="cancel order",
            retry_wait_fn=lambda attempt: 2**attempt,
        )

    def get_order_status(self, order_id: str) -> dict:
        """Get order status from exchange.

        Args:
            order_id: Order identifier

        Returns:
            Order status data

        Raises:
            Exception: If status check fails after retries
        """

        def _action():
            return self.client.get_order(order_id)

        return self._with_retries(
            _action,
            action_name="get order status",
            retry_wait_fn=lambda _attempt: 1,
        )

    def get_order_book(self, token_id: str) -> dict:
        """Get order book for a token.

        Args:
            token_id: Token identifier

        Returns:
            Order book data with bids and asks

        Raises:
            Exception: If request fails after retries
        """

        def _action():
            return self.client.get_order_book(token_id)

        return self._with_retries(
            _action,
            action_name="get order book",
            retry_wait_fn=lambda _attempt: 1,
        )

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

    def get_tick_size(self, token_id: str) -> float:
        """Get the tick size (minimum price increment) for a token.

        The tick size is the minimum price increment allowed for orders.
        It can be 0.1, 0.01, 0.001, or 0.0001 depending on the market.

        Tick sizes are dynamic and can change when:
        - Price > 0.96 or price < 0.04 (becomes smaller for precision)
        - Market becomes one-sided

        Args:
            token_id: Token identifier

        Returns:
            Tick size as float (e.g., 0.01 for 1 cent increments)

        Raises:
            Exception: If tick size fetch fails after retries
        """

        def _action():
            tick_size_str = self.client.get_tick_size(token_id)
            tick_size = float(tick_size_str)
            self.logger.debug(f"Tick size for {token_id[:8]}...: {tick_size}")
            return tick_size

        def _on_fail(_error: Exception) -> float:
            self.logger.warning(
                f"Failed to get tick size after {self.max_retries} attempts, " f"defaulting to 0.01"
            )
            return 0.01

        return self._with_retries(
            _action,
            action_name="get tick size",
            retry_wait_fn=lambda _attempt: 1,
            on_fail=_on_fail,
        )
