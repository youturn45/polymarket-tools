# Polymarket Order Management System - Requirements Document

## Document Information
- **Version**: 1.0
- **Date**: December 12, 2025
- **Purpose**: Automated order execution system with adaptive iceberg strategy for Polymarket
- **Target Platform**: Polymarket CLOB (Central Limit Order Book)

---

## 1. Executive Summary

This system provides automated order execution on Polymarket prediction markets using an adaptive iceberg strategy. It monitors market conditions in real-time, intelligently splits large orders into smaller tranches, and dynamically adjusts pricing based on competitive activity and undercutting patterns.

**Key Features:**
- Iceberg order splitting with sequential execution
- Real-time market monitoring and adaptation
- Dynamic bid adjustment based on market competitiveness
- Asynchronous order addition without interrupting monitoring
- Automatic cancellation and replacement of non-competitive orders

---

## 2. System Architecture Overview

### 2.1 Core Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Order Management System                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │   Order      │  │   Market     │  │   Order      │     │
│  │   Queue      │  │   Monitor    │  │   Executor   │     │
│  │   Manager    │  │              │  │              │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│         │                  │                  │             │
│         └──────────────────┼──────────────────┘             │
│                            │                                │
│                   ┌────────▼────────┐                       │
│                   │  Strategy       │                       │
│                   │  Engine         │                       │
│                   │  (Iceberg +     │                       │
│                   │   Adaptive)     │                       │
│                   └─────────────────┘                       │
│                            │                                │
│                   ┌────────▼────────┐                       │
│                   │  Polymarket     │                       │
│                   │  CLOB API       │                       │
│                   └─────────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

**Implementation Sketch:**
- Order Queue Manager runs an `asyncio.Queue`, accepting requests from CLI/HTTP and returning an `order_id` immediately. Each worker coroutine pops orders, stamps metadata, and hands them to the Strategy Engine.
- Market Monitor maintains a live cache (WebSocket if available, otherwise polling) of order books, trades, and our open orders, exposing read-only snapshots to strategy/executor.
- Strategy Engine converts total order intent into tranche plans (size/price targets) based on the latest market snapshot and urgency configuration.
- Order Executor wraps `py-clob-client` to place/cancel/replace Polymarket limit orders and to query fills. It should support both L1 signing and L2 API creds.
- Shared event bus/logger emits lifecycle events so monitoring/metrics remain decoupled from execution.

**How orders hit the Polymarket book (core interaction):**
1) Client call (`add_order`) → enqueue order with validated params.  
2) Worker pulls order → computes first tranche (size/limit).  
3) Order Executor calls `POST /order` (via `py_clob_client.create_order` + `post_order`) to place a limit order on the CLOB.  
4) Market Monitor listens on `user_orders`/`orderbook` streams to detect fills/undercuts; Executor polls as fallback.  
5) On fill/timeout/undercut, Strategy Engine decides to hold, cancel, or replace; Executor issues `DELETE /order/{id}` and re-places as needed.  
6) Loop until total size filled or order cancelled; updates persisted to order state store/logs.

**Interactive CLI flow to add orders:**
- `polymarket-tools add-order --market <id> --token <id> --side BUY --size 500 --price 0.45 --max-price 0.48 --urgency MEDIUM` (or prompt-driven inputs) collects parameters, validates them locally, and calls `add_order`.
- CLI prints immediate acknowledgment with `order_id` and optional tracking URL/command (`polymarket-tools status --order-id ...`).
- Order is enqueued without blocking the monitor; subsequent fills/adjustments are observable via `status`, `list-orders`, or a `tail` on structured logs.

### 2.2 Component Responsibilities

| Component | Responsibility |
|-----------|---------------|
| **Order Queue Manager** | Accept new orders asynchronously, maintain order queue, coordinate execution |
| **Market Monitor** | Track order book state, detect undercutting, measure market conditions |
| **Order Executor** | Place, cancel, and modify orders on Polymarket |
| **Strategy Engine** | Implement iceberg splitting logic, dynamic pricing adjustments |

---

## 3. Functional Requirements

### 3.1 Order Input and Management

#### 3.1.1 Order Input Specification

**Required Input Parameters:**
```python
{
    "market_id": str,           # Polymarket market/condition ID
    "token_id": str,            # Token ID (YES/NO token)
    "side": str,                # "BUY" or "SELL"
    "total_size": int,          # Total number of shares to trade
    "target_price": float,      # Initial target price (0.00 to 1.00)
    "max_price": float,         # Maximum acceptable price (buy orders)
    "min_price": float,         # Minimum acceptable price (sell orders)
    "urgency": str,             # "LOW", "MEDIUM", "HIGH"
    "strategy_params": {
        "initial_tranche_size": int,  # Size of first order chunk
        "min_tranche_size": int,      # Minimum chunk size
        "max_tranche_size": int,      # Maximum chunk size
        "tranche_randomization": float # 0.0 to 1.0 (amount of size randomization)
    }
}
```

**Validation Rules:**
- `total_size` > 0
- `0.00 <= target_price <= 1.00`
- `0.00 <= max_price <= 1.00`
- `0.00 <= min_price <= 1.00`
- For BUY orders: `min_price <= target_price <= max_price`
- For SELL orders: `min_price <= target_price <= max_price`
- `min_tranche_size <= initial_tranche_size <= max_tranche_size`
- `tranche_randomization` between 0.0 and 1.0

