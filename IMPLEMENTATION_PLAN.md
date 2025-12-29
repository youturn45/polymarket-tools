# Polymarket Order Management System - Implementation Plan

## Document Information
- **Version**: 1.0
- **Date**: December 15, 2025
- **Purpose**: Phased implementation plan for the automated order execution system
- **Source Requirements**: See `req_docs.md` for full specification

---

## Overview

This document breaks down the implementation of the Polymarket Order Management System into 6 manageable phases. Each phase builds on the previous, allowing for incremental testing and validation.

**Key Principles:**
- Build vertically (complete flows) not horizontally (all features at once)
- Test with real API after each phase
- Keep it simple - add complexity only when basics work
- Write tests after completing each phase
- Review and validate before proceeding to next phase

---

## Phase 1: Foundation (Week 1-2)

### Goal
Build core infrastructure for placing and monitoring a single order.

### Components to Build

#### 1.1 Data Models (`models/`)
- [ ] `models/order.py` - Order data class with Pydantic validation
  - order_id, market_id, token_id
  - side, total_size, target_price, max_price, min_price
  - urgency, strategy_params
  - status, filled_amount, remaining_amount
  - timestamps (created_at, updated_at)

- [ ] `models/market.py` - Market conditions data class
  - best_bid, best_ask, spread
  - bid_depth, ask_depth
  - Basic metrics only (no complex calculations yet)

- [ ] `models/enums.py` - Type-safe enumerations
  - OrderSide (BUY, SELL)
  - OrderStatus (QUEUED, ACTIVE, PARTIALLY_FILLED, COMPLETED, CANCELLED, FAILED)
  - Urgency (LOW, MEDIUM, HIGH)

#### 1.2 API Wrapper (`api/`)
- [ ] `api/polymarket_client.py` - Wrap py-clob-client
  - Initialize client with config
  - place_order() method
  - get_order_status() method
  - cancel_order() method
  - Basic error handling with try/except
  - Simple retry logic (3 attempts)

#### 1.3 Configuration (`config/`)
- [ ] Extend existing `config/settings.py`
  - Add strategy defaults (tranche_size, timeouts)
  - Add monitoring intervals
  - Keep using existing Pydantic setup

#### 1.4 Logging (`utils/`)
- [ ] `utils/logger.py` - Structured logging setup
  - Use Python's logging module
  - JSON structured logs
  - Log levels: DEBUG, INFO, WARNING, ERROR
  - Log to file and console

#### 1.5 Simple Executor (`core/`)
- [ ] `core/order_executor.py` - Basic order execution
  - execute_single_order() function
  - Place order via API
  - Poll status every 2 seconds
  - Wait for fill or timeout (60s)
  - Log all events

### Success Criteria
- ✅ Place one order successfully
- ✅ Poll and detect when order is filled
- ✅ Log entire lifecycle to structured logs
- ✅ Handle basic API errors gracefully
- ✅ All code follows existing project patterns

### Testing
- Manual test: Place 10 shares @ market price, verify fill
- Unit tests: Validate order model validation rules
- Integration test: End-to-end single order execution

### Files to Create
```
models/
  __init__.py
  order.py
  market.py
  enums.py
api/
  __init__.py
  polymarket_client.py
core/
  __init__.py
  order_executor.py
```

---

## Phase 2: Iceberg Strategy (Week 2-3)

### Goal
Split large orders into sequential tranches with basic randomization.

### Components to Build

#### 2.1 Strategy Engine (`strategies/`)
- [ ] `strategies/iceberg.py` - Iceberg splitting logic
  - calculate_next_tranche_size()
  - Apply size randomization (±20%)
  - Respect min/max tranche bounds
  - Ensure doesn't exceed remaining size

#### 2.2 Enhanced Order Executor
- [ ] Extend `core/order_executor.py`
  - execute_iceberg_order() function
  - Loop: place tranche → wait for fill → next tranche
  - Track cumulative fills across tranches
  - Update order status after each tranche
  - Add inter-tranche delay (1-3s randomized)

