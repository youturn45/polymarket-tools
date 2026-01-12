# Kelly Functions Guide

This guide explains how to use the Kelly criterion functions for automated trading.

## Quick Start

### For CLI Usage

Use the command-line calculator for interactive analysis:

```bash
# Basic usage
python -m utils.kelly_calculator --price 0.45 --true-prob 0.60 --side BUY

# Bid-ask spread analysis
python -m utils.kelly_calculator --bid 0.44 --ask 0.46 --true-prob 0.60

# With custom bankroll and edge bound
python -m utils.kelly_calculator --price 0.30 --true-prob 0.50 --bankroll 5000 --edge-upper-bound 0.10
```

### For Programmatic Usage

Import the core functions directly in your Python code:

```python
from utils.kelly_functions import (
    calculate_kelly_fraction,
    calculate_edge,
    calculate_position_size,
    calculate_fractional_kelly_sizes,
)

# Calculate Kelly fraction
kelly = calculate_kelly_fraction(
    true_probability=0.60,
    market_price=0.45,
    side="BUY",
    edge_upper_bound=0.05,
)

# Calculate position size
dollars, shares = calculate_position_size(
    true_probability=0.60,
    market_price=0.45,
    side="BUY",
    bankroll=10000.0,
    kelly_fraction_multiplier=0.25,  # Quarter Kelly
    edge_upper_bound=0.05,
)
```

## Module Organization

### `utils/kelly_functions.py`
Core calculation functions for programmatic use:
- `calculate_edge()` - Calculate expected value/edge
- `calculate_kelly_fraction()` - Calculate optimal bet fraction
- `calculate_position_size()` - Calculate position in dollars and shares
- `calculate_fractional_kelly_sizes()` - Get common fractional Kelly strategies

### `utils/kelly_calculator.py`
CLI tool that imports from `kelly_functions.py`:
- Command-line interface
- Display and formatting functions
- Bid-ask spread analysis

### `strategies/kelly.py`
Strategy implementation for order execution:
- `KellyStrategy` class
- Integration with micro-price strategy
- Position size recalculation

## Core Functions

### `calculate_kelly_fraction()`

Calculate the optimal Kelly fraction for a bet.

**Parameters:**
- `true_probability` (float): Your estimated probability (0-1)
- `market_price` (float): Current market price (0-1)
- `side` (str): "BUY" or "SELL"
- `edge_upper_bound` (float): Max edge to use (default: 0.05 = 5%)

**Returns:** Kelly fraction (0-1)

**Example:**
```python
kelly = calculate_kelly_fraction(
    true_probability=0.70,
    market_price=0.50,
    side="BUY",
    edge_upper_bound=0.05,
)
# Returns: 0.20 (20% of bankroll)
```

### `calculate_edge()`

Calculate the expected value (edge) of a bet.

**Parameters:**
- `true_probability` (float): Your estimated probability (0-1)
- `market_price` (float): Current market price (0-1)
- `side` (str): "BUY" or "SELL"

**Returns:** Edge as percentage (e.g., 5.0 for 5% edge)

**Example:**
```python
edge = calculate_edge(0.60, 0.45, "BUY")
# Returns: 15.0 (15% edge)
```

### `calculate_position_size()`

Calculate position size in dollars and shares.

**Parameters:**
- `true_probability` (float): Your estimated probability (0-1)
- `market_price` (float): Current market price (0-1)
- `side` (str): "BUY" or "SELL"
- `bankroll` (float): Available capital
- `kelly_fraction_multiplier` (float): Fraction of Kelly to use (default: 1.0)
- `edge_upper_bound` (float): Max edge to use (default: 0.05)

**Returns:** Tuple of (dollars, shares)

**Example:**
```python
dollars, shares = calculate_position_size(
    true_probability=0.65,
    market_price=0.50,
    side="BUY",
    bankroll=10000.0,
    kelly_fraction_multiplier=0.5,  # Half Kelly
    edge_upper_bound=0.05,
)
# Returns: (750.0, 1500)
```

### `calculate_fractional_kelly_sizes()`

Get position sizes for common fractional Kelly strategies.

