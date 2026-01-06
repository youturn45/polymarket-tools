# Dashboard Quick Start Guide

## Installation

1. **Install dashboard dependencies**:
   ```bash
   pip install -r requirements-dashboard.txt
   ```

2. **Make sure your `.env` is configured**:
   ```bash
   POLYMARKET_PRIVATE_KEY=your_key_here
   ```

## Running the Dashboard

### Basic Usage

Simply run:
```bash
python run_dashboard.py
```

This will:
- Start a web server on `http://127.0.0.1:5000`
- Automatically open the dashboard in your browser
- Begin auto-refreshing data every 10 seconds

### Advanced Options

```bash
# Run on a different port
python run_dashboard.py --port 8080

# Don't open browser automatically
python run_dashboard.py --no-browser

# Bind to all interfaces (be careful with this!)
python run_dashboard.py --host 0.0.0.0
```

## What You'll See

### Summary Section (Top Cards)
- **Total Orders**: How many orders you have open
- **Buy Orders**: Number of buy (long) positions
- **Sell Orders**: Number of sell (short) positions
- **Buy Exposure**: Total USD value of buy orders
- **Sell Exposure**: Total USD value of sell orders
- **Net Exposure**: Net position (green if long, red if short)

### Open Orders Table
Each row shows:
- **ID**: Shortened order ID
- **Side**: BUY (green) or SELL (red) badge
- **Size**: Total order size in shares
- **Filled**: How many shares have been filled
- **Price**: Order price per share
- **Fill %**: Visual progress bar showing fill percentage
- **Status**: Order status (usually ACTIVE)
- **Created**: When the order was placed

### Recent Trades Table
Shows your completed trades with:
- Trade ID, side, size, price, total value, and timestamp

## Tips

1. **Auto-refresh**: The dashboard updates every 10 seconds automatically. You can also click the "Refresh" button anytime.

2. **Multiple Markets**: If you have orders in multiple markets, they'll all show up in the same table.

3. **Fill Tracking**: Watch the progress bar in real-time as your orders get filled.

4. **Clean Data**: The dashboard only shows active orders. Completed or cancelled orders won't appear.

## Troubleshooting

**Problem**: Dashboard shows "Client not initialized"
- **Solution**: Check your `.env` file has `POLYMARKET_PRIVATE_KEY` set correctly

**Problem**: Shows "No open orders"
- **Solution**: This is normal if you don't have any active orders right now

**Problem**: Port 5000 already in use
- **Solution**: Run with `--port 5001` or any other available port

**Problem**: Browser doesn't open automatically
- **Solution**: Manually navigate to `http://127.0.0.1:5000` or use the URL shown in terminal

## Example Workflow

1. **Start your trading bot** (e.g., `python examples/phase3_demo.py`)
2. **Launch the dashboard** in another terminal:
   ```bash
   python run_dashboard.py
   ```
3. **Monitor in real-time** as orders are placed and filled
4. **Keep it running** while you trade to track all activity

## Stopping the Dashboard

Press `Ctrl+C` in the terminal where the dashboard is running.

## Integration with Trading Scripts

The dashboard reads the same data your trading scripts use:
- Same Polymarket API connection
- Same authentication
- Same order data
- Real-time synchronization

You can run your trading scripts and the dashboard simultaneously to monitor activity as it happens!
