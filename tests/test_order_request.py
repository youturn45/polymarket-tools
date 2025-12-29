"""Tests for order request models."""

import pytest

from models.enums import OrderSide, Urgency
from models.order import StrategyParams
from models.order_request import (
    KellyParams,
    MicroPriceParams,
    OrderRequest,
    StrategyType,
)


def test_strategy_type_enum():
    """Test StrategyType enum values."""
    assert StrategyType.ICEBERG == "iceberg"
    assert StrategyType.MICRO_PRICE == "micro_price"
    assert StrategyType.KELLY == "kelly"


def test_micro_price_params_defaults():
    """Test MicroPriceParams default values."""
    params = MicroPriceParams()

    assert params.threshold_bps == 50
    assert params.check_interval == 2.0
    assert params.max_adjustments == 10
    assert params.aggression_limit_bps == 100


def test_micro_price_params_conversions():
    """Test MicroPriceParams conversion methods."""
    params = MicroPriceParams(threshold_bps=100, aggression_limit_bps=200)

    assert params.get_threshold_fraction() == 0.01  # 100 bps = 1%
    assert params.get_aggression_limit_fraction() == 0.02  # 200 bps = 2%


def test_micro_price_params_validation():
    """Test MicroPriceParams validation."""
    # Valid params
    params = MicroPriceParams(
        threshold_bps=50, check_interval=2.0, max_adjustments=10, aggression_limit_bps=100
    )
    assert params.threshold_bps == 50

    # Invalid threshold_bps (too low)
    with pytest.raises(ValueError):
        MicroPriceParams(threshold_bps=0)

    # Invalid threshold_bps (too high)
    with pytest.raises(ValueError):
        MicroPriceParams(threshold_bps=1001)


def test_kelly_params_creation():
    """Test KellyParams creation."""
    params = KellyParams(
        win_probability=0.65,
        kelly_fraction=0.25,
        max_position_size=5000,
        bankroll=10000,
    )

    assert params.win_probability == 0.65
    assert params.kelly_fraction == 0.25
    assert params.max_position_size == 5000
    assert params.bankroll == 10000
    assert params.recalculate_interval == 5.0  # default
    assert isinstance(params.micro_price_params, MicroPriceParams)


def test_kelly_params_validation():
    """Test KellyParams validation."""
    # Valid params
    params = KellyParams(
        win_probability=0.65, kelly_fraction=0.25, max_position_size=5000, bankroll=10000
    )
    assert params.win_probability == 0.65

    # Invalid win_probability (too high)
    with pytest.raises(ValueError):
        KellyParams(
            win_probability=1.5, kelly_fraction=0.25, max_position_size=5000, bankroll=10000
        )

    # Invalid win_probability (negative)
    with pytest.raises(ValueError):
        KellyParams(
            win_probability=-0.1, kelly_fraction=0.25, max_position_size=5000, bankroll=10000
        )


def test_iceberg_order_request():
    """Test OrderRequest for iceberg strategy."""
    request = OrderRequest(
        market_id="market-123",
        token_id="token-456",
        side=OrderSide.BUY,
        strategy_type=StrategyType.ICEBERG,
        total_size=1000,
        max_price=0.60,
        min_price=0.40,
        iceberg_params=StrategyParams(
            initial_tranche_size=200, min_tranche_size=100, max_tranche_size=300
        ),
    )

    assert request.strategy_type == StrategyType.ICEBERG
    assert request.total_size == 1000
    assert request.iceberg_params.initial_tranche_size == 200


def test_iceberg_request_missing_params():
    """Test iceberg request requires iceberg_params."""
    with pytest.raises(ValueError, match="iceberg_params required"):
        OrderRequest(
            market_id="market-123",
            token_id="token-456",
            side=OrderSide.BUY,
            strategy_type=StrategyType.ICEBERG,
            total_size=1000,
            max_price=0.60,
            min_price=0.40,
            # Missing iceberg_params
        )


def test_iceberg_request_missing_size():
    """Test iceberg request requires total_size."""
    with pytest.raises(ValueError, match="total_size required"):
        OrderRequest(
            market_id="market-123",
            token_id="token-456",
            side=OrderSide.BUY,
            strategy_type=StrategyType.ICEBERG,
            max_price=0.60,
            min_price=0.40,
            iceberg_params=StrategyParams(),
            # Missing total_size
        )