#### 2.3 Fill Tracking
- [ ] `core/fill_tracker.py` - Track fills across tranches
  - Record each tranche's fill details
  - Calculate total filled amount
  - Calculate remaining amount
  - Calculate average fill price

### Success Criteria
- ✅ Split 1000 shares into 5 tranches of ~200 each
- ✅ Execute tranches sequentially (wait for fill)
- ✅ Track cumulative fills accurately
- ✅ Randomize tranche sizes within bounds
- ✅ Complete full order or stop on partial fill timeout

### Testing
- Test: 500 shares split into tranches, verify sequential execution
- Test: Verify tranche sizes vary within randomization bounds
- Test: Verify cumulative tracking is accurate

### Files to Modify/Create
```
strategies/
  __init__.py
  iceberg.py
core/
  order_executor.py (extend)
  fill_tracker.py (new)
```

---

## Phase 3: Market Monitoring (Week 3-4)

### Goal
Add real-time market awareness to detect competitive conditions.

### Components to Build

#### 3.1 Market Monitor (`core/`)
- [ ] `core/market_monitor.py` - Market state tracking
  - get_order_book() - Fetch current order book
  - get_best_bid_ask() - Extract best prices
  - calculate_spread() - Compute bid-ask spread
  - get_market_depth() - Size at best prices
  - Poll every 2 seconds initially

#### 3.2 Enhanced Market Conditions
- [ ] Extend `models/market.py`
  - Add our_position_in_queue
  - Add time_at_current_price
  - Add methods to detect competitive scenarios

#### 3.3 Basic Undercut Detection
- [ ] `strategies/detection.py` - Competitive detection
  - is_undercut() - Check if someone ahead at better price
  - calculate_undercut_margin() - How much better is their price
  - Simple threshold: 1¢ = undercut

#### 3.4 Integration with Executor
- [ ] Update `core/order_executor.py`
  - Check market conditions during tranche monitoring
  - Log when undercuts detected
  - Don't respond yet (just detect and log)

### Success Criteria
- ✅ Poll order book every 2s while order is live
- ✅ Accurately detect best bid/ask
- ✅ Detect when another order undercuts us
- ✅ Log market conditions with each check
- ✅ Continue execution (detection only, no response)

### Testing
- Test: Verify order book parsing is correct
- Test: Simulate undercut scenario, verify detection
- Test: Verify market data updates during execution

### Files to Create/Modify
```
core/
  market_monitor.py (new)
  order_executor.py (extend)
models/
  market.py (extend)
strategies/
  detection.py (new)
```

---

## Phase 4: Adaptive Pricing (Week 4-5)

### Goal
Respond to market conditions by adjusting prices dynamically.

### Components to Build

#### 4.1 Pricing Strategies (`strategies/`)
- [ ] `strategies/pricing.py` - Dynamic pricing logic
  - respond_to_undercut() - Calculate competitive price
  - detect_overpriced() - Check if our price is stale
  - calculate_competitive_price() - Target near best bid/ask
  - Respect max_price/min_price limits

#### 4.2 Price Adjustment Execution
- [ ] Extend `core/order_executor.py`
  - adjust_order_price() - Cancel and replace atomically
  - Wait for cancel confirmation
  - Place new order at adjusted price
  - Update order tracking with new ID

#### 4.3 Urgency Parameters
- [ ] `config/urgency.py` - Urgency-based parameters
  - LOW: 60s patience, 3 max adjustments, 0.3¢ steps
  - MEDIUM: 30s patience, 5 adjustments, 0.5¢ steps
  - HIGH: 10s patience, 10 adjustments, 1¢ steps

#### 4.4 Decision Engine
- [ ] `strategies/adaptation.py` - Decide when to adjust
  - should_adjust_price() - Check all conditions
  - Heavy undercut: margin >= 1¢
  - Timeout: elapsed > patience_timeout
  - Max adjustments: count < max_adjustments
  - Return Action: WAIT, INCREASE_BID, DECREASE_ASK

### Success Criteria
- ✅ Detect heavy undercutting (1¢ or more)
- ✅ Cancel and replace order at competitive price
- ✅ Respect max_price limits (never exceed)
- ✅ Apply urgency-based patience timeouts
- ✅ Limit number of adjustments per tranche

