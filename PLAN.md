# Polymarket Position Management Service - Implementation Plan

## Overview

Semi-automated trading bot for Polymarket that maintains top-of-book positions while intelligently splitting orders to prevent trade detection.

## Requirements

1. **Auto Top-Bidder**: Automatically maintain best bid/ask position without crossing limit price
2. **Order Splitting**: Split large orders using SOTA algorithms (TWAP, VWAP, Iceberg, Randomized)
3. **Position Tracking**: Monitor current positions and P&L
4. **Risk Management**: Position size limits, daily loss limits, total exposure caps

## Technology Stack

- **Language**: Python 3.9+
- **SDK**: `py-clob-client` (official Polymarket Python client)
- **Blockchain**: Polygon (Chain ID: 137)
- **Exchange**: Polymarket CLOB (Centralized Limit Order Book)

## Architecture

### Project Structure

```
polymarket-position-manage/
├── config/
│   ├── settings.py          # Configuration (API, risk limits)
│   └── .env                 # Private keys, API credentials (gitignored)
├── core/
│   ├── client.py            # Polymarket client wrapper
│   ├── order_manager.py     # Order placement & cancellation
│   └── position_tracker.py  # Track positions & P&L
├── strategies/
│   ├── top_bidder.py        # Auto top-bidder logic
│   └── order_splitter.py    # Order splitting algorithms (TWAP/VWAP/Iceberg/Random)
├── risk/
│   └── limits.py            # Risk management checks
├── utils/
│   ├── logger.py            # Logging configuration
│   └── helpers.py           # Utility functions
├── main.py                  # Entry point
├── requirements.txt
├── README.md
└── PLAN.md                  # This file
```

## Core Components

### 1. Client Wrapper (`core/client.py`)

**Responsibilities:**
- Initialize `py-clob-client` with authentication
- Handle L1 (private key) and L2 (API key) authentication
- Derive/create API credentials automatically
- Wrapper methods for common operations
- Rate limit handling and retry logic

**Key Methods:**
```python
- get_order_book(token_id)      # Get current order book
- get_best_bid_ask(token_id)    # Get top of book
- place_limit_order(...)        # Place GTC limit order
- cancel_order(order_id)        # Cancel specific order
- get_open_orders()             # Get all open orders
- get_positions()               # Get current positions
```

### 2. Top Bidder Strategy (`strategies/top_bidder.py`)

**Logic:**
1. Poll order book every 2-5 seconds (or via WebSocket)
2. Check current best bid (for BUY) or best ask (for SELL)
3. If not at top:
   - Calculate price 1 tick better than current best
   - Ensure price doesn't cross limit price
   - Cancel existing order
   - Place new order at optimal price
4. If at top, monitor for being outbid

**Configuration:**
```python
{
    "token_id": "market_token_id",
    "side": "BUY",              # or "SELL"
    "limit_price": 0.55,        # Never pay more than this
    "shares_per_order": 100,    # Size of each order
    "poll_interval": 3,         # Seconds between checks
}
```

### 3. Order Splitting (`strategies/order_splitter.py`)

Four SOTA algorithms to prevent trade detection:

#### TWAP (Time-Weighted Average Price)
- Split total shares into equal-sized orders
- Execute at regular intervals over time window
- Example: 1000 shares over 60min = 10 orders of 100 shares every 6 minutes

#### VWAP (Volume-Weighted Average Price)
- Size orders based on historical volume patterns
- Larger orders during high-volume periods
- Smaller orders during low-volume periods

#### Iceberg Orders
- Show only small portion of total order
- As filled, reveal next chunk
- Hides true order size from market

#### Randomized
- Random time intervals between orders (within constraints)
- Random order sizes (within min/max bounds)
- Makes patterns harder to detect

**Configuration:**
```python
{
    "strategy": "TWAP",         # TWAP, VWAP, ICEBERG, RANDOM
    "total_shares": 1000,       # Total amount to trade
    "time_window_minutes": 60,  # Complete execution within this time
    "min_order_size": 10,       # Minimum shares per order
    "max_order_size": 100,      # Maximum shares per order
}
```

### 4. Order Manager (`core/order_manager.py`)

**Responsibilities:**
- Queue orders from splitter
- Execute orders via client
- Track order lifecycle: pending → open → filled/cancelled
- Handle partial fills
- Retry failed orders
- Coordinate cancel-and-replace for top bidder

