# Polymarket Tools

Semi-automated trading tools for Polymarket prediction markets with Kelly criterion position sizing, micro-price tracking, and 24-hour monitoring.

## Features

- **Kelly Criterion Sizing**: Optimal position sizing based on win probability and bankroll
- **Micro-Price Tracking**: Depth-weighted fair value pricing
- **24-Hour Monitoring**: Automatic rebalancing when prices move
- **Portfolio Tracking**: Real-time positions and order monitoring
- **Event-Driven Architecture**: Async order execution with event bus
- **Multiple Strategies**: Iceberg, micro-price, and Kelly strategies

## Quick Start

1. **Install dependencies:**
```bash
uv pip install -e .
```

2. **Configure environment:**
```bash
cp .env.example .env
# Edit .env with your credentials
```

3. **Run your first order:**
```bash
python scripts/examples/example3_kelly_micro_price_order.py \
    --token-id YOUR_TOKEN_ID \
    --side BUY \
    --win-prob 0.60 \
    --bankroll 1000 \
    --kelly-fraction 0.25 \
    --monitor-hours 24.0
```

## Configuration

### Environment Variables

Create a `.env` file with the following:

```bash
# Required: Your Ethereum private key (without 0x prefix)
POLYMARKET_PRIVATE_KEY=your_64_character_hex_private_key

# Optional: Connection settings (defaults shown)
POLYMARKET_HOST=https://clob.polymarket.com
POLYMARKET_CHAIN_ID=137

# Signature Type:
# 0 = EOA (Externally Owned Account) - standard wallet
# 1 = Email/Social Login Proxy
# 2 = Browser Wallet Proxy (MetaMask, Coinbase Wallet)
POLYMARKET_SIGNATURE_TYPE=0

# Required for proxy wallets (signature_type 1 or 2):
POLYMARKET_FUNDER_ADDRESS=

# Note: API credentials are automatically generated from your private key
```

### Configuration Priority

Configuration values are loaded in this order (highest to lowest):
1. **System environment variables** (best for production)
2. **Decrypted secrets file** (`secrets.age` for `private_key` if env not set)
3. **Environment-specific .env file** (.env.production, .env.staging)
4. **Default .env file** (local development)
5. **Hardcoded defaults** (fallback values)

### Loading Configuration

```python
from config.settings import load_config

# Load default .env
config = load_config()

# Load specific environment file
config = load_config(".env.production")

# Use environment-specific file (ENV=staging loads .env.staging)
import os
os.environ['ENV'] = 'staging'
config = load_config()
```

### Multi-Environment Setup

```
your_project/
├── .env                    # Local dev (gitignored)
├── .env.example           # Template (committed)
├── .env.development       # Dev environment (gitignored)
├── .env.staging          # Staging (gitignored)
├── .env.production       # Production (gitignored)
└── .gitignore            # Ignore all .env except .env.example
```

**Usage Patterns:**

```bash
# Local development (uses .env)
python your_script.py

# Staging environment (uses .env.staging)
export ENV=staging
python your_script.py

# Production (uses system environment variables)
export POLYMARKET_PRIVATE_KEY=abc123...
export POLYMARKET_SIGNATURE_TYPE=0
python your_script.py
```

## Examples

### Example 1: Run Monitors
Monitor market data and portfolio in real-time:
```bash
python scripts/examples/example1_run_monitors.py --token-id YOUR_TOKEN_ID
```

### Example 2: Track Order
Place and track a simple order:
```bash
python scripts/examples/example2_track_order.py --token-id YOUR_TOKEN_ID
```

### Example 3: Kelly Strategy with 24h Monitoring
Advanced Kelly criterion trading with automatic rebalancing:
```bash
python scripts/examples/example3_kelly_micro_price_order.py \
    --token-id YOUR_TOKEN_ID \
    --side BUY \
    --win-prob 0.60 \
    --bankroll 1000 \
    --kelly-fraction 0.25 \
    --monitor-hours 24.0 \
    --price-threshold 0.05
```

This will:
- Calculate optimal position size using Kelly criterion
- Place initial order at micro-price (depth-weighted fair value)
- Monitor position for 24 hours
- Automatically rebalance when:
  - Price moves ≥5% from reference price
  - Position deviates ≥10% from optimal Kelly size
  - Every 15 minutes (periodic check)

## First Trade

Use the tracked order example:
```bash
python scripts/examples/example2_track_order.py \
    --token-id YOUR_TOKEN_ID \
    --side BUY \
    --price 0.50 \
    --size 100
```

## Architecture

### Core Components

- **`src/config/`** - Configuration management with Pydantic
- **`src/core/`** - Core trading infrastructure
  - `order_daemon.py` - Async order queue and execution
  - `portfolio_monitor.py` - Real-time position and order tracking
  - `kelly_monitor_daemon.py` - 24-hour Kelly position monitoring
  - `market_monitor.py` - Micro-price calculation and tracking
  - `event_bus.py` - Event-driven messaging
- **`src/strategies/`** - Trading strategies
  - `kelly.py` - Kelly criterion position sizing
  - `micro_price.py` - Micro-price based execution
  - `iceberg.py` - Iceberg order execution
- **`src/models/`** - Data models and enums
- **`scripts/examples/`** - Example scripts and usage patterns

### Event-Driven Design

The system uses an event bus for loose coupling:
- Orders emit events like QUEUED, STARTED, ACTIVE, PARTIALLY_FILLED, FILLED, CANCELLED, COMPLETED, FAILED, REPLACED, UNDERCUT
- Portfolio monitor updates in background (10s polling)
- Kelly monitor checks positions (60s interval)
- All components communicate via events

## Security Best Practices

- **Never commit `.env` files** (already in `.gitignore`)
- **Private key format**: 64 hex characters without `0x` prefix
- **Test first**: Always test with small amounts
- **Separate wallets**: Use dedicated test wallets for development
- **Key rotation**: Rotate API keys regularly
- **Production secrets**: Use AWS Secrets Manager, HashiCorp Vault, or K8s secrets for production

## Finding Token IDs

Token IDs are long numeric strings identifying specific market outcomes (YES/NO). Find them via:

1. **Polymarket API**: https://gamma-api.polymarket.com/events/slug/MARKET_SLUG
2. **Market URLs**: Extract from Polymarket market pages
3. **Example token ID**: `62595435619678438799673612599999067112702849851098967060818869994133628780778`

## Resources

- [Polymarket API Documentation](https://docs.polymarket.com/)
- [py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)
- [Pydantic Settings Docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
- [AI Contributors Guide](.claude/CLAUDE.md)

## License

MIT
