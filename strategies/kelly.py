"""Kelly criterion strategy for optimal position sizing."""

import asyncio
import logging
from typing import Optional

from api.polymarket_client import PolymarketClient
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
    2. Uses micro-price strategy for order placement and monitoring
    3. Recalculates position size periodically as prices change
    """

    def __init__(
        self,
        client: PolymarketClient,
        monitor: MarketMonitor,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize Kelly criterion strategy.

        Args:
            client: Polymarket API client
            monitor: Market monitor for tracking micro-price
            logger: Optional logger instance
        """
        self.client = client
        self.monitor = monitor
        self.logger = logger or logging.getLogger(__name__)

        # Micro-price strategy for execution
        self.micro_price_strategy = MicroPriceStrategy(client, monitor, logger)

    def calculate_kelly_fraction(
        self,
        win_probability: float,
        current_price: float,
        side: OrderSide,
        edge_upper_bound: float = 0.05,
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
            edge_upper_bound: Maximum edge to use in calculation (default: 0.05 = 5%)
                             Caps the edge to prevent over-betting on high-edge opportunities

        Returns:
            Kelly fraction (fraction of bankroll to bet)
        """
        # Calculate current edge
        if side == OrderSide.BUY:
            edge = win_probability - current_price
        else:
            edge = current_price - (1 - win_probability)

        # Apply edge upper bound if needed
        adjusted_probability = win_probability
        if edge > edge_upper_bound:
            # Cap the edge and derive the adjusted probability
            if side == OrderSide.BUY:
                adjusted_probability = current_price + edge_upper_bound
            else:
                adjusted_probability = 1 - current_price + edge_upper_bound

            # Clamp to valid probability range
            adjusted_probability = max(0.0, min(1.0, adjusted_probability))

            self.logger.info(
                f"Edge capped: {edge:.2%} -> {edge_upper_bound:.2%}, "
                f"adjusted probability: {win_probability:.2%} -> {adjusted_probability:.2%}"
            )

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
        # Use adjusted probability that respects edge upper bound
        loss_probability = 1 - adjusted_probability
        kelly_fraction = (odds * adjusted_probability - loss_probability) / odds

        # Clamp to [0, 1] - never bet negative or more than 100%
        kelly_fraction = max(0.0, min(1.0, kelly_fraction))

        return kelly_fraction

    def calculate_position_size(
        self,
        params: KellyParams,
        current_price: float,
        side: OrderSide,
    ) -> int:
        """Calculate position size using Kelly criterion.

        Args:
            params: Kelly parameters
            current_price: Current market price
            side: Order side

        Returns:
            Position size in shares
        """
        # Calculate Kelly fraction with edge upper bound
        kelly_fraction = self.calculate_kelly_fraction(
            params.win_probability, current_price, side, params.edge_upper_bound
        )

        # Apply Kelly fraction multiplier (for fractional Kelly)
        adjusted_fraction = kelly_fraction * params.kelly_fraction

        # Calculate position size in dollars
        position_dollars = params.bankroll * adjusted_fraction

        # Convert to shares
        # For prediction markets: shares = dollars / price
        if current_price == 0:
            position_size = 0
        else:
            position_size = int(position_dollars / current_price)

        # Cap at max position size
        position_size = min(position_size, params.max_position_size)

        self.logger.info(
            f"Kelly calculation: fraction={kelly_fraction:.3f}, "
            f"adjusted={adjusted_fraction:.3f}, "
            f"size={position_size} shares"
        )

        return position_size

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

            # Calculate initial position size
            position_size = self.calculate_position_size(params, current_price, order.side)

            if position_size == 0:
                self.logger.warning("Kelly calculation resulted in 0 position size, aborting")
                order.update_status(OrderStatus.FAILED)
                return order

            # Update order with calculated size
            order.total_size = position_size
            order.remaining_amount = position_size

            self.logger.info(
                f"Calculated position size: {position_size} shares at ${current_price:.4f}"
            )

            # Execute using micro-price strategy
            # We'll monitor and potentially recalculate size
            await self._execute_with_recalculation(order, params)

            self.logger.info(
                f"Kelly execution complete: {order.status.value}, "
                f"filled {order.filled_amount}/{order.total_size}"
            )

            return order

        except Exception as e:
            self.logger.error(f"Kelly execution failed: {e}")
            order.update_status(OrderStatus.FAILED)
            raise

    async def _execute_with_recalculation(
        self,
        order: Order,
        params: KellyParams,
    ) -> None:
        """Execute order with periodic position size recalculation.

        Args:
            order: Order to execute
            params: Kelly parameters
        """
        # Start micro-price execution in background
        micro_task = asyncio.create_task(
            self.micro_price_strategy.execute(order, params.micro_price_params)
        )

        # Periodically recalculate position size
        last_recalc_time = asyncio.get_event_loop().time()

        while not micro_task.done():
            # Wait for recalculation interval
            await asyncio.sleep(1.0)

            current_time = asyncio.get_event_loop().time()
            time_since_recalc = current_time - last_recalc_time

            if time_since_recalc >= params.recalculate_interval:
                # Time to recalculate
                await self._recalculate_position_size(order, params)
                last_recalc_time = current_time

            # Check if order is complete
            if order.status in [OrderStatus.COMPLETED, OrderStatus.FAILED]:
                break

        # Wait for micro-price task to complete
        try:
            await micro_task
        except Exception as e:
            self.logger.error(f"Micro-price execution failed: {e}")
            raise

    async def _recalculate_position_size(
        self,
        order: Order,
        params: KellyParams,
    ) -> None:
        """Recalculate optimal position size based on current price.

        If the optimal size has changed significantly, we may need to
        adjust our order (increase or decrease target size).

        Args:
            order: Current order
            params: Kelly parameters
        """
        # Get current market price
        snapshot = self.monitor.get_market_snapshot()
        current_price = snapshot.micro_price

        # Calculate new optimal position size
        new_size = self.calculate_position_size(params, current_price, order.side)

        # Calculate change from current target
        size_change = new_size - order.total_size
        change_pct = abs(size_change) / order.total_size if order.total_size > 0 else 0

        if change_pct > 0.1:  # More than 10% change
            self.logger.info(
                f"Position size changed significantly: "
                f"{order.total_size} -> {new_size} ({change_pct:.1%})"
            )

            # Update target size
            # Note: We can't easily change size of active orders,
            # so this mainly affects how much we're willing to fill
            order.total_size = new_size

            # Adjust remaining amount based on what's already filled
            order.remaining_amount = max(0, new_size - order.filled_amount)

            if order.remaining_amount == 0 and order.filled_amount < new_size:
                # We're already over-filled compared to new target
                self.logger.warning(
                    f"Already filled {order.filled_amount}, " f"but new target is {new_size}"
                )

    def reset(self) -> None:
        """Reset strategy state for new execution."""
        self.micro_price_strategy.reset()