**State Tracking:**
```python
{
    "order_id": "uuid",
    "status": "pending|open|filled|cancelled|failed",
    "token_id": "...",
    "side": "BUY|SELL",
    "price": 0.55,
    "size": 100,
    "filled": 0,              # Shares filled so far
    "timestamp": "...",
}
```

### 5. Position Tracker (`core/position_tracker.py`)

**Metrics:**
- Current positions (shares held per market)
- Average entry price
- Current market price
- Unrealized P&L: (current_price - avg_entry) * shares
- Realized P&L: Sum of closed position profits
- Total exposure: Sum of position values
- Win rate, average win/loss, etc.

**Data Sources:**
- Filled orders from order manager
- Current positions via `get_trades()` API
- Live prices via `get_price()` API

### 6. Risk Manager (`risk/limits.py`)

**Pre-Trade Checks:**
1. Position size limit: Reject if position would exceed max shares per market
2. Total exposure limit: Reject if total capital deployed exceeds limit
3. Daily loss limit: Stop trading if daily loss exceeds threshold
4. Limit price validation: Reject orders crossing limit price

**Emergency Controls:**
- `cancel_all_orders()`: Cancel everything immediately
- `emergency_stop()`: Cancel all + prevent new orders
- Alert/notification system for limit breaches

**Configuration:**
```python
{
    "max_position_size": 5000,      # Max shares per market
    "max_total_exposure": 10000,    # Max total USD deployed
    "max_daily_loss": 500,          # Max USD loss per day
    "max_order_size": 100,          # Max shares per single order
}
```

## Polymarket API Details

### Authentication

**Two-Level System:**

1. **L1 (Level 1) - Private Key Auth**
   - Uses Ethereum private key
   - Signs EIP-712 messages
   - Only for creating/deriving API keys
   - Should be used sparingly

2. **L2 (Level 2) - API Key Auth**
   - Derived from L1 signature
   - Components: API key, passphrase, secret
   - Used for all trading operations
   - More secure for day-to-day use

**Setup Code:**
```python
from py_clob_client.client import ClobClient

client = ClobClient(
    host="https://clob.polymarket.com",
    key="<private-key>",
    chain_id=137,
    signature_type=0  # 0=EOA, 1=Email, 2=Browser wallet
)

# Automatically creates or derives API credentials
client.create_or_derive_api_creds()
```

### Key API Endpoints

**Market Data (Public):**
- `get_order_book(token_id)` - Full order book
- `get_price(token_id, side)` - Best bid/ask
- `get_midpoint(token_id)` - Mid-market price
- `get_simplified_markets()` - All markets
- `get_last_trade_price(token_id)` - Most recent trade

**Order Management (Requires L2):**
- `create_order(OrderArgs)` - Create signed limit order
- `post_order(signed_order, OrderType.GTC)` - Submit to exchange
- `get_orders(OpenOrderParams())` - Get open orders
- `cancel(order_id)` - Cancel specific order
- `cancel_all()` - Cancel all orders

**Position Data (Requires L2):**
- `get_trades()` - Trade history

### Rate Limits

- General endpoints: 5,000 requests / 10 seconds
- Market data: 200 requests / 10 seconds
- POST `/order`: 2,400 / 10s (burst) OR 24,000 / 10 min (sustained)
- DELETE `/order`: 2,400 / 10s (burst) OR 24,000 / 10 min (sustained)
- `/cancel-all`: 200 / 10s (burst) OR 3,000 / 10 min (sustained)

### Order Types

- **GTC (Good-Til-Cancelled)**: Active until filled or cancelled
- **GTD (Good-Til-Day)**: Active until specific date
- **FOK (Fill-or-Kill)**: Execute completely immediately or cancel

### WebSocket Support

**Market Channel (Public):**
- Real-time order book updates
- Price changes
- Last trade updates

**User Channel (Private):**
- Order status changes
- Trade executions

**Note:** `py-clob-client` may not have built-in WebSocket support. May need custom implementation or community library.

## Implementation Steps

### Phase 1: Setup & Basic Order Flow

1. **Environment Setup**
   ```bash
   pip install py-clob-client python-dotenv
   ```

2. **Credential Management**
   - Create `.env` file for private key
   - Implement settings.py with configuration classes
   - Test authentication and API credential derivation

