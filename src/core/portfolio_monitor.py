"""Portfolio monitoring daemon for tracking orders, positions, and market data."""

import asyncio
import logging
from datetime import datetime
from threading import RLock
from typing import Optional

import httpx

from api.polymarket_client import PolymarketClient
from models.market_metadata import MarketMetadata, TokenInfo
from models.position import Position


class PortfolioMonitor:
    """Background daemon that polls Polymarket API to maintain portfolio cache.

    Continuously polls the Polymarket API every N seconds to maintain an
    in-memory cache of:
    - Open orders with market metadata
    - Current positions calculated from trades
    - Market metadata (token_id -> question mapping) with TTL caching

    All data access is thread-safe using RLock for synchronization.

    Example:
        async with PortfolioMonitor(client, poll_interval=10.0) as monitor:
            orders = monitor.get_orders_snapshot()
            positions = monitor.get_positions_snapshot()
            question = await monitor.get_market_question(token_id)
    """

    def __init__(
        self,
        client: PolymarketClient,
        poll_interval: float = 10.0,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize portfolio monitor.

        Args:
            client: Polymarket API client
            poll_interval: Polling interval in seconds (default: 10.0)
            logger: Optional logger instance
        """
        self.client = client
        self.poll_interval = poll_interval
        self.logger = logger or logging.getLogger(__name__)

        # Thread-safe cache with RLock
        self._cache_lock = RLock()
        self._orders: dict[str, dict] = {}
        self._positions: dict[str, Position] = {}
        self._market_metadata: dict[str, MarketMetadata] = {}

        # Timestamps for cache freshness tracking
        self._last_orders_update: Optional[datetime] = None
        self._last_positions_update: Optional[datetime] = None

        # Daemon state
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        """Start the monitoring daemon.

        Raises:
            RuntimeError: If daemon is already running
        """
        if self._running:
            raise RuntimeError("Portfolio monitor is already running")

        self.logger.info("Starting portfolio monitor daemon...")
        self._running = True

        # Start monitoring task
        self._task = asyncio.create_task(self._monitor_loop())

        self.logger.info(f"Portfolio monitor started (poll interval: {self.poll_interval}s)")

    async def stop(self) -> None:
        """Stop the daemon gracefully.

        Cancels the monitoring task and waits for cleanup.
        """
        if not self._running:
            self.logger.warning("Portfolio monitor is not running")
            return

        self.logger.info("Stopping portfolio monitor...")
        self._running = False

        # Cancel monitoring task
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                self.logger.debug("Monitoring task cancelled")

        self.logger.info("Portfolio monitor stopped")

    async def _monitor_loop(self) -> None:
        """Main monitoring loop - runs every poll_interval seconds.

        Continuously updates orders, positions, and refreshes stale metadata
        until the daemon is stopped.
        """
        self.logger.info("Monitor loop started")

        while self._running:
            try:
                # Update orders
                await self._update_orders()

                # Update positions
                await self._update_positions()

                # Refresh stale metadata (non-blocking, best effort)
                await self._refresh_stale_metadata()

            except Exception as e:
                self.logger.error(f"Monitor loop error: {e}", exc_info=True)
                # Continue running despite errors

            # Wait for next poll cycle
            await asyncio.sleep(self.poll_interval)

        self.logger.info("Monitor loop stopped")

    async def _update_orders(self) -> None:
        """Fetch all open orders and update cache.

        Uses asyncio.to_thread to avoid blocking the event loop during
        the synchronous API call. On error, keeps stale cache.
        """
        try:
            # Call synchronous API in thread pool
            orders = await asyncio.to_thread(self.client.get_orders)

            # Update cache atomically
            with self._cache_lock:
                self._orders = {o["id"]: o for o in orders}
                self._last_orders_update = datetime.now()

            self.logger.info(f"Updated {len(orders)} orders")

        except Exception as e:
            self.logger.warning(f"Failed to update orders: {e}")
            # Keep stale cache on error

    async def _update_positions(self) -> None:
        """Fetch positions from Polymarket Data API.

        Uses the wallet address from config to fetch current positions from
        data-api.polymarket.com, which provides accurate position information
        including shares held and average entry prices.

        On error, keeps stale cache.
        """
        try:
            # Get wallet address from config
            wallet_address = self.client.config.funder_address
            if not wallet_address:
                self.logger.warning("No wallet address configured (POLYMARKET_FUNDER_ADDRESS)")
                with self._cache_lock:
                    self._positions = {}
                    self._last_positions_update = datetime.now()
                return

            # Fetch positions from Data API
            url = "https://data-api.polymarket.com/positions"
            params = {
                "user": wallet_address.lower(),  # API expects lowercase address
                "sizeThreshold": 0.01,  # Include positions > 0.01 shares
                "limit": 100,
                "sortBy": "TOKENS",
                "sortDirection": "DESC",
            }

            self.logger.debug(f"Fetching positions for wallet: {wallet_address}")
            response = await asyncio.to_thread(lambda: httpx.get(url, params=params, timeout=10))
            response.raise_for_status()
            raw_data = response.json()

            # Debug: Log the response structure
            self.logger.info(f"API Response type: {type(raw_data)}")
            if isinstance(raw_data, dict):
                self.logger.info(f"Response keys: {list(raw_data.keys())}")
                # If data is wrapped in a dict, extract the positions array
                data = raw_data.get("data", raw_data.get("positions", raw_data))
            else:
                data = raw_data
            self.logger.info(f"Positions count in response: {len(data) if data else 0}")

            if not data:
                self.logger.info("No positions found for wallet")
                with self._cache_lock:
                    self._positions = {}
                    self._last_positions_update = datetime.now()
                return

            # Parse positions from API response
            positions: dict[str, Position] = {}

            for position_data in data:
                # Extract position details - using correct field names from API
                token_id = position_data.get("asset")  # API uses 'asset' not 'asset_id'
                if not token_id:
                    self.logger.debug(
                        f"Skipping position without asset: {list(position_data.keys())}"
                    )
                    continue

                # Get position size
                size = float(position_data.get("size", 0))
                if size <= 0:
                    self.logger.debug(f"Skipping position with zero/negative size: {size}")
                    continue

                # Skip resolved/redeemable positions
                is_redeemable = position_data.get("redeemable", False)
                if is_redeemable:
                    self.logger.debug(
                        f"Skipping resolved position: {position_data.get('title', 'Unknown')[:50]}"
                    )
                    continue

                # Parse other fields with correct API field names
                market_id = position_data.get("conditionId")  # API uses 'conditionId'
                outcome = position_data.get("outcome", "Unknown")
                market_question = position_data.get("title", "Unknown")  # API uses 'title'

                # Price information
                avg_price = float(position_data.get("avgPrice", 0))  # API uses 'avgPrice'
                current_price = float(position_data.get("curPrice", 0))  # API uses 'curPrice'

                # P&L information
                cash_pnl = float(position_data.get("cashPnl", 0))  # API provides 'cashPnl'

                # Create position object
                pos = Position(
                    token_id=str(token_id),
                    market_id=market_id,
                    question=market_question,
                    outcome=outcome,
                    total_shares=size,
                    avg_entry_price=avg_price,
                    current_price=current_price,
                    unrealized_pnl=cash_pnl,  # Use API's calculated P&L
                )

                positions[str(token_id)] = pos

            # Update cache atomically
            with self._cache_lock:
                self._positions = positions
                self._last_positions_update = datetime.now()

            self.logger.info(f"Updated {len(positions)} positions from Data API")

        except Exception as e:
            self.logger.warning(f"Failed to update positions: {e}")
            # Keep stale cache on error

    async def _refresh_stale_metadata(self) -> None:
        """Refresh market metadata that's older than TTL.

        Checks for stale metadata and refreshes up to 5 entries per cycle
        to avoid rate limits. This is best-effort and won't block if it fails.
        """
        try:
            with self._cache_lock:
                stale_tokens = [
                    tid for tid, meta in self._market_metadata.items() if meta.is_stale()
                ]

            if not stale_tokens:
                return

            # Refresh in batches to avoid rate limits
            refresh_count = min(5, len(stale_tokens))
            self.logger.debug(f"Refreshing {refresh_count} stale metadata entries")

            for token_id in stale_tokens[:refresh_count]:
                try:
                    await self.get_market_question(token_id)
                except Exception as e:
                    self.logger.warning(f"Failed to refresh metadata for {token_id[:8]}: {e}")

        except Exception as e:
            self.logger.warning(f"Failed to refresh stale metadata: {e}")

    async def get_market_question(self, token_id: str) -> str:
        """Get human-readable market question for a token ID.

        Lazy loads market metadata from API if not cached or stale.
        Uses order data to find the condition_id for API lookup.

        Args:
            token_id: Token ID to lookup

        Returns:
            Market question string or error message
        """
        # Check cache first
        with self._cache_lock:
            if token_id in self._market_metadata:
                metadata = self._market_metadata[token_id]
                if not metadata.is_stale():
                    return metadata.question

        # Cache miss or stale - need to fetch
        # Strategy: Extract condition_id from order data
        condition_id = None
        with self._cache_lock:
            for order in self._orders.values():
                if order.get("asset_id") == token_id:
                    condition_id = order.get("market")
                    break

            # Also check positions if not found in orders
            if not condition_id and token_id in self._positions:
                condition_id = self._positions[token_id].market_id

        if not condition_id:
            return f"Unknown Market ({token_id[:8]}...)"

        # Fetch market metadata from API
        try:
            market = await asyncio.to_thread(self.client.client.get_market, condition_id)

            # Parse market data
            question = market.get("question", "Unknown")
            outcomes = market.get("outcomes", [])
            tokens_data = market.get("tokens", [])

            # Build token info list
            tokens = []
            for i, token_data in enumerate(tokens_data):
                token_info = TokenInfo(
                    token_id=token_data.get("token_id", ""),
                    outcome=outcomes[i] if i < len(outcomes) else "Unknown",
                )
                tokens.append(token_info)

            # Create metadata object
            metadata = MarketMetadata(
                condition_id=condition_id,
                question=question,
                tokens=tokens,
                end_date=market.get("end_date_iso"),
            )

            # Cache metadata for all tokens in this market
            with self._cache_lock:
                for token in tokens:
                    if token.token_id:
                        self._market_metadata[token.token_id] = metadata

                # Also update position outcome if we have this position
                if token_id in self._positions:
                    outcome = metadata.get_token_outcome(token_id)
                    if outcome:
                        self._positions[token_id].outcome = outcome
                        self._positions[token_id].question = question

            self.logger.debug(f"Cached metadata for market: {question[:50]}...")
            return question

        except Exception as e:
            self.logger.error(f"Failed to fetch market metadata for {token_id[:8]}: {e}")
            return f"Error loading market ({token_id[:8]}...)"

    def get_orders_snapshot(self) -> dict[str, dict]:
        """Get thread-safe snapshot of current orders.

        Returns:
            Dictionary mapping order_id to order data
        """
        with self._cache_lock:
            return self._orders.copy()

    def get_positions_snapshot(self) -> dict[str, Position]:
        """Get thread-safe snapshot of current positions.

        Returns:
            Dictionary mapping token_id to Position objects
        """
        with self._cache_lock:
            return self._positions.copy()

    def get_metadata_snapshot(self) -> dict[str, MarketMetadata]:
        """Get thread-safe snapshot of cached market metadata.

        Returns:
            Dictionary mapping token_id to MarketMetadata objects
        """
        with self._cache_lock:
            return self._market_metadata.copy()

    def get_last_update_time(self) -> tuple[Optional[datetime], Optional[datetime]]:
        """Get timestamps of last cache updates.

        Returns:
            Tuple of (orders_update_time, positions_update_time)
        """
        with self._cache_lock:
            return (self._last_orders_update, self._last_positions_update)

    def is_data_stale(self, max_age_seconds: int = 60) -> bool:
        """Check if cached data is too old.

        Args:
            max_age_seconds: Maximum acceptable cache age (default: 60)

        Returns:
            True if data is stale or not yet populated
        """
        with self._cache_lock:
            if not self._last_orders_update:
                return True
            age = (datetime.now() - self._last_orders_update).total_seconds()
            return age > max_age_seconds

    def is_running(self) -> bool:
        """Check if daemon is running.

        Returns:
            True if running
        """
        return self._running

    def get_stats(self) -> dict:
        """Get monitoring statistics.

        Returns:
            Dictionary with cache sizes and update times
        """
        with self._cache_lock:
            return {
                "orders_count": len(self._orders),
                "positions_count": len(self._positions),
                "metadata_count": len(self._market_metadata),
                "last_orders_update": self._last_orders_update,
                "last_positions_update": self._last_positions_update,
                "is_running": self._running,
                "poll_interval": self.poll_interval,
            }

    async def __aenter__(self):
        """Async context manager entry."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop()
