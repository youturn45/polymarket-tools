# Polymarket Position Management Service

Semi-automated trading bot for Polymarket that maintains top-of-book positions while intelligently splitting orders to prevent trade detection.

## Features

- **Auto Top-Bidder**: Automatically maintain best bid/ask position without crossing limit price
- **Order Splitting**: Split large orders using SOTA algorithms (TWAP, VWAP, Iceberg, Randomized)
- **Position Tracking**: Monitor current positions and P&L
- **Risk Management**: Position size limits, daily loss limits, total exposure caps

## Prerequisites

- Python 3.9 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- Ethereum wallet with private key
- Polygon (MATIC) for gas fees
- USDC on Polygon for trading

## Installation

### 1. Install Dependencies

Using uv:

```bash
# Install dependencies
uv pip install -e .

# Or install with dev dependencies
uv pip install -e ".[dev]"
```

### 2. Configure Environment

Copy the example environment file:

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```bash
# Required: Your Ethereum private key (without 0x prefix)
PRIVATE_KEY=your_private_key_here

# Required: Market configuration
TOKEN_ID=your_market_token_id
SIDE=BUY
LIMIT_PRICE=0.55
TOTAL_SHARES=1000

# Optional: Customize other settings
SPLITTING_STRATEGY=TWAP
TIME_WINDOW_MINUTES=60
MIN_ORDER_SIZE=10
MAX_ORDER_SIZE=100
```

### 3. Test Connection

Verify your API connection:

```bash
uv run python check_connection.py
```

You should see output confirming:
- ✓ Connection to Polymarket
- ✓ API authentication
- ✓ Market data retrieval
- ✓ Order book access

## Getting Your Credentials

### Private Key

1. **MetaMask**: Settings → Security & Privacy → Reveal Private Key
2. **Other wallets**: Consult your wallet's documentation

**⚠️ SECURITY WARNING**: Never share your private key or commit it to version control!

### Token ID

To find the token ID for a market:

1. Visit the Polymarket market you want to trade
2. Use the Polymarket API or inspect network requests
3. Or use this helper script:

```bash
uv run python -c "
from core.client import PolymarketClient
from config.settings import PolymarketConfig

config = PolymarketConfig(private_key='your_key')
client = PolymarketClient(config)
client.connect()

markets = client.get_markets()
for m in markets[:5]:
    print(f\"{m['question']}: {m['tokens'][0]['token_id']}\")
"
```

## Configuration

See `.env.example` for all available configuration options:

### Trading Strategy

- `TOKEN_ID`: Market token to trade
- `SIDE`: BUY or SELL
- `LIMIT_PRICE`: Maximum price (0-1 range)
- `TOTAL_SHARES`: Total shares to acquire

### Order Splitting

- `SPLITTING_STRATEGY`: TWAP, VWAP, ICEBERG, or RANDOM
- `TIME_WINDOW_MINUTES`: Execute over this timeframe
- `MIN_ORDER_SIZE` / `MAX_ORDER_SIZE`: Order size bounds

### Risk Limits

- `MAX_POSITION_SIZE`: Maximum shares per market
- `MAX_TOTAL_EXPOSURE`: Maximum USD deployed
- `MAX_DAILY_LOSS`: Daily loss threshold

## Usage

### Basic Usage (Coming Soon)

```bash
# Run the trading bot
uv run python main.py
```

### Phase 1 Status (Current)

✅ **Completed**:
- Project structure
- Configuration management with pydantic
- Polymarket API client wrapper
- Authentication and connection testing
- Logging utilities

🚧 **In Progress**:
- Top bidder strategy
- Order splitting algorithms
- Position tracking
- Risk management

## Project Structure

```
polymarket-position-manage/
├── config/
│   ├── settings.py          # Configuration using pydantic-settings
│   └── __init__.py
├── core/
│   ├── client.py            # Polymarket API client wrapper
│   ├── order_manager.py     # Order lifecycle management (TODO)
│   ├── position_tracker.py  # Position tracking (TODO)
│   └── __init__.py
├── strategies/
│   ├── top_bidder.py        # Auto top-bidder logic (TODO)
│   ├── order_splitter.py    # Order splitting algorithms (TODO)
│   └── __init__.py
├── risk/
│   ├── limits.py            # Risk management (TODO)
│   └── __init__.py
├── utils/
│   ├── logger.py            # Logging setup
│   └── __init__.py
├── check_connection.py      # Connection test script
├── main.py                  # Entry point (TODO)
├── .env.example             # Example configuration
├── .gitignore
├── pyproject.toml
├── PLAN.md                  # Detailed implementation plan
└── README.md                # This file
```

## Development

### Code Quality

Format code:
```bash
uv run black .
```

Lint code:
```bash
uv run ruff check .
```

Type check:
```bash
uv run mypy .
```

### Running Tests

```bash
uv run pytest
```

## Security Best Practices

1. **Never commit `.env`** - It's in `.gitignore` by default
2. **Use environment-specific keys** - Don't use your main wallet for testing
3. **Start small** - Test with minimal amounts first
4. **Monitor closely** - Always watch the bot during initial runs
5. **Set conservative limits** - Use risk limits to prevent large losses

## API Rate Limits

Polymarket CLOB API limits:
- General endpoints: 5,000 requests / 10 seconds
- Market data: 200 requests / 10 seconds
- Order placement: 2,400 / 10s (burst) or 24,000 / 10 min (sustained)

The client handles rate limiting automatically.

## Troubleshooting

### "No module named 'pydantic'"

Install dependencies:
```bash
uv pip install -e .
```

### "Private key must be 64 hex characters"

Ensure your private key:
- Is exactly 64 characters
- Contains only hex (0-9, a-f)
- Does NOT include the "0x" prefix

### "Failed to connect to Polymarket"

Check:
1. Internet connection
2. Private key is valid
3. Wallet has USDC and MATIC on Polygon

### "Token ID not found"

Verify:
1. Token ID is correct for your target market
2. Market is still active
3. You're using the correct token (YES or NO outcome)

## Resources

- [Polymarket Documentation](https://docs.polymarket.com/)
- [py-clob-client GitHub](https://github.com/Polymarket/py-clob-client)
- [Implementation Plan](PLAN.md)

## License

This project is for educational and personal use only. Use at your own risk.

## Disclaimer

This software is provided "as is" without warranty. Trading prediction markets involves risk. Only trade with funds you can afford to lose. The authors are not responsible for any losses incurred through use of this software.