3. **Client Wrapper**
   - Wrap `py-clob-client` with our interface
   - Add error handling and retry logic
   - Test basic operations (get markets, prices, order book)

4. **Order Manager**
   - Implement order state tracking
   - Create place/cancel/modify functions
   - Test with small orders on real market

### Phase 2: Top Bidder Strategy

1. **Order Book Monitoring**
   - Poll order book at intervals
   - Extract best bid/ask
   - Calculate optimal price (1 tick better)

2. **Cancel-and-Replace Logic**
   - Cancel existing order
   - Place new order at better price
   - Handle race conditions (order filled before cancel)

3. **Limit Price Enforcement**
   - Check against configured limit
   - Never cross limit regardless of market moves
   - Stop strategy if limit becomes unreachable

### Phase 3: Order Splitting

1. **TWAP Implementation**
   - Calculate order sizes and timings
   - Schedule orders over time window
   - Integrate with order manager

2. **Additional Strategies**
   - Implement VWAP (needs historical volume data)
   - Implement Iceberg (progressive reveal)
   - Implement Randomized (random timing/size)

3. **Strategy Coordination**
   - Combine top-bidder with order splitter
   - Feed split orders to top-bidder strategy
   - Ensure smooth handoff between components

### Phase 4: Position & Risk Management

1. **Position Tracker**
   - Query trades via API
   - Calculate current positions
   - Compute P&L metrics

2. **Risk Limits**
   - Pre-trade validation checks
   - Position size enforcement
   - Daily loss tracking

3. **Emergency Controls**
   - Cancel-all functionality
   - Emergency stop button
   - Alerts for limit breaches

### Phase 5: Integration & Testing

1. **Wire Components Together**
   - Connect all modules in main.py
   - Add configuration loading
   - Implement clean startup/shutdown

2. **Logging & Monitoring**
   - Structured logging throughout
   - Performance metrics
   - Trade/P&L reporting

3. **Testing Strategy**
   - Start with small positions
   - Test each strategy independently
   - Monitor for issues over extended periods
   - Gradually increase position sizes

## Configuration Example

```python
# config/settings.py

POLYMARKET_CONFIG = {
    "host": "https://clob.polymarket.com",
    "chain_id": 137,
    "signature_type": 0,  # EOA
}

STRATEGY_CONFIG = {
    "token_id": "21742633143463906290569050155826241533067272736897614950488156847949938836455",
    "side": "BUY",
    "limit_price": 0.55,
    "total_shares": 1000,

    # Order splitting
    "splitting_strategy": "TWAP",  # TWAP, VWAP, ICEBERG, RANDOM
    "time_window_minutes": 60,
    "min_order_size": 10,
    "max_order_size": 100,

    # Top bidder
    "poll_interval": 3,  # seconds
    "enable_top_bidder": True,
}

RISK_LIMITS = {
    "max_position_size": 5000,
    "max_total_exposure": 10000,
    "max_daily_loss": 500,
    "max_order_size": 100,
}

LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file": "logs/trading.log",
}
```

## Security Considerations

1. **Private Key Storage**
   - Store in `.env` file (add to `.gitignore`)
   - Never log or print private keys
   - Use environment variables in production

2. **API Credentials**
   - Derive L2 credentials programmatically
   - Don't hardcode API keys
   - Rotate keys periodically

3. **Code Security**
   - Validate all inputs
   - Use parameterized queries if using databases
   - Sanitize log output (no sensitive data)

4. **Operational Security**
   - Start with small positions
   - Test thoroughly before scaling
   - Monitor for unexpected behavior
   - Have kill switch ready

## Next Steps

1. Set up Python environment and install dependencies
2. Create project structure with all directories
3. Implement authentication and test API connection
4. Build client wrapper with basic order operations
5. Implement top-bidder strategy
6. Add order splitting algorithms
7. Integrate risk management
8. Test end-to-end on small positions

## Resources

- **Polymarket Docs**: https://docs.polymarket.com/
- **py-clob-client GitHub**: https://github.com/Polymarket/py-clob-client
- **Polygon Network**: https://polygon.technology/
- **Trading Agent Examples**: https://github.com/Polymarket/agents

## Notes

- Trading is off-chain (no gas fees per trade)
- Settlement happens on Polygon (requires gas)
- Rate limits are generous for most strategies
- Consider premium tier ($99/mo) for higher limits and historical data
- WebSocket integration can reduce latency vs polling
