# Polymarket Tools - AI Contributor Guide

This document provides context for AI assistants working on this codebase.

## Project Overview

Semi-automated trading tools for Polymarket prediction markets. The project uses Python with Pydantic for configuration management and py-clob-client for Polymarket API interaction.

## Configuration System

Configuration is managed through `config/settings.py` using Pydantic Settings.

### Loading Configuration

```python
from config.settings import load_config

# Default: loads .env file
config = load_config()

# Explicit env file
config = load_config(".env.production")

# Environment-specific: ENV=staging loads .env.staging
config = load_config()
```

### Configuration Priority (highest to lowest)
1. System environment variables
2. `.env` file (or environment-specific file)
3. Default values in the config class

### PolymarketConfig Fields

**Authentication:**
- `private_key` (required): Ethereum private key without `0x` prefix
- `api_key`, `api_secret`, `api_passphrase` (optional): L2 API credentials for full trading

**Connection:**
- `host`: API endpoint (default: `https://clob.polymarket.com`)
- `chain_id`: Polygon chain ID (default: `137`)

**Proxy Wallet Settings:**
- `signature_type`: 0=EOA, 1=Email, 2=Browser (default: `0`)
- `funder_address`: Required for proxy wallets (signature_type 1 or 2)

### Environment Variable Naming

All config fields use `POLYMARKET_` prefix:
```bash
POLYMARKET_PRIVATE_KEY=abc123...
POLYMARKET_HOST=https://clob.polymarket.com
POLYMARKET_CHAIN_ID=137
POLYMARKET_SIGNATURE_TYPE=2
POLYMARKET_FUNDER_ADDRESS=0x...
```

### Authentication Levels

**L1 (Private Key Only):**
- Can create and sign orders
- Can derive API credentials
- Use `client.create_or_derive_api_creds()` to enable L2

**L2 (Private Key + API Credentials):**
- Full trading access
- Can post and cancel orders
- Requires API key, secret, and passphrase

Check auth level:
```python
config.get_auth_level()  # Returns "L1" or "L2"
config.has_l1_auth()     # True if private_key available
config.has_l2_auth()     # True if API creds available
```

### Private Key Validation

The config automatically validates private keys:
- Strips `0x` prefix if present
- Ensures exactly 64 hex characters
- Validates hex format

## First Trade Script

Location: `code/first_trade.py`

### Basic Flow

```python
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from config.settings import load_config

# 1. Load configuration
config = load_config()

# 2. Initialize client (Browser Wallet example - signature_type=2)
client = ClobClient(
    host=config.host,
    chain_id=config.chain_id,
    key=config.private_key,
    funder=config.funder_address,
    signature_type=2
)

# 3. Derive API credentials (upgrades L1 to L2 auth)
client.set_api_creds(client.create_or_derive_api_creds())

# 4. Create order arguments
order_args = OrderArgs(
    price=0.008,           # Price in dollars (0-1 range for binary markets)
    size=100.0,            # Number of shares
    side="SELL",           # "BUY" or "SELL"
    token_id="11430..."    # Market token ID (YES or NO outcome)
)

# 5. Create and sign order
signed_order = client.create_order(order_args)

# 6. Post order (GTC = Good-Till-Cancelled)
resp = client.post_order(signed_order, OrderType.GTC)
print(resp)
```

### Client Initialization Options

Choose one based on your wallet type:

**EOA (Externally Owned Account):**
```python
client = ClobClient(
    host=config.host,
    chain_id=config.chain_id,
    key=config.private_key,
    signature_type=0
)
```

**Email/Social Login Proxy:**
```python
client = ClobClient(
    host=config.host,
    chain_id=config.chain_id,
    key=config.private_key,
    funder=config.funder_address,
    signature_type=1
)
```

**Browser Wallet Proxy (MetaMask, Coinbase Wallet):**
```python
client = ClobClient(
    host=config.host,
    chain_id=config.chain_id,
    key=config.private_key,
    funder=config.funder_address,
    signature_type=2
)
```

### Order Arguments

- `price`: USD price per share (0-1 for binary markets)
- `size`: Number of shares to trade
- `side`: "BUY" or "SELL"
- `token_id`: Market outcome token ID (find via Polymarket API)

### Order Types

- `OrderType.GTC`: Good-Till-Cancelled (stays until filled or cancelled)
- `OrderType.FOK`: Fill-Or-Kill (must fill immediately or cancel)
- `OrderType.GTD`: Good-Till-Date (expires at specified time)

## Environment File Structure

Required variables in `.env`:

```bash
# Authentication (required)
POLYMARKET_PRIVATE_KEY=your_64_char_hex_private_key_without_0x

# Connection (optional - defaults provided)
POLYMARKET_HOST=https://clob.polymarket.com
POLYMARKET_CHAIN_ID=137

# Signature type (required if using proxy wallet)
POLYMARKET_SIGNATURE_TYPE=0  # 0=EOA, 1=Email, 2=Browser
POLYMARKET_FUNDER_ADDRESS=   # Required for signature_type 1 or 2

# L2 API Credentials (optional - can be derived)
POLYMARKET_API_KEY=
POLYMARKET_API_SECRET=
POLYMARKET_API_PASSPHRASE=
```

## Project Structure

```
polymarket-tools/
├── config/
│   ├── settings.py         # Main config (load_config function)
│   └── _settings.py        # Legacy/alternative config
├── core/
│   ├── first_trade.py      # Example trading script
│   └── _find_markets.py    # Market discovery utilities
├── _core/
│   ├── client.py           # API client wrapper
│   └── __init__.py
├── utils/
│   ├── logger.py           # Logging utilities
│   └── __init__.py
├── .env                    # Environment variables (git-ignored)
├── .env.example            # Template for .env
└── README.md               # User-facing documentation
```

## Development Guidelines

### When Adding New Configuration

1. Add fields to `PolymarketConfig` class in `config/settings.py`
2. Use Pydantic `Field` with description
3. Add validation if needed (use `@field_validator`)
4. Update `.env.example` with new variables
5. Document in this file

### When Modifying Trading Logic

1. Test with small amounts first
2. Validate all order parameters
3. Handle API errors gracefully
4. Log important events

### Security Notes

- Never log or print full private keys
- Never commit `.env` files
- Validate all user inputs
- Use test accounts for development

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

Token IDs are long numeric strings identifying specific market outcomes (YES/NO). Use Polymarket API or market URLs to find them.

## Useful Resources

- [Polymarket API Docs](https://docs.polymarket.com/)
- [py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)
- [Pydantic Settings Docs](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