#### 3.1.2 Order Addition Mechanism

**Non-Blocking Order Addition:**
The system MUST support adding new orders without interrupting the monitoring and execution of existing orders.

**Implementation Requirements:**
1. **Thread-Safe Queue**: Use a thread-safe queue (e.g., `queue.Queue` in Python) to accept new orders
2. **Async Processing**: Order addition should return immediately with an order ID
3. **No Interruption**: Adding orders must NOT pause or restart the monitoring loop
4. **Concurrent Execution**: System should handle multiple simultaneous orders across different markets

**API Specification:**
```python
# Add order endpoint
order_id = add_order(order_params)
# Returns immediately with unique order_id

# Order status endpoint
status = get_order_status(order_id)
# Returns: "queued", "active", "partially_filled", "completed", "cancelled", "failed"

# Cancel order endpoint
cancel_order(order_id)
# Gracefully stops execution of specified order
```

**Order State Machine:**
```
                    add_order()
                        │
                        ▼
   ┌─────────────────────────────────────┐
   │         QUEUED                      │
   └─────────────────────────────────────┘
                        │
        processing picks up order
                        │
                        ▼
   ┌─────────────────────────────────────┐
   │         ACTIVE                      │
   │  (monitoring & executing tranches)  │
   └─────────────────────────────────────┘
                        │
            ┌───────────┼───────────┐
            │           │           │
            ▼           ▼           ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │PARTIALLY │  │COMPLETED │  │ FAILED   │
    │ FILLED   │  │          │  │          │
    └──────────┘  └──────────┘  └──────────┘
            │           
            ▼           
    ┌──────────┐
    │CANCELLED │
    └──────────┘
```

### 3.2 Iceberg Strategy Implementation

#### 3.2.1 Order Splitting Logic

**Requirements:**
1. **Sequential Execution**: Only place next tranche AFTER previous tranche is filled
2. **Size Randomization**: Add randomness to tranche sizes to avoid detection
3. **Adaptive Sizing**: Adjust tranche size based on market conditions

**Tranche Size Calculation:**
```python
def calculate_next_tranche_size(
    remaining_size: int,
    market_conditions: MarketConditions,
    strategy_params: dict
) -> int:
    """
    Calculate size of next order tranche.
    
    Logic:
    1. Start with base_size from strategy_params
    2. Apply randomization factor
    3. Adjust for market conditions
    4. Ensure within min/max bounds
    5. Don't exceed remaining_size
    """
    
    base_size = strategy_params['initial_tranche_size']
    
    # Apply randomization (e.g., ±20%)
    random_factor = 1.0 + (random.random() - 0.5) * 2 * strategy_params['tranche_randomization']
    randomized_size = base_size * random_factor
    
    # Adjust for market conditions
    if market_conditions.high_competition:
        # Use smaller sizes when heavily contested
        adjusted_size = randomized_size * 0.7
    elif market_conditions.low_liquidity:
        # Use smaller sizes in thin markets
        adjusted_size = randomized_size * 0.5
    else:
        adjusted_size = randomized_size
    
    # Apply bounds
    final_size = max(
        strategy_params['min_tranche_size'],
        min(strategy_params['max_tranche_size'], adjusted_size)
    )
    
    # Don't exceed remaining
    final_size = min(final_size, remaining_size)
    
    return int(final_size)
```

#### 3.2.2 Tranche Execution Flow

```
Start Order (1000 shares @ $0.45)
        │
        ▼
Calculate tranche_1 size (150 shares)
        │
        ▼
Place limit order: 150 @ $0.45
        │
        ▼
Monitor order status
        │
        ├──────► If filled (100%) ──────┐
        │                               │
        ├──────► If partially filled ───┤
        │         (after timeout)       │
        │                               │
        └──────► If not filled ─────────┤
                  (see section 3.3)     │
                                        │
                                        ▼
                    Remaining = 1000 - filled_amount
                                        │
                                        ▼
                            Is remaining > 0?
                                    │   │
                                Yes │   │ No
                                    ▼   ▼
                    Calculate next tranche   COMPLETED
                                    │
                                    ▼
                    Place next order...
                          (loop)
```

**Fill Detection Requirements:**
- Poll order status every 500ms-2000ms (configurable)
- Consider order "filled" when `filled_amount == order_size`
- Consider order "partially filled" when `0 < filled_amount < order_size`
- Track cumulative fills across all tranches

### 3.3 Market Monitoring and Adaptation

#### 3.3.1 Market State Monitoring

**Required Metrics to Track:**

```python
class MarketConditions:
    """Real-time market state"""
    
    # Order book metrics
    best_bid: float              # Current best bid price
    best_ask: float              # Current best ask price
    spread: float                # best_ask - best_bid
    bid_depth: int               # Total size at best bid
    ask_depth: int               # Total size at best ask
    
    # Position in queue
    our_position_in_queue: int   # How many orders ahead of us
    total_orders_at_price: int   # Total orders at our price level
    
    # Competition metrics
    undercut_detected: bool      # Someone placed order ahead of us
    undercut_margin: float       # Price difference of undercut
    undercut_size: int           # Size of undercutting order
    
    # Market activity
    recent_trade_volume: int     # Volume in last 60 seconds
    recent_trade_count: int      # Number of trades in last 60 seconds
    price_volatility: float      # Price variance in last 5 minutes
    
    # Time tracking
    time_at_current_price: float # Seconds our order has been live
    time_since_last_fill: float  # Seconds since last market trade
```

