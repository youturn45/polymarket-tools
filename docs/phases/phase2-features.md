# Phase 3 (Revised): Advanced Order Management System

**Version:** 2.0 (Revised)
**Date:** 2025-12-29
**Supersedes:** Original Phase 3 plan in IMPLEMENTATION_PLAN.md

**Note:** This is an archived plan; current implementation may differ from the design described here.

---

## Overview

Phase 3 (Revised) combines the original market monitoring features with a complete order management daemon, micro-price based order adjustment, strategy pattern, and Kelly criterion position sizing.

**This phase integrates:**
- Original Phase 3: Market Monitoring
- Original Phase 4: Adaptive Pricing
- Original Phase 5 (partial): Order Queue System
- New: Micro-price calculation and monitoring
- New: Kelly criterion position sizing

---

## Goals

1. **Daemon Infrastructure**: Long-running process with order queue
2. **Market Monitoring**: Real-time order book tracking and micro-price calculation
3. **Adaptive Order Management**: Automatically adjust orders based on market conditions
4. **Strategy Pattern**: Support multiple order execution strategies
5. **Kelly Criterion**: Intelligent position sizing based on edge

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   Order Management Daemon                    │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │ Order Queue  │────────▶│   Worker     │                  │
│  │  (asyncio)   │         │   Pool       │                  │
│  └──────────────┘         └──────────────┘                  │
│         ▲                        │                           │
│         │                        ▼                           │
│  ┌──────────────┐         ┌──────────────┐                  │
│  │  API/CLI     │         │  Strategy    │                  │
│  │  Interface   │         │   Router     │                  │
│  └──────────────┘         └──────────────┘                  │
│                                  │                           │
│         ┌────────────────────────┴─────────────┐            │
│         ▼                        ▼              ▼            │
│  ┌──────────────┐      ┌──────────────┐  ┌──────────────┐  │
│  │   Iceberg    │      │ Micro-Price  │  │    Kelly     │  │
│  │   Strategy   │      │   Strategy   │  │   Strategy   │  │
│  └──────────────┘      └──────────────┘  └──────────────┘  │
│         │                        │              │            │
│         └────────────────────────┴──────────────┘            │
│                        ▼                                     │
│              ┌──────────────────┐                           │
│              │ Market Monitor   │                           │
│              │ (Order Book +    │                           │
│              │  Micro-Price)    │                           │
│              └──────────────────┘                           │
│                        ▼                                     │
│              ┌──────────────────┐                           │
│              │ Order Executor   │                           │
│              └──────────────────┘                           │
│                        ▼                                     │
│                Polymarket CLOB API                          │
└─────────────────────────────────────────────────────────────┘
```

---

## Phase 3 Components

### 3.1 Order Queue & Daemon (Core Infrastructure)

**File:** `core/order_daemon.py`

**Purpose:** Long-running background process managing order lifecycle

**Features:**
- `asyncio.Queue` for thread-safe order submission
- Background worker coroutines processing orders
- Order state management (QUEUED → ACTIVE → COMPLETED/CANCELLED)
- Graceful shutdown handling
- Health check endpoint

**Key Classes:**
```python
class OrderDaemon:
    """Main daemon managing order lifecycle."""

    def __init__(self, config, client, logger):
        self.order_queue = asyncio.Queue()
        self.active_orders = {}  # order_id -> Order
        self.workers = []
        self.running = False

    async def submit_order(self, order_request) -> str:
        """Add order to queue, return order_id immediately."""

    async def cancel_order(self, order_id) -> bool:
        """Request cancellation of active order."""

    async def get_order_status(self, order_id) -> dict:
        """Get current status of order."""

    async def start(self, num_workers=3):
        """Start daemon with worker pool."""

    async def stop(self):
        """Graceful shutdown."""
