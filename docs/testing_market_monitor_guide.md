# Testing Market Monitor - Practical Guide

This guide shows you how to test `MarketMonitor` without connecting to real APIs.

## Quick Start - Run Existing Tests

```bash
# Run all market monitor tests
pytest tests/test_market_monitor.py -v

# Run a specific test
pytest tests/test_market_monitor.py::test_calculate_micro_price_balanced -v

# Run with output
pytest tests/test_market_monitor.py -v -s
```

## Understanding the Basics

### Why We Use Mocks

A **Mock** is a fake object that pretends to be the real thing. Instead of calling the Polymarket API:

```python
# ❌ Real API call (slow, requires auth, costs money)
real_client = PolymarketClient(config)
order_book = real_client.get_order_book("token-123")  # Actual network request

# ✅ Mock (instant, no auth needed, free)
mock_client = Mock()
mock_client.get_order_book.return_value = fake_data  # No network request
```

## Example 1: Testing Pure Functions (No API Needed)

The simplest tests check math functions that don't need the API at all.

```python
from unittest.mock import Mock
from core.market_monitor import MarketMonitor

def test_micro_price_calculation():
    """Test that micro-price is calculated correctly."""
    # Create a fake client (won't be used)
    client = Mock()

    # Create monitor
    monitor = MarketMonitor(client, "token-123")

    # Test the calculation
    # Formula: (best_bid × ask_depth + best_ask × bid_depth) / (bid_depth + ask_depth)
    # Example: (0.44 × 1000 + 0.46 × 1000) / 2000 = 0.45
    result = monitor.calculate_micro_price(
        best_bid=0.44,
        best_ask=0.46,
        bid_depth=1000,
        ask_depth=1000
    )

    assert result == 0.45
    print(f"✅ Micro-price calculated correctly: {result}")
```

**Run this test:**
```bash
pytest tests/test_market_monitor.py::test_calculate_micro_price_balanced -v
```

## Example 2: Testing with Mocked API Responses

When your function calls the API, you need to tell the mock what to return.

```python
from unittest.mock import Mock
from types import SimpleNamespace
from core.market_monitor import MarketMonitor

def test_getting_market_snapshot():
    """Test fetching and processing order book data."""

    # 1. Create a fake client
    client = Mock()

    # 2. Create fake order book data (what the API would return)
    fake_bid = SimpleNamespace(price="0.44", size="1000")
    fake_ask = SimpleNamespace(price="0.46", size="800")
    fake_order_book = SimpleNamespace(
        bids=[fake_bid],
        asks=[fake_ask]
    )

    # 3. Tell the mock what to return when get_order_book() is called
    client.get_order_book.return_value = fake_order_book
    client.get_orders.return_value = []  # No active orders

    # 4. Create monitor and call the function
    monitor = MarketMonitor(client, "token-123")
    snapshot = monitor.get_market_snapshot()

    # 5. Verify the results
    assert snapshot.best_bid == 0.44
    assert snapshot.best_ask == 0.46
    assert snapshot.bid_depth == 1000
    assert snapshot.ask_depth == 800

    print(f"✅ Snapshot created: bid={snapshot.best_bid}, ask={snapshot.best_ask}")
    print(f"   Micro-price: {snapshot.micro_price}")
```

**Run this test:**
```bash
pytest tests/test_market_monitor.py::test_get_market_snapshot -v
```

## Example 3: Testing Different Market Scenarios

You can test edge cases that are hard to reproduce with real APIs.

