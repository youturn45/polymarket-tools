# Order Monitoring Examples

This directory contains practical examples demonstrating the order monitoring system for Polymarket trading.

## Examples Overview

**Example 1:** Portfolio and market monitoring
**Example 2:** Order placement with fill tracking
**Example 3:** Kelly-sized orders with micro-price and auto-replacement

### Example 1: Run Portfolio and Market Monitors

**File:** `scripts/examples/example1_run_monitors.py`

Demonstrates how to run both the PortfolioMonitor (for tracking all orders and positions) and MarketMonitor (for tracking specific market conditions) together in a real-time monitoring system.

**Features:**
- Continuous portfolio monitoring with configurable poll interval
- Real-time position tracking with P&L
- Market snapshot with order book depth (top 5 levels)
- Micro-price calculation (depth-weighted fair value)
- Competitive price analysis for your orders
- Auto-refresh display at configurable intervals

**Usage:**

```bash
# Monitor portfolio only
python scripts/examples/example1_run_monitors.py

# Monitor portfolio + specific market
python scripts/examples/example1_run_monitors.py --token-id <token_id>

# Custom intervals
python scripts/examples/example1_run_monitors.py \
    --token-id <token_id> \
    --poll-interval 5.0 \
    --display-interval 15.0
```

**Arguments:**
- `--token-id`: Token ID to monitor (optional - portfolio-only mode if not provided)
- `--poll-interval`: Portfolio monitor poll interval in seconds (default: 10.0)
- `--display-interval`: Display update interval in seconds (default: 30.0)

**Example Output:**

```
================================================================================
PORTFOLIO STATUS
================================================================================
Monitor Running: True
Poll Interval: 10.0s
Last Update: 14:23:45

OPEN ORDERS (2)
--------------------------------------------------------------------------------
  Order ID: 0x7f3a2b1c...
  Market: Will Donald Trump win the 2024 Presidential Election?
  Side: BUY | Price: $0.4800 | Size: 500
  Filled: 150 (30.0%)

  Order ID: 0x9e4c8d2a...
  Market: Will Bitcoin reach $100,000 by end of 2024?
  Side: SELL | Price: $0.6500 | Size: 200
  Filled: 0 (0.0%)

POSITIONS (1)
--------------------------------------------------------------------------------
  Token: 214858393...
  Market: Will Donald Trump win the 2024 Presidential Election?
  Outcome: Yes
  Shares: 1250.00
  Avg Entry: $0.4550 | Current: $0.4800
  P&L: $31.25

================================================================================
MARKET SNAPSHOT
================================================================================
Token ID: 214858393...
Timestamp: 14:23:45

PRICES
  Best Bid: $0.4750 (depth: 1,200)
  Best Ask: $0.4850 (depth: 800)
  Spread: $0.0100 (100.0 bps)

MICRO-PRICE (Depth-Weighted Fair Value)
  Fair Value: $0.4810
  Lower Band: $0.4786
  Upper Band: $0.4834

ORDER BOOK (Top 5 Levels)
  BIDS                    |  ASKS
  Price      Size         |  Price      Size
  --------------------------------------------------
  $0.4750      1,200  |  $0.4850        800
  $0.4700        450  |  $0.4900      1,100
  $0.4650        320  |  $0.4950        600
  $0.4600        890  |  $0.5000      2,300
  $0.4550        150  |  $0.5050        420

OUR ORDERS (1)
  BUY    500 @ $0.4800 - ✓ COMPETITIVE
```

---

### Example 2: Place and Track Order Until Filled

**File:** `scripts/examples/example2_track_order.py`

Demonstrates how to place an order and track it in real-time until it's filled or cancelled, with detailed progress updates and fill tracking.

**Features:**
- Place a new order with competitive price analysis
- Track order fills in real-time with progress bar
- Calculate volume-weighted average fill price
- Display market context during tracking (bid/ask/fair value)
- Record fill details across multiple tranches
- Comprehensive final summary with fill breakdown
- Option to track existing orders without placing new ones

**Usage:**

