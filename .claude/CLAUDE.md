# Polymarket Tools - AI Contributor Guide

This document provides context for AI assistants working on this codebase.

## Project Overview

Semi-automated trading tools for Polymarket prediction markets. The project uses Python with Pydantic for configuration management and py-clob-client for Polymarket API interaction.

## Configuration System

Configuration is managed through `src/config/settings.py` using Pydantic Settings.

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
2. Decrypted secrets file (`secrets.age` for `private_key` if env not set)
3. `.env` file (or environment-specific file)
4. Default values in the config class

### PolymarketConfig Fields

**Authentication:**
- `private_key` (required): Ethereum private key without `0x` prefix
  - API credentials are auto-generated from this key - no need to provide them manually

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

### Authentication

The system automatically generates API credentials from your private key when initializing the client. You only need to provide your private key - API credentials are derived on-the-fly using `client.create_or_derive_api_creds()`.

### Private Key Validation

The config automatically validates private keys:
- Strips `0x` prefix if present
- Ensures exactly 64 hex characters
- Validates hex format

## First Trade Script

Location: `scripts/examples/example2_track_order.py`

### Basic Flow

- Loads config via `load_config()`
- Initializes `PolymarketClient`
- Places a single order (unless `--skip-place` is used)
- Tracks fills until completion or timeout

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

# Note: API credentials are auto-generated from PRIVATE_KEY - no need to set them
```

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

## Development Guidelines

### When Adding New Configuration

1. Add fields to `PolymarketConfig` class in `src/config/settings.py`
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
