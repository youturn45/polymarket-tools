"""Strategy router for directing orders to appropriate execution strategy."""

import logging
import uuid
from typing import Optional

from api.polymarket_client import PolymarketClient
from core.market_monitor import MarketMonitor
from models.enums import OrderStatus
from models.order import Order
from models.order_request import OrderRequest, StrategyType
from strategies.kelly import KellyStrategy
from strategies.micro_price import MicroPriceStrategy


class StrategyRouter:
    """Routes order requests to appropriate execution strategy."""

    def __init__(
        self,
        client: PolymarketClient,
        portfolio_monitor=None,
        event_bus=None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize strategy router.

        Args:
            client: Polymarket API client
            portfolio_monitor: Portfolio monitor for position tracking
            event_bus: Event bus for order events
            logger: Optional logger instance
        """
        self.client = client
        self.portfolio_monitor = portfolio_monitor
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger(__name__)

    def create_order_from_request(self, request: OrderRequest) -> Order:
        """Create Order object from OrderRequest.

        Args:
            request: Order request from user

        Returns:
            Order object ready for execution
        """
        # Generate order ID if not provided
        order_id = f"{request.strategy_type.value}-{uuid.uuid4().hex[:8]}"

        # Determine target price (use mid-point of min/max as default)
        target_price = (request.min_price + request.max_price) / 2

        # Create order
        # Build order parameters
        order_params = {
            "order_id": order_id,
            "market_id": request.market_id,
            "token_id": request.token_id,
            "side": request.side,
            "total_size": request.total_size or 0,  # Kelly will set this later
            "target_price": target_price,
            "max_price": request.max_price,
            "min_price": request.min_price,
            "urgency": request.urgency,
        }

        # Only add strategy_params for iceberg orders
        if request.strategy_type == StrategyType.ICEBERG and request.iceberg_params:
            order_params["strategy_params"] = request.iceberg_params

        order = Order(**order_params)

        return order

    async def execute_order(self, request: OrderRequest) -> Order:
        """Route order request to appropriate strategy and execute.

        Args:
            request: Order request with strategy specification

        Returns:
            Executed order with final status

        Raises:
            ValueError: If strategy type is unknown or not implemented
        """
        self.logger.info(
            f"Routing {request.strategy_type.value} order: "
            f"{request.side.value} {request.total_size or 'dynamic'} "
            f"@ {request.min_price}-{request.max_price}"
        )

        # Route to appropriate strategy
        if request.strategy_type == StrategyType.ICEBERG:
            return await self._execute_iceberg(request)

        elif request.strategy_type == StrategyType.MICRO_PRICE:
            return await self._execute_micro_price(request)

        elif request.strategy_type == StrategyType.KELLY:
            return await self._execute_kelly(request)

        else:
            raise ValueError(f"Unknown strategy type: {request.strategy_type}")

    async def _execute_iceberg(self, request: OrderRequest) -> Order:
        """Execute iceberg strategy.

        Args:
            request: Order request

        Returns:
            Executed order
        """
        from core.order_executor import OrderExecutor

        # Create order
        order = self.create_order_from_request(request)

        # For now, use synchronous executor (will convert to async later)
        # This is a placeholder - in full implementation we'd use async
        executor = OrderExecutor(self.client, self.logger)

        try:
            # Execute using iceberg strategy
            result = executor.execute_iceberg_order(order)
            self.logger.info(
                f"Iceberg order {order.order_id} completed: "
                f"{result.status.value}, filled {result.filled_amount}/{result.total_size}"
            )
            return result

        except Exception as e:
            self.logger.error(f"Iceberg execution failed: {e}")
            order.update_status(OrderStatus.FAILED)
            raise

    async def _execute_micro_price(self, request: OrderRequest) -> Order:
        """Execute micro-price strategy.

        Args:
            request: Order request

        Returns:
            Executed order
        """
        # Create order
        order = self.create_order_from_request(request)

        # Create market monitor
        monitor = MarketMonitor(
            self.client,
            request.token_id,
            band_width_bps=request.micro_price_params.threshold_bps,
            logger=self.logger,
        )

        # Create micro-price strategy with event bus
        strategy = MicroPriceStrategy(self.client, monitor, self.event_bus, self.logger)

        try:
            # Execute using micro-price strategy
            result = await strategy.execute(order, request.micro_price_params)
            self.logger.info(
                f"Micro-price order {order.order_id} completed: "
                f"{result.status.value}, filled {result.filled_amount}/{result.total_size}"
            )
            return result

        except Exception as e:
            self.logger.error(f"Micro-price execution failed: {e}")
            order.update_status(OrderStatus.FAILED)
            raise

    async def _execute_kelly(self, request: OrderRequest) -> Order:
        """Execute Kelly criterion strategy.

        Args:
            request: Order request

        Returns:
            Executed order
        """
        # Create order (total_size will be calculated by Kelly strategy)
        order = self.create_order_from_request(request)

        # Create market monitor
        monitor = MarketMonitor(
            self.client,
            request.token_id,
            band_width_bps=request.kelly_params.micro_price_params.threshold_bps,
            logger=self.logger,
        )

        # Create Kelly strategy with portfolio monitor and event bus
        strategy = KellyStrategy(
            self.client, monitor, self.portfolio_monitor, self.event_bus, self.logger
        )

        try:
            # Execute using Kelly criterion strategy
            result = await strategy.execute(order, request.kelly_params)
            self.logger.info(
                f"Kelly order {order.order_id} completed: "
                f"{result.status.value}, filled {result.filled_amount}/{result.total_size}"
            )
            return result

        except Exception as e:
            self.logger.error(f"Kelly execution failed: {e}")
            order.update_status(OrderStatus.FAILED)
            raise