```bash
# Place and track a new order
python scripts/examples/example2_track_order.py \
    --token-id <token_id> \
    --side BUY \
    --price 0.50 \
    --size 100

# Track existing order
python scripts/examples/example2_track_order.py \
    --token-id <token_id> \
    --side BUY \
    --price 0.50 \
    --size 100 \
    --skip-place <order_id>

# Custom tracking parameters
python scripts/examples/example2_track_order.py \
    --token-id <token_id> \
    --side SELL \
    --price 0.65 \
    --size 500 \
    --check-interval 3.0 \
    --timeout 600
```

**Arguments:**
- `--token-id`: Token ID to trade (required)
- `--side`: Order side - BUY or SELL (required)
- `--price`: Order price between 0.0 and 1.0 (required)
- `--size`: Order size in shares (required)
- `--check-interval`: How often to check order status in seconds (default: 5.0)
- `--timeout`: Maximum tracking time in seconds (default: 300)
- `--skip-place`: Skip placing order and track existing order ID instead (optional)

**Example Output:**

```
Loading configuration...
Initializing Polymarket client...
Initializing market monitor for token: 214858393...
Fetching market snapshot...
Current market: Bid $0.4750 | Ask $0.4850
Micro-price (fair value): $0.4810

Your price: $0.4800
Status: ✓ COMPETITIVE
Distance from fair value: -0.21%

Starting portfolio monitor...
================================================================================
PLACING ORDER: BUY 100 @ $0.4800
================================================================================
Order placed successfully! ID: 0x7f3a2b1c...

Initializing order tracker...
================================================================================
TRACKING ORDER
================================================================================
Starting to track order: 0x7f3a2b1c...
Target size: 100 shares
Check interval: 5.0s | Timeout: 300s

[  5s] ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░   0.0% | 0/100 shares
        Market: Bid $0.4750 | Ask $0.4850 | Fair $0.4810

[  10s] ██████████░░░░░░░░░░░░░░░░░░░░  30.0% | 30/100 shares
  ✓ Fill detected: +30 shares @ $0.4800
        Avg Fill Price: $0.4800 | Remaining: 70
        Market: Bid $0.4750 | Ask $0.4850 | Fair $0.4810

[  15s] ████████████████████░░░░░░░░░░  65.0% | 65/100 shares
  ✓ Fill detected: +35 shares @ $0.4800
        Avg Fill Price: $0.4800 | Remaining: 35
        Market: Bid $0.4750 | Ask $0.4850 | Fair $0.4810

[  20s] ██████████████████████████████ 100.0% | 100/100 shares
  ✓ Fill detected: +35 shares @ $0.4800

================================================================================
ORDER FILLED SUCCESSFULLY!
================================================================================

FINAL SUMMARY
--------------------------------------------------------------------------------
Order ID: 0x7f3a2b1c4e9d8a5f
Duration: 20.3s
Filled: 100/100 shares (100.0%)
Remaining: 0 shares
Avg Fill Price: $0.4800
Total Cost: $48.00

FILL DETAILS
--------------------------------------------------------------------------------
  Tranche 1: 30 shares @ $0.4800 at 2026-01-14T14:23:15.123456
  Tranche 2: 35 shares @ $0.4800 at 2026-01-14T14:23:20.234567
  Tranche 3: 35 shares @ $0.4800 at 2026-01-14T14:23:25.345678

✓ Order tracking completed successfully
```

---

### Example 3: Kelly-Sized Order with Micro-Price and Auto-Replacement

**File:** `scripts/examples/example3_kelly_micro_price_order.py`

This is the most advanced example, demonstrating a complete automated trading system that combines Kelly criterion position sizing with micro-price execution and automatic order replacement when the market moves.

**Features:**
- **Kelly Criterion Sizing**: Calculates optimal position size based on edge and bankroll
- **Micro-Price Execution**: Places orders at depth-weighted fair value
- **Automatic Replacement**: Cancels and replaces orders when price moves >1 tick (0.01)
- **Real-time Monitoring**: Continuous market monitoring with configurable check interval
- **Position Awareness**: Accounts for existing positions when sizing
- **Fill Tracking**: Tracks partial fills across order replacements
- **Comprehensive Logging**: Detailed market analysis and execution statistics

