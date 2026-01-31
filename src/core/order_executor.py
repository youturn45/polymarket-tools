"""Order executor for single and iceberg order execution."""

import logging
import time
from typing import Optional

from py_clob_client.clob_types import OrderType

from api.polymarket_client import PolymarketClient
from core.fill_tracker import FillTracker
from models.enums import OrderStatus
from models.order import Order
from strategies.iceberg import IcebergStrategy
from utils.logger import log_order_event


class OrderExecutor:
    """Executes single and iceberg orders on Polymarket with monitoring."""

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
            exchange_order_id = self.client.extract_order_id(response)

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

    def _monitor_order(self, order: Order, exchange_order_id: str) -> int:
        """Monitor order status until filled or timeout.

        Args:
            order: Order being monitored
            exchange_order_id: Exchange-assigned order ID

        Returns:
            Amount filled
        """
        return self._monitor_until_filled(
            exchange_order_id,
            order.total_size,
            context="Order",
            log_progress=True,
            log_level=logging.INFO,
        )

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

    def _monitor_until_filled(
        self,
        exchange_order_id: str,
        target_size: int,
        *,
        context: str,
        log_progress: bool,
        log_level: int,
    ) -> int:
        """Monitor status until filled or timeout."""
        start_time = time.time()
        last_log_time = start_time

        self.logger.log(
            log_level,
            f"Monitoring {context.lower()} {exchange_order_id} (timeout in {self.timeout}s)",
        )

        while True:
            elapsed = time.time() - start_time

            # Check timeout
            if elapsed >= self.timeout:
                self.logger.warning(f"{context} monitoring timeout after {self.timeout}s")
                break

            try:
                status_response = self.client.get_order_status(exchange_order_id)
                filled_amount = self._extract_filled_amount(status_response)

                if log_progress and time.time() - last_log_time >= 10:
                    self.logger.info(f"{context} status: {filled_amount}/{target_size} filled")
                    last_log_time = time.time()

                if filled_amount >= target_size:
                    self.logger.log(log_level, f"{context} fully filled: {filled_amount} shares")
                    return filled_amount

                if filled_amount > 0:
                    self.logger.log(
                        log_level, f"{context} partial fill: {filled_amount}/{target_size}"
                    )

            except Exception as e:
                self.logger.warning(f"Error checking {context.lower()} status: {e}")

            time.sleep(self.poll_interval)

        try:
            status_response = self.client.get_order_status(exchange_order_id)
            return self._extract_filled_amount(status_response)
        except Exception as e:
            self.logger.error(f"Failed to get final {context.lower()} status: {e}")
            return 0
    def execute_iceberg_order(
        self,
        order: Order,
        order_type: OrderType = OrderType.GTC,
    ) -> Order:
        """Execute order using iceberg strategy (split into tranches).

        Args:
            order: Order to execute with iceberg strategy
            order_type: Order type (GTC, FOK, GTD)

        Returns:
            Updated order with final status
        """
        self.logger.info(
            f"Starting iceberg execution: {order.side.value} {order.total_size} shares @ ${order.target_price}"
        )

        # Initialize strategy and tracker
        strategy = IcebergStrategy(order.strategy_params)
        tracker = FillTracker(order.total_size)

        # Update order status
        order.update_status(OrderStatus.ACTIVE)

        log_order_event(
            self.logger,
            "iceberg_started",
            order.order_id,
            f"Starting iceberg execution: {order.side.value} {order.total_size} shares",
            market_id=order.market_id,
            extra_data={
                "total_size": order.total_size,
                "price": order.target_price,
                "strategy": order.strategy_params.model_dump(),
            },
        )

        try:
            tranche_number = 0

            while not tracker.is_complete():
                tranche_number += 1
                is_first_tranche = tranche_number == 1

                # Calculate tranche size
                tranche_size = strategy.calculate_next_tranche_size(
                    remaining_size=tracker.total_remaining,
                    is_first_tranche=is_first_tranche,
                )

                if tranche_size == 0:
                    break

                self.logger.info(
                    f"Executing tranche {tranche_number}: {tranche_size} shares @ ${order.target_price}"
                )

                log_order_event(
                    self.logger,
                    "tranche_started",
                    order.order_id,
                    f"Tranche {tranche_number}: {tranche_size} shares",
                    market_id=order.market_id,
                    extra_data={
                        "tranche_number": tranche_number,
                        "tranche_size": tranche_size,
                        "remaining": tracker.total_remaining,
                    },
                )

                # Place tranche order
                try:
                    response = self.client.place_order(
                        token_id=order.token_id,
                        price=order.target_price,
                        size=float(tranche_size),
                        side=order.side.value,
                        order_type=order_type,
                    )

                    exchange_order_id = self.client.extract_order_id(response)

                    # Monitor tranche until filled or timeout
                    filled_amount = self._monitor_tranche(exchange_order_id, tranche_size)

                    # Record fill in tracker
                    tracker.record_tranche_fill(
                        tranche_number=tranche_number,
                        size=tranche_size,
                        filled=filled_amount,
                        price=order.target_price,
                    )

                    # Update order
                    if filled_amount > 0:
                        order.record_fill(filled_amount)

                    log_order_event(
                        self.logger,
                        "tranche_completed",
                        order.order_id,
                        f"Tranche {tranche_number} filled: {filled_amount}/{tranche_size}",
                        market_id=order.market_id,
                        extra_data={
                            "tranche_number": tranche_number,
                            "filled": filled_amount,
                            "size": tranche_size,
                            "total_filled": tracker.total_filled,
                        },
                    )

                    # If partial fill or no fill, stop execution
                    if filled_amount < tranche_size:
                        self.logger.warning(
                            f"Tranche {tranche_number} only filled {filled_amount}/{tranche_size} - stopping"
                        )
                        break

                except Exception as e:
                    self.logger.error(f"Tranche {tranche_number} failed: {e}")
                    break

                # Inter-tranche delay (if not complete)
                if not tracker.is_complete():
                    delay = strategy.calculate_inter_tranche_delay()
                    self.logger.info(f"Waiting {delay:.2f}s before next tranche...")
                    time.sleep(delay)

            # Final status update
            if tracker.is_complete():
                order.update_status(OrderStatus.COMPLETED)
                log_order_event(
                    self.logger,
                    "iceberg_completed",
                    order.order_id,
                    f"Iceberg order completed: {tracker.total_filled} shares filled",
                    market_id=order.market_id,
                    extra_data={
                        "total_filled": tracker.total_filled,
                        "tranches": tranche_number,
                        "average_price": tracker.average_fill_price,
                    },
                )
            elif tracker.total_filled > 0:
                order.update_status(OrderStatus.PARTIALLY_FILLED)
                log_order_event(
                    self.logger,
                    "iceberg_partially_filled",
                    order.order_id,
                    f"Iceberg partially filled: {tracker.total_filled}/{order.total_size}",
                    market_id=order.market_id,
                    extra_data={
                        "filled": tracker.total_filled,
                        "total": order.total_size,
                        "tranches": tranche_number,
                    },
                )
            else:
                order.update_status(OrderStatus.FAILED)
                log_order_event(
                    self.logger,
                    "iceberg_failed",
                    order.order_id,
                    "Iceberg order failed - no fills",
                    market_id=order.market_id,
                )

            return order

        except Exception as e:
            self.logger.error(f"Iceberg execution failed: {e}", exc_info=True)
            order.update_status(OrderStatus.FAILED)

            log_order_event(
                self.logger,
                "iceberg_failed",
                order.order_id,
                f"Iceberg execution failed: {str(e)}",
                market_id=order.market_id,
                extra_data={"error": str(e)},
            )

            raise

    def _monitor_tranche(self, exchange_order_id: str, tranche_size: int) -> int:
        """Monitor a single tranche until filled or timeout.

        Args:
            order: Parent order
            exchange_order_id: Exchange order ID
            tranche_size: Size of this tranche

        Returns:
            Amount filled
        """
        return self._monitor_until_filled(
            exchange_order_id,
            tranche_size,
            context="Tranche",
            log_progress=False,
            log_level=logging.DEBUG,
        )