**Monitoring Frequency:**
- Order book updates: Every 500ms (via WebSocket if available)
- Order status checks: Every 1000ms
- Market condition calculations: Every 2000ms
- Strategy adjustments: Every 5000ms or on significant market change

#### 3.3.2 Undercutting Detection

**Definition of "Heavily Undercut":**

An order is considered "heavily undercut" when:
```python
def is_heavily_undercut(
    our_order: Order,
    market_conditions: MarketConditions
) -> bool:
    """
    Determine if our order is heavily undercut.
    
    Conditions for BUY orders:
    1. Another order exists at higher price than ours
    2. That order has priority (placed before ours)
    3. The undercut is significant enough to prevent fill
    """
    
    if our_order.side == "BUY":
        # Check if someone is bidding higher
        if market_conditions.best_bid > our_order.price:
            undercut_margin = market_conditions.best_bid - our_order.price
            
            # Heavy undercut criteria:
            if undercut_margin >= 0.01:  # 1¢ or more
                return True
            
            # OR if we've been undercut multiple times
            if our_order.undercut_count >= 3:
                return True
            
            # OR if we've been waiting too long
            if market_conditions.time_at_current_price > 30:  # 30 seconds
                return True
    
    elif our_order.side == "SELL":
        # Check if someone is asking lower
        if market_conditions.best_ask < our_order.price:
            undercut_margin = our_order.price - market_conditions.best_ask
            
            if undercut_margin >= 0.01:
                return True
            if our_order.undercut_count >= 3:
                return True
            if market_conditions.time_at_current_price > 30:
                return True
    
    return False
```

**Undercutting Response Strategy:**

When heavy undercutting is detected:

```python
def respond_to_undercut(
    our_order: Order,
    market_conditions: MarketConditions
) -> Action:
    """
    Decide how to respond to being undercut.
    
    Returns:
    - INCREASE_BID: Make our price more competitive
    - WAIT: Be patient, don't change yet
    - CANCEL: Give up on this tranche
    """
    
    # Calculate how much to improve price
    if our_order.side == "BUY":
        current_best = market_conditions.best_bid
        
        # Step 1: Try to match best bid
        if our_order.price < current_best:
            new_price = current_best
        else:
            # Already at best bid, try to outbid slightly
            new_price = current_best + 0.001  # +0.1¢
        
        # Step 2: Check if new price is within acceptable range
        if new_price <= our_order.max_price:
            return Action(
                type="INCREASE_BID",
                new_price=new_price
            )
        else:
            # Price would exceed max, decide based on urgency
            if our_order.urgency == "HIGH":
                # Increase to max_price
                return Action(
                    type="INCREASE_BID", 
                    new_price=our_order.max_price
                )
            else:
                # Wait it out
                return Action(type="WAIT")
    
    elif our_order.side == "SELL":
        current_best = market_conditions.best_ask
        
        if our_order.price > current_best:
            new_price = current_best
        else:
            new_price = current_best - 0.001  # -0.1¢
        
        if new_price >= our_order.min_price:
            return Action(
                type="DECREASE_ASK",
                new_price=new_price
            )
        else:
            if our_order.urgency == "HIGH":
                return Action(
                    type="DECREASE_ASK",
                    new_price=our_order.min_price
                )
            else:
                return Action(type="WAIT")
```

#### 3.3.3 Overpriced Order Detection

**Definition of "Overpriced":**

An order is considered "overpriced" when:
```python
def is_overpriced(
    our_order: Order,
    market_conditions: MarketConditions
) -> bool:
    """
    Determine if our order is priced uncompetitively.
    
    For BUY orders: We're bidding too low
    For SELL orders: We're asking too high
    """
    
    if our_order.side == "BUY":
        # We're overpriced if our bid is significantly below best bid
        spread_to_best_bid = market_conditions.best_bid - our_order.price
        
        # Overpriced if:
        # 1. More than 2¢ below best bid
        if spread_to_best_bid > 0.02:
            return True
        
        # 2. OR market has moved significantly up
        if market_conditions.best_ask > (our_order.price + 0.05):
            return True
        
        # 3. OR we're far from spread midpoint in thin market
        mid_price = (market_conditions.best_bid + market_conditions.best_ask) / 2
        if abs(our_order.price - mid_price) > 0.03:
            if market_conditions.bid_depth < 100:  # Thin market
                return True
    
    elif our_order.side == "SELL":
        # We're overpriced if our ask is significantly above best ask
        spread_to_best_ask = our_order.price - market_conditions.best_ask
        
        if spread_to_best_ask > 0.02:
            return True
        
        if market_conditions.best_bid < (our_order.price - 0.05):
            return True
        
        mid_price = (market_conditions.best_bid + market_conditions.best_ask) / 2
        if abs(our_order.price - mid_price) > 0.03:
            if market_conditions.ask_depth < 100:
                return True
    
    return False
```

**Overpriced Order Response:**

