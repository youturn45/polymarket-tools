"""Tests for iceberg order splitting strategy."""

import random

from models.order import StrategyParams
from strategies.iceberg import IcebergStrategy


def test_iceberg_strategy_initialization():
    """Test IcebergStrategy initialization."""
    params = StrategyParams(
        initial_tranche_size=100,
        min_tranche_size=50,
        max_tranche_size=200,
    )
    strategy = IcebergStrategy(params)

    assert strategy.params == params
    assert strategy.params.initial_tranche_size == 100
    assert strategy.params.min_tranche_size == 50
    assert strategy.params.max_tranche_size == 200


def test_first_tranche_uses_initial_size():
    """Test that first tranche uses initial_tranche_size as base."""
    params = StrategyParams(
        initial_tranche_size=100,
        min_tranche_size=50,
        max_tranche_size=200,
        tranche_randomization=0.0,  # No randomization for predictable test
    )
    strategy = IcebergStrategy(params)

    # First tranche should be exactly initial_tranche_size (no randomization)
    tranche_size = strategy.calculate_next_tranche_size(remaining_size=1000, is_first_tranche=True)
    assert tranche_size == 100


def test_subsequent_tranches_use_min_size():
    """Test that subsequent tranches use min_tranche_size as base."""
    params = StrategyParams(
        initial_tranche_size=100,
        min_tranche_size=50,
        max_tranche_size=200,
        tranche_randomization=0.0,  # No randomization
    )
    strategy = IcebergStrategy(params)

    # Subsequent tranche should be min_tranche_size
    tranche_size = strategy.calculate_next_tranche_size(remaining_size=1000, is_first_tranche=False)
    assert tranche_size == 50


def test_tranche_respects_max_bound():
    """Test that tranche size respects max_tranche_size."""
    params = StrategyParams(
        initial_tranche_size=100,
        min_tranche_size=50,
        max_tranche_size=150,
        tranche_randomization=1.0,  # 100% randomization - wide range
    )
    strategy = IcebergStrategy(params)

    # Run multiple times to ensure randomization doesn't exceed max
    random.seed(42)
    for _ in range(100):
        tranche_size = strategy.calculate_next_tranche_size(
            remaining_size=1000, is_first_tranche=True
        )
        assert tranche_size <= 150


def test_tranche_respects_min_bound():
    """Test that tranche size respects min_tranche_size."""
    params = StrategyParams(
        initial_tranche_size=100,
        min_tranche_size=75,
        max_tranche_size=200,
        tranche_randomization=1.0,  # 100% randomization
    )
    strategy = IcebergStrategy(params)

    # Run multiple times to ensure randomization doesn't go below min
    random.seed(42)
    for _ in range(100):
        tranche_size = strategy.calculate_next_tranche_size(
            remaining_size=1000, is_first_tranche=True
        )
        assert tranche_size >= 75


def test_tranche_does_not_exceed_remaining():
    """Test that tranche size never exceeds remaining size."""
    params = StrategyParams(
        initial_tranche_size=100,
        min_tranche_size=50,
        max_tranche_size=200,
    )
    strategy = IcebergStrategy(params)

    # Remaining is less than min_tranche_size
    tranche_size = strategy.calculate_next_tranche_size(remaining_size=30, is_first_tranche=False)
    assert tranche_size == 30

    # Remaining is less than initial_tranche_size
    tranche_size = strategy.calculate_next_tranche_size(remaining_size=80, is_first_tranche=True)
    assert tranche_size == 80


def test_zero_remaining_returns_zero():
    """Test that zero remaining size returns zero tranche."""
    params = StrategyParams()
    strategy = IcebergStrategy(params)

    tranche_size = strategy.calculate_next_tranche_size(remaining_size=0, is_first_tranche=False)
    assert tranche_size == 0


def test_negative_remaining_returns_zero():
    """Test that negative remaining size returns zero tranche."""
    params = StrategyParams()
    strategy = IcebergStrategy(params)

    tranche_size = strategy.calculate_next_tranche_size(remaining_size=-10, is_first_tranche=False)
    assert tranche_size == 0


def test_randomization_varies_sizes():
    """Test that randomization produces varying tranche sizes."""
    params = StrategyParams(
        initial_tranche_size=100,
        min_tranche_size=50,
        max_tranche_size=200,
        tranche_randomization=0.2,  # ±20%
    )
    strategy = IcebergStrategy(params)

    # Generate multiple tranches and verify they vary
    random.seed(42)
    sizes = set()
    for _ in range(50):
        size = strategy.calculate_next_tranche_size(remaining_size=1000, is_first_tranche=True)
        sizes.add(size)

    # Should have multiple different sizes (not all the same)
    assert len(sizes) > 1


def test_calculate_all_tranches():
    """Test calculating all tranches for an order."""
    params = StrategyParams(
        initial_tranche_size=200,
        min_tranche_size=100,
        max_tranche_size=300,
        tranche_randomization=0.0,  # No randomization for predictable test
    )
    strategy = IcebergStrategy(params)

    # 1000 shares should split into multiple tranches
    tranches = strategy.calculate_all_tranches(1000)

    # Verify tranches sum to total
    assert sum(tranches) == 1000

    # First tranche should be 200 (initial_tranche_size)
    assert tranches[0] == 200

    # Subsequent tranches should be 100 (min_tranche_size)
    for tranche in tranches[1:]:
        assert tranche == 100

    # Should have 1 initial + 8 subsequent tranches
    assert len(tranches) == 9


def test_calculate_all_tranches_with_randomization():
    """Test all tranches calculation with randomization."""
    params = StrategyParams(
        initial_tranche_size=200,
        min_tranche_size=100,
        max_tranche_size=300,
        tranche_randomization=0.2,
    )
    strategy = IcebergStrategy(params)

    random.seed(42)
    tranches = strategy.calculate_all_tranches(1000)

    # Verify tranches sum exactly to total
    assert sum(tranches) == 1000

    # All tranches within bounds (except last which can be smaller)
    for i, tranche in enumerate(tranches):
        if i < len(tranches) - 1:
            # All tranches except last should respect bounds
            assert 100 <= tranche <= 300
        else:
            # Last tranche can be smaller (remainder)
            assert tranche <= 300


def test_calculate_all_tranches_small_order():
    """Test calculating tranches for order smaller than initial size."""
    params = StrategyParams(
        initial_tranche_size=200,
        min_tranche_size=100,
        max_tranche_size=300,
    )
    strategy = IcebergStrategy(params)

    # Order smaller than initial_tranche_size
    tranches = strategy.calculate_all_tranches(150)

    # Should have exactly one tranche of 150
    assert len(tranches) == 1
    assert tranches[0] == 150


def test_inter_tranche_delay():
    """Test inter-tranche delay is within expected range."""
    params = StrategyParams()
    strategy = IcebergStrategy(params)

    # Test multiple delays
    random.seed(42)
    for _ in range(50):
        delay = strategy.calculate_inter_tranche_delay()
        assert 1.0 <= delay <= 3.0


def test_inter_tranche_delay_varies():
    """Test that inter-tranche delays vary."""
    params = StrategyParams()
    strategy = IcebergStrategy(params)

    random.seed(42)
    delays = [strategy.calculate_inter_tranche_delay() for _ in range(50)]

    # Should have multiple different delays
    assert len(set(delays)) > 1
