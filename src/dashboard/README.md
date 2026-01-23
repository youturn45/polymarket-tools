# Polymarket Trading Dashboard

A real-time web dashboard for monitoring your Polymarket trading activity, positions, and orders.

## Features

- **Real-time Order Monitoring**: View all open orders with fill status
- **Position Tracking**: Monitor your buy/sell exposure and net position
- **Trade History**: See your recent trades
- **Auto-refresh**: Data updates automatically every 10 seconds
- **Clean UI**: Modern, responsive interface with visual indicators

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements-dashboard.txt
```

### 2. Configure Your Environment

Make sure you have a `.env` file with your Polymarket credentials:

```bash
POLYMARKET_PRIVATE_KEY=your_private_key_here
POLYMARKET_HOST=https://clob.polymarket.com
POLYMARKET_CHAIN_ID=137
```

### 3. Launch the Dashboard

```bash
python scripts/run_dashboard.py
```

The dashboard will automatically open in your default browser at `http://127.0.0.1:5000`.

## Command Line Options

```bash
# Custom host and port
python scripts/run_dashboard.py --host 0.0.0.0 --port 8080

# Don't open browser automatically
python scripts/run_dashboard.py --no-browser
```

## Dashboard Sections

### Summary Cards

Displays key metrics at a glance:
- **Total Orders**: Number of active orders
- **Buy/Sell Orders**: Breakdown by side
- **Buy/Sell Exposure**: Total value of open positions
- **Net Exposure**: Net position (positive = long, negative = short)

### Open Orders Table

Shows all active orders with:
- Order ID
- Side (BUY/SELL)
- Size and filled amount
- Price
- Fill percentage (visual progress bar)
- Status
- Creation time

### Recent Trades

Displays your trade history with:
- Trade ID
- Side
- Size and price
- Total value
- Timestamp

## API Endpoints

The dashboard exposes the following REST API endpoints:

- `GET /api/orders` - Fetch all open orders
- `GET /api/trades` - Fetch recent trades
- `GET /api/summary` - Get position summary
- `GET /api/health` - Health check

## Architecture

### Backend (Flask)

- **app.py**: Main Flask application with API endpoints
- Integrates with existing `PolymarketClient` from `src/api/polymarket_client.py`
- Provides RESTful API for fetching orders, trades, and positions
- Auto-generates API credentials from private key

### Frontend (HTML/CSS/JS)

- **templates/dashboard.html**: Single-page application
- Vanilla JavaScript (no frameworks required)
- Responsive design with gradient UI
- Auto-refresh functionality (10-second interval)

## Troubleshooting

### Dashboard won't start

**Issue**: `Client not initialized` error

**Solution**: Check your `.env` file has a valid `POLYMARKET_PRIVATE_KEY`

### No orders showing

**Issue**: Dashboard loads but shows "No open orders"

**Solution**: This is normal if you don't have any active orders on Polymarket

### Port already in use

**Issue**: `Address already in use` error

**Solution**: Use a different port:
```bash
python scripts/run_dashboard.py --port 5001
```

## Development

### Project Structure

```
src/dashboard/
├── __init__.py           # Module initialization
├── app.py                # Flask backend
├── templates/
│   └── dashboard.html    # Frontend UI
└── README.md             # This file

scripts/run_dashboard.py   # Launcher script
requirements-dashboard.txt # Python dependencies
```

### Adding New Features

1. **New API Endpoint**: Add route to `app.py`
2. **New UI Component**: Update `templates/dashboard.html`
3. **New Data Source**: Extend `PolymarketClient` in `api/polymarket_client.py`

## Security Notes

- Dashboard binds to `127.0.0.1` by default (localhost only)
- Never expose dashboard to public internet without authentication
- Private keys are never displayed in the UI
- All API calls use existing client authentication

## Performance

- Auto-refresh: 10 seconds (configurable in HTML)
- Lightweight: Vanilla JavaScript, no heavy frameworks
- Parallel requests: Orders, trades, and summary fetched simultaneously
- Minimal server resources: Flask development server

## Future Enhancements

Potential improvements:
- WebSocket support for real-time updates
- Order placement from dashboard
- Historical charts and analytics
- Market price integration
- Position P&L calculations
- Mobile-responsive improvements
- Dark mode toggle

## Support

For issues or questions:
1. Check this README
2. Review logs in the terminal
3. Verify `.env` configuration
4. Check Polymarket API status