When overpricing is detected:
```python
def respond_to_overpricing(
    our_order: Order,
    market_conditions: MarketConditions
) -> Action:
    """
    Cancel and replace overpriced orders.
    """
    
    # Calculate competitive price
    if our_order.side == "BUY":
        # Target slightly below best ask (save spread)
        target_price = market_conditions.best_ask - 0.005  # -0.5¢ from ask
        
        # But stay above our minimum
        competitive_price = max(target_price, our_order.target_price)
        
        # And respect max_price
        competitive_price = min(competitive_price, our_order.max_price)
    
    elif our_order.side == "SELL":
        # Target slightly above best bid
        target_price = market_conditions.best_bid + 0.005  # +0.5¢ from bid
        
        competitive_price = min(target_price, our_order.target_price)
        competitive_price = max(competitive_price, our_order.min_price)
    
    return Action(
        type="CANCEL_AND_REPLACE",
        new_price=competitive_price,
        reason="overpriced"
    )
```

### 3.4 Price Adjustment Strategy

#### 3.4.1 Dynamic Pricing Algorithm

**Price Adjustment Decision Tree:**

```
Check order every 5 seconds
        │
        ▼
Is order filled? ─────Yes────► Continue to next tranche
        │
       No
        │
        ▼
Time at current price > threshold?
        │
        ├────No────► Continue monitoring
        │
       Yes
        │
        ▼
Analyze market conditions
        │
        ├──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
  Heavy undercut   Overpriced    Competitive    Price moved
        │              │              │              │
        ▼              ▼              ▼              ▼
   Increase bid   Cancel/Replace   Wait longer   Adjust price
```

**Adjustment Parameters by Urgency Level:**

```python
URGENCY_PARAMS = {
    "LOW": {
        "patience_timeout": 60,        # Wait 60s before adjusting
        "max_adjustments": 3,          # Max 3 price improvements
        "adjustment_step": 0.003,      # Adjust by 0.3¢
        "use_max_price": False         # Don't jump to max immediately
    },
    "MEDIUM": {
        "patience_timeout": 30,        # Wait 30s
        "max_adjustments": 5,          # Max 5 adjustments
        "adjustment_step": 0.005,      # Adjust by 0.5¢
        "use_max_price": False
    },
    "HIGH": {
        "patience_timeout": 10,        # Wait 10s only
        "max_adjustments": 10,         # Many adjustments allowed
        "adjustment_step": 0.01,       # Adjust by 1¢
        "use_max_price": True          # Jump to max if needed
    }
}
```

#### 3.4.2 Price Adjustment Execution

**Atomic Cancel-and-Replace:**

```python
async def adjust_order_price(
    order_id: str,
    new_price: float,
    reason: str
) -> bool:
    """
    Cancel existing order and place new one at adjusted price.
    
    Requirements:
    1. Cancel existing order first
    2. Wait for cancellation confirmation
    3. Place new order at adjusted price
    4. Update order tracking
    5. Log adjustment for analysis
    
    Returns:
    - True if successful
    - False if cancellation or replacement failed
    """
    
    try:
        # Step 1: Cancel existing order
        cancel_result = await cancel_order_on_exchange(order_id)
        
        if not cancel_result.success:
            logger.error(f"Failed to cancel order {order_id}")
            return False
        
        # Step 2: Brief delay to ensure cancellation processed
        await asyncio.sleep(0.1)
        
        # Step 3: Place new order
        new_order = await place_order_on_exchange(
            market_id=order.market_id,
            token_id=order.token_id,
            side=order.side,
            size=order.remaining_size,
            price=new_price
        )
        
        if not new_order.success:
            logger.error(f"Failed to place replacement order")
            return False
        
        # Step 4: Update tracking
        update_order_tracking(
            old_order_id=order_id,
            new_order_id=new_order.order_id,
            new_price=new_price,
            adjustment_reason=reason
        )
        
        # Step 5: Log for analysis
        log_price_adjustment(
            order_id=order_id,
            old_price=order.price,
            new_price=new_price,
            reason=reason,
            timestamp=time.time()
        )
        
        return True
        
    except Exception as e:
        logger.error(f"Error in adjust_order_price: {e}")
        return False
```

### 3.5 Order Lifecycle Management

#### 3.5.1 Complete Order Execution Flow

```python
async def execute_order(order: Order):
    """
    Main execution loop for a single order.
    
    Handles:
    - Tranche splitting
    - Market monitoring
    - Price adjustments
    - Fill detection
    - Completion tracking
    """
    
    remaining_size = order.total_size
    tranches_executed = 0
    total_filled = 0
    
    while remaining_size > 0:
        # Calculate next tranche
        tranche_size = calculate_next_tranche_size(
            remaining_size=remaining_size,
            market_conditions=get_market_conditions(order.market_id),
            strategy_params=order.strategy_params
        )
        
        # Determine price for this tranche
        current_price = calculate_tranche_price(
            order=order,
            market_conditions=get_market_conditions(order.market_id),
            tranche_number=tranches_executed
        )
        
        # Place order
        tranche_order_id = await place_order_on_exchange(
            market_id=order.market_id,
            token_id=order.token_id,
            side=order.side,
            size=tranche_size,
            price=current_price
        )
        
        # Monitor and adapt
        filled_amount = await monitor_and_adapt_tranche(
            order=order,
            tranche_order_id=tranche_order_id,
            tranche_size=tranche_size,
            current_price=current_price
        )
        
        # Update counters
        total_filled += filled_amount
        remaining_size -= filled_amount
        tranches_executed += 1
        
        # Update order status
        update_order_status(
            order_id=order.order_id,
            status="partially_filled" if remaining_size > 0 else "completed",
            filled_amount=total_filled,
            remaining_amount=remaining_size
        )
        
        # Check if we should continue
        if remaining_size <= 0:
            break
        
        # Check for cancellation request
        if order.cancellation_requested:
            break
        
        # Delay before next tranche (randomized)
        delay = random.uniform(1.0, 3.0)
        await asyncio.sleep(delay)
    
    # Final status update
    finalize_order(
        order_id=order.order_id,
        total_filled=total_filled,
        tranches_executed=tranches_executed
    )
```