**Parameters:**
- `true_probability` (float): Your estimated probability (0-1)
- `market_price` (float): Current market price (0-1)
- `side` (str): "BUY" or "SELL"
- `bankroll` (float): Available capital
- `edge_upper_bound` (float): Max edge to use (default: 0.05)

**Returns:** Dictionary mapping strategy name to (kelly_fraction, dollars, shares)

**Example:**
```python
strategies = calculate_fractional_kelly_sizes(
    true_probability=0.70,
    market_price=0.50,
    side="BUY",
    bankroll=5000.0,
)

# Access results:
# strategies["full"] = (0.20, 1000.0, 2000)
# strategies["half"] = (0.10, 500.0, 1000)
# strategies["quarter"] = (0.05, 250.0, 500)
# strategies["tenth"] = (0.02, 100.0, 200)
```

## Edge Upper Bound

The edge upper bound feature caps the maximum edge used in Kelly calculations to prevent over-betting on high-edge opportunities.

**Why use it?**
- Prevents over-confidence: Large perceived edges may be miscalibrated
- Risk management: Limits exposure to potentially mispriced markets
- Reduces variance: Smaller position sizes = lower bankroll swings

**Default:** 5% (0.05)

**Example:**
```python
# Without edge bound (uses full 15% edge)
kelly_unlimited = calculate_kelly_fraction(
    true_probability=0.60,
    market_price=0.45,
    side="BUY",
    edge_upper_bound=1.0,  # No practical limit
)
# Returns: ~0.273 (27.3% of bankroll)

# With 5% edge bound (caps edge at 5%)
kelly_capped = calculate_kelly_fraction(
    true_probability=0.60,
    market_price=0.45,
    side="BUY",
    edge_upper_bound=0.05,  # Cap at 5%
)
# Returns: ~0.091 (9.1% of bankroll)
```

## Automated Trading Example

See `examples/kelly_programmatic_example.py` for complete examples.

```python
from utils.kelly_functions import calculate_edge, calculate_position_size

# Market data
markets = [
    {"name": "Market A", "true_prob": 0.65, "ask": 0.50},
    {"name": "Market B", "true_prob": 0.55, "ask": 0.54},
]

bankroll = 10000.0
min_edge = 0.03  # Only trade if edge > 3%

for market in markets:
    # Check if we have edge
    edge = calculate_edge(market["true_prob"], market["ask"], "BUY") / 100

    if edge > min_edge:
        # Calculate position size (half Kelly)
        dollars, shares = calculate_position_size(
            true_probability=market["true_prob"],
            market_price=market["ask"],
            side="BUY",
            bankroll=bankroll,
            kelly_fraction_multiplier=0.5,
            edge_upper_bound=0.05,
        )

        print(f"{market['name']}: BUY ${dollars:.2f} ({shares} shares)")
```

## Best Practices

1. **Use Fractional Kelly**: Full Kelly can be too aggressive. Half Kelly (0.5) or Quarter Kelly (0.25) are recommended for most use cases.

2. **Set Conservative Edge Bounds**: The default 5% edge bound prevents over-betting. Increase cautiously.

3. **Validate Your Probabilities**: Kelly assumes your probability estimates are accurate. Garbage in, garbage out.

4. **Monitor Bankroll**: Recalculate positions as your bankroll changes.

5. **Consider Transaction Costs**: Kelly doesn't account for fees. Adjust accordingly.

## Integration with Order Execution

The Kelly functions integrate with the order execution system:

```python
from models.order_request import OrderRequest, StrategyType, KellyParams

# Create Kelly order request
request = OrderRequest(
    token_id="123456",
    side=OrderSide.BUY,
    strategy_type=StrategyType.KELLY,
    max_price=0.55,
    min_price=0.45,
    kelly_params=KellyParams(
        win_probability=0.65,
        kelly_fraction=0.25,  # Quarter Kelly
        max_position_size=5000,
        bankroll=10000,
        edge_upper_bound=0.05,  # 5% edge cap
    ),
)
```

## Further Reading

- [Kelly Criterion on Wikipedia](https://en.wikipedia.org/wiki/Kelly_criterion)
- `CLAUDE.md` - Project documentation
- `examples/kelly_programmatic_example.py` - Complete examples
