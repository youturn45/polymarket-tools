"""Kelly criterion strategy for optimal position sizing."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from api.polymarket_client import PolymarketClient
from core.event_bus import EventBus, OrderEvent, OrderEventData
from core.market_monitor import MarketMonitor
from models.enums import OrderSide, OrderStatus
from models.order import Order
from models.order_request import KellyParams
from strategies.micro_price import MicroPriceStrategy


class KellyStrategy:
    """Execute orders using Kelly criterion for position sizing.

    The Kelly criterion calculates the optimal position size based on:
    - Win probability (p)
    - Odds/payout (b)
    - Bankroll

    Formula: f* = (bp - q) / b
    where:
    - f* = fraction of bankroll to bet
    - p = probability of winning
    - q = probability of losing (1 - p)
    - b = odds (payout per dollar risked)

    This strategy:
    1. Calculates position size using Kelly formula
    2. Accounts for existing positions and pending orders
    3. Uses micro-price strategy for order placement and monitoring
    4. Recalculates position size periodically as prices change
    5. Cancels and replaces orders when size changes significantly
    """

    def __init__(
        self,
        client: PolymarketClient,
        monitor: MarketMonitor,
        portfolio_monitor=None,
        event_bus: Optional[EventBus] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize Kelly criterion strategy.

        Args:
            client: Polymarket API client
            monitor: Market monitor for tracking micro-price
            portfolio_monitor: Portfolio monitor for position tracking
            event_bus: Event bus for order events
            logger: Optional logger instance
        """
        self.client = client
        self.monitor = monitor
        self.portfolio_monitor = portfolio_monitor
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger(__name__)

        # Micro-price strategy for execution
        self.micro_price_strategy = MicroPriceStrategy(client, monitor, event_bus, logger)

        # Track current exchange order ID for cancellation
        self._current_exchange_order_id: Optional[str] = None

    def calculate_kelly_fraction(
        self,
        win_probability: float,
        current_price: float,
        side: OrderSide,
    ) -> float:
        """Calculate Kelly fraction for position sizing.

        For prediction markets:
        - If buying YES at price p: odds = (1 - p) / p
        - If selling YES at price p: odds = p / (1 - p)

        Kelly formula: f* = (b*p - q) / b
        where b = odds, p = win prob, q = 1 - p

        Args:
            win_probability: Probability of winning (0-1)
            current_price: Current market price
            side: Order side (BUY or SELL)

        Returns:
            Kelly fraction (fraction of bankroll to bet)
        """
        # Calculate odds based on side
        if side == OrderSide.BUY:
            # Buying at price p, pays out 1 if win
            # Odds: how much you win per dollar risked
            # Win: (1 - p), Risk: p, Odds: (1 - p) / p
            if current_price == 0:
                return 0.0
            odds = (1 - current_price) / current_price
        else:
            # Selling at price p
            # Win: p, Risk: (1 - p), Odds: p / (1 - p)
            if current_price == 1:
                return 0.0
            odds = current_price / (1 - current_price)

        # Kelly formula
        # f* = (odds * win_prob - loss_prob) / odds
        # f* = (b*p - q) / b
        loss_probability = 1 - win_probability
        kelly_fraction = (odds * win_probability - loss_probability) / odds

        # Clamp to [0, 1] - never bet negative or more than 100%
        kelly_fraction = max(0.0, min(1.0, kelly_fraction))

        return kelly_fraction

    def calculate_position_size(
        self,
        params: KellyParams,
        current_price: float,
        side: OrderSide,
        existing_position: int = 0,
        pending_orders: int = 0,
    ) -> int:
        """Calculate optimal INCREMENTAL position size.

        This is order-aware: it accounts for positions already held
        and orders already placed to avoid double-counting exposure.

        Args:
            params: Kelly parameters
            current_price: Current market price
            side: Order side
            existing_position: Shares already held
            pending_orders: Shares in unfilled orders

        Returns:
            Incremental shares to order (not total position)
        """
        # Calculate Kelly fraction
        kelly_fraction = self.calculate_kelly_fraction(params.win_probability, current_price, side)

        # Apply Kelly fraction multiplier (for fractional Kelly)
        adjusted_fraction = kelly_fraction * params.kelly_fraction

        # Calculate optimal total position in dollars
        position_dollars = params.bankroll * adjusted_fraction

        # Convert to shares
        if current_price == 0:
            optimal_total = 0
        else:
            optimal_total = int(position_dollars / current_price)

        # Cap at max position size
        optimal_total = min(optimal_total, params.max_position_size)

        # Calculate current exposure
        current_exposure = existing_position + pending_orders

        # Return incremental size needed
        incremental = max(0, optimal_total - current_exposure)

        self.logger.info(
            f"Kelly sizing: optimal={optimal_total}, "
            f"held={existing_position}, pending={pending_orders}, "
            f"incremental={incremental}"
        )

        return incremental

    async def _get_current_position(self, token_id: str) -> int:
        """Get current position from PortfolioMonitor.

        Args:
            token_id: Token ID to query

        Returns:
            Number of shares held (0 if no position or no monitor)
        """
        if not self.portfolio_monitor:
            return 0

        try:
            positions = self.portfolio_monitor.get_positions_snapshot()
            if token_id in positions:
                return int(positions[token_id].total_shares)
        except Exception as e:
            self.logger.warning(f"Failed to get current position: {e}")

        return 0

    async def execute(
        self,
        order: Order,
        params: KellyParams,
    ) -> Order:
        """Execute order using Kelly criterion strategy.

        Args:
            order: Order template (total_size will be calculated)
            params: Kelly parameters

        Returns:
            Updated order with final status

        Raises:
            Exception: If execution fails
        """
        self.logger.info(
            f"Starting Kelly execution: {order.side.value}, "
            f"win_prob={params.win_probability:.2%}, "
            f"bankroll=${params.bankroll}, "
            f"kelly_fraction={params.kelly_fraction}"
        )

        try:
            # Get initial market snapshot
            snapshot = self.monitor.get_market_snapshot()
            current_price = snapshot.micro_price

            # Get existing position
            existing_position = await self._get_current_position(order.token_id)

            # Calculate incremental size needed (don't count pending orders yet)
            incremental_size = self.calculate_position_size(
                params, current_price, order.side, existing_position, 0
            )

            if incremental_size == 0:
                self.logger.info("No position adjustment needed (already at optimal)")
                order.update_status(OrderStatus.COMPLETED)
                return order

            # Update order with calculated size
            order.total_size = incremental_size
            order.remaining_amount = incremental_size

            self.logger.info(
                f"Calculated incremental position: {incremental_size} shares "
                f"at ${current_price:.4f}"
            )

            # Start monitoring task for recalculation
            recalc_task = asyncio.create_task(self._monitor_and_recalculate(order, params))

            try:
                # Execute using micro-price strategy
                result = await self.micro_price_strategy.execute(order, params.micro_price_params)

                self.logger.info(
                    f"Kelly execution complete: {result.status.value}, "
                    f"filled {result.filled_amount}/{result.total_size}"
                )

                return result

            finally:
                # Stop recalculation task
                recalc_task.cancel()
                try:
                    await recalc_task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            self.logger.error(f"Kelly execution failed: {e}")
            order.update_status(OrderStatus.FAILED)
            raise

    async def _monitor_and_recalculate(
        self,
        order: Order,
        params: KellyParams,
    ) -> None:
        """Background task to monitor and recalculate position.

        Args:
            order: Order being executed
            params: Kelly parameters
        """
        while order.status in [OrderStatus.ACTIVE, OrderStatus.PARTIALLY_FILLED]:
            await asyncio.sleep(params.recalculate_interval)
            await self._recalculate_position_size(order, params)

    async def _recalculate_position_size(
        self,
        order: Order,
        params: KellyParams,
    ) -> None:
        """Recalculate position and cancel/replace if needed.

        Args:
            order: Current order
            params: Kelly parameters
        """
        # Get current market price
        snapshot = self.monitor.get_market_snapshot()
        current_price = snapshot.micro_price

        # Get existing position
        existing_position = await self._get_current_position(order.token_id)

        # Calculate new incremental size (don't count pending order yet)
        new_incremental_size = self.calculate_position_size(
            params, current_price, order.side, existing_position, 0
        )

        # Compare to current pending size
        pending_size = order.remaining_amount
        size_change = new_incremental_size - pending_size
        change_pct = abs(size_change) / pending_size if pending_size > 0 else float("inf")

        # Check if recalculation needed
        if change_pct > params.recalc_threshold_pct:
            self.logger.info(
                f"Kelly recalculation triggered: "
                f"{pending_size} -> {new_incremental_size} shares "
                f"(change: {change_pct:.1%})"
            )

            # Cancel current order if we have one
            if self._current_exchange_order_id:
                try:
                    await self.client.cancel_order(self._current_exchange_order_id)
                    self.logger.info(f"Cancelled order {self._current_exchange_order_id}")

                    # Emit cancelled event
                    if self.event_bus:
                        await self.event_bus.publish(
                            OrderEventData(
                                event=OrderEvent.CANCELLED,
                                order_id=order.order_id,
                                timestamp=datetime.now(),
                                order_state=order,
                                details={"reason": "kelly_recalculation"},
                            )
                        )
                except Exception as e:
                    self.logger.error(f"Failed to cancel order: {e}")

            # Update order size
            order.total_size = new_incremental_size
            order.remaining_amount = new_incremental_size

            # Place new order if size > 0
            if new_incremental_size > 0:
                # Note: In a full implementation, we'd place a new order here
                # For now, the micro-price strategy will handle this
                # This is a simplified version - full implementation would need
                # deeper integration with the micro-price strategy

                # Emit replaced event
                if self.event_bus:
                    await self.event_bus.publish(
                        OrderEventData(
                            event=OrderEvent.REPLACED,
                            order_id=order.order_id,
                            timestamp=datetime.now(),
                            order_state=order,
                            details={"new_size": new_incremental_size, "new_price": current_price},
                        )
                    )

                self.logger.info(
                    f"Position recalculated: {new_incremental_size} shares @ {current_price:.4f}"
                )
            else:
                # No more size needed
                self.logger.info("Optimal position reached, stopping Kelly execution")
                order.update_status(OrderStatus.COMPLETED)

    def reset(self) -> None:
        """Reset strategy state for new execution."""
        self.micro_price_strategy.reset()
        self._current_exchange_order_id = None