#### 3.5.2 Tranche Monitoring Loop

```python
async def monitor_and_adapt_tranche(
    order: Order,
    tranche_order_id: str,
    tranche_size: int,
    current_price: float
) -> int:
    """
    Monitor a single tranche until filled or timeout.
    
    Returns:
    - Amount filled
    """
    
    start_time = time.time()
    urgency_params = URGENCY_PARAMS[order.urgency]
    adjustment_count = 0
    
    while True:
        # Check order status
        order_status = await get_order_status_from_exchange(tranche_order_id)
        
        # Fully filled - success!
        if order_status.filled_amount >= tranche_size:
            return order_status.filled_amount
        
        # Partial fill - continue monitoring
        elapsed_time = time.time() - start_time
        
        # Get market conditions
        market_conditions = get_market_conditions(order.market_id)
        
        # Check if we should adjust
        should_adjust = False
        adjustment_reason = None
        
        # Check for heavy undercutting
        if is_heavily_undercut(order, market_conditions):
            should_adjust = True
            adjustment_reason = "heavily_undercut"
        
        # Check if overpriced
        elif is_overpriced(order, market_conditions):
            should_adjust = True
            adjustment_reason = "overpriced"
        
        # Check timeout
        elif elapsed_time > urgency_params['patience_timeout']:
            should_adjust = True
            adjustment_reason = "timeout"
        
        # Perform adjustment if needed
        if should_adjust and adjustment_count < urgency_params['max_adjustments']:
            
            # Determine new price
            if adjustment_reason == "heavily_undercut":
                action = respond_to_undercut(order, market_conditions)
            elif adjustment_reason == "overpriced":
                action = respond_to_overpricing(order, market_conditions)
            else:  # timeout
                action = Action(
                    type="INCREASE_BID",
                    new_price=current_price + urgency_params['adjustment_step']
                )
            
            # Execute adjustment
            if action.type in ["INCREASE_BID", "DECREASE_ASK", "CANCEL_AND_REPLACE"]:
                
                # Respect price limits
                if order.side == "BUY":
                    new_price = min(action.new_price, order.max_price)
                else:
                    new_price = max(action.new_price, order.min_price)
                
                # Perform cancel and replace
                success = await adjust_order_price(
                    order_id=tranche_order_id,
                    new_price=new_price,
                    reason=adjustment_reason
                )
                
                if success:
                    adjustment_count += 1
                    current_price = new_price
                    start_time = time.time()  # Reset timer
        
        # If we've hit max adjustments and still not filled
        elif adjustment_count >= urgency_params['max_adjustments']:
            # Accept partial fill or cancel
            if order_status.filled_amount > 0:
                # Accept what we got
                await cancel_order_on_exchange(tranche_order_id)
                return order_status.filled_amount
            else:
                # Nothing filled, cancel and move on
                await cancel_order_on_exchange(tranche_order_id)
                return 0
        
        # Wait before next check
        await asyncio.sleep(1.0)
```

---

## 4. Non-Functional Requirements

### 4.1 Performance Requirements

| Metric | Requirement |
|--------|-------------|
| Order addition response time | < 100ms |
| Market data update frequency | Every 500ms |
| Order status check frequency | Every 1000ms |
| Price adjustment execution time | < 500ms |
| Maximum concurrent orders | 20 orders |
| System uptime | 99.5% during market hours |

### 4.2 Reliability Requirements

1. **Fault Tolerance**:
   - System must handle API failures gracefully
   - Retry failed API calls with exponential backoff (3 attempts)
   - Continue monitoring other orders if one fails

2. **Data Persistence**:
   - All orders must be logged to persistent storage
   - Order state must survive system restart
   - Trade history must be retained for 90 days

3. **Error Recovery**:
   - Detect and handle network disconnections
   - Recover order state from exchange after reconnection
   - Alert operator on critical failures

### 4.3 Safety Requirements

1. **Order Validation**:
   - Validate all inputs before placing orders
   - Prevent orders that exceed available balance
   - Enforce maximum order size limits
   - Verify market IDs exist before placing orders

2. **Price Protection**:
   - Never exceed `max_price` for buy orders
   - Never go below `min_price` for sell orders
   - Warn if spread exceeds configurable threshold (e.g., 10¢)
   - Require confirmation for very large orders (> $1000)

3. **Rate Limiting**:
   - Respect Polymarket API rate limits
   - Implement internal rate limiter (max 10 orders/second)
   - Exponential backoff on rate limit errors

### 4.4 Monitoring and Observability

