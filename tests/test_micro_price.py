"""Tests for micro-price strategy."""

import asyncio
from unittest.mock import Mock

from models.enums import OrderSide, OrderStatus
from models.market import MarketSnapshot
from models.order import Order
from models.order_request import MicroPriceParams
from strategies.micro_price import MicroPriceStrategy


def test_micro_price_strategy_initialization():
    """Test MicroPriceStrategy initialization."""
    client = Mock()
    monitor = Mock()

    strategy = MicroPriceStrategy(client, monitor)

    assert strategy.client == client
    assert strategy.monitor == monitor
    assert strategy._active_order_id is None
    assert strategy._adjustment_count == 0


def test_get_adjustment_count():
    """Test getting adjustment count."""
    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    assert strategy.get_adjustment_count() == 0

    strategy._adjustment_count = 5
    assert strategy.get_adjustment_count() == 5


def test_reset():
    """Test resetting strategy state."""
    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    # Set some state
    strategy._active_order_id = "order-123"
    strategy._adjustment_count = 5

    # Reset
    strategy.reset()

    assert strategy._active_order_id is None
    assert strategy._adjustment_count == 0


def test_get_initial_price_buy():
    """Test initial price calculation for buy orders."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    # Mock market snapshot
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.45,
        micro_price_upper_band=0.455,
        micro_price_lower_band=0.445,
    )
    monitor.get_market_snapshot.return_value = snapshot

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    params = MicroPriceParams()

    # Get initial price
    price = asyncio.run(strategy._get_initial_price(order, params))

    # For buy, should be at or below micro-price, but not below best bid
    assert price >= snapshot.best_bid
    assert price <= order.max_price
    assert price >= order.min_price


def test_get_initial_price_sell():
    """Test initial price calculation for sell orders."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    # Mock market snapshot
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.45,
        micro_price_upper_band=0.455,
        micro_price_lower_band=0.445,
    )
    monitor.get_market_snapshot.return_value = snapshot

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.SELL,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    params = MicroPriceParams()

    # Get initial price
    price = asyncio.run(strategy._get_initial_price(order, params))

    # For sell, should be at or above micro-price, but not above best ask
    assert price <= snapshot.best_ask
    assert price <= order.max_price
    assert price >= order.min_price


def test_place_order():
    """Test placing an order."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    # Mock client response
    client.place_order.return_value = "exchange-order-123"

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    # Place order
    order_id = asyncio.run(strategy._place_order(order, 0.45))

    assert order_id == "exchange-order-123"
    client.place_order.assert_called_once_with(
        token_id="token-123", side=OrderSide.BUY, price=0.45, size=1000
    )


def test_should_replace_order_out_of_bounds():
    """Test replacement decision when price is out of bounds."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    # Mock market snapshot - price is out of bounds
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.50,  # Moved significantly
        micro_price_upper_band=0.505,
        micro_price_lower_band=0.495,
    )
    monitor.get_market_snapshot.return_value = snapshot

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    params = MicroPriceParams(threshold_bps=50)

    # Current price is 0.45, but micro-price is now 0.50 - out of bounds
    should_replace = asyncio.run(strategy._should_replace_order(order, 0.45, params))

    assert should_replace


def test_should_replace_order_in_bounds():
    """Test replacement decision when price is in bounds."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    # Mock market snapshot - price is in bounds and not too aggressive
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.448,  # Close to current price to pass aggression check
        best_ask=0.46,
        spread=0.012,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.45,
        micro_price_upper_band=0.455,
        micro_price_lower_band=0.445,
    )
    monitor.get_market_snapshot.return_value = snapshot

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    params = MicroPriceParams(threshold_bps=100, aggression_limit_bps=100)  # 1%

    # Current price is 0.45, micro-price is 0.45 - in bounds
    # Distance from best bid: (0.45 - 0.448) / 0.448 = 0.45% < 1% limit
    should_replace = asyncio.run(strategy._should_replace_order(order, 0.45, params))

    assert not should_replace


def test_should_replace_order_too_aggressive_buy():
    """Test replacement when buy order is too aggressive."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    # Mock market snapshot
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.40,  # Best bid is low
        best_ask=0.46,
        spread=0.06,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.45,
        micro_price_upper_band=0.455,
        micro_price_lower_band=0.445,
    )
    monitor.get_market_snapshot.return_value = snapshot

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    params = MicroPriceParams(aggression_limit_bps=100)  # 1% limit

    # Current price is 0.45, best bid is 0.40 - 12.5% above (too aggressive)
    should_replace = asyncio.run(strategy._should_replace_order(order, 0.45, params))

    assert should_replace


def test_check_fills():
    """Test checking for order fills."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    # Set active order
    strategy._active_order_id = "exchange-order-123"

    # Mock order status with partial fill
    client.get_order_status.return_value = {"filled_amount": 300}

    # Check fills
    asyncio.run(strategy._check_fills(order))

    # Verify fill was recorded
    assert order.filled_amount == 300
    assert order.remaining_amount == 700
    assert order.status == OrderStatus.PARTIALLY_FILLED


def test_check_fills_no_active_order():
    """Test checking fills with no active order."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    # No active order
    strategy._active_order_id = None

    # Check fills - should not call client
    asyncio.run(strategy._check_fills(order))

    client.get_order_status.assert_not_called()


def test_replace_order():
    """Test replacing an order."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    # Mock market snapshot
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.45,
        micro_price_upper_band=0.455,
        micro_price_lower_band=0.445,
    )
    monitor.get_market_snapshot.return_value = snapshot

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    params = MicroPriceParams()

    # Set active order
    strategy._active_order_id = "old-order-123"
    client.place_order.return_value = "new-order-456"

    # Replace order
    new_price = asyncio.run(strategy._replace_order(order, params))

    # Verify cancellation and placement
    client.cancel_order.assert_called_once_with("old-order-123")
    assert strategy._active_order_id == "new-order-456"
    assert new_price is not None
    assert order.adjustment_count == 1


def test_replace_order_failure():
    """Test replacing order when placement fails."""

    client = Mock()
    monitor = Mock()
    strategy = MicroPriceStrategy(client, monitor)

    # Mock market snapshot
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.45,
        micro_price_upper_band=0.455,
        micro_price_lower_band=0.445,
    )
    monitor.get_market_snapshot.return_value = snapshot

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    params = MicroPriceParams()

    # Set active order
    strategy._active_order_id = "old-order-123"

    # Make placement fail
    client.place_order.side_effect = Exception("Placement failed")

    # Replace order
    new_price = asyncio.run(strategy._replace_order(order, params))

    # Should return None on failure
    assert new_price is None