**How It Works:**

1. **Market Analysis**: Fetches order book and calculates micro-price (depth-weighted fair value)
2. **Kelly Sizing**: Calculates optimal position size based on:
   - Your win probability estimate
   - Current micro-price
   - Available bankroll
   - Kelly fraction (0.25 = quarter Kelly, recommended)
3. **Order Placement**: Places order at micro-price rounded to nearest tick (0.01)
4. **Continuous Monitoring**: Every N seconds:
   - Checks if order has been filled
   - Fetches new market snapshot
   - Calculates new micro-price
   - If micro-price moved >1 tick: cancels old order and places new one at updated price
5. **Completion**: Stops when order is filled, timeout reached, or error occurs

**Usage:**

```bash
# Basic usage with quarter Kelly (recommended)
python scripts/examples/example3_kelly_micro_price_order.py \
    --token-id <token_id> \
    --side BUY \
    --win-prob 0.60 \
    --bankroll 1000 \
    --kelly-fraction 0.25

# More aggressive with half Kelly
python scripts/examples/example3_kelly_micro_price_order.py \
    --token-id <token_id> \
    --side SELL \
    --win-prob 0.55 \
    --bankroll 5000 \
    --kelly-fraction 0.50

# With position limit and custom intervals
python scripts/examples/example3_kelly_micro_price_order.py \
    --token-id <token_id> \
    --side BUY \
    --win-prob 0.65 \
    --bankroll 2000 \
    --kelly-fraction 0.25 \
    --max-position 1000 \
    --check-interval 3.0 \
    --timeout 600

# Win probability as percentage
python scripts/examples/example3_kelly_micro_price_order.py \
    --token-id <token_id> \
    --side BUY \
    --win-prob 60 \
    --bankroll 1000 \
    --kelly-fraction 0.25
```

**Arguments:**
- `--token-id`: Token ID to trade (required)
- `--side`: Order side - BUY or SELL (required)
- `--win-prob`: Your estimated win probability - decimal (0.0-1.0) or percentage (0-100) (required)
- `--bankroll`: Available capital for position sizing in dollars (required)
- `--kelly-fraction`: Fraction of Kelly to use (default: 0.25)
  - 1.0 = Full Kelly (highest growth, highest variance)
  - 0.5 = Half Kelly (recommended for most)
  - 0.25 = Quarter Kelly (conservative, recommended default)
  - 0.1 = Tenth Kelly (very conservative)
- `--max-position`: Maximum position size in shares (optional, default: unlimited)
- `--check-interval`: Market check interval in seconds (default: 5.0)
- `--timeout`: Maximum monitoring time in seconds (default: 300)

**Example Output:**