### Testing
- Test: Place order, simulate undercut, verify adjustment
- Test: Verify max_price is never exceeded
- Test: Verify different urgency levels have different timeouts
- Test: Verify stops adjusting after max_adjustments reached

### Files to Create/Modify
```
strategies/
  pricing.py (new)
  adaptation.py (new)
config/
  urgency.py (new)
core/
  order_executor.py (extend with adjustment logic)
```

---

## Phase 5: Concurrent Orders (Week 5-6)

### Goal
Support multiple simultaneous orders across different markets.

### Components to Build

#### 5.1 Order Queue Manager (`core/`)
- [ ] `core/order_manager.py` - Thread-safe order queue
  - asyncio.Queue for order queue
  - add_order() - Returns order_id immediately
  - Worker pool to process orders concurrently
  - get_order_status() - Query by order_id
  - cancel_order() - Request cancellation
  - Order state dictionary (thread-safe)

#### 5.2 Async Execution
- [ ] Convert `core/order_executor.py` to async
  - async def execute_iceberg_order()
  - Use asyncio.sleep() instead of time.sleep()
  - Support concurrent execution
  - Each order runs in separate coroutine

#### 5.3 Market Monitor Pool
- [ ] Extend `core/market_monitor.py`
  - Support monitoring multiple markets simultaneously
  - Shared market data cache
  - Async data fetching

#### 5.4 State Management
- [ ] `core/state_manager.py` - In-memory state
  - Track all active orders
  - Thread-safe updates
  - Query order status by ID
  - List all orders

### Success Criteria
- ✅ Add multiple orders without blocking
- ✅ Execute 3+ orders concurrently on different markets
- ✅ Query status of any order by ID
- ✅ Cancel in-flight orders gracefully
- ✅ No race conditions or deadlocks

### Testing
- Test: Add 5 orders rapidly, verify all queued
- Test: Execute 3 orders concurrently, verify no interference
- Test: Cancel order mid-execution, verify graceful stop
- Test: Query status while orders executing

### Files to Create/Modify
```
core/
  order_manager.py (new)
  order_executor.py (convert to async)
  market_monitor.py (extend for concurrent)
  state_manager.py (new)
```

---

## Phase 6: Production Hardening (Week 6+)

### Goal
Make system production-ready with robustness, persistence, and monitoring.

### Components to Build

#### 6.1 WebSocket Streams (`api/`)
- [ ] `api/websocket_client.py` - Real-time data
  - Subscribe to orderbook channel
  - Subscribe to user_orders channel
  - Subscribe to trades channel
  - Fallback to polling if WebSocket fails
  - Auto-reconnect on disconnect

#### 6.2 State Persistence (`storage/`)
- [ ] `storage/database.py` - SQLite storage
  - Orders table (full order history)
  - Fills table (individual fill records)
  - Market snapshots table
  - Save order state periodically
  - Load state on startup

#### 6.3 Error Recovery
- [ ] Extend error handling throughout
  - Exponential backoff on API errors
  - Retry logic with jitter
  - Graceful degradation (WebSocket → polling)
  - Reconcile state with exchange after reconnect

#### 6.4 CLI Interface (`cli/`)
- [ ] `cli/commands.py` - Command-line interface
  - add-order command
  - list-orders command
  - status command
  - cancel command
  - metrics command
  - emergency-stop command

#### 6.5 Safety Checks
- [ ] `core/safety.py` - Pre-trade validation
  - Check balance before trading
  - Validate market exists
  - Verify token IDs are valid
  - Check spread isn't too wide
  - Confirm large orders (> $1000)

#### 6.6 Monitoring & Metrics
- [ ] `utils/metrics.py` - Performance tracking
  - Track execution times
  - Track fill rates
  - Track price adjustments
  - Track API errors
  - Export metrics for analysis

### Success Criteria
- ✅ System runs for 24h without manual intervention
- ✅ Survives network disconnections
- ✅ State persists across restarts
- ✅ CLI interface is intuitive and complete
- ✅ All safety checks prevent bad trades
- ✅ Comprehensive logs and metrics available

