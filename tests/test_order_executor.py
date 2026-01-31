"""Tests for order executor - integration tests require API access."""

# Note: Full integration tests for execute_single_order and execute_iceberg_order
# require actual API access and are covered in phase demos and manual testing.
# Unit tests for helper methods are below.

from api.polymarket_client import PolymarketClient
from core.order_executor import OrderExecutor


def test_extract_order_id_from_dict():
    """Test extracting order ID from dict response."""
    client = PolymarketClient.__new__(PolymarketClient)

    # Test with orderID field
    response = {"orderID": "12345", "other": "data"}
    assert client.extract_order_id(response) == "12345"

    # Test with id field
    response = {"id": "67890", "other": "data"}
    assert client.extract_order_id(response) == "67890"

    # Test with unknown format
    response = {"unknown": "format"}
    assert client.extract_order_id(response) == "unknown"


def test_extract_order_id_from_string():
    """Test extracting order ID from string response."""
    client = PolymarketClient.__new__(PolymarketClient)

    response = "order-id-12345"
    assert client.extract_order_id(response) == "order-id-12345"


def test_extract_filled_amount_from_response():
    """Test extracting filled amount from status response."""
    from unittest.mock import Mock

    executor = OrderExecutor(client=Mock(), logger=Mock())

    # Test with size_matched field
    response = {"size_matched": "100.5"}
    assert executor._extract_filled_amount(response) == 100

    # Test with filled field
    response = {"filled": "50.0"}
    assert executor._extract_filled_amount(response) == 50

    # Test with no fill data
    response = {"other": "data"}
    assert executor._extract_filled_amount(response) == 0


def test_extract_filled_amount_handles_zero():
    """Test that zero filled amount is handled correctly."""
    from unittest.mock import Mock

    executor = OrderExecutor(client=Mock(), logger=Mock())

    response = {"size_matched": "0"}
    assert executor._extract_filled_amount(response) == 0
