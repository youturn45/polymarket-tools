# Configuration

Configuration lives in `src/config/settings.py` and uses Pydantic Settings with an optional
`secrets.age` fallback for the private key.

## Loading Configuration

```python
from config.settings import load_config

# Default: loads .env or .env.{ENV} if present
config = load_config()

# Explicit env file (also sets ENV_FILE)
config = load_config(".env.production")
```

## Priority Order (highest to lowest)

1. System environment variables
2. Decrypted secrets file (`secrets.age` for `private_key` if env not set)
3. `.env` file (or `.env.{ENV}` if it exists)
4. Default values in the config class

## PolymarketConfig Fields

**Authentication**
- `private_key` (required): Ethereum private key without `0x` prefix
  - API credentials are auto-generated from this key

**Connection**
- `host`: API endpoint (default: `https://clob.polymarket.com`)
- `chain_id`: Polygon chain ID (default: `137`)

**Proxy Wallet Settings**
- `signature_type`: 0=EOA, 1=Email, 2=Browser (default: `0`)
- `funder_address`: Required for proxy wallets (signature_type 1 or 2)

## Environment Variable Naming

All config fields use the `POLYMARKET_` prefix:

```bash
POLYMARKET_PRIVATE_KEY=abc123...
POLYMARKET_HOST=https://clob.polymarket.com
POLYMARKET_CHAIN_ID=137
POLYMARKET_SIGNATURE_TYPE=2
POLYMARKET_FUNDER_ADDRESS=0x...
```

## Secrets Decryption

If `POLYMARKET_PRIVATE_KEY` is not set, `load_config` attempts to decrypt it from
`secrets.age` using the `age` CLI and your SSH private key (default:
`~/.ssh/Youturn`). The helper lives in `src/config/encryption.py` and shells out to:

```
age -d -i ~/.ssh/Youturn secrets.age
```

## Private Key Validation

The config validates private keys by:
- Stripping `0x` prefix if present
- Ensuring exactly 64 hex characters
- Validating hex format

## Required `.env` Variables

```bash
# Authentication (required)
POLYMARKET_PRIVATE_KEY=your_64_char_hex_private_key_without_0x

# Optional overrides (defaults shown)
# POLYMARKET_HOST=https://clob.polymarket.com
# POLYMARKET_CHAIN_ID=137

# Required only for proxy wallets (signature_type 1 or 2)
# POLYMARKET_SIGNATURE_TYPE=0
# POLYMARKET_FUNDER_ADDRESS=

# Note: API credentials are auto-generated from PRIVATE_KEY - no need to set them
```

## Client Initialization

Choose one based on your wallet type:

**EOA (Externally Owned Account)**
```python
client = ClobClient(
    host=config.host,
    chain_id=config.chain_id,
    key=config.private_key
)
```

**Email/Social Login Proxy**
```python
client = ClobClient(
    host=config.host,
    chain_id=config.chain_id,
    key=config.private_key,
    funder=config.funder_address,
    signature_type=1
)
```

**Browser Wallet Proxy (MetaMask, Coinbase Wallet)**
```python
client = ClobClient(
    host=config.host,
    chain_id=config.chain_id,
    key=config.private_key,
    funder=config.funder_address,
    signature_type=2
)
```
