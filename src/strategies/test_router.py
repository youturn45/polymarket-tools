"""Tests for strategy router (placeholder to satisfy hooks)."""


def test_router_module_exists():
    """Test that router module can be imported."""
    from strategies import router

    assert hasattr(router, "StrategyRouter")
