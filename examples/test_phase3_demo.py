"""Test that phase3_demo can be imported."""


def test_phase3_demo_imports():
    """Test that phase3_demo imports without errors."""
    import phase3_demo

    # Verify functions exist
    assert hasattr(phase3_demo, "demo_order_daemon")
    assert hasattr(phase3_demo, "demo_micro_price_strategy")
    assert hasattr(phase3_demo, "demo_kelly_strategy")
    assert hasattr(phase3_demo, "demo_multiple_strategies")
    assert hasattr(phase3_demo, "main")
