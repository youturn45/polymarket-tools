"""Kelly monitoring daemon for long-term position rebalancing."""

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from api.polymarket_client import PolymarketClient
from core.event_bus import EventBus, OrderEvent, OrderEventData
from core.market_monitor import MarketMonitor
from models.enums import OrderSide
from models.order_request import KellyMonitorParams, OrderRequest, StrategyType


@dataclass
class MonitoringSession:
    """State for a single token monitoring session."""

    session_id: str
    token_id: str
    side: OrderSide
    params: KellyMonitorParams
    start_time: datetime
    end_time: datetime

    # Price tracking
    reference_price: float  # Price at last rebalance
    last_check_time: datetime = field(default_factory=datetime.now)
    last_rebalance_time: datetime = field(default_factory=datetime.now)

    # Rebalancing tracking
    rebalance_count: int = 0
    is_active: bool = True

    # Market monitor
    market_monitor: Optional[MarketMonitor] = None

    def is_expired(self) -> bool:
        """Check if monitoring session has expired."""
        return datetime.now() >= self.end_time

    def can_rebalance(self) -> bool:
        """Check if session can still rebalance (not at max limit)."""
        return self.rebalance_count < self.params.max_rebalances_per_day


class KellyMonitorDaemon:
    """Long-term monitoring daemon for Kelly positions with automatic rebalancing.

    Monitors tokens for 24+ hours after initial order placement and automatically
    rebalances positions when:
    - Price moves significantly from reference price
    - Position deviates from optimal Kelly size
    - Periodic check interval is reached

    Key behaviors:
    - Only rebalances to INCREASE position (never sells automatically)
    - Cancels old orders and places new ones at updated micro-price
    - Respects maximum rebalances per day limit
    - Tracks exposure including pending orders
    """

    def __init__(
        self,
        client: PolymarketClient,
        portfolio_monitor,
        order_daemon,
        event_bus: Optional[EventBus] = None,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize Kelly monitoring daemon.

        Args:
            client: Polymarket API client
            portfolio_monitor: Portfolio monitor for position/order tracking
            order_daemon: Order daemon for submitting rebalancing orders
            event_bus: Optional event bus for monitoring events
            logger: Optional logger instance
        """
        self.client = client
        self.portfolio_monitor = portfolio_monitor
        self.order_daemon = order_daemon
        self.event_bus = event_bus
        self.logger = logger or logging.getLogger(__name__)

        # Active monitoring sessions
        self._sessions: dict[str, MonitoringSession] = {}
        self._sessions_lock = asyncio.Lock()

        # Daemon state
        self._running = False
        self._monitor_task: Optional[asyncio.Task] = None

        # Statistics
        self._total_rebalances = 0
        self._total_sessions = 0

    async def start(self) -> None:
        """Start the monitoring daemon.

        Raises:
            RuntimeError: If daemon is already running
        """
        if self._running:
            raise RuntimeError("Kelly monitor daemon is already running")

        self.logger.info("Starting Kelly monitor daemon...")
        self._running = True

        # Start monitoring loop
        self._monitor_task = asyncio.create_task(self._monitor_loop())

        self.logger.info("Kelly monitor daemon started")

    async def stop(self) -> None:
        """Stop the daemon gracefully.

        Stops monitoring all sessions and waits for cleanup.
        """
        if not self._running:
            self.logger.warning("Kelly monitor daemon is not running")
            return

        self.logger.info("Stopping Kelly monitor daemon...")
        self._running = False

        # Cancel monitoring task
        if self._monitor_task and not self._monitor_task.done():
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                self.logger.debug("Monitor task cancelled")

        # Mark all sessions as inactive
        async with self._sessions_lock:
            for session in self._sessions.values():
                session.is_active = False

        self.logger.info("Kelly monitor daemon stopped")

    async def add_token_monitor(
        self,
        token_id: str,
        side: OrderSide,
        params: KellyMonitorParams,
        initial_price: float,
    ) -> str:
        """Add a token to long-term monitoring.

        Args:
            token_id: Token ID to monitor
            side: Order side (BUY or SELL)
            params: Monitoring parameters
            initial_price: Initial reference price (micro-price)

        Returns:
            Session ID for this monitoring session

        Raises:
            RuntimeError: If daemon is not running
            ValueError: If token is already being monitored
        """
        if not self._running:
            raise RuntimeError("Kelly monitor daemon is not running")

        async with self._sessions_lock:
            # Check if token already being monitored
            for session in self._sessions.values():
                if session.token_id == token_id and session.is_active:
                    raise ValueError(f"Token {token_id} is already being monitored")

            # Create monitoring session
            session_id = str(uuid.uuid4())[:8]
            now = datetime.now()
            end_time = now + timedelta(hours=params.monitor_duration_hours)

            # Create market monitor for this token
            market_monitor = MarketMonitor(
                client=self.client,
                token_id=token_id,
                band_width_bps=50,
                logger=self.logger,
            )

            session = MonitoringSession(
                session_id=session_id,
                token_id=token_id,
                side=side,
                params=params,
                start_time=now,
                end_time=end_time,
                reference_price=initial_price,
                market_monitor=market_monitor,
            )

            self._sessions[session_id] = session
            self._total_sessions += 1

            self.logger.info(
                f"Added monitoring session {session_id} for token {token_id[:16]}... "
                f"(duration: {params.monitor_duration_hours}h, ends: {end_time:%Y-%m-%d %H:%M:%S})"
            )

            # Emit monitoring started event
            if self.event_bus:
                await self.event_bus.publish(
                    OrderEventData(
                        event=OrderEvent.STARTED,
                        order_id=f"monitor-{session_id}",
                        timestamp=now,
                        order_state=None,
                        details={
                            "session_id": session_id,
                            "token_id": token_id,
                            "side": side.value,
                            "duration_hours": params.monitor_duration_hours,
                            "initial_price": initial_price,
                        },
                    )
                )

            return session_id

    async def remove_token_monitor(self, token_id: str) -> None:
        """Remove a token from monitoring.

        Args:
            token_id: Token ID to stop monitoring
        """
        async with self._sessions_lock:
            sessions_to_remove = []
            for session_id, session in self._sessions.items():
                if session.token_id == token_id:
                    session.is_active = False
                    sessions_to_remove.append(session_id)
                    self.logger.info(f"Removed monitoring session {session_id}")

            for session_id in sessions_to_remove:
                del self._sessions[session_id]

    async def _monitor_loop(self) -> None:
        """Main monitoring loop - checks all active sessions periodically."""
        self.logger.info("Kelly monitor loop started")

        while self._running:
            try:
                async with self._sessions_lock:
                    sessions = list(self._sessions.values())

                # Check each active session
                for session in sessions:
                    if not session.is_active:
                        continue

                    try:
                        await self._check_session(session)
                    except Exception as e:
                        self.logger.error(
                            f"Error checking session {session.session_id}: {e}",
                            exc_info=True,
                        )

                # Clean up expired sessions
                await self._cleanup_expired_sessions()

            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}", exc_info=True)

            # Wait for next check (use minimum interval from all sessions)
            async with self._sessions_lock:
                if self._sessions:
                    min_interval = min(
                        s.params.monitor_check_interval_seconds
                        for s in self._sessions.values()
                        if s.is_active
                    )
                    await asyncio.sleep(min_interval)
                else:
                    await asyncio.sleep(60.0)

        self.logger.info("Kelly monitor loop stopped")

    async def _check_session(self, session: MonitoringSession) -> None:
        """Check a single monitoring session and rebalance if needed.

        Args:
            session: Monitoring session to check
        """
        now = datetime.now()

        # Check if session expired
        if session.is_expired():
            self.logger.info(
                f"Session {session.session_id} expired, stopping monitoring "
                f"(duration: {session.params.monitor_duration_hours}h)"
            )
            session.is_active = False

            # Cancel orders if configured
            if session.params.cancel_orders_on_completion:
                await self._cancel_token_orders(session.token_id)

            return

        # Update last check time
        session.last_check_time = now

        # Get current market snapshot
        if not session.market_monitor:
            self.logger.warning(f"No market monitor for session {session.session_id}")
            return

        try:
            snapshot = session.market_monitor.get_market_snapshot()
            current_price = snapshot.micro_price
        except Exception as e:
            self.logger.warning(f"Failed to get market snapshot: {e}")
            return

        # Get current exposure (held + pending orders)
        current_exposure = await self._get_current_exposure(session.token_id)

        # Calculate optimal position size
        optimal_size = await self._calculate_optimal_position(
            session, current_price, current_exposure
        )

        # Check if rebalancing needed
        should_rebalance, reason = await self._should_rebalance(
            session, current_price, current_exposure, optimal_size
        )

        if should_rebalance:
            self.logger.info(
                f"Rebalancing triggered for {session.token_id[:16]}... - Reason: {reason}"
            )
            await self._execute_rebalance(session, current_price, optimal_size, current_exposure)

    async def _should_rebalance(
        self,
        session: MonitoringSession,
        current_price: float,
        current_exposure: int,
        optimal_size: int,
    ) -> tuple[bool, str]:
        """Determine if rebalancing is needed.

        Args:
            session: Monitoring session
            current_price: Current market price
            current_exposure: Current position + pending orders
            optimal_size: Optimal position size from Kelly

        Returns:
            Tuple of (should_rebalance, reason)
        """
        now = datetime.now()

        # Check max rebalances limit first
        if not session.can_rebalance():
            return False, "Max rebalances per day reached"

        # Trigger 1: Price movement
        price_change_pct = abs(current_price - session.reference_price) / session.reference_price
        if price_change_pct >= session.params.price_change_threshold_pct:
            return True, f"Price moved {price_change_pct:.1%}"

        # Trigger 2: Position deviation
        if optimal_size > 0:
            deviation_pct = abs(current_exposure - optimal_size) / optimal_size
            if deviation_pct >= session.params.position_deviation_threshold_pct:
                return True, f"Position deviated {deviation_pct:.1%}"

        # Trigger 3: Periodic check
        time_since_last_minutes = (now - session.last_rebalance_time).total_seconds() / 60
        if time_since_last_minutes >= session.params.periodic_check_interval_minutes:
            # Only rebalance if there's meaningful work to do
            delta = optimal_size - current_exposure
            if abs(delta) >= session.params.min_rebalance_shares:
                return True, f"Periodic check ({time_since_last_minutes:.1f} min)"

        return False, "No trigger"

    async def _execute_rebalance(
        self,
        session: MonitoringSession,
        current_price: float,
        optimal_size: int,
        current_exposure: int,
    ) -> None:
        """Execute rebalancing by canceling old orders and placing new ones.

        Args:
            session: Monitoring session
            current_price: Current market price
            optimal_size: Optimal position size from Kelly
            current_exposure: Current position + pending orders
        """
        try:
            # Calculate delta
            delta = optimal_size - current_exposure

            self.logger.info(
                f"Rebalancing {session.token_id[:16]}...: "
                f"optimal={optimal_size}, current={current_exposure}, delta={delta}"
            )

            # Only rebalance to INCREASE position
            if delta < session.params.min_rebalance_shares:
                if delta < 0:
                    self.logger.warning(
                        f"Position oversized by {-delta} shares, but NOT selling automatically. "
                        f"Continuing to monitor."
                    )
                else:
                    self.logger.info(f"Delta too small ({delta} shares), skipping rebalance")
                return

            # Cancel all pending orders for this token
            cancelled_count = await self._cancel_token_orders(session.token_id)
            self.logger.info(f"Cancelled {cancelled_count} pending orders")

            # Place new order for delta shares
            await self._place_rebalance_order(session, current_price, delta)

            # Update session state
            session.reference_price = current_price
            session.last_rebalance_time = datetime.now()
            session.rebalance_count += 1
            self._total_rebalances += 1

            self.logger.info(
                f"Rebalance complete: placed order for {delta} shares @ ${current_price:.4f} "
                f"(rebalance #{session.rebalance_count})"
            )

            # Emit rebalance event
            if self.event_bus:
                await self.event_bus.publish(
                    OrderEventData(
                        event=OrderEvent.REPLACED,
                        order_id=f"monitor-{session.session_id}",
                        timestamp=datetime.now(),
                        order_state=None,
                        details={
                            "session_id": session.session_id,
                            "token_id": session.token_id,
                            "rebalance_count": session.rebalance_count,
                            "new_price": current_price,
                            "new_size": delta,
                            "optimal_size": optimal_size,
                            "current_exposure": current_exposure,
                        },
                    )
                )

        except Exception as e:
            self.logger.error(f"Rebalancing failed: {e}", exc_info=True)

    async def _place_rebalance_order(
        self,
        session: MonitoringSession,
        price: float,
        size: int,
    ) -> None:
        """Place a rebalancing order through the order daemon.

        Args:
            session: Monitoring session
            price: Order price (micro-price)
            size: Order size in shares
        """
        # Create order request using Kelly strategy
        request = OrderRequest(
            token_id=session.token_id,
            side=session.side,
            strategy_type=StrategyType.MICRO_PRICE,
            max_price=price,
            min_price=price,
            total_size=size,
            micro_price_params=session.params.kelly_params.micro_price_params,
            timeout=300.0,
        )

        # Submit to order daemon
        await self.order_daemon.submit_order(request)

        self.logger.info(f"Rebalance order submitted: {size} shares @ ${price:.4f}")

    async def _cancel_token_orders(self, token_id: str) -> int:
        """Cancel all pending orders for a token.

        Args:
            token_id: Token ID

        Returns:
            Number of orders cancelled
        """
        try:
            orders = self.portfolio_monitor.get_orders_snapshot()
            cancelled_count = 0

            for order_id, order in orders.items():
                if order.get("asset_id") == token_id:
                    try:
                        await asyncio.to_thread(self.client.cancel_order, order_id)
                        cancelled_count += 1
                        self.logger.debug(f"Cancelled order {order_id[:16]}...")
                    except Exception as e:
                        self.logger.warning(f"Failed to cancel order {order_id[:16]}...: {e}")

            return cancelled_count

        except Exception as e:
            self.logger.error(f"Failed to cancel orders: {e}")
            return 0

    async def _get_current_exposure(self, token_id: str) -> int:
        """Get current exposure (held shares + pending orders).

        Args:
            token_id: Token ID

        Returns:
            Total exposure in shares
        """
        # Get held shares from positions
        positions = self.portfolio_monitor.get_positions_snapshot()
        held_shares = 0
        if token_id in positions:
            held_shares = int(positions[token_id].total_shares)

        # Get pending order shares
        orders = self.portfolio_monitor.get_orders_snapshot()
        pending_shares = 0
        for order in orders.values():
            if order.get("asset_id") == token_id:
                # Calculate unfilled size
                size = int(order.get("original_size", 0))
                matched = int(order.get("size_matched", 0))
                pending_shares += size - matched

        total_exposure = held_shares + pending_shares

        self.logger.debug(
            f"Exposure for {token_id[:16]}...: held={held_shares}, pending={pending_shares}, "
            f"total={total_exposure}"
        )

        return total_exposure

    async def _calculate_optimal_position(
        self,
        session: MonitoringSession,
        current_price: float,
        current_exposure: int,
    ) -> int:
        """Calculate optimal position size using Kelly criterion.

        Args:
            session: Monitoring session
            current_price: Current market price
            current_exposure: Current exposure (not used in calculation, just for logging)

        Returns:
            Optimal total position size in shares
        """
        kelly_params = session.params.kelly_params

        # Calculate Kelly fraction
        from strategies.kelly import KellyStrategy

        kelly_strategy = KellyStrategy(
            client=self.client,
            monitor=session.market_monitor,
            portfolio_monitor=self.portfolio_monitor,
            event_bus=self.event_bus,
            logger=self.logger,
        )

        kelly_fraction = kelly_strategy.calculate_kelly_fraction(
            kelly_params.win_probability, current_price, session.side
        )

        # Apply Kelly fraction multiplier
        adjusted_fraction = kelly_fraction * kelly_params.kelly_fraction

        # Calculate optimal total position in dollars
        position_dollars = kelly_params.bankroll * adjusted_fraction

        # Convert to shares
        if current_price == 0:
            optimal_total = 0
        else:
            optimal_total = int(position_dollars / current_price)

        # Cap at max position size
        optimal_total = min(optimal_total, kelly_params.max_position_size)

        self.logger.debug(
            f"Kelly calculation: fraction={kelly_fraction:.4f}, "
            f"adjusted={adjusted_fraction:.4f}, "
            f"position_dollars=${position_dollars:.2f}, "
            f"optimal_total={optimal_total}"
        )

        return optimal_total

    async def _cleanup_expired_sessions(self) -> None:
        """Remove expired and inactive sessions."""
        async with self._sessions_lock:
            expired = [
                session_id
                for session_id, session in self._sessions.items()
                if not session.is_active or session.is_expired()
            ]

            for session_id in expired:
                session = self._sessions[session_id]
                self.logger.info(
                    f"Cleaning up session {session_id} "
                    f"(rebalances: {session.rebalance_count}, "
                    f"duration: {(datetime.now() - session.start_time).total_seconds() / 3600:.1f}h)"
                )
                del self._sessions[session_id]

    def get_active_sessions(self) -> list[dict]:
        """Get information about active monitoring sessions.

        Returns:
            List of session info dictionaries
        """
        sessions = []
        for session in self._sessions.values():
            if session.is_active:
                sessions.append(
                    {
                        "session_id": session.session_id,
                        "token_id": session.token_id,
                        "side": session.side.value,
                        "start_time": session.start_time,
                        "end_time": session.end_time,
                        "reference_price": session.reference_price,
                        "rebalance_count": session.rebalance_count,
                        "last_check_time": session.last_check_time,
                        "last_rebalance_time": session.last_rebalance_time,
                    }
                )
        return sessions

    def get_stats(self) -> dict:
        """Get daemon statistics.

        Returns:
            Dictionary with statistics
        """
        return {
            "is_running": self._running,
            "active_sessions": len([s for s in self._sessions.values() if s.is_active]),
            "total_sessions": self._total_sessions,
            "total_rebalances": self._total_rebalances,
        }

    def is_running(self) -> bool:
        """Check if daemon is running.

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