### Testing
- Test: Disconnect network, verify graceful reconnect
- Test: Restart system, verify state recovery
- Test: Attempt unsafe trade, verify rejection
- Test: Run for 24h, verify stability

### Files to Create
```
api/
  websocket_client.py
storage/
  __init__.py
  database.py
cli/
  __init__.py
  commands.py
core/
  safety.py
utils/
  metrics.py
```

---

## Implementation Guidelines

### Code Standards
- Follow existing project patterns (see `CLAUDE.md`)
- Use Pydantic for all data models
- Use Python 3.10+ features
- Type hints on all functions
- Docstrings on all public functions
- Keep functions small (<50 lines)

### Testing Strategy
- Unit tests for pure logic (calculations, validations)
- Integration tests for API interactions
- End-to-end tests for full order flows
- Use testnet for integration tests
- Small amounts on mainnet for validation

### Review Points
- End of each phase: Review code, run tests, validate behavior
- Before starting new phase: Ensure previous phase is solid
- Don't rush: Better to have 3 working phases than 6 broken ones

### Logging Strategy
- Log all order lifecycle events
- Log all market condition checks
- Log all price adjustments with reasoning
- Structured JSON logs for analysis
- Include timestamps, order_id, market_id in all logs

---

## Project Structure (Final)

```
polymarket-tools/
├── config/
│   ├── settings.py         # Main config (existing)
│   └── urgency.py          # Urgency parameters
├── models/
│   ├── __init__.py
│   ├── order.py           # Order data models
│   ├── market.py          # Market data models
│   └── enums.py           # Type enums
├── api/
│   ├── __init__.py
│   ├── polymarket_client.py  # API wrapper
│   └── websocket_client.py   # WebSocket handler (Phase 6)
├── core/
│   ├── __init__.py
│   ├── order_manager.py    # Order queue (Phase 5)
│   ├── order_executor.py   # Execution engine
│   ├── market_monitor.py   # Market monitoring (Phase 3)
│   ├── fill_tracker.py     # Fill tracking (Phase 2)
│   ├── state_manager.py    # State management (Phase 5)
│   └── safety.py           # Safety checks (Phase 6)
├── strategies/
│   ├── __init__.py
│   ├── iceberg.py         # Iceberg logic (Phase 2)
│   ├── detection.py       # Competitive detection (Phase 3)
│   ├── pricing.py         # Dynamic pricing (Phase 4)
│   └── adaptation.py      # Adaptation logic (Phase 4)
├── storage/
│   ├── __init__.py
│   └── database.py        # Persistence (Phase 6)
├── cli/
│   ├── __init__.py
│   └── commands.py        # CLI interface (Phase 6)
├── utils/
│   ├── __init__.py
│   ├── logger.py          # Logging setup (Phase 1)
│   └── metrics.py         # Performance metrics (Phase 6)
├── tests/
│   ├── __init__.py
│   ├── test_models.py
│   ├── test_iceberg.py
│   ├── test_pricing.py
│   └── test_integration.py
├── .env                   # Configuration
├── req_docs.md           # Requirements
├── IMPLEMENTATION_PLAN.md # This file
└── README.md             # User documentation
```

---

## Current Status

**Current Phase**: Phase 3 Complete ✅
**Next Step**: Begin Phase 4 - Adaptive Pricing

### Phase Completion Tracking

- [x] Phase 1: Foundation (Week 1-2) - **COMPLETED 2025-12-15**
- [x] Phase 2: Iceberg Strategy (Week 2-3) - **COMPLETED 2025-12-26**
- [x] Phase 3: Advanced Strategies (Revised) - **COMPLETED 2025-12-29**
- [ ] Phase 4: Adaptive Pricing (Week 4-5)
- [ ] Phase 5: Concurrent Orders (Week 5-6)
- [ ] Phase 6: Production Hardening (Week 6+)

### Phase 1 Summary (Completed 2025-12-15)

