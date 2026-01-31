# System Design

## Overview

Semi-automated trading tools for Polymarket prediction markets. The system uses Python with
Pydantic for configuration management and `py-clob-client` for Polymarket API interaction.

## Core Components

- `src/api/`: Polymarket client wrapper and retry logic
- `src/config/`: Settings and secrets handling
- `src/core/`: Daemons, monitors, event bus, and execution loop
- `src/strategies/`: Trading strategies (Kelly, micro-price, iceberg)
- `src/models/`: Data models and enums
- `src/dashboard/`: Flask dashboard
- `src/utils/`: Utility scripts and helpers
- `scripts/examples/`: Example flows for orders and monitoring

## Project Structure

```
polymarket-tools/
├── .claude/                # Claude instructions and metadata
├── docs/                   # Product and technical docs
├── scripts/                # Utility scripts and examples
├── src/                    # Source code
│   ├── api/                # Polymarket client wrapper
│   ├── config/             # Settings + secrets handling
│   ├── core/               # Daemons, monitors, and execution
│   ├── dashboard/          # Flask dashboard
│   ├── models/             # Pydantic data models
│   ├── strategies/         # Trading strategies
│   └── utils/              # Shared helpers
├── tests/                  # Test suite
├── .env                    # Environment variables (git-ignored)
├── .env.example            # Template for .env
└── README.md               # User-facing documentation
```

## Key Flows

### First Trade Script

Location: `scripts/examples/example2_track_order.py`

Basic flow:
- Loads config via `load_config()`
- Initializes `PolymarketClient`
- Places a single order (unless `--skip-place` is used)
- Tracks fills until completion or timeout

### Order Arguments

- `price`: USD price per share (0-1 for binary markets)
- `size`: Number of shares to trade
- `side`: "BUY" or "SELL"
- `token_id`: Market outcome token ID (find via Polymarket API)

### Order Types

- `OrderType.GTC`: Good-Till-Cancelled (stays until filled or cancelled)
- `OrderType.FOK`: Fill-Or-Kill (must fill immediately or cancel)
- `OrderType.GTD`: Good-Till-Date (expires at specified time)

## Common Patterns

### Error Handling for Orders

```python
try:
    resp = client.post_order(signed_order, OrderType.GTC)
    print(f"Order posted: {resp}")
except Exception as e:
    print(f"Order failed: {e}")
    # Handle specific error types
```

### Checking Balances Before Trading

```python
# Get balance for specific token
balance = client.get_balance(token_id)
print(f"Available: {balance}")
```

### Finding Token IDs

Token IDs are long numeric strings identifying specific market outcomes (YES/NO). Use Polymarket
API or market URLs to find them.

## Development Guidelines

### When Adding New Configuration

1. Add fields to `PolymarketConfig` in `src/config/settings.py`
2. Use Pydantic `Field` with description
3. Add validation if needed (use `@field_validator`)
4. Update `.env.example` with new variables
5. Document in `docs/CONFIG.md`

### When Modifying Trading Logic

1. Test with small amounts first
2. Validate all order parameters
3. Handle API errors gracefully
4. Log important events
