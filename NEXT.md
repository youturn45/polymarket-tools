You need to review the market monitor changes to make sure items are reflected correctly.

python src/utils/gamma_parse.py khamenei-out-as-supreme-leader-of-iran-by-january-31

---

## Kelly Strategy Bot Revamp

### Summary

Create a self-contained Kelly trading bot with a single async loop that monitors a token's order book every 10s, calculates position size using Kelly criterion with enforced guardrails, and places/cancels/replaces orders as the micro-price moves -- all while tracking existing positions to avoid oversizing.

### New Files to Create

#### 1. `src/strategies/kelly_sizing.py` -- Pure Kelly math with guardrails

Pure functions, no side effects, no API calls.

**Hardcoded guardrails (not configurable):**
- `MAX_EDGE = 0.10` -- If calculated edge > 10%, cap it at 10% for sizing
- `MAX_WIN_PROBABILITY = 0.99` -- Clamp win probability before calculation
- `KELLY_MULTIPLIER = 0.25` -- Always quarter Kelly

**Functions:**
- `calculate_edge(win_prob, market_price, side)` -- Returns edge as decimal
- `calculate_kelly_fraction(win_prob, market_price, side)` -- Clamps inputs, caps edge, applies 1/4 kelly, returns fraction [0, 0.25]
- `calculate_position_size(kelly_fraction, bankroll, price, max_position)` -- Converts fraction to shares
- `calculate_incremental_size(optimal_total, held_shares, pending_shares)` -- Returns `max(0, optimal - held - pending)`

#### 2. `src/strategies/kelly_bot.py` -- Self-contained bot

Single class with one `async run()` loop.

**Config model** (`KellyBotConfig`):
- `token_id`, `side`, `win_probability`, `bankroll`, `max_position_size`
- `poll_interval=10.0`, `replace_threshold_pct=0.005` (0.5% micro-price drift triggers cancel/replace)
- `depth_levels=5`, `band_width_bps=50`

**Core loop (each 10s tick):**
1. Fetch market snapshot (5 levels) via `MarketMonitor.get_market_snapshot()`
2. Get held shares + pending shares from `PortfolioMonitor`
3. Calculate kelly fraction with guardrails via `kelly_sizing`
4. Calculate incremental size needed
5. If active order exists and micro-price drifted > threshold: cancel, recalculate with pending=0, place new
6. If no active order and incremental > 0: place order
7. If active order and no drift: check fills, log status
8. Sleep 10s

**Dependencies:** `PolymarketClient`, `PortfolioMonitor` (injected), `MarketMonitor` (created internally)

#### 3. `scripts/examples/run_kelly_bot.py` -- Runner script

CLI args: `--token-id`, `--side`, `--win-prob`, `--bankroll`, `--max-position`
No `--kelly-fraction` arg (always 1/4 kelly, hardcoded).

Wires: `load_config()` -> `PolymarketClient` -> `PortfolioMonitor` -> `KellyBot` -> `run()`

#### 4. `tests/unit/test_kelly_sizing.py` -- Tests for Kelly math

Table-driven tests covering:
- Normal edge produces positive fraction <= 0.25
- No edge returns 0
- Edge > 10% gets capped (not refused), still produces a bet sized at 10% edge
- Win prob > 99% clamped to 99%
- Position-aware incremental calculation
- Already at optimal returns 0
- Over optimal returns 0 (not negative)

### Files to Modify

#### `src/strategies/router.py`
- Remove import of `KellyStrategy` (from deleted `kelly.py`)
- Remove import of `MicroPriceStrategy` (from deleted `micro_price.py`)
- Remove `_execute_kelly` and `_execute_micro_price` methods
- Keep only ICEBERG routing

#### `src/models/order_request.py`
- Remove `KellyParams`, `KellyMonitorParams`, `MicroPriceParams` classes
- Remove `StrategyType.KELLY` and `StrategyType.MICRO_PRICE` enum values
- Remove `kelly_params` and `micro_price_params` fields from `OrderRequest`
- Remove related validation in `validate_strategy_params()` and `model_post_init()`

### Files to Delete

| File | Reason |
|------|--------|
| `src/strategies/kelly.py` | Replaced by `kelly_sizing.py` + `kelly_bot.py` |
| `src/strategies/micro_price.py` | Cancel/replace logic folded into `kelly_bot.py` |
| `src/utils/kelly_calculator.py` | Consolidated into `kelly_sizing.py` |
| `src/core/kelly_monitor_daemon.py` | Replaced by `kelly_bot.py`'s built-in loop |
| `scripts/examples/example3_kelly_micro_price_order.py` | Replaced by `run_kelly_bot.py` |

**Keep untouched:** `event_bus.py`, `order_daemon.py`, `order_executor.py`, `portfolio_monitor.py`, `market_monitor.py`, `polymarket_client.py`

### Key Design Decisions

1. **Guardrails in math layer, not config** -- Max edge, max probability, and quarter kelly are constants in `kelly_sizing.py`, not user-configurable parameters. Prevents accidental misconfiguration.

2. **Edge capped, not refused** -- If edge > 10%, cap it at 10% for Kelly sizing. The bot still bets, just conservatively.

3. **Single loop, no daemons** -- One async loop instead of wiring 4 separate daemons (EventBus, OrderDaemon, KellyMonitorDaemon, PortfolioMonitor). Simpler, easier to debug, fewer race conditions.

4. **Position-aware via PortfolioMonitor** -- Reuses existing `get_positions_snapshot()` and `get_orders_snapshot()`. On cancel, recalculates with pending=0. Example: Kelly says 300 shares, holding 200, only orders 100.

5. **Sync API calls wrapped in `asyncio.to_thread()`** -- `PolymarketClient` methods are synchronous; bot wraps them to avoid blocking the event loop.

### Cancel/Replace Flow

The bot tracks exactly one exchange order ID at a time.

**Trigger:** micro-price has drifted > `replace_threshold_pct` (default 0.5%) from the price at which the active order was placed.

**Sequence per loop tick:**
1. Detect micro-price drift
2. Cancel active order via `asyncio.to_thread(client.cancel_order, order_id)`
3. Reset state (active_order_id = None)
4. Recalculate incremental with pending=0 (since we just cancelled)
5. If incremental > 0, place new order at current micro-price
6. Store new order ID and price for next drift check

### Verification

1. Run `pytest tests/unit/test_kelly_sizing.py` -- all guardrail tests pass
2. Run `python scripts/examples/run_kelly_bot.py --help` -- verify CLI args
3. Run bot against a real token with small bankroll, verify:
   - Fetches order book every 10s with 5 levels
   - Logs micro-price, kelly fraction, position info
   - Places initial order
   - Cancels/replaces when micro-price drifts
   - Accounts for held positions in sizing

### Execution Command

```
# To implement this plan, ask Claude:
# "Implement the Kelly bot revamp plan from NEXT.md"
```