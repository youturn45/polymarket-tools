"""Tests for market monitor."""

from unittest.mock import Mock

import pytest

from core.market_monitor import MarketMonitor
from models.market import MarketSnapshot


def test_market_monitor_initialization():
    """Test MarketMonitor initialization."""
    client = Mock()
    token_id = "token-123"

    monitor = MarketMonitor(client, token_id)

    assert monitor.client == client
    assert monitor.token_id == token_id
    assert monitor.band_width_bps == 50  # default
    assert monitor._last_snapshot is None


def test_market_monitor_custom_band_width():
    """Test MarketMonitor with custom band width."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123", band_width_bps=100)

    assert monitor.band_width_bps == 100


def test_calculate_micro_price_balanced():
    """Test micro-price calculation with balanced depth."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    # Equal depth on both sides
    micro_price = monitor.calculate_micro_price(
        best_bid=0.44, best_ask=0.46, bid_depth=1000, ask_depth=1000
    )

    # With equal depth, micro-price should equal mid-price
    assert micro_price == 0.45


def test_calculate_micro_price_bid_heavy():
    """Test micro-price calculation with more bid depth."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    # More depth on bid side (2000 vs 1000)
    # micro = (0.44 * 1000 + 0.46 * 2000) / 3000
    #       = (440 + 920) / 3000
    #       = 1360 / 3000
    #       = 0.4533...
    micro_price = monitor.calculate_micro_price(
        best_bid=0.44, best_ask=0.46, bid_depth=2000, ask_depth=1000
    )

    expected = (0.44 * 1000 + 0.46 * 2000) / 3000
    assert abs(micro_price - expected) < 0.0001


def test_calculate_micro_price_ask_heavy():
    """Test micro-price calculation with more ask depth."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    # More depth on ask side (1000 vs 2000)
    # micro = (0.44 * 2000 + 0.46 * 1000) / 3000
    #       = (880 + 460) / 3000
    #       = 1340 / 3000
    #       = 0.4466...
    micro_price = monitor.calculate_micro_price(
        best_bid=0.44, best_ask=0.46, bid_depth=1000, ask_depth=2000
    )

    expected = (0.44 * 2000 + 0.46 * 1000) / 3000
    assert abs(micro_price - expected) < 0.0001


def test_calculate_micro_price_no_depth():
    """Test micro-price falls back to mid-price when no depth."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    # No depth - should fall back to mid-price
    micro_price = monitor.calculate_micro_price(
        best_bid=0.44, best_ask=0.46, bid_depth=0, ask_depth=0
    )

    assert micro_price == 0.45  # mid-price


def test_calculate_bands_default():
    """Test threshold band calculation with default width."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123", band_width_bps=50)

    # 50 bps = 0.5%
    # For micro_price = 0.50
    # band_size = 0.50 * 0.005 = 0.0025
    # lower = 0.50 - 0.0025 = 0.4975
    # upper = 0.50 + 0.0025 = 0.5025
    lower, upper = monitor.calculate_bands(0.50)

    assert abs(lower - 0.4975) < 0.0001
    assert abs(upper - 0.5025) < 0.0001


def test_calculate_bands_wider():
    """Test threshold band calculation with wider bands."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123", band_width_bps=100)

    # 100 bps = 1%
    # For micro_price = 0.50
    # band_size = 0.50 * 0.01 = 0.005
    # lower = 0.50 - 0.005 = 0.495
    # upper = 0.50 + 0.005 = 0.505
    lower, upper = monitor.calculate_bands(0.50)

    assert abs(lower - 0.495) < 0.0001
    assert abs(upper - 0.505) < 0.0001


def test_calculate_bands_clamped_to_zero():
    """Test bands are clamped to [0, 1] range."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123", band_width_bps=500)  # 5%

    # For micro_price = 0.03, 5% would go negative
    # band_size = 0.03 * 0.05 = 0.0015
    # lower would be 0.0285, upper would be 0.0315
    # But for extreme case with 0.01
    lower, upper = monitor.calculate_bands(0.01)

    # Lower bound should be clamped to 0
    assert lower >= 0.0
    assert upper <= 1.0