```

**File:** `models/order_request.py`

**Purpose:** Define order submission format

```python
class OrderRequest(BaseModel):
    """Request to create and execute an order."""

    market_id: str
    token_id: str
    side: OrderSide

    # Strategy selection
    strategy_type: StrategyType  # ICEBERG, MICRO_PRICE, KELLY

    # Size specification (depends on strategy)
    total_size: Optional[int] = None  # For iceberg/micro-price
    kelly_params: Optional[KellyParams] = None  # For Kelly

    # Price parameters
    target_price: Optional[float] = None
    max_price: float
    min_price: float

    # Strategy-specific params
    iceberg_params: Optional[StrategyParams] = None
    micro_price_params: Optional[MicroPriceParams] = None

    urgency: Urgency = Urgency.MEDIUM
```

---

### 3.2 Market Monitor with Micro-Price

**File:** `core/market_monitor.py`

**Purpose:** Real-time market data tracking

**Features:**
- Fetch order book via API
- Calculate best bid/ask
- Calculate spread and depth
- **NEW: Calculate micro-price**
- Cache market snapshots
- Async polling loop

**Key Classes:**
```python
class MarketMonitor:
    """Monitors market conditions in real-time."""

    def __init__(self, client, poll_interval=2.0):
        self.client = client
        self.poll_interval = poll_interval
        self.market_cache = {}  # token_id -> MarketSnapshot

    async def start_monitoring(self, token_id: str):
        """Begin monitoring a specific market."""

    async def stop_monitoring(self, token_id: str):
        """Stop monitoring a market."""

    def get_snapshot(self, token_id: str) -> MarketSnapshot:
        """Get latest market snapshot."""

    async def _poll_market(self, token_id: str):
        """Background polling loop for a market."""

class MicroPriceCalculator:
    """Calculates micro-price from order book."""

    def calculate_micro_price(self, order_book: dict) -> float:
        """
        Calculate micro-price (fair value) from order book.

        Micro-price = (best_bid * ask_size + best_ask * bid_size) /
                      (bid_size + ask_size)

        This weighs the mid-price by available liquidity.
        """

    def calculate_threshold_bands(
        self,
        micro_price: float,
        threshold_bps: int = 50
    ) -> tuple[float, float]:
        """Calculate acceptable price bands around micro-price."""
```

**File:** `models/market.py` (extend existing)

**Add:**
```python
class MarketSnapshot(BaseModel):
    """Snapshot of market state at a point in time."""

    token_id: str
    timestamp: datetime

    # Order book
    best_bid: float
    best_ask: float
    spread: float
    bid_depth: int  # Size at best bid
    ask_depth: int  # Size at best ask

    # Micro-price
    micro_price: float
    micro_price_upper_band: float  # micro + threshold
    micro_price_lower_band: float  # micro - threshold

    # Full book (top N levels)
    bids: list[tuple[float, int]]  # [(price, size), ...]
    asks: list[tuple[float, int]]

    # Our position
    our_orders: list[dict]  # Our active orders in this market
```

---

### 3.3 Micro-Price Strategy

**File:** `strategies/micro_price.py`

**Purpose:** Place and maintain orders near micro-price

**Features:**
- Monitor order position relative to micro-price
- Detect when order is outside threshold bands
- Cancel and replace orders that drift too far
- Detect overly aggressive orders (too far ahead of competition)
- Adjust orders to stay competitive

**Key Classes:**
```python
class MicroPriceParams(BaseModel):
    """Parameters for micro-price strategy."""

    threshold_bps: int = 50  # Basis points from micro-price
    check_interval: float = 2.0  # How often to check
    max_adjustments: int = 10  # Max replacements per order
    aggression_limit_bps: int = 100  # Max distance ahead of other orders

class MicroPriceStrategy:
    """Maintains order near micro-price."""

    def __init__(
        self,
        params: MicroPriceParams,
        monitor: MarketMonitor,
        client: PolymarketClient
    ):
        self.params = params
        self.monitor = monitor
        self.client = client

    async def execute_order(self, order: Order) -> Order:
        """Execute order with micro-price monitoring."""

    async def _monitor_and_adjust(
        self,
        order: Order,
        exchange_order_id: str
    ):
        """
        Monitor order and replace if:
        1. Outside micro-price threshold bands
        2. Too aggressive (way ahead of other orders)
        """

    async def _should_replace_order(
        self,
        order: Order,
        snapshot: MarketSnapshot
    ) -> tuple[bool, str, float]:
        """
        Check if order needs replacement.

        Returns: (should_replace, reason, new_price)
        """

    async def _replace_order(
        self,
        old_order_id: str,
        order: Order,
        new_price: float
    ) -> str:
        """Cancel old order and place new one."""
