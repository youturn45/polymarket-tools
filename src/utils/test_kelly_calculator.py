"""Tests for kelly_calculator and kelly_functions modules."""


def test_kelly_functions_module_exists():
    """Test that kelly_functions module can be imported."""
    from utils import kelly_functions

    assert hasattr(kelly_functions, "calculate_kelly_fraction")
    assert hasattr(kelly_functions, "calculate_edge")
    assert hasattr(kelly_functions, "calculate_position_size")
    assert hasattr(kelly_functions, "calculate_fractional_kelly_sizes")


def test_kelly_calculator_imports():
    """Test that kelly_calculator CLI imports work correctly."""
    from utils import kelly_calculator

    # Calculator should import functions from kelly_functions
    assert hasattr(kelly_calculator, "display_kelly_analysis")
    assert hasattr(kelly_calculator, "calculate_bid_ask_analysis")
    assert hasattr(kelly_calculator, "format_percentage")
    assert hasattr(kelly_calculator, "format_currency")