def test_calculate_bands_clamped_to_one():
    """Test bands are clamped to [0, 1] range at upper end."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123", band_width_bps=500)  # 5%

    # For micro_price = 0.99, 5% would exceed 1.0
    lower, upper = monitor.calculate_bands(0.99)

    # Upper bound should be clamped to 1.0
    assert lower >= 0.0
    assert upper <= 1.0


def test_get_market_snapshot():
    """Test getting market snapshot."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    # Mock order book data
    client.get_order_book.return_value = {
        "bids": [
            {"price": "0.44", "size": "1000"},
            {"price": "0.43", "size": "500"},
            {"price": "0.42", "size": "300"},
        ],
        "asks": [
            {"price": "0.46", "size": "800"},
            {"price": "0.47", "size": "600"},
            {"price": "0.48", "size": "400"},
        ],
    }

    # Mock our orders
    client.get_orders.return_value = []

    snapshot = monitor.get_market_snapshot()

    # Verify snapshot
    assert snapshot.token_id == "token-123"
    assert snapshot.best_bid == 0.44
    assert snapshot.best_ask == 0.46
    assert abs(snapshot.spread - 0.02) < 0.0001
    assert snapshot.bid_depth == 1000
    assert snapshot.ask_depth == 800

    # Verify micro-price
    expected_micro = (0.44 * 800 + 0.46 * 1000) / 1800
    assert abs(snapshot.micro_price - expected_micro) < 0.0001

    # Verify bands
    assert snapshot.micro_price_lower_band < snapshot.micro_price
    assert snapshot.micro_price_upper_band > snapshot.micro_price

    # Verify order book levels
    assert len(snapshot.bids) == 3
    assert len(snapshot.asks) == 3
    assert snapshot.bids[0] == (0.44, 1000)
    assert snapshot.asks[0] == (0.46, 800)


def test_get_market_snapshot_with_our_orders():
    """Test snapshot includes our active orders."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    # Mock order book
    client.get_order_book.return_value = {
        "bids": [{"price": "0.44", "size": "1000"}],
        "asks": [{"price": "0.46", "size": "800"}],
    }

    # Mock our orders
    client.get_orders.return_value = [
        {"id": "order-1", "price": "0.45", "size": "100", "side": "BUY", "status": "OPEN"},
        {"id": "order-2", "price": "0.46", "size": "50", "side": "SELL", "status": "OPEN"},
        {"id": "order-3", "price": "0.47", "size": "75", "side": "BUY", "status": "FILLED"},
    ]

    snapshot = monitor.get_market_snapshot()

    # Should have 2 active orders (OPEN status)
    assert len(snapshot.our_orders) == 2
    assert snapshot.our_orders[0]["order_id"] == "order-1"
    assert snapshot.our_orders[1]["order_id"] == "order-2"


def test_get_market_snapshot_empty_book_raises():
    """Test that empty order book raises error."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    # Mock empty order book
    client.get_order_book.return_value = {"bids": [], "asks": []}

    with pytest.raises(ValueError, match="Empty order book"):
        monitor.get_market_snapshot()


def test_is_price_competitive_in_bounds():
    """Test checking if price is competitive (within bands)."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123", band_width_bps=100)

    # Create snapshot with micro_price = 0.45
    # 100 bps = 1%, so bands are [0.4455, 0.4545]
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=1000,
        micro_price=0.45,
        micro_price_upper_band=0.4545,
        micro_price_lower_band=0.4455,
    )

    # Price within bands
    assert monitor.is_price_competitive(0.45, snapshot)
    assert monitor.is_price_competitive(0.4455, snapshot)
    assert monitor.is_price_competitive(0.4545, snapshot)


def test_is_price_competitive_out_of_bounds():
    """Test checking if price is not competitive (outside bands)."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=1000,
        micro_price=0.45,
        micro_price_upper_band=0.4545,
        micro_price_lower_band=0.4455,
    )

    # Price outside bands
    assert not monitor.is_price_competitive(0.44, snapshot)  # Too low
    assert not monitor.is_price_competitive(0.47, snapshot)  # Too high


def test_get_distance_from_fair_value():
    """Test calculating distance from micro-price."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=1000,
        micro_price=0.50,
        micro_price_upper_band=0.51,
        micro_price_lower_band=0.49,
    )

    # Exact match
    assert monitor.get_distance_from_fair_value(0.50, snapshot) == 0.0

    # 10% away
    distance = monitor.get_distance_from_fair_value(0.55, snapshot)
    assert abs(distance - 0.1) < 0.0001


def test_get_last_snapshot():
    """Test getting cached snapshot."""
    client = Mock()
    monitor = MarketMonitor(client, "token-123")

    # Initially None
    assert monitor.get_last_snapshot() is None

    # Mock order book
    client.get_order_book.return_value = {
        "bids": [{"price": "0.44", "size": "1000"}],
        "asks": [{"price": "0.46", "size": "800"}],
    }
    client.get_orders.return_value = []

    # Get snapshot
    snapshot = monitor.get_market_snapshot()

    # Should be cached
    cached = monitor.get_last_snapshot()
    assert cached is not None
    assert cached.token_id == snapshot.token_id
    assert cached.micro_price == snapshot.micro_price