```

---

### 3.4 Strategy Router

**File:** `strategies/router.py`

**Purpose:** Route orders to appropriate strategy

**Features:**
- Factory pattern for strategy selection
- Validate strategy parameters
- Extensible for new strategies

```python
class StrategyType(str, Enum):
    """Available order execution strategies."""
    ICEBERG = "iceberg"
    MICRO_PRICE = "micro_price"
    KELLY = "kelly"

class StrategyRouter:
    """Routes orders to appropriate execution strategy."""

    def __init__(
        self,
        client: PolymarketClient,
        monitor: MarketMonitor,
        logger: logging.Logger
    ):
        self.client = client
        self.monitor = monitor
        self.logger = logger

    async def execute_order(self, request: OrderRequest) -> Order:
        """Route order to appropriate strategy and execute."""

        # Convert request to Order
        order = self._create_order_from_request(request)

        # Select strategy
        if request.strategy_type == StrategyType.ICEBERG:
            from strategies.iceberg import IcebergStrategy
            strategy = IcebergStrategy(request.iceberg_params)
            return await strategy.execute_order(order)

        elif request.strategy_type == StrategyType.MICRO_PRICE:
            from strategies.micro_price import MicroPriceStrategy
            strategy = MicroPriceStrategy(
                request.micro_price_params,
                self.monitor,
                self.client
            )
            return await strategy.execute_order(order)

        elif request.strategy_type == StrategyType.KELLY:
            from strategies.kelly import KellyStrategy
            strategy = KellyStrategy(
                request.kelly_params,
                self.monitor,
                self.client
            )
            return await strategy.execute_order(order)

        else:
            raise ValueError(f"Unknown strategy: {request.strategy_type}")
```

---

### 3.5 Kelly Criterion Strategy

**File:** `strategies/kelly.py`

**Purpose:** Position sizing using Kelly criterion

**Features:**
- Calculate optimal position size based on edge
- Use Kelly formula: f* = (bp - q) / b
- Dynamically recalculate as prices change
- Inherit micro-price strategy for execution

**Key Classes:**
```python
class KellyParams(BaseModel):
    """Parameters for Kelly criterion strategy."""

    win_probability: float = Field(ge=0.0, le=1.0)  # User's edge estimate
    kelly_fraction: float = Field(default=0.25, ge=0.0, le=1.0)  # Fractional Kelly
    max_position_size: int = Field(gt=0)  # Hard cap on position
    recalculate_interval: float = 5.0  # Recalc every N seconds

    # Inherit micro-price params for execution
    micro_price_params: MicroPriceParams = Field(default_factory=MicroPriceParams)

class KellyStrategy:
    """
    Kelly criterion position sizing with dynamic recalculation.

    Kelly formula: f* = (bp - q) / b
    Where:
      f* = fraction of bankroll to bet
      b = odds received (decimal_odds - 1)
      p = probability of winning
      q = probability of losing (1 - p)

    For prediction markets:
      b = (1 / current_price) - 1

    Example:
      Current price: 0.40 (40%)
      Win probability: 0.60 (60%)

      b = (1/0.40) - 1 = 1.5
      f* = (1.5 * 0.60 - 0.40) / 1.5 = 0.47

      Bet 47% of bankroll (or fractional Kelly: 0.25 * 47% = 11.75%)
    """

    def __init__(
        self,
        params: KellyParams,
        monitor: MarketMonitor,
        client: PolymarketClient
    ):
        self.params = params
        self.monitor = monitor
        self.client = client

    async def execute_order(self, order: Order) -> Order:
        """Execute order with Kelly sizing and micro-price execution."""

    def calculate_kelly_size(
        self,
        current_price: float,
        bankroll: int
    ) -> int:
        """
        Calculate optimal position size using Kelly criterion.

        Args:
            current_price: Market price (0.0 to 1.0)
            bankroll: Available capital

        Returns:
            Optimal position size in shares
        """
        p = self.params.win_probability
        q = 1 - p

        # Odds received on winning bet
        b = (1 / current_price) - 1

        # Full Kelly
        f_star = (b * p - q) / b

        # Apply fractional Kelly for safety
        f_star = f_star * self.params.kelly_fraction

        # Clamp to [0, 1]
        f_star = max(0, min(1, f_star))

        # Convert to shares
        position_size = int(bankroll * f_star / current_price)

        # Apply max limit
        position_size = min(position_size, self.params.max_position_size)

        return position_size

    async def _monitor_and_recalculate(self, order: Order):
        """
        Monitor market and recalculate position size as price changes.

        If new Kelly size is significantly different, cancel and replace
        with new size.
        """
