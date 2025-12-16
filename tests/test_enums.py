"""Tests for enumerations."""

from models.enums import OrderSide, OrderStatus, Urgency


def test_order_side_values():
    """Test OrderSide enum values."""
    assert OrderSide.BUY.value == "BUY"
    assert OrderSide.SELL.value == "SELL"


def test_order_status_values():
    """Test OrderStatus enum values."""
    assert OrderStatus.QUEUED.value == "queued"
    assert OrderStatus.ACTIVE.value == "active"
    assert OrderStatus.PARTIALLY_FILLED.value == "partially_filled"
    assert OrderStatus.COMPLETED.value == "completed"
    assert OrderStatus.CANCELLED.value == "cancelled"
    assert OrderStatus.FAILED.value == "failed"


def test_urgency_values():
    """Test Urgency enum values."""
    assert Urgency.LOW.value == "LOW"
    assert Urgency.MEDIUM.value == "MEDIUM"
    assert Urgency.HIGH.value == "HIGH"
