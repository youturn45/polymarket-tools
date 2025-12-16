"""Simple order executor for Phase 1 - single order execution."""

import logging
import time
from typing import Optional

from py_clob_client.clob_types import OrderType

from api.polymarket_client import PolymarketClient
from models.enums import OrderStatus
from models.order import Order
from utils.logger import log_order_event


class OrderExecutor:
    """Executes single orders on Polymarket with basic monitoring."""

    def __init__(
        self,
        client: PolymarketClient,
        logger: Optional[logging.Logger] = None,
        poll_interval: float = 2.0,
        timeout: float = 60.0,
    ):
        """Initialize order executor.

        Args:
            client: Polymarket API client
            logger: Optional logger instance
            poll_interval: Seconds between status checks
            timeout: Maximum seconds to wait for fill
        """
        self.client = client
        self.logger = logger or logging.getLogger(__name__)
        self.poll_interval = poll_interval
        self.timeout = timeout

    def execute_single_order(
        self,
        order: Order,
        order_type: OrderType = OrderType.GTC,
    ) -> Order:
        """Execute a single order and wait for fill or timeout.

        Args:
            order: Order to execute
            order_type: Order type (GTC, FOK, GTD)

        Returns:
            Updated order with final status
        """
        self.logger.info(
            f"Starting execution: {order.side.value} {order.total_size} shares @ ${order.target_price}"
        )

        # Update order status
        order.update_status(OrderStatus.ACTIVE)

        log_order_event(
            self.logger,
            "order_started",
            order.order_id,
            f"Executing {order.side.value} order",
            market_id=order.market_id,
            extra_data={
                "size": order.total_size,
                "price": order.target_price,
                "token_id": order.token_id,
            },
        )

        try:
            # Place order on exchange
            response = self.client.place_order(
                token_id=order.token_id,
                price=order.target_price,
                size=float(order.total_size),
                side=order.side.value,
                order_type=order_type,
            )

            # Extract order ID from response
            exchange_order_id = self._extract_order_id(response)

            log_order_event(
                self.logger,
                "order_placed",
                order.order_id,
                f"Order placed on exchange: {exchange_order_id}",
                market_id=order.market_id,
                extra_data={"exchange_order_id": exchange_order_id},
            )

            # Monitor order until filled or timeout
            filled_amount = self._monitor_order(order, exchange_order_id)

            # Update order with fill
            if filled_amount > 0:
                order.record_fill(filled_amount)

            # Final status
            if order.status == OrderStatus.COMPLETED:
                log_order_event(
                    self.logger,
                    "order_completed",
                    order.order_id,
                    f"Order completed: {filled_amount}/{order.total_size} shares filled",
                    market_id=order.market_id,
                    extra_data={"filled": filled_amount, "total": order.total_size},
                )
            elif order.status == OrderStatus.PARTIALLY_FILLED:
                log_order_event(
                    self.logger,
                    "order_partially_filled",
                    order.order_id,
                    f"Order partially filled: {filled_amount}/{order.total_size} shares",
                    market_id=order.market_id,
                    extra_data={"filled": filled_amount, "total": order.total_size},
                )
            else:
                log_order_event(
                    self.logger,
                    "order_failed",
                    order.order_id,
                    "Order not filled within timeout",
                    market_id=order.market_id,
                )

            return order

        except Exception as e:
            self.logger.error(f"Order execution failed: {e}", exc_info=True)
            order.update_status(OrderStatus.FAILED)

            log_order_event(
                self.logger,
                "order_failed",
                order.order_id,
                f"Order execution failed: {str(e)}",
                market_id=order.market_id,
                extra_data={"error": str(e)},
            )

            raise

    def _extract_order_id(self, response: dict) -> str:
        """Extract order ID from API response.

        Args:
            response: API response from place_order

        Returns:
            Order ID string
        """
        # Handle different response formats
        if isinstance(response, dict):
            return response.get("orderID", response.get("id", "unknown"))
        return str(response)

    def _monitor_order(self, order: Order, exchange_order_id: str) -> int:
        """Monitor order status until filled or timeout.

        Args:
            order: Order being monitored
            exchange_order_id: Exchange-assigned order ID

        Returns:
            Amount filled
        """
        start_time = time.time()
        last_log_time = start_time

        self.logger.info(f"Monitoring order {exchange_order_id} (timeout in {self.timeout}s)")

        while True:
            elapsed = time.time() - start_time

            # Check timeout
            if elapsed >= self.timeout:
                self.logger.warning(f"Order monitoring timeout after {self.timeout}s")
                break

            # Get order status from exchange
            try:
                status_response = self.client.get_order_status(exchange_order_id)
                filled_amount = self._extract_filled_amount(status_response)

                # Log progress every 10 seconds
                if time.time() - last_log_time >= 10:
                    self.logger.info(f"Order status: {filled_amount}/{order.total_size} filled")
                    last_log_time = time.time()

                # Check if filled
                if filled_amount >= order.total_size:
                    self.logger.info(f"Order fully filled: {filled_amount} shares")
                    return filled_amount

                # Check for partial fill
                if filled_amount > 0:
                    self.logger.info(f"Partial fill detected: {filled_amount}/{order.total_size}")

            except Exception as e:
                self.logger.warning(f"Error checking order status: {e}")

            # Wait before next check
            time.sleep(self.poll_interval)

        # Timeout reached - check final status
        try:
            status_response = self.client.get_order_status(exchange_order_id)
            filled_amount = self._extract_filled_amount(status_response)
            return filled_amount
        except Exception as e:
            self.logger.error(f"Failed to get final order status: {e}")
            return 0

    def _extract_filled_amount(self, status_response: dict) -> int:
        """Extract filled amount from status response.

        Args:
            status_response: Status response from API

        Returns:
            Filled amount as integer
        """
        if isinstance(status_response, dict):
            # Try common field names
            size_matched = status_response.get("size_matched", 0)
            if size_matched:
                return int(float(size_matched))

            filled = status_response.get("filled", 0)
            if filled:
                return int(float(filled))

        return 0
