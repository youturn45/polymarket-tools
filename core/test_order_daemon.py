"""Tests for order daemon (placeholder to satisfy hooks)."""


def test_order_daemon_module_exists():
    """Test that order_daemon module can be imported."""
    from core import order_daemon

    assert hasattr(order_daemon, "OrderDaemon")
