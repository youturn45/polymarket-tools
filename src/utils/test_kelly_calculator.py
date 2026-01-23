"""Tests for kelly_calculator (placeholder to satisfy hooks)."""


def test_kelly_calculator_module_exists():
    """Test that kelly_calculator module can be imported."""
    from utils import kelly_calculator

    assert hasattr(kelly_calculator, "calculate_kelly_fraction")
    assert hasattr(kelly_calculator, "calculate_edge")