**Required Logging:**
```python
# Order lifecycle events
LOG_EVENT_TYPES = [
    "order_added",              # New order added to queue
    "order_started",            # Execution began
    "tranche_placed",           # Tranche order placed
    "tranche_filled",           # Tranche completely filled
    "tranche_partial_fill",     # Tranche partially filled
    "price_adjusted",           # Price changed
    "undercut_detected",        # Detected undercutting
    "order_completed",          # All tranches filled
    "order_cancelled",          # Order cancelled by user
    "order_failed",             # Order execution failed
]

# Market condition snapshots
LOG_MARKET_CONDITIONS = {
    "timestamp": float,
    "market_id": str,
    "best_bid": float,
    "best_ask": float,
    "spread": float,
    "our_position": int,
    "recent_volume": int,
}

# Performance metrics
LOG_PERFORMANCE = {
    "order_id": str,
    "total_execution_time": float,
    "number_of_tranches": int,
    "number_of_adjustments": int,
    "average_fill_price": float,
    "price_improvement": float,  # vs initial target
}
```

**Required Metrics Dashboard:**
- Active orders count
- Completed orders (last 24h)
- Average execution time per order
- Fill rate percentage
- Price adjustment frequency
- API error rate
- System uptime

---

## 5. API Integration Requirements

### 5.1 Polymarket CLOB API

**Required API Endpoints:**

| Endpoint | Purpose | Frequency |
|----------|---------|-----------|
| `GET /markets` | Get market information | On startup, then cached |
| `GET /book` | Get order book for market | Every 500ms (WebSocket preferred) |
| `POST /order` | Place limit order | Per tranche |
| `DELETE /order/{id}` | Cancel order | When adjusting price |
| `GET /orders` | Get open orders | Every 2000ms |
| `GET /trades` | Get recent trades | Every 2000ms |
| `POST /approve` | Approve USDC spending | Once per session |

**WebSocket Streams (Preferred):**
```python
WEBSOCKET_CHANNELS = [
    "orderbook",      # Real-time order book updates
    "trades",         # Recent trade feed
    "user_orders",    # Our order status updates
]
```

### 5.2 Authentication and Security

**Requirements:**
1. Store API keys securely (environment variables or secrets manager)
2. Use signature-based authentication (HMAC-SHA256)
3. Refresh authentication tokens before expiration
4. Log all API requests/responses (excluding sensitive data)

### 5.3 Error Handling

**API Error Response Mapping:**

```python
API_ERROR_HANDLERS = {
    400: "Invalid order parameters - log and alert",
    401: "Authentication failed - refresh credentials",
    429: "Rate limit exceeded - exponential backoff",
    500: "Exchange error - retry after delay",
    503: "Exchange unavailable - pause trading",
}
```

**Retry Strategy:**
```python
RETRY_CONFIG = {
    "max_attempts": 3,
    "base_delay": 1.0,      # Start with 1 second
    "max_delay": 30.0,      # Cap at 30 seconds
    "exponential_base": 2,  # Double delay each time
    "jitter": 0.1,          # Add ±10% randomization
}
```

---

## 6. System Configuration

### 6.1 Configuration File Structure

```yaml
# config.yaml

system:
  max_concurrent_orders: 20
  order_check_interval: 1.0  # seconds
  market_update_interval: 0.5  # seconds
  log_level: "INFO"
  
api:
  base_url: "https://clob.polymarket.com"
  websocket_url: "wss://ws-subscriptions-clob.polymarket.com"
  timeout: 30  # seconds
  max_retries: 3
  
strategy:
  default_urgency: "MEDIUM"
  default_tranche_size: 50
  min_tranche_size: 10
  max_tranche_size: 200
  tranche_randomization: 0.2  # ±20%
  
pricing:
  undercut_threshold: 0.01  # 1¢
  overpriced_threshold: 0.02  # 2¢
  adjustment_step_low: 0.003  # 0.3¢
  adjustment_step_medium: 0.005  # 0.5¢
  adjustment_step_high: 0.01  # 1¢
  
safety:
  max_spread_warning: 0.10  # Warn if spread > 10¢
  max_order_value: 10000  # USD
  require_confirmation_above: 1000  # USD
  
monitoring:
  dashboard_port: 8080
  metrics_enabled: true
  log_to_file: true
  log_directory: "./logs"
```

### 6.2 Environment Variables

```bash
# .env file
POLYMARKET_API_KEY=your_api_key_here
POLYMARKET_API_SECRET=your_api_secret_here
POLYMARKET_API_PASSPHRASE=your_passphrase_here
WALLET_PRIVATE_KEY=your_private_key_here
PROXY_WALLET_ADDRESS=your_proxy_address_here
```

---

## 7. Implementation Architecture

### 7.1 Technology Stack

**Recommended Stack:**
- **Language**: Python 3.10+
- **Async Framework**: `asyncio` + `aiohttp`
- **WebSocket**: `websockets` library
- **Database**: SQLite for order history (or PostgreSQL for production)
- **Queue**: `asyncio.Queue` for thread-safe order queue
- **Logging**: `structlog` for structured logging
- **Configuration**: `pydantic` for validation
- **API Client**: `py-clob-client` (Polymarket official)

### 7.2 Module Structure

