"""Web dashboard for monitoring Polymarket positions and orders."""

import logging
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from flask import Flask, jsonify, render_template
from flask_cors import CORS

from api.polymarket_client import PolymarketClient
from config.settings import load_config

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
CORS(app)

# Global client instance
polymarket_client: Optional[PolymarketClient] = None


def initialize_client():
    """Initialize Polymarket client."""
    global polymarket_client
    try:
        config = load_config()
        polymarket_client = PolymarketClient(config=config, logger=logger)
        logger.info("Polymarket client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Polymarket client: {e}")
        raise


def format_order_data(order: dict) -> dict:
    """Format order data for display."""
    return {
        "id": order.get("id", "N/A"),
        "market": order.get("market", "N/A"),
        "side": order.get("side", "N/A"),
        "size": float(order.get("original_size", 0)),
        "filled": float(order.get("size_matched", 0)),
        "remaining": float(order.get("original_size", 0)) - float(order.get("size_matched", 0)),
        "price": float(order.get("price", 0)),
        "status": order.get("status", "N/A"),
        "created_at": order.get("created_at", "N/A"),
        "fill_percentage": (
            float(order.get("size_matched", 0)) / float(order.get("original_size", 1)) * 100
            if float(order.get("original_size", 0)) > 0
            else 0
        ),
    }


def format_trade_data(trade: dict) -> dict:
    """Format trade data for display."""
    return {
        "id": trade.get("id", "N/A"),
        "market": trade.get("market", "N/A"),
        "side": trade.get("side", "N/A"),
        "size": float(trade.get("size", 0)),
        "price": float(trade.get("price", 0)),
        "timestamp": trade.get("timestamp", "N/A"),
        "total": float(trade.get("size", 0)) * float(trade.get("price", 0)),
    }


def get_balance_summary(orders: List[dict]) -> dict:
    """Calculate balance summary from open orders."""
    total_buy_exposure = sum(
        float(o.get("original_size", 0)) * float(o.get("price", 0))
        for o in orders
        if o.get("side") == "BUY"
    )
    total_sell_exposure = sum(
        float(o.get("original_size", 0)) * float(o.get("price", 0))
        for o in orders
        if o.get("side") == "SELL"
    )

    return {
        "total_orders": len(orders),
        "buy_orders": len([o for o in orders if o.get("side") == "BUY"]),
        "sell_orders": len([o for o in orders if o.get("side") == "SELL"]),
        "buy_exposure": total_buy_exposure,
        "sell_exposure": total_sell_exposure,
        "net_exposure": total_buy_exposure - total_sell_exposure,
    }


@app.route("/")
def index():
    """Render main dashboard page."""
    return render_template("dashboard.html")


@app.route("/api/orders")
def get_orders():
    """Get all open orders."""
    try:
        if not polymarket_client:
            return jsonify({"error": "Client not initialized"}), 500

        orders = polymarket_client.get_orders()
        formatted_orders = [format_order_data(order) for order in orders]

        return jsonify(
            {"success": True, "orders": formatted_orders, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error fetching orders: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/trades")
def get_trades():
    """Get recent trades."""
    try:
        if not polymarket_client:
            return jsonify({"error": "Client not initialized"}), 500

        # Try to get trades using the underlying client
        trades = []
        try:
            # Access the underlying py-clob-client
            if hasattr(polymarket_client.client, "get_trades"):
                trades = polymarket_client.client.get_trades() or []
        except Exception as e:
            logger.warning(f"Could not fetch trades: {e}")

        formatted_trades = [format_trade_data(trade) for trade in trades[:50]]  # Last 50 trades

        return jsonify(
            {"success": True, "trades": formatted_trades, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error fetching trades: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/summary")
def get_summary():
    """Get summary statistics."""
    try:
        if not polymarket_client:
            return jsonify({"error": "Client not initialized"}), 500

        orders = polymarket_client.get_orders()
        summary = get_balance_summary(orders)

        return jsonify(
            {"success": True, "summary": summary, "timestamp": datetime.now().isoformat()}
        )
    except Exception as e:
        logger.error(f"Error fetching summary: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/health")
def health_check():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "client_initialized": polymarket_client is not None,
            "timestamp": datetime.now().isoformat(),
        }
    )


def run_dashboard(host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True):
    """Run the dashboard server.

    Args:
        host: Host to bind to
        port: Port to bind to
        open_browser: Whether to open browser automatically
    """
    try:
        # Initialize client
        initialize_client()

        # Open browser
        if open_browser:
            url = f"http://{host}:{port}"
            logger.info(f"Opening dashboard at {url}")
            webbrowser.open(url)

        # Run Flask app
        logger.info(f"Starting dashboard server on {host}:{port}")
        app.run(host=host, port=port, debug=False)

    except Exception as e:
        logger.error(f"Failed to start dashboard: {e}")
        raise


if __name__ == "__main__":
    run_dashboard()
