"""Main trading system integration.

This module provides the TradingSystem class that integrates all components
of the polymarket-tools order system into a unified interface.
"""

import asyncio
import logging
from typing import Optional

from api.polymarket_client import PolymarketClient
from config.settings import PolymarketConfig, load_config
from core.event_bus import EventBus, OrderEvent
from core.order_daemon import OrderDaemon
from core.persistence import OrderDatabase
from core.persistence_subscriber import PersistenceSubscriber
from core.portfolio_monitor import PortfolioMonitor


class TradingSystem:
    """Main trading system that integrates all components.

    The TradingSystem coordinates:
    - API client for Polymarket interaction
    - Event bus for order lifecycle notifications
    - SQLite database for order persistence
    - Portfolio monitor for position tracking
    - Order daemon for queue-based execution

    Example:
        async with TradingSystem() as system:
            # Submit orders
            await system.daemon.submit_order(order_request)

            # Wait for completion
            await system.daemon.wait_for_completion()
    """

    def __init__(
        self,
        config: Optional[PolymarketConfig] = None,
        config_path: Optional[str] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize trading system.

        Args:
            config: Optional PolymarketConfig instance
            config_path: Optional path to config file (e.g., ".env")
            logger: Optional logger instance
        """
        # Load configuration
        if config is None:
            self.config = load_config(config_path)
        else:
            self.config = config

        self.logger = logger or logging.getLogger(__name__)

        # Initialize components
        self.client = PolymarketClient(self.config, self.logger)
        self.event_bus = EventBus(self.logger)
        self.db = OrderDatabase(self.config.db_path, self.logger)
        self.portfolio_monitor = PortfolioMonitor(self.client, self.logger)

        # Subscribe persistence to all events
        persistence_sub = PersistenceSubscriber(self.db, self.logger)
        for event in OrderEvent:
            self.event_bus.subscribe(event, persistence_sub.handle_event)

        # Create order daemon
        self.daemon = OrderDaemon(
            client=self.client,
            portfolio_monitor=self.portfolio_monitor,
            event_bus=self.event_bus,
            db=self.db,
            max_queue_size=100,
            max_concurrent=self.config.max_concurrent_orders,
            logger=self.logger,
        )

        self._running = False

    async def start(self) -> None:
        """Start all components.

        Starts the event bus, portfolio monitor, and order daemon.
        Recovers any active orders from the database on startup.

        Raises:
            RuntimeError: If system is already running
        """
        if self._running:
            raise RuntimeError("Trading system is already running")

        self.logger.info("Starting trading system...")

        # Start components in order
        await self.event_bus.start()
        await self.portfolio_monitor.start()
        await self.daemon.start()

        self._running = True

        self.logger.info(
            f"Trading system started "
            f"(max concurrent: {self.config.max_concurrent_orders}, "
            f"db: {self.config.db_path})"
        )

    async def stop(self) -> None:
        """Stop all components gracefully.

        Waits for active orders to complete before shutting down.
        Stops the daemon, portfolio monitor, and event bus in reverse order.
        """
        if not self._running:
            self.logger.warning("Trading system is not running")
            return

        self.logger.info("Stopping trading system...")
        self._running = False

        # Stop components in reverse order
        await self.daemon.stop()
        await self.portfolio_monitor.stop()
        await self.event_bus.stop()

        self.logger.info("Trading system stopped")

    def is_running(self) -> bool:
        """Check if system is running.

        Returns:
            True if running
        """
        return self._running

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()


async def main():
    """Example usage of TradingSystem."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Create and start system
    async with TradingSystem() as system:
        print("Trading system started!")
        print(f"Database: {system.config.db_path}")
        print(f"Max concurrent orders: {system.config.max_concurrent_orders}")
        print(f"Queue size: {system.daemon.get_queue_size()}")

        # System is now ready to accept orders
        # await system.daemon.submit_order(order_request)

        # Wait a bit
        await asyncio.sleep(2)

        print("Shutting down...")

    print("Trading system stopped!")


if __name__ == "__main__":
    asyncio.run(main())
