# Polymarket Tools

Trading tools for Polymarket prediction markets.

## Setup

1. Install dependencies:
```bash
uv pip install -e .
```

2. Configure environment:
```bash
cp .env.example .env
# Edit .env with your credentials
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

### Loading Configuration

```python
from config.settings import load_config

# Load default .env
config = load_config()

# Load specific environment file
config = load_config(".env.production")

# Use environment-specific file
# export ENV=staging
config = load_config()  # loads .env.staging
```

Configuration priority (highest to lowest):
1. System environment variables
2. `.env` file
3. Default values

## First Trade

Run your first trade using `code/first_trade.py`:

```python
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from config.settings import load_config

# 1. Load configuration
config = load_config()

# 2. Initialize client (choose based on your wallet type)
# For Browser Wallet (MetaMask, Coinbase Wallet):
client = ClobClient(
    host=config.host,
    chain_id=config.chain_id,
    key=config.private_key,
    funder=config.funder_address,
    signature_type=2
)

# For standard EOA wallet:
# client = ClobClient(
#     host=config.host,
#     chain_id=config.chain_id,
#     key=config.private_key,
#     signature_type=0
# )

# 3. Enable full trading (derives API credentials)
client.set_api_creds(client.create_or_derive_api_creds())

# 4. Create order
order_args = OrderArgs(
    price=0.008,           # Price per share (0-1 range)
    size=100.0,            # Number of shares
    side="SELL",           # "BUY" or "SELL"
    token_id="114304..."   # Market token ID
)

# 5. Sign and post order
signed_order = client.create_order(order_args)
resp = client.post_order(signed_order, OrderType.GTC)
print(resp)
```

Execute the script:
```bash
uv run python code/first_trade.py
```

## Security

- Never commit `.env` files (already in `.gitignore`)
- Private key must be 64 hex characters without `0x` prefix
- Test with small amounts first
- Use separate test wallets for development

## Resources

- [Polymarket API Documentation](https://docs.polymarket.com/)
- [py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)
- [AI Contributors Guide](CLAUDE.md)