```
polymarket_order_system/
│
├── main.py                 # Application entry point
├── config.py               # Configuration management
├── requirements.txt        # Python dependencies
│
├── core/
│   ├── __init__.py
│   ├── order_manager.py    # Order Queue Manager
│   ├── market_monitor.py   # Market Monitor
│   ├── order_executor.py   # Order Executor
│   └── strategy_engine.py  # Strategy Engine
│
├── models/
│   ├── __init__.py
│   ├── order.py           # Order data models
│   ├── market.py          # Market data models
│   └── enums.py           # Enums (OrderSide, OrderStatus, etc.)
│
├── api/
│   ├── __init__.py
│   ├── polymarket_client.py  # Polymarket API wrapper
│   └── websocket_client.py   # WebSocket handler
│
├── strategies/
│   ├── __init__.py
│   ├── iceberg.py          # Iceberg strategy logic
│   ├── pricing.py          # Dynamic pricing algorithms
│   └── adaptation.py       # Market adaptation logic
│
├── utils/
│   ├── __init__.py
│   ├── logging.py          # Logging utilities
│   ├── validation.py       # Input validation
│   └── metrics.py          # Performance metrics
│
└── tests/
    ├── __init__.py
    ├── test_order_manager.py
    ├── test_strategy.py
    └── test_integration.py
```

### 7.3 Class Diagram

```python
# Core classes

class Order:
    """Represents a single order request"""
    order_id: str
    market_id: str
    token_id: str
    side: OrderSide  # BUY or SELL
    total_size: int
    target_price: float
    max_price: float
    min_price: float
    urgency: Urgency
    strategy_params: StrategyParams
    status: OrderStatus
    filled_amount: int
    remaining_amount: int
    created_at: datetime
    updated_at: datetime

class OrderManager:
    """Manages order queue and lifecycle"""
    async def add_order(order: Order) -> str
    async def cancel_order(order_id: str) -> bool
    async def get_order_status(order_id: str) -> OrderStatus
    async def process_order_queue() -> None

class MarketMonitor:
    """Monitors market conditions"""
    async def get_market_conditions(market_id: str) -> MarketConditions
    async def detect_undercut(order: Order) -> bool
    async def detect_overpricing(order: Order) -> bool
    async def subscribe_to_market(market_id: str) -> None

class OrderExecutor:
    """Executes orders on Polymarket"""
    async def place_order(order: Order) -> str
    async def cancel_order(order_id: str) -> bool
    async def get_order_status(order_id: str) -> OrderStatusResponse
    async def get_fills(order_id: str) -> List[Fill]

class StrategyEngine:
    """Implements trading strategies"""
    def calculate_tranche_size(order: Order, conditions: MarketConditions) -> int
    def calculate_tranche_price(order: Order, conditions: MarketConditions) -> float
    def should_adjust_price(order: Order, conditions: MarketConditions) -> bool
    def calculate_new_price(order: Order, conditions: MarketConditions) -> float
```

---

## 8. Testing Requirements

### 8.1 Unit Tests

**Required Test Coverage:**
- Order validation logic
- Tranche size calculation
- Price adjustment algorithms
- Undercut detection
- Overpricing detection
- Order state transitions

**Example Test Cases:**
```python
def test_tranche_size_calculation():
    """Test that tranche sizes are correctly calculated"""
    assert calculate_tranche_size(
        remaining=1000,
        base_size=100,
        randomization=0.2
    ) in range(80, 120)

def test_undercut_detection():
    """Test heavy undercut detection"""
    order = create_test_order(price=0.45)
    market = MarketConditions(best_bid=0.46)
    assert is_heavily_undercut(order, market) == True

def test_price_limits():
    """Test that price never exceeds max_price"""
    order = create_test_order(max_price=0.50)
    new_price = calculate_new_price(order, market)
    assert new_price <= 0.50
```

### 8.2 Integration Tests

**Required Integration Tests:**
1. End-to-end order execution (testnet)
2. WebSocket connection and disconnection handling
3. Order queue concurrent access
4. Database persistence and recovery
5. API rate limit handling

### 8.3 Simulation Testing

**Paper Trading Mode:**
```python
# Enable paper trading for testing
config = {
    "paper_trading": True,
    "simulate_fills": True,
    "simulated_delay": 5.0  # seconds
}
```

**Requirements:**
- Simulate order fills based on order book
- Simulate market movements
- Log all simulated trades
- Compare performance metrics

---

## 9. Deployment Requirements

### 9.1 Infrastructure

**Recommended Setup:**
- **Server**: Linux VPS (minimum 2GB RAM, 2 CPU cores)
- **Location**: Close to Polymarket infrastructure (US East Coast)
- **Uptime**: 99.9% SLA
- **Monitoring**: Uptime monitoring + alerting

### 9.2 Process Management

**Use process manager for reliability:**
```bash
# Using systemd or supervisor
[program:polymarket_order_system]
command=/path/to/venv/bin/python main.py
directory=/path/to/project
autostart=true
autorestart=true
stderr_logfile=/var/log/polymarket/err.log
stdout_logfile=/var/log/polymarket/out.log
```

### 9.3 Backup and Recovery

**Required Backups:**
1. Order history database (daily)
2. Configuration files (on change)
3. Log files (weekly)
4. API credentials (encrypted, secure location)

**Recovery Procedure:**
1. Restore configuration and credentials
2. Restart system
3. Query exchange for open orders
4. Reconcile state
5. Resume monitoring

---

## 10. Security Requirements

### 10.1 Credential Management

- Store API keys in environment variables or secrets manager (never in code)
- Use separate API keys for testing vs. production
- Rotate API keys monthly
- Implement key expiration monitoring

### 10.2 Network Security

- Use HTTPS for all API communication
- Validate SSL certificates
- Implement IP whitelisting if supported by exchange
- Use VPN or private network when possible

