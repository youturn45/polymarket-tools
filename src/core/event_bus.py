"""Event bus for order lifecycle notifications."""

import asyncio
import logging
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from models.order import Order


class OrderEvent(str, Enum):
    """Order lifecycle events."""

    QUEUED = "queued"
    STARTED = "started"
    ACTIVE = "active"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REPLACED = "replaced"
    UNDERCUT = "undercut"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class OrderEventData:
    """Event data container."""

    event: OrderEvent
    order_id: str
    timestamp: datetime
    order_state: Optional[Order]
    details: dict[str, Any]


CallbackType = Callable[[OrderEventData], Awaitable[None]]


class EventBus:
    """Async event bus for order events.

    Features:
    - Non-blocking publish (events queued, not awaited)
    - Async worker processes events in background
    - Failed callbacks don't crash the system
    - Queue bounded to prevent memory issues
    """

    def __init__(self, logger: Optional[logging.Logger] = None):
        """Initialize event bus.

        Args:
            logger: Optional logger instance
        """
        self.logger = logger or logging.getLogger(__name__)
        self._subscribers: dict[OrderEvent, list[CallbackType]] = {}
        self._event_queue: asyncio.Queue[OrderEventData] = asyncio.Queue(maxsize=1000)
        self._worker_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        """Start event processing worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._process_events())
        self.logger.info("EventBus started")

    async def stop(self):
        """Stop event processing."""
        if not self._running:
            return
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        self.logger.info("EventBus stopped")

    def subscribe(self, event: OrderEvent, callback: CallbackType):
        """Subscribe to event type.

        Args:
            event: Event type to subscribe to
            callback: Async callback function
        """
        if event not in self._subscribers:
            self._subscribers[event] = []
        self._subscribers[event].append(callback)
        self.logger.debug(f"Subscribed to {event.value}")

    async def publish(self, event_data: OrderEventData):
        """Publish event (non-blocking).

        Args:
            event_data: Event data to publish
        """
        try:
            self._event_queue.put_nowait(event_data)
        except asyncio.QueueFull:
            self.logger.error(f"Event queue full, dropping {event_data.event.value}")

    async def _process_events(self):
        """Worker that dispatches events to subscribers."""
        while self._running:
            try:
                event_data = await asyncio.wait_for(self._event_queue.get(), timeout=1.0)
                await self._dispatch_event(event_data)
                self._event_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Event processing error: {e}")

    async def _dispatch_event(self, event_data: OrderEventData):
        """Dispatch event to all subscribers.

        Args:
            event_data: Event data to dispatch
        """
        subscribers = self._subscribers.get(event_data.event, [])
        for callback in subscribers:
            try:
                await callback(event_data)
            except Exception as e:
                self.logger.error(f"Subscriber error for {event_data.event.value}: {e}")