**Files Created:**
- `models/enums.py` - OrderSide, OrderStatus, Urgency enums
- `models/order.py` - Order and StrategyParams data models
- `models/market.py` - MarketConditions data model
- `api/polymarket_client.py` - API wrapper with retry logic
- `core/order_executor.py` - Single order execution engine
- `utils/logger.py` - Enhanced with JSON structured logging
- `examples/phase1_demo.py` - Demo script
- `tests/test_enums.py` - Enum tests (3 tests)
- `tests/test_models.py` - Model tests (9 tests)

**Test Coverage:**
- 12 tests passing
- All data models validated
- Pydantic validation working correctly

**Success Criteria Met:**
- ✅ Data models created with full validation
- ✅ API client wrapper with error handling and retries
- ✅ Order executor can place and monitor single orders
- ✅ Structured logging in place
- ✅ All code follows project patterns

**Ready for Phase 2:** Iceberg order splitting

### Notes
- Phase 1 completed in single session
- No blockers encountered
- Test hooks working correctly

### Phase 3 Summary (Completed 2025-12-29)

**Note:** Phase 3 was revised from the original "Market Monitoring" plan to implement advanced strategies and daemon infrastructure based on user requirements.

**Files Created:**
- `models/order_request.py` - OrderRequest, StrategyType, MicroPriceParams, KellyParams
- `core/market_monitor.py` - Market monitoring with micro-price calculation
- `strategies/micro_price.py` - Micro-price adaptive strategy
- `strategies/kelly.py` - Kelly criterion position sizing strategy
- `core/order_daemon.py` - Asynchronous order queue daemon
- `examples/phase3_demo.py` - Comprehensive demo script
- `tests/test_strategy_router.py` - Router tests (4 tests)
- `tests/test_market_monitor.py` - Market monitor tests (17 tests)
- `tests/test_micro_price.py` - Micro-price strategy tests (13 tests)
- `tests/test_kelly.py` - Kelly strategy tests (13 tests)
- `tests/test_order_daemon.py` - Order daemon tests (14 tests)
- `tests/test_phase3_demo.py` - Demo script test (1 test)

**Files Modified:**
- `models/market.py` - Extended with MarketSnapshot class
- `strategies/router.py` - Implemented micro-price and Kelly strategies

**Test Coverage:**
- 62 new tests passing
- Total: 117 tests passing
- All strategies fully tested
- Integration tests for daemon

**Key Features Implemented:**
1. **Order Daemon**
   - Asynchronous queue-based order management
   - Concurrent order processing
   - Order status tracking and history
   - Graceful start/stop with context manager support

2. **Market Monitor**
   - Real-time order book monitoring
   - Micro-price calculation: `(best_bid × ask_size + best_ask × bid_size) / (bid_size + ask_size)`
   - Threshold band calculation in basis points
   - Price competitiveness checking

3. **Micro-Price Strategy**
   - Adaptive order placement near fair value
   - Continuous market monitoring
   - Automatic order replacement when out of bounds
   - Aggression limit to avoid over-paying
   - Configurable thresholds and check intervals

4. **Kelly Criterion Strategy**
   - Optimal position sizing based on win probability
   - Dynamic size calculation: `f* = (bp - q) / b`
   - Fractional Kelly support (e.g., quarter Kelly)
   - Position recalculation as prices change
   - Integrated with micro-price for execution

5. **Strategy Router**
   - Routes orders to appropriate strategy
   - Supports ICEBERG, MICRO_PRICE, and KELLY strategies
   - Creates market monitors per token
   - Handles strategy-specific parameters

**Success Criteria Met:**
- ✅ Order daemon with asynchronous queue
- ✅ Micro-price calculation and monitoring
- ✅ Micro-price adaptive strategy with automatic replacement
- ✅ Kelly criterion position sizing
- ✅ Strategy selection and routing
- ✅ Comprehensive test coverage
- ✅ Demo scripts with examples

**Ready for Phase 4:** The system now has advanced strategies and daemon infrastructure. Next phase can focus on additional features like adaptive pricing optimization or production hardening.

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-12-15 | Initial implementation plan created |

---

**Ready to start Phase 1?** Review the Foundation phase components and begin with data models.