### 10.3 Access Control

- Implement admin authentication for management interface
- Log all configuration changes with user attribution
- Require confirmation for high-value orders
- Implement emergency stop mechanism

---

## 11. User Interface Requirements

### 11.1 Command-Line Interface

**Required CLI Commands:**
```bash
# Add new order
python main.py add-order --market <id> --side BUY --size 1000 --price 0.45

# List active orders
python main.py list-orders

# Check order status
python main.py status --order-id <id>

# Cancel order
python main.py cancel --order-id <id>

# View metrics
python main.py metrics

# Emergency stop all
python main.py emergency-stop
```

### 11.2 Web Dashboard (Optional)

**Dashboard Features:**
- Real-time order status display
- Market conditions visualization
- Performance metrics charts
- Order history table
- Manual order addition form
- System health indicators

---

## 12. Success Criteria

The system is considered successful when:

1. **Functional Completeness:**
   - ✅ Orders can be added without interrupting monitoring
   - ✅ Iceberg strategy correctly splits and sequences tranches
   - ✅ Undercut detection and response works accurately
   - ✅ Overpriced orders are detected and replaced
   - ✅ All tranches eventually fill or timeout gracefully

2. **Performance Metrics:**
   - ✅ 95%+ of orders complete within urgency timeframe
   - ✅ Average execution price within 1¢ of target
   - ✅ System uptime > 99% during market hours
   - ✅ No API rate limit violations

3. **Reliability:**
   - ✅ Zero lost orders due to system failure
   - ✅ State recovers correctly after restart
   - ✅ All trades logged and reconcilable

4. **Safety:**
   - ✅ No orders exceed max_price/min_price
   - ✅ No unauthorized orders placed
   - ✅ Balance checks prevent over-trading

---

## 13. Future Enhancements

**Potential Future Features:**

1. **Advanced Strategies:**
   - TWAP (Time-Weighted Average Price)
   - VWAP (Volume-Weighted Average Price)
   - Participation rate targeting
   - Dark pool integration

2. **Machine Learning:**
   - Bot detection using ML models
   - Optimal tranche size prediction
   - Fill probability estimation
   - Market impact modeling

3. **Multi-Market:**
   - Correlated market trading
   - Cross-market arbitrage
   - Portfolio-level optimization

4. **Risk Management:**
   - Position limits per market
   - Daily loss limits
   - Exposure monitoring
   - Correlation risk analysis

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **Iceberg Order** | Large order split into smaller visible portions |
| **Tranche** | Individual portion of a split order |
| **Undercutting** | Placing order ahead in queue with better price |
| **CLOB** | Central Limit Order Book |
| **Maker** | Order that adds liquidity (passive) |
| **Taker** | Order that removes liquidity (aggressive) |
| **Spread** | Difference between best bid and best ask |
| **Fill** | Execution of an order or partial order |
| **Queue Priority** | Order of execution at same price level |

---

## Appendix B: Example Order Scenarios

### Scenario 1: Simple Iceberg Execution

```
Input:
- Total size: 500 shares
- Target price: $0.45
- Tranche size: 100
- Market: Stable, no competition

Expected Behavior:
1. Place 100 @ $0.45
2. Wait for fill
3. Place 100 @ $0.45
4. Wait for fill
5. Place 100 @ $0.45
6. Wait for fill
7. Place 100 @ $0.45
8. Wait for fill
9. Place 100 @ $0.45
10. Wait for fill
11. Order complete

Result: All tranches filled at $0.45
```

### Scenario 2: Heavy Undercutting

```
Input:
- Total size: 300 shares
- Target price: $0.45
- Max price: $0.50
- Tranche size: 100
- Urgency: MEDIUM

Market Events:
1. Place 100 @ $0.45
2. Bot places 10 @ $0.46 (undercut!)
3. Wait 30s (patience timeout)
4. Cancel our order
5. Place 100 @ $0.465 (match and improve)
6. Fills in 10s
7. Place 100 @ $0.465
8. Fills in 5s
9. Place 100 @ $0.465
10. Fills in 3s

Result: All filled at average $0.465 (1.5¢ worse than target)
```

### Scenario 3: Overpriced Order

```
Input:
- Total size: 200 shares
- Target price: $0.45
- Max price: $0.55
- Tranche size: 100

Market Events:
1. Place 100 @ $0.45
2. Market moves: best bid now $0.51, best ask $0.53
3. Detect overpricing (we're 6¢ behind)
4. Cancel order
5. Place 100 @ $0.525 (near spread)
6. Fills immediately
7. Place 100 @ $0.525
8. Fills immediately

Result: All filled at $0.525 (7.5¢ worse than target, but market moved)
```

---

## Appendix C: Configuration Examples

### Conservative Configuration (LOW urgency)

```yaml
strategy:
  default_urgency: "LOW"
  default_tranche_size: 30
  tranche_randomization: 0.3
  patience_timeout: 90
  max_adjustments: 2
  adjustment_step: 0.002
```

### Aggressive Configuration (HIGH urgency)

```yaml
strategy:
  default_urgency: "HIGH"
  default_tranche_size: 100
  tranche_randomization: 0.1
  patience_timeout: 10
  max_adjustments: 10
  adjustment_step: 0.01
  use_max_price_on_timeout: true
```

---

## Document Control

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2024-12-12 | Initial | Complete requirements specification |

---

**End of Requirements Document**