```python
from unittest.mock import Mock
from types import SimpleNamespace
import pytest
from core.market_monitor import MarketMonitor

def test_market_with_unbalanced_depth():
    """Test when one side has much more depth (common in real markets)."""
    client = Mock()

    # Create imbalanced order book (2x more buyers than sellers)
    fake_order_book = SimpleNamespace(
        bids=[
            SimpleNamespace(price="0.44", size="2000"),  # Heavy bid side
            SimpleNamespace(price="0.43", size="1500"),
        ],
        asks=[
            SimpleNamespace(price="0.46", size="1000"),  # Light ask side
            SimpleNamespace(price="0.47", size="800"),
        ]
    )

    client.get_order_book.return_value = fake_order_book
    client.get_orders.return_value = []

    monitor = MarketMonitor(client, "token-123")
    snapshot = monitor.get_market_snapshot()

    # Micro-price should be closer to ask (0.46) due to heavy bid depth
    # Formula: (0.44 × 1000 + 0.46 × 2000) / 3000 = 0.453
    expected_micro = (0.44 * 1000 + 0.46 * 2000) / 3000

    assert abs(snapshot.micro_price - expected_micro) < 0.001
    print(f"✅ Imbalanced market handled correctly")
    print(f"   Heavy bid side pushes micro-price toward ask: {snapshot.micro_price:.4f}")

def test_empty_order_book_raises_error():
    """Test that empty order books are detected."""
    client = Mock()

    # Empty order book (market might be paused)
    client.get_order_book.return_value = SimpleNamespace(bids=[], asks=[])

    monitor = MarketMonitor(client, "token-123")

    # Should raise ValueError
    with pytest.raises(ValueError, match="Empty order book"):
        monitor.get_market_snapshot()

    print("✅ Empty order book correctly raises error")
```

## Example 4: Interactive Testing (Manual Exploration)

Create a test file to explore behavior interactively:

```python
# tests/manual_test_monitor.py

from unittest.mock import Mock
from types import SimpleNamespace
from core.market_monitor import MarketMonitor

def create_fake_order_book(bid_price, ask_price, bid_size=1000, ask_size=1000):
    """Helper to quickly create test order books."""
    return SimpleNamespace(
        bids=[SimpleNamespace(price=str(bid_price), size=str(bid_size))],
        asks=[SimpleNamespace(price=str(ask_price), size=str(ask_size))]
    )

if __name__ == "__main__":
    # Create mock client
    client = Mock()

    # Scenario: Trump wins 2024 market
    print("=== Testing Trump Market ===")
    client.get_order_book.return_value = create_fake_order_book(
        bid_price=0.52,  # People willing to buy at 52 cents
        ask_price=0.54,  # People willing to sell at 54 cents
        bid_size=5000,
        ask_size=3000
    )
    client.get_orders.return_value = []

    monitor = MarketMonitor(client, "trump-token", band_width_bps=50)
    snapshot = monitor.get_market_snapshot()

    print(f"Best Bid: ${snapshot.best_bid}")
    print(f"Best Ask: ${snapshot.best_ask}")
    print(f"Spread: ${snapshot.spread:.4f}")
    print(f"Micro-price: ${snapshot.micro_price:.4f}")
    print(f"Fair value range: ${snapshot.micro_price_lower_band:.4f} - ${snapshot.micro_price_upper_band:.4f}")

    # Test if our order would be competitive
    our_buy_price = 0.53
    is_competitive = monitor.is_price_competitive(our_buy_price, snapshot)
    print(f"\nWould buying at ${our_buy_price} be competitive? {is_competitive}")
```

**Run this:**
```bash
python tests/manual_test_monitor.py
```

## Example 5: Testing with Multiple Order Book Levels

Test with realistic multi-level order books:

```python
from unittest.mock import Mock
from types import SimpleNamespace
from core.market_monitor import MarketMonitor

def test_deep_order_book():
    """Test with 5 levels of depth on each side."""
    client = Mock()

    # Create realistic order book with multiple levels
    fake_order_book = SimpleNamespace(
        bids=[
            SimpleNamespace(price="0.50", size="100"),  # Best bid
            SimpleNamespace(price="0.49", size="200"),
            SimpleNamespace(price="0.48", size="300"),
            SimpleNamespace(price="0.47", size="400"),
            SimpleNamespace(price="0.46", size="500"),
        ],
        asks=[
            SimpleNamespace(price="0.51", size="110"),  # Best ask
            SimpleNamespace(price="0.52", size="220"),
            SimpleNamespace(price="0.53", size="330"),
            SimpleNamespace(price="0.54", size="440"),
            SimpleNamespace(price="0.55", size="550"),
        ]
    )

    client.get_order_book.return_value = fake_order_book
    client.get_orders.return_value = []

    monitor = MarketMonitor(client, "token-123")
    snapshot = monitor.get_market_snapshot(depth_levels=5)

    # Verify all 5 levels are captured
    assert len(snapshot.bids) == 5
    assert len(snapshot.asks) == 5

    # Verify levels are sorted correctly
    assert snapshot.bids[0][0] == 0.50  # Best bid first
    assert snapshot.asks[0][0] == 0.51  # Best ask first

    print("✅ Multi-level order book processed correctly")
    print(f"   Captured {len(snapshot.bids)} bid levels and {len(snapshot.asks)} ask levels")
```

