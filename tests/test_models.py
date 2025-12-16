"""Tests for data models."""

import pytest

from models.enums import OrderSide, OrderStatus, Urgency
from models.market import MarketConditions
from models.order import Order, StrategyParams


def test_strategy_params_defaults():
    """Test StrategyParams default values."""
    params = StrategyParams()
    assert params.initial_tranche_size == 50
    assert params.min_tranche_size == 10
    assert params.max_tranche_size == 200
    assert params.tranche_randomization == 0.2


def test_strategy_params_validation():
    """Test StrategyParams validation."""
    # Valid params
    params = StrategyParams(
        initial_tranche_size=100,
        min_tranche_size=20,
        max_tranche_size=150,
        tranche_randomization=0.3,
    )
    assert params.initial_tranche_size == 100

    # Invalid randomization
    with pytest.raises(ValueError):
        StrategyParams(tranche_randomization=1.5)


def test_order_creation():
    """Test Order creation with required fields."""
    order = Order(
        order_id="test-123",
        market_id="market-456",
        token_id="token-789",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    assert order.order_id == "test-123"
    assert order.side == OrderSide.BUY
    assert order.total_size == 1000
    assert order.remaining_amount == 1000
    assert order.filled_amount == 0
    assert order.status == OrderStatus.QUEUED
    assert order.urgency == Urgency.MEDIUM


def test_order_price_validation():
    """Test Order price validation."""
    # Valid prices
    order = Order(
        order_id="test-1",
        market_id="m1",
        token_id="t1",
        side=OrderSide.BUY,
        total_size=100,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )
    assert order.target_price == 0.45

    # Invalid price (> 1.0)
    with pytest.raises(ValueError):
        Order(
            order_id="test-2",
            market_id="m1",
            token_id="t1",
            side=OrderSide.BUY,
            total_size=100,
            target_price=1.5,
            max_price=0.50,
            min_price=0.40,
        )


def test_order_record_fill():
    """Test recording fills."""
    order = Order(
        order_id="test-1",
        market_id="m1",
        token_id="t1",
        side=OrderSide.BUY,
        total_size=1000,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    # Partial fill
    order.record_fill(300)
    assert order.filled_amount == 300
    assert order.remaining_amount == 700
    assert order.status == OrderStatus.PARTIALLY_FILLED

    # Complete fill
    order.record_fill(700)
    assert order.filled_amount == 1000
    assert order.remaining_amount == 0
    assert order.status == OrderStatus.COMPLETED


def test_order_record_adjustment():
    """Test recording price adjustments."""
    order = Order(
        order_id="test-1",
        market_id="m1",
        token_id="t1",
        side=OrderSide.BUY,
        total_size=100,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    assert order.adjustment_count == 0
    order.record_adjustment()
    assert order.adjustment_count == 1
    order.record_adjustment()
    assert order.adjustment_count == 2


def test_order_record_undercut():
    """Test recording undercuts."""
    order = Order(
        order_id="test-1",
        market_id="m1",
        token_id="t1",
        side=OrderSide.BUY,
        total_size=100,
        target_price=0.45,
        max_price=0.50,
        min_price=0.40,
    )

    assert order.undercut_count == 0
    order.record_undercut()
    assert order.undercut_count == 1


def test_market_conditions_creation():
    """Test MarketConditions creation."""
    conditions = MarketConditions(
        market_id="m1",
        token_id="t1",
        best_bid=0.44,
        best_ask=0.46,
        spread=0.02,
        bid_depth=500,
        ask_depth=300,
    )

    assert conditions.best_bid == 0.44
    assert conditions.best_ask == 0.46
    assert conditions.spread == 0.02
    assert conditions.mid_price == 0.45


def test_market_conditions_mid_price():
    """Test mid_price calculation."""
    conditions = MarketConditions(
        market_id="m1",
        token_id="t1",
        best_bid=0.40,
        best_ask=0.50,
        spread=0.10,
    )

    assert conditions.mid_price == 0.45
