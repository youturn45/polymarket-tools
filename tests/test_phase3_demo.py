"""Tests for Phase 3 demo script."""


def test_phase3_demo_imports():
    """Test that phase3_demo can be imported without errors."""
    # Import the demo module to verify it has no syntax errors
    # and all dependencies are available
    try:
        import sys
        from pathlib import Path

        # Add examples directory to path
        examples_dir = Path(__file__).parent.parent / "examples"
        sys.path.insert(0, str(examples_dir))

        # Import should work
        import phase3_demo

        # Verify main functions exist
        assert hasattr(phase3_demo, "demo_order_daemon")
        assert hasattr(phase3_demo, "demo_micro_price_strategy")
        assert hasattr(phase3_demo, "demo_kelly_strategy")
        assert hasattr(phase3_demo, "demo_multiple_strategies")
        assert hasattr(phase3_demo, "main")

    finally:
        # Clean up
        if str(examples_dir) in sys.path:
            sys.path.remove(str(examples_dir))