## Example 6: Helper Function for Quick Tests

Create reusable helpers for common test scenarios:

```python
# tests/test_helpers.py

from types import SimpleNamespace
from unittest.mock import Mock

def make_simple_monitor(bid_price=0.44, ask_price=0.46, bid_size=1000, ask_size=1000):
    """Create a monitor with a simple mocked order book."""
    client = Mock()

    order_book = SimpleNamespace(
        bids=[SimpleNamespace(price=str(bid_price), size=str(bid_size))],
        asks=[SimpleNamespace(price=str(ask_price), size=str(ask_size))]
    )

    client.get_order_book.return_value = order_book
    client.get_orders.return_value = []

    from core.market_monitor import MarketMonitor
    return MarketMonitor(client, "test-token")

# Use in tests:
def test_with_helper():
    """Test using the helper function."""
    monitor = make_simple_monitor(bid_price=0.40, ask_price=0.60)
    snapshot = monitor.get_market_snapshot()

    assert snapshot.best_bid == 0.40
    assert snapshot.best_ask == 0.60
    print("✅ Helper function makes testing easy!")
```

## Key Concepts Summary

### 1. Mock Objects
```python
client = Mock()  # Fake client that does nothing
```

### 2. Setting Return Values
```python
client.get_order_book.return_value = fake_data  # Control what it returns
```

### 3. SimpleNamespace
```python
# Creates objects with attributes (like API responses)
obj = SimpleNamespace(price="0.44", size="1000")
print(obj.price)  # "0.44"
```

### 4. Assertions
```python
assert actual == expected  # Test passes if true, fails if false
assert abs(actual - expected) < 0.001  # For floating point comparisons
```

## Running Tests

```bash
# All tests
pytest tests/test_market_monitor.py

# Verbose output
pytest tests/test_market_monitor.py -v

# Show print statements
pytest tests/test_market_monitor.py -v -s

# Run one test
pytest tests/test_market_monitor.py::test_calculate_micro_price_balanced

# Stop on first failure
pytest tests/test_market_monitor.py -x
```

## What Gets Tested vs What Gets Mocked

**Tested (Real Code):**
- ✅ `calculate_micro_price()` - math logic
- ✅ `calculate_bands()` - band calculation
- ✅ `get_market_snapshot()` - data processing
- ✅ `is_price_competitive()` - price checking

**Mocked (Fake Responses):**
- 🔷 `client.get_order_book()` - API call
- 🔷 `client.get_orders()` - API call
- 🔷 Network requests
- 🔷 Authentication

## Common Patterns

### Test Setup Pattern
```python
def test_something():
    # 1. Arrange - set up test data
    client = Mock()
    client.get_order_book.return_value = fake_data

    # 2. Act - call the function
    monitor = MarketMonitor(client, "token")
    result = monitor.some_function()

    # 3. Assert - verify results
    assert result == expected
```

### Testing Edge Cases
```python
# Zero depth
monitor.calculate_micro_price(0.44, 0.46, 0, 0)

# Extreme prices
monitor.calculate_micro_price(0.01, 0.99, 100, 100)

# Very imbalanced
monitor.calculate_micro_price(0.50, 0.51, 10000, 1)
```

This guide shows you don't need real API access to thoroughly test your code!
