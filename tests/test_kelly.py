"""Tests for Kelly criterion strategy."""

import asyncio
from unittest.mock import Mock

from models.enums import OrderSide, OrderStatus
from models.market import MarketSnapshot
from models.order import Order
from models.order_request import KellyParams
from strategies.kelly import KellyStrategy


def test_kelly_strategy_initialization():
    """Test KellyStrategy initialization."""
    client = Mock()
    monitor = Mock()

    strategy = KellyStrategy(client, monitor)

    assert strategy.client == client
    assert strategy.monitor == monitor
    assert strategy.micro_price_strategy is not None


def test_calculate_kelly_fraction_buy():
    """Test Kelly fraction calculation for buy orders."""
    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    # Example: Buying at 0.40 with 60% win probability
    # Odds: (1 - 0.40) / 0.40 = 0.60 / 0.40 = 1.5
    # Kelly: (1.5 * 0.6 - 0.4) / 1.5 = (0.9 - 0.4) / 1.5 = 0.5 / 1.5 = 0.333...
    kelly_fraction = strategy.calculate_kelly_fraction(
        win_probability=0.6, current_price=0.4, side=OrderSide.BUY
    )

    expected = (1.5 * 0.6 - 0.4) / 1.5
    assert abs(kelly_fraction - expected) < 0.001


def test_calculate_kelly_fraction_sell():
    """Test Kelly fraction calculation for sell orders."""
    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    # Example: Selling at 0.60 with 70% win probability
    # Odds: 0.60 / (1 - 0.60) = 0.60 / 0.40 = 1.5
    # Kelly: (1.5 * 0.7 - 0.3) / 1.5 = (1.05 - 0.3) / 1.5 = 0.75 / 1.5 = 0.5
    kelly_fraction = strategy.calculate_kelly_fraction(
        win_probability=0.7, current_price=0.6, side=OrderSide.SELL
    )

    expected = (1.5 * 0.7 - 0.3) / 1.5
    assert abs(kelly_fraction - expected) < 0.001


def test_calculate_kelly_fraction_zero_price_buy():
    """Test Kelly fraction with zero price for buy."""
    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    # Edge case: price = 0
    kelly_fraction = strategy.calculate_kelly_fraction(
        win_probability=0.6, current_price=0.0, side=OrderSide.BUY
    )

    assert kelly_fraction == 0.0


def test_calculate_kelly_fraction_one_price_sell():
    """Test Kelly fraction with price = 1 for sell."""
    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    # Edge case: price = 1
    kelly_fraction = strategy.calculate_kelly_fraction(
        win_probability=0.6, current_price=1.0, side=OrderSide.SELL
    )

    assert kelly_fraction == 0.0


def test_calculate_kelly_fraction_negative_clamped():
    """Test Kelly fraction is clamped to 0 when negative."""
    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    # Low win probability should result in negative Kelly, clamped to 0
    kelly_fraction = strategy.calculate_kelly_fraction(
        win_probability=0.2, current_price=0.5, side=OrderSide.BUY
    )

    assert kelly_fraction >= 0.0


def test_calculate_position_size():
    """Test position size calculation."""
    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    params = KellyParams(
        win_probability=0.6,
        kelly_fraction=0.5,  # Use half Kelly
        max_position_size=10000,
        bankroll=5000,
    )

    # At price 0.40, Kelly fraction ≈ 0.333
    # Adjusted: 0.333 * 0.5 = 0.1665
    # Position dollars: 5000 * 0.1665 = 832.5
    # Shares: 832.5 / 0.40 = 2081.25 ≈ 2081
    size = strategy.calculate_position_size(params, current_price=0.4, side=OrderSide.BUY)

    # Should be around 2000-2100 shares
    assert 2000 <= size <= 2200


def test_calculate_position_size_capped_at_max():
    """Test position size is capped at max_position_size."""
    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    params = KellyParams(
        win_probability=0.9,  # Very high win probability
        kelly_fraction=1.0,  # Full Kelly
        max_position_size=1000,  # Low cap
        bankroll=10000,  # High bankroll
    )

    size = strategy.calculate_position_size(params, current_price=0.5, side=OrderSide.BUY)

    # Should be capped at max
    assert size == 1000


def test_calculate_position_size_zero_price():
    """Test position size with zero price."""
    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    params = KellyParams(
        win_probability=0.6, kelly_fraction=0.5, max_position_size=5000, bankroll=10000
    )

    size = strategy.calculate_position_size(params, current_price=0.0, side=OrderSide.BUY)

    assert size == 0


def test_reset():
    """Test resetting strategy state."""
    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    # Set some state on micro-price strategy
    strategy.micro_price_strategy._active_order_id = "order-123"
    strategy.micro_price_strategy._adjustment_count = 5

    # Reset
    strategy.reset()

    # Micro-price strategy should be reset
    assert strategy.micro_price_strategy._active_order_id is None
    assert strategy.micro_price_strategy._adjustment_count == 0


def test_execute_zero_position_size():
    """Test execution when Kelly calculation results in 0 position size."""

    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    # Mock snapshot
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.0,  # Zero price - will result in 0 position size
        micro_price_upper_band=0.01,
        micro_price_lower_band=0.0,
    )
    monitor.get_market_snapshot.return_value = snapshot

    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=1000,  # Initial size, will be recalculated to 0
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    params = KellyParams(
        win_probability=0.6, kelly_fraction=0.5, max_position_size=5000, bankroll=10000
    )

    # Execute
    result = asyncio.run(strategy.execute(order, params))

    # Should fail because calculated size is 0
    assert result.status == OrderStatus.FAILED


def test_recalculate_position_size():
    """Test position size recalculation."""

    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    # Initial order
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
    order.filled_amount = 200  # Partially filled

    params = KellyParams(
        win_probability=0.6, kelly_fraction=0.5, max_position_size=5000, bankroll=10000
    )

    # Mock snapshot with different price
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.30,  # Price dropped significantly
        micro_price_upper_band=0.31,
        micro_price_lower_band=0.29,
    )
    monitor.get_market_snapshot.return_value = snapshot

    # Recalculate
    asyncio.run(strategy._recalculate_position_size(order, params))

    # Position size should have changed
    # At lower price, we can buy more shares for same dollar amount
    assert order.total_size != 1000  # Should be different
    assert order.total_size > 1000  # Should be higher at lower price


def test_recalculate_position_size_small_change():
    """Test position size recalculation with small change."""

    client = Mock()
    monitor = Mock()
    strategy = KellyStrategy(client, monitor)

    # Initial order
    order = Order(
        order_id="order-1",
        market_id="market-1",
        token_id="token-123",
        side=OrderSide.BUY,
        total_size=2000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    params = KellyParams(
        win_probability=0.6, kelly_fraction=0.5, max_position_size=5000, bankroll=10000
    )

    # Mock snapshot with similar price (small change)
    snapshot = MarketSnapshot(
        token_id="token-123",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=1000,
        ask_depth=800,
        micro_price=0.41,  # Only slightly different from 0.40
        micro_price_upper_band=0.42,
        micro_price_lower_band=0.40,
    )
    monitor.get_market_snapshot.return_value = snapshot

    # Recalculate
    asyncio.run(strategy._recalculate_position_size(order, params))

    # With less than 10% change, size might not change much
    # Just verify it ran without error
    assert order.total_size >= 0
