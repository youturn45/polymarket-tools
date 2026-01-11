"""Micro-price strategy for adaptive order placement."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from api.polymarket_client import PolymarketClient
from core.event_bus import EventBus, OrderEvent, OrderEventData
from core.market_monitor import MarketMonitor
from models.enums import OrderSide, OrderStatus
from models.order import Order
from models.order_request import MicroPriceParams


class MicroPriceStrategy:
    """Execute orders using micro-price adaptive strategy.

    This strategy places orders at competitive prices near the micro-price and
    continuously monitors market conditions. Orders are automatically adjusted
    when they drift outside threshold bands or become too aggressive.

    Features:
    - Initial placement near micro-price
    - Continuous monitoring of order effectiveness
    - Automatic cancellation and replacement when out of bounds
    - Aggression limit to avoid placing orders too far from competition
    - Respects maximum adjustment limit
    - Event-driven status updates
    """

    def __init__(
        self,
        client: PolymarketClient,
        monitor: MarketMonitor,
        event_bus: Optional[EventBus] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize micro-price strategy.

        Args:
            client: Polymarket API client
            monitor: Market monitor for tracking micro-price
            event_bus: Event bus for order events
            logger: Optional logger instance
        """
        self.client = client
        self.monitor = monitor
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger(__name__)

        # Active order tracking
        self._active_order_id: Optional[str] = None
        self._adjustment_count = 0

    async def execute(
        self,
        order: Order,
        params: MicroPriceParams,
    ) -> Order:
        """Execute order using micro-price strategy.

        Args:
            order: Order to execute
            params: Micro-price strategy parameters

        Returns:
            Updated order with final status

        Raises:
            Exception: If execution fails
        """
        self.logger.info(
            f"Starting micro-price execution: {order.side.value} {order.total_size} "
            f"@ {order.min_price}-{order.max_price}, "
            f"threshold={params.threshold_bps}bps"
        )

        try:
            # Place initial order
            current_price = await self._get_initial_price(order, params)
            placed_order_id = await self._place_order(order, current_price)
            self._active_order_id = placed_order_id

            # Monitor and adjust until complete
            while order.status not in [OrderStatus.COMPLETED, OrderStatus.FAILED]:
                # Wait for check interval
                await asyncio.sleep(params.check_interval)

                # Check if order is still effective
                should_replace = await self._should_replace_order(order, current_price, params)

                if should_replace:
                    # Check if we've hit adjustment limit
                    if self._adjustment_count >= params.max_adjustments:
                        self.logger.warning(
                            f"Hit max adjustments ({params.max_adjustments}), "
                            f"keeping current order"
                        )
                        break

                    # Cancel and replace
                    new_price = await self._replace_order(order, params)
                    if new_price is not None:
                        current_price = new_price
                        self._adjustment_count += 1

                # Check for fills
                await self._check_fills(order)

                # Break if complete
                if order.remaining_amount == 0:
                    order.update_status(OrderStatus.COMPLETED)
                    break

            self.logger.info(
                f"Micro-price execution complete: {order.status.value}, "
                f"filled {order.filled_amount}/{order.total_size}, "
                f"adjustments={self._adjustment_count}"
            )

            return order

        except Exception as e:
            self.logger.error(f"Micro-price execution failed: {e}")
            order.update_status(OrderStatus.FAILED)
            raise

    async def _get_initial_price(self, order: Order, params: MicroPriceParams) -> float:
        """Determine initial order price based on micro-price.

        Args:
            order: Order to price
            params: Strategy parameters

        Returns:
            Initial price to use
        """
        # Get current market snapshot
        snapshot = self.monitor.get_market_snapshot()

        # Start at micro-price
        initial_price = snapshot.micro_price

        # Adjust based on side
        if order.side == OrderSide.BUY:
            # For buys, we want to be slightly below micro-price
            # but not lower than best bid
            initial_price = max(snapshot.best_bid, initial_price - 0.01)
        else:
            # For sells, we want to be slightly above micro-price
            # but not higher than best ask
            initial_price = min(snapshot.best_ask, initial_price + 0.01)

        # Clamp to user's price bounds
        initial_price = max(order.min_price, min(order.max_price, initial_price))

        self.logger.info(
            f"Initial price: {initial_price:.4f} "
            f"(micro={snapshot.micro_price:.4f}, "
            f"bid={snapshot.best_bid:.4f}, ask={snapshot.best_ask:.4f})"
        )

        return initial_price

    async def _place_order(self, order: Order, price: float) -> str:
        """Place order at specified price.

        Args:
            order: Order to place
            price: Price to use

        Returns:
            Order ID from exchange

        Raises:
            Exception: If placement fails
        """
        # Place order via client
        response = self.client.place_order(
            token_id=order.token_id,
            side=order.side,
            price=price,
            size=order.remaining_amount,
        )

        # Extract order ID from response
        if isinstance(response, dict):
            order_id = response.get("orderID", response.get("id", str(response)))
        else:
            order_id = str(response)

        self.logger.info(f"Placed order {order_id} at {price:.4f} for {order.remaining_amount}")

        # Emit ACTIVE event
        if self.event_bus:
            await self.event_bus.publish(
                OrderEventData(
                    event=OrderEvent.ACTIVE,
                    order_id=order.order_id,
                    timestamp=datetime.now(),
                    order_state=order,
                    details={"price": price, "size": order.remaining_amount},
                )
            )

        return order_id

    async def _should_replace_order(
        self, order: Order, current_price: float, params: MicroPriceParams
    ) -> bool:
        """Check if current order should be replaced.

        An order should be replaced if:
        1. Price is outside micro-price threshold bands (not competitive)
        2. Price is too aggressive (far from best bid/ask)

        Args:
            order: Current order
            current_price: Current order price
            params: Strategy parameters

        Returns:
            True if order should be replaced
        """
        # Get fresh market snapshot
        snapshot = self.monitor.get_market_snapshot()

        # Calculate distance from micro-price
        distance = snapshot.distance_from_micro_price(current_price)
        threshold = params.get_threshold_fraction()

        # Log detailed calculation
        self.logger.info(
            f"Order check: price={current_price:.4f}, micro={snapshot.micro_price:.4f}, "
            f"distance={distance:.2%}, threshold={threshold:.2%} ({params.threshold_bps}bps)"
        )

        # Check if price is within threshold bands
        in_bounds = snapshot.is_price_in_bounds(current_price)

        if not in_bounds:
            self.logger.info(
                f"❌ Order OUT of bounds: {distance:.2%} > {threshold:.2%} → WILL REPLACE"
            )
            # Emit undercut event
            if self.event_bus:
                await self.event_bus.publish(
                    OrderEventData(
                        event=OrderEvent.UNDERCUT,
                        order_id=order.order_id,
                        timestamp=datetime.now(),
                        order_state=order,
                        details={"reason": "out_of_bounds", "distance": distance},
                    )
                )
            return True

        # Log that order is within bounds
        self.logger.info(
            f"✅ Order within bounds: {distance:.2%} <= {threshold:.2%} → keeping order"
        )

        # Check if we're too aggressive (far from competition)
        aggression_limit = params.get_aggression_limit_fraction()

        if order.side == OrderSide.BUY:
            # For buys, check if we're too far above best bid
            distance_from_best = (current_price - snapshot.best_bid) / snapshot.best_bid
            self.logger.info(
                f"Aggression check (BUY): {distance_from_best:.2%} above best bid "
                f"(limit: {aggression_limit:.2%})"
            )
            if distance_from_best > aggression_limit:
                self.logger.info(
                    f"❌ Buy order TOO AGGRESSIVE: {distance_from_best:.2%} > {aggression_limit:.2%} → WILL REPLACE"
                )
                # Emit undercut event
                if self.event_bus:
                    await self.event_bus.publish(
                        OrderEventData(
                            event=OrderEvent.UNDERCUT,
                            order_id=order.order_id,
                            timestamp=datetime.now(),
                            order_state=order,
                            details={
                                "reason": "too_aggressive_buy",
                                "distance": distance_from_best,
                            },
                        )
                    )
                return True
        else:
            # For sells, check if we're too far below best ask
            distance_from_best = (snapshot.best_ask - current_price) / snapshot.best_ask
            self.logger.info(
                f"Aggression check (SELL): {distance_from_best:.2%} below best ask "
                f"(limit: {aggression_limit:.2%})"
            )
            if distance_from_best > aggression_limit:
                self.logger.info(
                    f"❌ Sell order TOO AGGRESSIVE: {distance_from_best:.2%} > {aggression_limit:.2%} → WILL REPLACE"
                )
                # Emit undercut event
                if self.event_bus:
                    await self.event_bus.publish(
                        OrderEventData(
                            event=OrderEvent.UNDERCUT,
                            order_id=order.order_id,
                            timestamp=datetime.now(),
                            order_state=order,
                            details={
                                "reason": "too_aggressive_sell",
                                "distance": distance_from_best,
                            },
                        )
                    )
                return True

        self.logger.info("✅ Order is competitive → keeping order")
        return False

    async def _replace_order(self, order: Order, params: MicroPriceParams) -> Optional[float]:
        """Cancel current order and place new one at better price.

        Args:
            order: Order to replace
            params: Strategy parameters

        Returns:
            New price if successful, None if failed
        """
        try:
            # Cancel current order
            if self._active_order_id:
                self.logger.info(f"Canceling order {self._active_order_id}")
                self.client.cancel_order(self._active_order_id)
                order.record_adjustment()

            # Get new price
            new_price = await self._get_initial_price(order, params)

            # Place new order
            new_order_id = await self._place_order(order, new_price)
            self._active_order_id = new_order_id

            # Emit replaced event
            if self.event_bus:
                await self.event_bus.publish(
                    OrderEventData(
                        event=OrderEvent.REPLACED,
                        order_id=order.order_id,
                        timestamp=datetime.now(),
                        order_state=order,
                        details={
                            "new_price": new_price,
                            "adjustment_count": self._adjustment_count,
                        },
                    )
                )

            return new_price

        except Exception as e:
            self.logger.error(f"Failed to replace order: {e}")
            return None

    async def _check_fills(self, order: Order) -> None:
        """Check for order fills and update order state.

        Args:
            order: Order to check
        """
        if not self._active_order_id:
            return

        try:
            # Fetch order status from exchange
            order_status = self.client.get_order_status(self._active_order_id)

            # Check for fills
            filled = order_status.get("filled_amount", 0)
            if filled > 0:
                # Record fill
                new_fill = filled - order.filled_amount
                if new_fill > 0:
                    order.record_fill(new_fill)
                    self.logger.info(
                        f"Fill: {new_fill} (total: {order.filled_amount}/{order.total_size})"
                    )

                    # Emit fill event
                    if self.event_bus:
                        event = (
                            OrderEvent.FILLED
                            if order.filled_amount == order.total_size
                            else OrderEvent.PARTIALLY_FILLED
                        )
                        await self.event_bus.publish(
                            OrderEventData(
                                event=event,
                                order_id=order.order_id,
                                timestamp=datetime.now(),
                                order_state=order,
                                details={
                                    "amount": new_fill,
                                    "price": order_status.get("price", 0),
                                    "filled_amount": order.filled_amount,
                                    "total_size": order.total_size,
                                },
                            )
                        )

        except Exception as e:
            self.logger.warning(f"Failed to check fills: {e}")

    def get_adjustment_count(self) -> int:
        """Get number of adjustments made.

        Returns:
            Adjustment count
        """
        return self._adjustment_count

    def reset(self) -> None:
        """Reset strategy state for new execution."""
        self._active_order_id = None
        self._adjustment_count = 0