```
Loading configuration...
Initializing Polymarket client...
Initializing market monitor for token: 214858393...
Starting portfolio monitor...
Waiting for initial data...

================================================================================
KELLY MICRO-PRICE ORDER MANAGER
================================================================================
Token: 214858393...
Side: BUY
Win Probability: 60.00%
Bankroll: $1,000.00
Kelly Fraction: 0.25x

================================================================================
MARKET SNAPSHOT
================================================================================
Best Bid: $0.4750
Best Ask: $0.4850
Spread: $0.0100 (100.0 bps)
Micro-Price: $0.4810
  Lower Band: $0.4786
  Upper Band: $0.4834

================================================================================
KELLY POSITION SIZING
================================================================================
Win Probability: 60.00%
Bankroll: $1,000.00
Kelly Fraction: 0.25 (Quarter Kelly)

Kelly calculation:
  Full Kelly: 0.1869 (18.69% of bankroll)
  Adjusted (0.25x): 0.0467
  Position $: $46.73
  Shares: 97

================================================================================
PLACING ORDER
================================================================================
Side: BUY
Price: $0.4800 (rounded to tick)
Size: 97 shares
Notional: $46.56

✓ Order placed: 0x7f3a2b1c4e9d...

================================================================================
MONITORING STARTED
================================================================================
Check Interval: 5.0s
Timeout: 300s
Replace Trigger: Price moves >1 tick ($0.01)

[  5s] Market: Bid $0.4750 | Ask $0.4850 | Fair $0.4810
[ 10s] Market: Bid $0.4750 | Ask $0.4850 | Fair $0.4810
[ 15s] Market: Bid $0.4760 | Ask $0.4860 | Fair $0.4820
Price moved 1.0 ticks ($0.4810 -> $0.4820)

🔄 REPLACING ORDER (price moved >1 tick)
--------------------------------------------------------------------------------
Cancelling order: 0x7f3a2b1c4e9d...
✓ Order cancelled

================================================================================
MARKET SNAPSHOT
================================================================================
Best Bid: $0.4760
Best Ask: $0.4860
Spread: $0.0100 (100.0 bps)
Micro-Price: $0.4820
  Lower Band: $0.4796
  Upper Band: $0.4844

================================================================================
KELLY POSITION SIZING
================================================================================
Win Probability: 60.00%
Bankroll: $1,000.00
Kelly Fraction: 0.25 (Quarter Kelly)

Kelly calculation:
  Full Kelly: 0.1825 (18.25% of bankroll)
  Adjusted (0.25x): 0.0456
  Position $: $45.63
  Shares: 94

================================================================================
PLACING ORDER
================================================================================
Side: BUY
Price: $0.4800 (rounded to tick)
Size: 94 shares
Notional: $45.12

✓ Order placed: 0x9e4c8d2a5f3b...
✓ Order replacement complete

[ 20s] Market: Bid $0.4760 | Ask $0.4860 | Fair $0.4820
✓ Partial fill: +30 shares (total: 30)
[ 25s] Market: Bid $0.4760 | Ask $0.4860 | Fair $0.4820
✓ Partial fill: +64 shares (total: 94)

================================================================================
ORDER FULLY FILLED
================================================================================

EXECUTION SUMMARY
--------------------------------------------------------------------------------
Duration: 25.3s
Total Fills: 2
Total Filled: 94 shares
Fill Rate: 100.0%
Order Replacements: 1

Execution complete
```

**Kelly Criterion Explained:**

The Kelly criterion calculates the optimal fraction of your bankroll to bet based on your edge:

**Formula:** `f* = (bp - q) / b`
- `f*` = fraction of bankroll to bet
- `b` = odds (payout per dollar risked)
- `p` = win probability (your true belief)
- `q` = loss probability (1 - p)

**For Polymarket:**
- Buying YES at price 0.48 with 60% win probability:
  - Odds: (1 - 0.48) / 0.48 = 1.083
  - Kelly: (1.083 × 0.60 - 0.40) / 1.083 = 0.231 (23.1% of bankroll)
  - Quarter Kelly: 0.231 × 0.25 = 5.8% of bankroll

**Why Use Fractional Kelly:**
- **Full Kelly (1.0)**: Maximum growth rate, but high variance (can lose 50%+ of bankroll)
- **Half Kelly (0.5)**: 75% of growth rate, 50% less variance (recommended for most)
- **Quarter Kelly (0.25)**: 50% of growth rate, 75% less variance (conservative, recommended default)
- **Tenth Kelly (0.1)**: Very conservative, minimal variance

**When to Use This Example:**

Use this when you:
1. Have a probability estimate for a market outcome
2. Want to size positions optimally based on edge
3. Need to stay at fair value as the market moves
4. Want automated order management
5. Are managing multiple orders that need continuous adjustment

**Best Practices:**

1. **Conservative Kelly Fractions**: Start with 0.25 (quarter Kelly) or lower
2. **Accurate Probabilities**: Kelly is sensitive to probability estimates - be conservative
3. **Position Limits**: Always set `--max-position` to cap risk
4. **Monitor Execution**: Watch for excessive replacements (may indicate volatile market)
5. **Bankroll Management**: Only use capital you can afford to lose
6. **Edge Required**: Kelly only works with positive edge - if market price matches your estimate, don't bet

