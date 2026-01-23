# Phase 1: Foundation - Documentation

**Version:** 1.0
**Completed:** December 15, 2025
**Status:** ✅ Complete

**Note:** This is an archived document; current code may differ from the Phase 1 snapshot described here.

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Components](#components)
4. [Usage Guide](#usage-guide)
5. [API Reference](#api-reference)
6. [Testing](#testing)
7. [Examples](#examples)

---

## Overview

Phase 1 establishes the foundational infrastructure for the Polymarket Order Management System. It provides the core building blocks needed for placing and monitoring individual orders on Polymarket.

### Goals Achieved

- ✅ Type-safe data models with Pydantic validation
- ✅ API client wrapper with automatic retry logic
- ✅ Single order execution with status monitoring
- ✅ Structured logging with JSON support
- ✅ Comprehensive test coverage (12 tests passing)

### Success Criteria Met

All Phase 1 success criteria from the implementation plan have been met:
- Place one order successfully
- Poll and detect when order is filled
- Log entire lifecycle to structured logs
- Handle basic API errors gracefully
- All code follows existing project patterns

---

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────┐
│              Phase 1 Architecture                │
├─────────────────────────────────────────────────┤
│                                                  │
│  ┌──────────────┐         ┌──────────────┐     │
│  │   Order      │────────▶│   Order      │     │
│  │   Models     │         │   Executor   │     │
│  └──────────────┘         └──────────────┘     │
│         │                        │              │
│         │                        ▼              │
│         │              ┌──────────────┐         │
│         └─────────────▶│  Polymarket  │         │
│                        │   Client     │         │
│                        └──────────────┘         │
│                               │                 │
│                               ▼                 │
│                      ┌──────────────┐           │
│                      │ py-clob-     │           │
│                      │ client       │           │
│                      └──────────────┘           │
│                               │                 │
│                               ▼                 │
│                      Polymarket CLOB API        │
└─────────────────────────────────────────────────┘
```

### Data Flow

1. **Create Order** - User creates Order object with validated parameters
2. **Initialize Client** - PolymarketClient wraps py-clob-client with config
3. **Execute Order** - OrderExecutor places order via client
4. **Monitor Status** - Executor polls order status until filled/timeout
5. **Log Events** - Structured logging captures entire lifecycle

---

## Components

### 1. Data Models (`models/`)

Type-safe Pydantic models representing orders, market conditions, and enums.

#### `models/enums.py`

**OrderSide**
- `BUY` - Buy side order
- `SELL` - Sell side order

**OrderStatus**
- `QUEUED` - Order created but not yet active
- `ACTIVE` - Order being executed
- `PARTIALLY_FILLED` - Some shares filled
- `COMPLETED` - All shares filled
- `CANCELLED` - Order cancelled
- `FAILED` - Order execution failed

**Urgency**
- `LOW` - Patient execution (for future phases)
- `MEDIUM` - Balanced execution
- `HIGH` - Aggressive execution (for future phases)

#### `models/order.py`

**StrategyParams**
Configuration for iceberg strategy (used in Phase 2+):
- `initial_tranche_size` - Size of first order chunk (default: 50)
- `min_tranche_size` - Minimum chunk size (default: 10)
- `max_tranche_size` - Maximum chunk size (default: 200)
- `tranche_randomization` - Randomization factor 0.0-1.0 (default: 0.2)

**Order**
Main order data model with:
- **Identification**: `order_id`, `market_id`, `token_id`
- **Parameters**: `side`, `total_size`, `target_price`, `max_price`, `min_price`
- **Execution**: `urgency`, `strategy_params`
- **State**: `status`, `filled_amount`, `remaining_amount`
- **Tracking**: `created_at`, `updated_at`, `adjustment_count`, `undercut_count`

Methods:
- `update_status(new_status)` - Update order status
- `record_fill(amount)` - Record shares filled
- `record_adjustment()` - Increment adjustment counter
- `record_undercut()` - Increment undercut counter

#### `models/market.py`

**MarketConditions**
Snapshot of market state:
- **Order Book**: `best_bid`, `best_ask`, `spread`, `bid_depth`, `ask_depth`
- **Position**: `our_position_in_queue`, `total_orders_at_price`
- **Competition**: `undercut_detected`, `undercut_margin`
- **Time**: `timestamp`

Properties:
- `mid_price` - Calculated mid-point between bid and ask

---

### 2. API Client (`api/`)

#### `api/polymarket_client.py`

Wrapper around `py-clob-client` with error handling and retry logic.

**Features:**
- Automatic API credential generation from private key
- Exponential backoff retry (3 attempts by default)
- Comprehensive error logging
- Support for all signature types (EOA, Email, Browser)

**Key Methods:**

**`place_order(token_id, price, size, side, order_type)`**
- Places order with retry logic
- Returns order response from API
- Retries up to `max_retries` times with exponential backoff

**`cancel_order(order_id)`**
- Cancels order with retry logic
- Returns cancellation response

**`get_order_status(order_id)`**
- Fetches current order status
- Returns order data from exchange

**`get_order_book(token_id)`**
- Fetches order book for token
- Returns bids and asks

---

### 3. Order Executor (`core/`)

#### `core/order_executor.py`

Executes and monitors single orders until filled or timeout.

**Configuration:**
- `poll_interval` - Seconds between status checks (default: 2.0)
- `timeout` - Maximum seconds to wait for fill (default: 60.0)

**Key Methods:**

**`execute_single_order(order, order_type)`**
Main execution loop:
1. Updates order status to ACTIVE
2. Places order on exchange
3. Monitors until filled or timeout
4. Records fills and updates status
5. Returns final order state

**Internal Methods:**
- `_extract_order_id(response)` - Parse order ID from API response
- `_monitor_order(order, exchange_order_id)` - Poll status until complete
- `_extract_filled_amount(status_response)` - Parse fill amount from status

---

### 4. Logging (`utils/`)

#### `utils/logger.py`

Enhanced logging with structured JSON support.

**JSONFormatter**
Custom formatter that outputs logs as JSON with:
- `timestamp` - ISO format timestamp
- `level` - Log level (INFO, WARNING, ERROR, etc.)
- `logger` - Logger name
- `message` - Human-readable message
- `order_id` - Order identifier (if present)
- `market_id` - Market identifier (if present)
- `event_type` - Event type (if present)
- `data` - Additional structured data
- `exception` - Exception traceback (if error)

**Functions:**

**`setup_logger(name, level, log_file, json_format)`**
Creates configured logger instance:
- `name` - Logger name (default: "polymarket")
- `level` - Log level (default: "INFO")
- `log_file` - Optional file path for file logging
- `json_format` - Use JSON formatting (default: False)

**`log_order_event(logger, event_type, order_id, message, market_id, extra_data)`**
Convenience function for logging order lifecycle events with structured data.

---

## Usage Guide

### Basic Usage

#### 1. Setup

```python
from config.settings import load_config
from utils.logger import setup_logger

# Load configuration
config = load_config()

# Setup logger
logger = setup_logger(
    name="my_app",
    level="INFO",
    log_file="logs/trading.log",
    json_format=False  # or True for JSON logs
)
```

#### 2. Initialize Client

```python
from api.polymarket_client import PolymarketClient

# Create client
client = PolymarketClient(
    config=config,
    logger=logger,
    max_retries=3
)
```

#### 3. Create an Order

```python
import uuid
from models.order import Order, StrategyParams
from models.enums import OrderSide, Urgency

# Create order
order = Order(
    order_id=f"order-{uuid.uuid4().hex[:8]}",
    market_id="your-market-id",
    token_id="your-token-id",
    side=OrderSide.BUY,
    total_size=100,
    target_price=0.45,
    max_price=0.50,
    min_price=0.40,
    urgency=Urgency.MEDIUM,
    strategy_params=StrategyParams(
        initial_tranche_size=50,
        min_tranche_size=10,
        max_tranche_size=100,
    )
)
```

#### 4. Execute Order

```python
from core.order_executor import OrderExecutor

# Create executor
executor = OrderExecutor(
    client=client,
    logger=logger,
    poll_interval=2.0,
    timeout=60.0
)

# Execute order
try:
    result = executor.execute_single_order(order)

    # Check result
    if result.status == OrderStatus.COMPLETED:
        print(f"✅ Order completed: {result.filled_amount} shares")
    elif result.status == OrderStatus.PARTIALLY_FILLED:
        print(f"⚠️  Partial fill: {result.filled_amount}/{result.total_size}")
    else:
        print(f"❌ Order failed: {result.status}")

except Exception as e:
    print(f"Error: {e}")
```

### Advanced Usage

#### Using JSON Logging

```python
# Setup JSON logger
logger = setup_logger(
    name="trading",
    level="INFO",
    log_file="logs/trading.json",
    json_format=True  # Enable JSON format
)

# Logs will be output as:
# {"timestamp": "2025-12-15T10:30:00", "level": "INFO", "logger": "trading", ...}
```

#### Logging Order Events

```python
from utils.logger import log_order_event

log_order_event(
    logger=logger,
    event_type="order_placed",
    order_id=order.order_id,
    message=f"Placed {order.side.value} order for {order.total_size} shares",
    market_id=order.market_id,
    extra_data={
        "price": order.target_price,
        "token_id": order.token_id,
    }
)
```

#### Handling Different Order Types

```python
from py_clob_client.clob_types import OrderType

# Good-Till-Cancelled (default)
result = executor.execute_single_order(order, OrderType.GTC)

# Fill-Or-Kill (must fill immediately)
result = executor.execute_single_order(order, OrderType.FOK)

# Good-Till-Date (expires at specific time)
result = executor.execute_single_order(order, OrderType.GTD)
```

---

## API Reference

### Order Model

```python
Order(
    order_id: str,           # Unique identifier
    market_id: str,          # Market/condition ID
    token_id: str,           # Token ID (YES/NO)
    side: OrderSide,         # BUY or SELL
    total_size: int,         # Total shares (>0)
    target_price: float,     # Target price (0.0-1.0)
    max_price: float,        # Max acceptable price (0.0-1.0)
    min_price: float,        # Min acceptable price (0.0-1.0)
    urgency: Urgency = MEDIUM,
    strategy_params: StrategyParams = StrategyParams(),
    status: OrderStatus = QUEUED,
    filled_amount: int = 0,
    remaining_amount: Optional[int] = None,  # Auto-set to total_size
    created_at: datetime = now(),
    updated_at: datetime = now(),
    adjustment_count: int = 0,
    undercut_count: int = 0,
)
```

**Validation Rules:**
- `total_size` must be > 0
- Prices must be between 0.0 and 1.0
- For BUY: `min_price <= target_price <= max_price`
- For SELL: `min_price <= target_price <= max_price`

### PolymarketClient

```python
PolymarketClient(
    config: PolymarketConfig,
    logger: Optional[logging.Logger] = None,
    max_retries: int = 3,
)

# Methods
.place_order(token_id, price, size, side, order_type=GTC) -> dict
.cancel_order(order_id) -> dict
.get_order_status(order_id) -> dict
.get_order_book(token_id) -> dict
```

### OrderExecutor

```python
OrderExecutor(
    client: PolymarketClient,
    logger: Optional[logging.Logger] = None,
    poll_interval: float = 2.0,
    timeout: float = 60.0,
)

# Methods
.execute_single_order(order, order_type=GTC) -> Order
```

---

## Testing

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_models.py -v

# Run with coverage
python -m pytest tests/ --cov=models --cov=api --cov=core
```

### Test Coverage

**`tests/test_enums.py` (3 tests)**
- Test OrderSide values
- Test OrderStatus values
- Test Urgency values

**`tests/test_models.py` (9 tests)**
- Test StrategyParams defaults and validation
- Test Order creation and validation
- Test Order price validation
- Test fill recording
- Test adjustment tracking
- Test undercut tracking
- Test MarketConditions creation
- Test mid_price calculation

### Writing Tests

Example test structure:

```python
def test_order_creation():
    """Test Order creation with required fields."""
    order = Order(
        order_id="test-123",
        market_id="market-456",
        token_id="token-789",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    assert order.order_id == "test-123"
    assert order.side == OrderSide.BUY
    assert order.total_size == 1000
    assert order.remaining_amount == 1000
    assert order.status == OrderStatus.QUEUED
```

---

## Examples

### Example 1: Simple Buy Order

```python
"""Execute a simple buy order."""

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.order_executor import OrderExecutor
from models.order import Order
from models.enums import OrderSide
from utils.logger import setup_logger
import uuid

# Setup
config = load_config()
logger = setup_logger(name="simple_buy", level="INFO")
client = PolymarketClient(config, logger)
executor = OrderExecutor(client, logger)

# Create order
order = Order(
    order_id=f"buy-{uuid.uuid4().hex[:8]}",
    market_id="your-market-id",
    token_id="your-token-id",
    side=OrderSide.BUY,
    total_size=50,
    target_price=0.45,
    max_price=0.50,
    min_price=0.40,
)

# Execute
result = executor.execute_single_order(order)
print(f"Status: {result.status}")
print(f"Filled: {result.filled_amount}/{result.total_size}")
```

### Example 2: Sell Order with Logging

```python
"""Execute sell order with detailed logging."""

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.order_executor import OrderExecutor
from models.order import Order
from models.enums import OrderSide
from utils.logger import setup_logger, log_order_event
import uuid

# Setup with JSON logging
config = load_config()
logger = setup_logger(
    name="sell_order",
    level="INFO",
    log_file="logs/sell_order.json",
    json_format=True  # JSON output
)

client = PolymarketClient(config, logger)
executor = OrderExecutor(client, logger, timeout=120.0)

# Create order
order = Order(
    order_id=f"sell-{uuid.uuid4().hex[:8]}",
    market_id="your-market-id",
    token_id="your-token-id",
    side=OrderSide.SELL,
    total_size=100,
    target_price=0.55,
    max_price=0.60,
    min_price=0.50,
)

# Log order creation
log_order_event(
    logger,
    "order_created",
    order.order_id,
    f"Created SELL order for {order.total_size} shares",
    market_id=order.market_id,
    extra_data={"price": order.target_price}
)

# Execute
try:
    result = executor.execute_single_order(order)

    # Log result
    log_order_event(
        logger,
        "execution_complete",
        order.order_id,
        f"Execution complete: {result.status}",
        market_id=order.market_id,
        extra_data={
            "filled": result.filled_amount,
            "total": result.total_size,
        }
    )

except Exception as e:
    log_order_event(
        logger,
        "execution_failed",
        order.order_id,
        f"Execution failed: {str(e)}",
        market_id=order.market_id,
        extra_data={"error": str(e)}
    )
```

### Example 3: Using the Demo Script

```bash
# Run the included demo
python examples/phase1_demo.py

# Expected output:
# 2025-12-15 10:30:00 - phase1_demo - INFO - === Phase 1 Demo: Single Order Execution ===
# 2025-12-15 10:30:00 - phase1_demo - INFO - Loading configuration...
# 2025-12-15 10:30:00 - phase1_demo - INFO - Configuration loaded successfully
# 2025-12-15 10:30:01 - phase1_demo - INFO - Initializing Polymarket client...
# ...
```

---

## Troubleshooting

### Common Issues

**Issue: "Private key validation failed"**
- Ensure `POLYMARKET_PRIVATE_KEY` is 64 hex characters without `0x` prefix
- Check `.env` file is properly loaded

**Issue: "Module not found" errors**
- Ensure you're running from project root
- Activate virtual environment: `source .venv/bin/activate`

**Issue: "Order placement fails"**
- Check logs for "API credentials generated successfully"
- Ensure sufficient balance for the order
- Check market_id and token_id are valid

**Issue: "Order timeout"**
- Increase timeout parameter: `OrderExecutor(client, logger, timeout=120.0)`
- Check if order was placed but not filled (check exchange directly)
- Verify market has liquidity

### Debug Logging

Enable debug logging for detailed output:

```python
logger = setup_logger(
    name="debug",
    level="DEBUG",  # More verbose
    log_file="logs/debug.log"
)
```

---

## Next Steps

Phase 1 provides the foundation. Next phases will add:

- **Phase 2**: Iceberg order splitting - break large orders into smaller tranches
- **Phase 3**: Market monitoring - real-time order book tracking
- **Phase 4**: Adaptive pricing - dynamic price adjustments based on competition
- **Phase 5**: Concurrent orders - manage multiple orders simultaneously
- **Phase 6**: Production hardening - WebSocket, persistence, CLI interface

---

## File Structure

```
polymarket-tools/
├── models/
│   ├── __init__.py
│   ├── enums.py              # OrderSide, OrderStatus, Urgency
│   ├── order.py              # Order, StrategyParams
│   └── market.py             # MarketConditions
├── api/
│   ├── __init__.py
│   └── polymarket_client.py  # API wrapper with retry logic
├── core/
│   ├── __init__.py
│   └── order_executor.py     # Single order execution
├── utils/
│   ├── __init__.py
│   └── logger.py             # Structured logging
├── examples/
│   └── phase1_demo.py        # Demo script
├── tests/
│   ├── __init__.py
│   ├── test_enums.py         # Enum tests (3)
│   └── test_models.py        # Model tests (9)
└── docs/
    └── phase1.md             # This file
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-15 | Initial Phase 1 documentation |

---

**Phase 1 Complete ✅** - Ready for Phase 2: Iceberg Strategy