def test_micro_price_order_request():
    """Test OrderRequest for micro-price strategy."""
    request = OrderRequest(
        market_id="market-123",
        token_id="token-456",
        side=OrderSide.BUY,
        strategy_type=StrategyType.MICRO_PRICE,
        total_size=1000,
        max_price=0.60,
        min_price=0.40,
        micro_price_params=MicroPriceParams(threshold_bps=50, max_adjustments=10),
    )

    assert request.strategy_type == StrategyType.MICRO_PRICE
    assert request.total_size == 1000
    assert request.micro_price_params.threshold_bps == 50


def test_micro_price_request_missing_params():
    """Test micro-price request requires micro_price_params."""
    with pytest.raises(ValueError, match="micro_price_params required"):
        OrderRequest(
            market_id="market-123",
            token_id="token-456",
            side=OrderSide.BUY,
            strategy_type=StrategyType.MICRO_PRICE,
            total_size=1000,
            max_price=0.60,
            min_price=0.40,
            # Missing micro_price_params
        )


def test_kelly_order_request():
    """Test OrderRequest for Kelly criterion strategy."""
    request = OrderRequest(
        market_id="market-123",
        token_id="token-456",
        side=OrderSide.BUY,
        strategy_type=StrategyType.KELLY,
        max_price=0.60,
        min_price=0.40,
        kelly_params=KellyParams(
            win_probability=0.65,
            kelly_fraction=0.25,
            max_position_size=5000,
            bankroll=10000,
        ),
    )

    assert request.strategy_type == StrategyType.KELLY
    assert request.total_size is None  # Kelly calculates dynamically
    assert request.kelly_params.win_probability == 0.65


def test_kelly_request_missing_params():
    """Test Kelly request requires kelly_params."""
    with pytest.raises(ValueError, match="kelly_params required"):
        OrderRequest(
            market_id="market-123",
            token_id="token-456",
            side=OrderSide.BUY,
            strategy_type=StrategyType.KELLY,
            max_price=0.60,
            min_price=0.40,
            # Missing kelly_params
        )


def test_kelly_request_should_not_have_total_size():
    """Test Kelly request should not specify total_size."""
    with pytest.raises(ValueError, match="total_size should not be set"):
        OrderRequest(
            market_id="market-123",
            token_id="token-456",
            side=OrderSide.BUY,
            strategy_type=StrategyType.KELLY,
            total_size=1000,  # Should not be set for Kelly
            max_price=0.60,
            min_price=0.40,
            kelly_params=KellyParams(
                win_probability=0.65,
                kelly_fraction=0.25,
                max_position_size=5000,
                bankroll=10000,
            ),
        )


def test_order_request_price_validation():
    """Test price bounds validation."""
    # min_price >= max_price should fail
    with pytest.raises(ValueError, match="min_price must be less than max_price"):
        OrderRequest(
            market_id="market-123",
            token_id="token-456",
            side=OrderSide.BUY,
            strategy_type=StrategyType.ICEBERG,
            total_size=1000,
            max_price=0.40,
            min_price=0.60,  # Invalid: min > max
            iceberg_params=StrategyParams(),
        )


def test_order_request_defaults():
    """Test OrderRequest default values."""
    request = OrderRequest(
        market_id="market-123",
        token_id="token-456",
        side=OrderSide.BUY,
        strategy_type=StrategyType.ICEBERG,
        total_size=1000,
        max_price=0.60,
        min_price=0.40,
        iceberg_params=StrategyParams(),
    )

    assert request.urgency == Urgency.MEDIUM
    assert request.timeout == 300.0


def test_order_request_custom_urgency():
    """Test OrderRequest with custom urgency."""
    request = OrderRequest(
        market_id="market-123",
        token_id="token-456",
        side=OrderSide.BUY,
        strategy_type=StrategyType.ICEBERG,
        total_size=1000,
        max_price=0.60,
        min_price=0.40,
        iceberg_params=StrategyParams(),
        urgency=Urgency.HIGH,
        timeout=600.0,
    )

    assert request.urgency == Urgency.HIGH
    assert request.timeout == 600.0