**Troubleshooting:**

**Order size is 0:**
- Your win probability is too close to market price (no edge)
- Increase win probability or wait for better market price
- Kelly suggests not betting when there's no edge

**Too many replacements:**
- Market is very volatile
- Increase `--check-interval` to reduce replacement frequency
- Consider using a wider threshold than 1 tick

**Order not filling:**
- Your price may be too aggressive or not aggressive enough
- Check if you're on the right side (BUY vs SELL)
- Verify there's sufficient liquidity in the market

---

## How the Monitoring System Works

### PortfolioMonitor (`core/portfolio_monitor.py`)

Async background daemon that continuously polls Polymarket APIs:

- **Orders**: Fetches all open orders from CLOB API every poll interval
- **Positions**: Fetches current positions from Data API
- **Metadata**: Lazy-loads and caches market questions (1-hour TTL)
- **Thread-safe**: Uses RLock for safe concurrent access
- **Stale detection**: Tracks last update times and can detect stale data

### MarketMonitor (`core/market_monitor.py`)

Real-time market analysis for a specific token:

- **Order Book**: Fetches and sorts bids/asks from CLOB API
- **Micro-Price**: Calculates depth-weighted fair value
  - Formula: `(best_bid × ask_depth + best_ask × bid_depth) / (bid_depth + ask_depth)`
- **Threshold Bands**: Creates upper/lower bands around micro-price (±50 bps default)
- **Competitive Analysis**: Checks if prices are within fair value bands
- **Snapshot Caching**: Caches latest snapshot for performance

### FillTracker (`core/fill_tracker.py`)

Tracks order fills across multiple tranches:

- **Tranche Recording**: Records each partial fill with timestamp
- **Volume-Weighted Avg**: Calculates average fill price weighted by size
- **Fill Rate**: Tracks completion percentage
- **Completion Detection**: Identifies when order is fully filled

### OrderTracker (Example 2)

Orchestrates order tracking:

- Polls portfolio monitor cache for efficiency
- Falls back to direct API calls when needed
- Detects new fills and updates FillTracker
- Displays real-time progress with visual progress bar
- Shows market context during tracking
- Handles order completion and cancellation

---

## Prerequisites

1. Configure your `.env` file with Polymarket credentials:

```bash
POLYMARKET_PRIVATE_KEY=your_64_char_hex_key
POLYMARKET_SIGNATURE_TYPE=2  # 0=EOA, 1=Email, 2=Browser
POLYMARKET_FUNDER_ADDRESS=0x...  # Required for proxy wallets
```

2. Find a token ID to trade:
   - Visit a market on Polymarket
   - Get the token ID from the URL or API

---

## Tips

1. **Start with Example 1** to understand your current portfolio state
2. **Use Example 2** to place new orders with tracking
3. **Adjust poll/check intervals** based on market volatility
4. **Monitor micro-price** to ensure competitive pricing
5. **Track fill rates** to optimize order sizing
6. **Use --skip-place** to track orders placed externally

---

## Architecture Notes

- **Async Design**: All monitors use asyncio for non-blocking operations
- **Thread Safety**: RLock ensures safe concurrent access to cached data
- **Smart Caching**: Metadata cached with TTL, stale entries refreshed in batches
- **Error Resilience**: Monitors continue running despite API errors
- **Rate Limit Aware**: Batch refreshes prevent API rate limit issues

---

## Troubleshooting

**No orders showing up:**
- Wait 10-15 seconds for initial poll cycle
- Check that orders are still open (not filled/cancelled)
- Verify API credentials in `.env`

**Position data missing:**
- Ensure `POLYMARKET_FUNDER_ADDRESS` is set correctly
- Check that positions are non-zero and not resolved
- Data API requires lowercase wallet address

**Order tracking timeout:**
- Increase `--timeout` value
- Check that your price is competitive (within fair value bands)
- Consider adjusting order price closer to micro-price

**API errors:**
- Check network connectivity
- Verify Polymarket API is operational
- Ensure credentials are valid