```

---

### 3.6 Worker Pool

**File:** `core/order_worker.py`

**Purpose:** Process orders from queue asynchronously

```python
class OrderWorker:
    """Worker coroutine processing orders from queue."""

    def __init__(
        self,
        worker_id: int,
        order_queue: asyncio.Queue,
        router: StrategyRouter,
        daemon: 'OrderDaemon',
        logger: logging.Logger
    ):
        self.worker_id = worker_id
        self.order_queue = order_queue
        self.router = router
        self.daemon = daemon
        self.logger = logger

    async def run(self):
        """Main worker loop."""
        while True:
            try:
                # Get order from queue
                request = await self.order_queue.get()

                # Process order
                await self._process_order(request)

                # Mark task done
                self.order_queue.task_done()

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Worker {self.worker_id} error: {e}")

    async def _process_order(self, request: OrderRequest):
        """Execute order using appropriate strategy."""
```

---

## Implementation Order

### Step 1: Basic Infrastructure (Week 1)
1. ✅ `models/order_request.py` - Order request format
2. ✅ `strategies/router.py` - Strategy routing
3. ✅ `core/order_daemon.py` - Basic daemon (no workers yet)
4. ✅ Tests for models and routing

### Step 2: Market Monitoring (Week 1-2)
1. ✅ `core/market_monitor.py` - Order book fetching
2. ✅ `models/market.py` - Market snapshot model
3. ✅ Micro-price calculation
4. ✅ Tests for market monitoring

### Step 3: Micro-Price Strategy (Week 2)
1. ✅ `strategies/micro_price.py` - Implementation
2. ✅ Order replacement logic
3. ✅ Aggression detection
4. ✅ Integration with daemon
5. ✅ Tests for micro-price strategy

### Step 4: Kelly Criterion (Week 2-3)
1. ✅ `strategies/kelly.py` - Implementation
2. ✅ Kelly calculation logic
3. ✅ Dynamic recalculation
4. ✅ Integration with micro-price
5. ✅ Tests for Kelly strategy

### Step 5: Worker Pool & Integration (Week 3)
1. ✅ `core/order_worker.py` - Worker implementation
2. ✅ Complete daemon with workers
3. ✅ Async coordination
4. ✅ Integration tests

### Step 6: CLI/API Interface (Week 3)
1. ✅ CLI commands for daemon control
2. ✅ Submit/cancel/status commands
3. ✅ Demo scripts
4. ✅ End-to-end tests

---

## Success Criteria

**Infrastructure:**
- ✅ Daemon runs continuously
- ✅ Order queue accepts submissions
- ✅ Workers process orders concurrently
- ✅ Graceful shutdown works

**Market Monitoring:**
- ✅ Real-time order book tracking
- ✅ Accurate micro-price calculation
- ✅ Market snapshots cached correctly

**Micro-Price Strategy:**
- ✅ Orders stay within threshold bands
- ✅ Detects out-of-band orders
- ✅ Replaces orders correctly
- ✅ Detects overly aggressive orders
- ✅ Max adjustments limit respected

**Kelly Strategy:**
- ✅ Correct Kelly calculation
- ✅ Position sizes make sense
- ✅ Recalculates on price changes
- ✅ Inherits micro-price execution

**Overall:**
- ✅ Multiple strategies work concurrently
- ✅ No race conditions or deadlocks
- ✅ Comprehensive logging
- ✅ All tests passing

---

## File Structure

```
polymarket-tools/
├── core/
│   ├── order_daemon.py          # Main daemon
│   ├── order_worker.py          # Worker pool
│   ├── market_monitor.py        # Market monitoring
│   ├── order_executor.py        # Existing (extend for async)
│   └── fill_tracker.py          # Existing
├── models/
│   ├── order_request.py         # Order submission format
│   ├── market.py                # Market snapshot (extend)
│   └── order.py                 # Existing
├── strategies/
│   ├── router.py                # Strategy routing
│   ├── iceberg.py               # Existing (adapt for async)
│   ├── micro_price.py           # Micro-price strategy
│   └── kelly.py                 # Kelly criterion
├── cli/
│   ├── daemon_commands.py       # Daemon control CLI
│   └── order_commands.py        # Order submission CLI
├── examples/
│   ├── phase3_daemon_demo.py    # Daemon demo
│   ├── phase3_micro_price_demo.py
│   └── phase3_kelly_demo.py
└── tests/
    ├── test_daemon.py
    ├── test_market_monitor.py
    ├── test_micro_price.py
    ├── test_kelly.py
    └── test_integration.py
