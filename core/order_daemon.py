"""Order daemon for managing order queue and execution."""

import asyncio
import logging
from typing import Optional

from api.polymarket_client import PolymarketClient
from models.order import Order
from models.order_request import OrderRequest
from strategies.router import StrategyRouter


class OrderDaemon:
    """Daemon for managing order queue and asynchronous execution.

    The daemon maintains a queue of order requests and processes them
    asynchronously using the appropriate execution strategies.

    Features:
    - Asynchronous order queue
    - Strategy-based execution routing
    - Graceful shutdown
    - Order status tracking
    """

    def __init__(
        self,
        client: PolymarketClient,
        max_queue_size: int = 100,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize order daemon.

        Args:
            client: Polymarket API client
            max_queue_size: Maximum queue size (default: 100)
            logger: Optional logger instance
        """
        self.client = client
        self.logger = logger or logging.getLogger(__name__)

        # Order queue
        self._queue: asyncio.Queue[OrderRequest] = asyncio.Queue(maxsize=max_queue_size)

        # Strategy router
        self._router = StrategyRouter(client, logger)

        # Daemon state
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

        # Completed orders tracking
        self._completed_orders: list[Order] = []
        self._failed_orders: list[Order] = []

    async def start(self) -> None:
        """Start the daemon.

        Raises:
            RuntimeError: If daemon is already running
        """
        if self._running:
            raise RuntimeError("Daemon is already running")

        self.logger.info("Starting order daemon...")
        self._running = True

        # Start worker task
        self._worker_task = asyncio.create_task(self._process_queue())

        self.logger.info("Order daemon started")

    async def stop(self) -> None:
        """Stop the daemon gracefully.

        Waits for current order to complete before shutting down.
        """
        if not self._running:
            self.logger.warning("Daemon is not running")
            return

        self.logger.info("Stopping order daemon...")
        self._running = False

        # Cancel worker task
        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                self.logger.debug("Worker task cancelled")

        self.logger.info("Order daemon stopped")

    async def shutdown(self) -> None:
        """Alias for stop() for backwards compatibility."""
        await self.stop()

    async def submit_order(self, request: OrderRequest) -> Order:
        """Submit an order request to the queue.

        Args:
            request: Order request to execute

        Returns:
            Order object created from request

        Raises:
            RuntimeError: If daemon is not running
            asyncio.QueueFull: If queue is full
        """
        if not self._running:
            raise RuntimeError("Daemon is not running. Call start() first.")

        self.logger.info(
            f"Submitting order: {request.strategy_type.value} "
            f"{request.side.value} {request.total_size or 'dynamic'}"
        )

        # Create order from request
        order = self._router.create_order_from_request(request)

        # Add to queue (non-blocking)
        try:
            self._queue.put_nowait(request)
            self.logger.debug(f"Order queued (queue size: {self._queue.qsize()})")
            return order
        except asyncio.QueueFull:
            self.logger.error("Order queue is full")
            raise

    async def _process_queue(self) -> None:
        """Process orders from the queue.

        This runs continuously until the daemon is stopped.
        """
        self.logger.info("Worker started, processing queue...")

        while self._running:
            try:
                # Wait for order with timeout
                try:
                    request = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                except asyncio.TimeoutError:
                    # No order available, continue loop
                    continue

                self.logger.info(
                    f"Processing order: {request.strategy_type.value} "
                    f"{request.side.value} {request.total_size or 'dynamic'}"
                )

                # Execute order using router
                try:
                    result = await self._router.execute_order(request)

                    # Track result
                    if result.status.value in ["completed", "partially_filled"]:
                        self._completed_orders.append(result)
                        self.logger.info(
                            f"Order completed: {result.order_id}, "
                            f"filled {result.filled_amount}/{result.total_size}"
                        )
                    else:
                        self._failed_orders.append(result)
                        self.logger.warning(
                            f"Order failed: {result.order_id}, status={result.status.value}"
                        )

                except Exception as e:
                    self.logger.error(f"Order execution failed: {e}", exc_info=True)
                    # Continue processing other orders

                finally:
                    # Mark task as done
                    self._queue.task_done()

            except asyncio.CancelledError:
                self.logger.info("Worker task cancelled")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error in worker: {e}", exc_info=True)
                # Continue running despite errors

        self.logger.info("Worker stopped")

    def is_running(self) -> bool:
        """Check if daemon is running.

        Returns:
            True if running
        """
        return self._running

    def get_queue_size(self) -> int:
        """Get current queue size.

        Returns:
            Number of pending orders
        """
        return self._queue.qsize()

    def get_completed_orders(self) -> list[Order]:
        """Get list of completed orders.

        Returns:
            List of completed orders
        """
        return self._completed_orders.copy()

    def get_failed_orders(self) -> list[Order]:
        """Get list of failed orders.

        Returns:
            List of failed orders
        """
        return self._failed_orders.copy()

    def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get order status by order ID.

        Args:
            order_id: Order ID to lookup

        Returns:
            Order object if found, None otherwise
        """
        # Search in completed orders
        for order in self._completed_orders:
            if order.order_id == order_id:
                return order

        # Search in failed orders
        for order in self._failed_orders:
            if order.order_id == order_id:
                return order

        return None

    def clear_history(self) -> None:
        """Clear completed and failed order history."""
        self._completed_orders.clear()
        self._failed_orders.clear()
        self.logger.debug("Order history cleared")

    async def wait_for_completion(self, timeout: Optional[float] = None) -> bool:
        """Wait for all queued orders to complete.

        Args:
            timeout: Optional timeout in seconds

        Returns:
            True if all orders completed, False if timed out

        Raises:
            RuntimeError: If daemon is not running
        """
        if not self._running:
            raise RuntimeError("Daemon is not running")

        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
