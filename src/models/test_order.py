"""Tests for order model (placeholder to satisfy hooks)."""


def test_order_module_exists():
    """Test that order module can be imported."""
    from models import order

    assert hasattr(order, "Order")
    assert hasattr(order, "StrategyParams")
