"""Event subscriber for persisting order data to database."""

import logging
from typing import Optional

from core.event_bus import OrderEvent, OrderEventData
from core.persistence import OrderDatabase


class PersistenceSubscriber:
    """Subscribes to order events and persists to database.

    Features:
    - Saves order state on every event
    - Records event audit trail
    - Records fills separately
    - Graceful error handling
    """

    def __init__(self, db: OrderDatabase, logger: Optional[logging.Logger] = None):
        """Initialize persistence subscriber.

        Args:
            db: Order database instance
            logger: Optional logger instance
        """
        self.db = db
        self.logger = logger or logging.getLogger(__name__)

    async def handle_event(self, event_data: OrderEventData):
        """Handle order event by persisting.

        Args:
            event_data: Event data to persist
        """
        try:
            # Only save order state if order exists
            if event_data.order_state:
                self.db.save_order(
                    event_data.order_state,
                    strategy_type=event_data.details.get("strategy_type", "unknown"),
                )

            # Record event
            self.db.record_event(event_data.order_id, event_data.event.value, event_data.details)

            # Record fills
            if event_data.event in [OrderEvent.FILLED, OrderEvent.PARTIALLY_FILLED]:
                amount = event_data.details.get("amount", 0)
                price = event_data.details.get("price", 0)
                if amount > 0:
                    self.db.record_fill(event_data.order_id, amount, price)

            self.logger.debug(f"Persisted {event_data.event.value} for {event_data.order_id}")

        except Exception as e:
            self.logger.error(f"Failed to persist event: {e}")