```

---

## Example Usage

### Submit Micro-Price Order
```python
from core.order_daemon import OrderDaemon
from models.order_request import OrderRequest
from strategies.micro_price import MicroPriceParams

# Start daemon
daemon = OrderDaemon(config, client, logger)
await daemon.start(num_workers=3)

# Submit micro-price order
request = OrderRequest(
    market_id="market-123",
    token_id="token-456",
    side=OrderSide.BUY,
    strategy_type=StrategyType.MICRO_PRICE,
    total_size=1000,
    max_price=0.55,
    min_price=0.45,
    micro_price_params=MicroPriceParams(
        threshold_bps=50,  # ±0.5%
        check_interval=2.0,
        max_adjustments=10,
        aggression_limit_bps=100,
    )
)

order_id = await daemon.submit_order(request)
print(f"Order submitted: {order_id}")

# Check status
status = await daemon.get_order_status(order_id)
print(f"Status: {status}")
```

### Submit Kelly Order
```python
request = OrderRequest(
    market_id="market-123",
    token_id="token-456",
    side=OrderSide.BUY,
    strategy_type=StrategyType.KELLY,
    max_price=0.60,
    min_price=0.40,
    kelly_params=KellyParams(
        win_probability=0.65,  # I think it's 65% likely
        kelly_fraction=0.25,   # Use 25% Kelly for safety
        max_position_size=5000,
        recalculate_interval=5.0,
        micro_price_params=MicroPriceParams(
            threshold_bps=50
        )
    )
)

order_id = await daemon.submit_order(request)
```

---

## Testing Strategy

**Unit Tests:**
- Kelly calculation with various inputs
- Micro-price calculation from order books
- Order replacement logic
- Threshold band calculations

**Integration Tests:**
- Daemon + queue + workers
- Market monitor polling
- Strategy routing
- Order lifecycle

**End-to-End Tests:**
- Submit order → execute → monitor → adjust → complete
- Multiple concurrent orders
- Kelly recalculation on price change
- Graceful shutdown with active orders

---

## Notes

1. **Async Everything:** All execution is async for concurrency
2. **Micro-Price is Key:** Both micro-price and Kelly use it for execution
3. **Strategy Pattern:** Easy to add new strategies (e.g., VWAP, TWAP)
4. **Kelly Safety:** Use fractional Kelly (25% recommended) to avoid over-betting
5. **Monitoring Overhead:** Each active order spawns a monitoring task
6. **Graceful Degradation:** If market monitor fails, fall back to last known snapshot

---

## Next: Phase 4

After Phase 3, we can add:
- **Phase 4:** WebSocket streaming (replace polling)
- **Phase 5:** State persistence (database)
- **Phase 6:** Production hardening (monitoring, alerts, safety checks)
