"""Example: Using Kelly criterion functions programmatically for automated trading.

This example demonstrates how to import and use the core Kelly calculation functions
directly in your Python code for automated order placement.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.kelly_functions import (
    calculate_edge,
    calculate_fractional_kelly_sizes,
    calculate_kelly_fraction,
    calculate_position_size,
)


def example_1_basic_calculation():
    """Example 1: Basic Kelly fraction calculation."""
    print("=" * 80)
    print("EXAMPLE 1: Basic Kelly Fraction Calculation")
    print("=" * 80)

    # Your belief: 60% chance of YES outcome
    true_probability = 0.60

    # Market is pricing YES at 45%
    market_price = 0.45

    # Calculate Kelly fraction for buying YES
    kelly = calculate_kelly_fraction(
        true_probability=true_probability,
        market_price=market_price,
        side="BUY",
        edge_upper_bound=0.05,  # Cap edge at 5%
    )

    print(f"True Probability: {true_probability:.2%}")
    print(f"Market Price: {market_price:.2%}")
    print(f"Kelly Fraction: {kelly:.2%}")
    print()


def example_2_position_sizing():
    """Example 2: Calculate position size for a trade."""
    print("=" * 80)
    print("EXAMPLE 2: Position Sizing")
    print("=" * 80)

    # Market parameters
    true_probability = 0.70
    market_price = 0.50
    bankroll = 10000.0  # $10,000 available

    # Use quarter Kelly (conservative)
    dollars, shares = calculate_position_size(
        true_probability=true_probability,
        market_price=market_price,
        side="BUY",
        bankroll=bankroll,
        kelly_fraction_multiplier=0.25,  # Quarter Kelly
        edge_upper_bound=0.05,
    )

    print(f"Bankroll: ${bankroll:,.2f}")
    print(f"True Probability: {true_probability:.2%}")
    print(f"Market Price: {market_price:.2%}")
    print(f"Strategy: Quarter Kelly")
    print(f"Position Size: ${dollars:,.2f} ({shares:,} shares)")
    print()


def example_3_multiple_strategies():
    """Example 3: Compare different Kelly fractions."""
    print("=" * 80)
    print("EXAMPLE 3: Compare Kelly Strategies")
    print("=" * 80)

    # Market parameters
    true_probability = 0.75
    market_price = 0.60
    bankroll = 5000.0

    # Get all common fractional Kelly strategies
    strategies = calculate_fractional_kelly_sizes(
        true_probability=true_probability,
        market_price=market_price,
        side="BUY",
        bankroll=bankroll,
        edge_upper_bound=0.05,
    )

    print(f"Bankroll: ${bankroll:,.2f}")
    print(f"True Probability: {true_probability:.2%}")
    print(f"Market Price: {market_price:.2%}")
    print()
    print(f"{'Strategy':<15} {'Kelly %':<12} {'Bet Size':<15} {'Shares':<10}")
    print("-" * 52)

    for name, (kelly_pct, dollars, shares) in strategies.items():
        print(f"{name.capitalize():<15} {kelly_pct:>6.2%}      ${dollars:>10,.2f}  {shares:>8,}")

    print()


def example_4_edge_calculation():
    """Example 4: Calculate edge for different scenarios."""
    print("=" * 80)
    print("EXAMPLE 4: Edge Calculation")
    print("=" * 80)

    scenarios = [
        (0.60, 0.45, "BUY", "Strong edge"),
        (0.52, 0.50, "BUY", "Small edge"),
        (0.30, 0.40, "SELL", "Good sell opportunity"),
        (0.50, 0.50, "BUY", "No edge"),
    ]

    print(f"{'Scenario':<25} {'True Prob':<12} {'Market':<12} {'Side':<6} {'Edge':<10}")
    print("-" * 65)

    for true_prob, market_price, side, description in scenarios:
        edge = calculate_edge(true_prob, market_price, side)
        print(
            f"{description:<25} {true_prob:>6.1%}       {market_price:>6.1%}       "
            f"{side:<6} {edge:>+6.2f}%"
        )

    print()


def example_5_automated_trading():
    """Example 5: Automated trading decision logic."""
    print("=" * 80)
    print("EXAMPLE 5: Automated Trading Decision")
    print("=" * 80)

    # Market data (simulated)
    markets = [
        {
            "name": "Market A",
            "true_probability": 0.65,
            "best_ask": 0.50,
            "best_bid": 0.48,
        },
        {
            "name": "Market B",
            "true_probability": 0.35,
            "best_ask": 0.45,
            "best_bid": 0.43,
        },
        {
            "name": "Market C",
            "true_probability": 0.55,
            "best_ask": 0.54,
            "best_bid": 0.52,
        },
    ]

    bankroll = 10000.0
    min_edge_threshold = 0.03  # Only trade if edge > 3%

    print(f"Bankroll: ${bankroll:,.2f}")
    print(f"Min Edge Threshold: {min_edge_threshold:.1%}")
    print()

    for market in markets:
        name = market["name"]
        true_prob = market["true_probability"]
        ask = market["best_ask"]
        bid = market["best_bid"]

        # Determine which side to trade (if any)
        buy_edge = calculate_edge(true_prob, ask, "BUY") / 100
        sell_edge = calculate_edge(true_prob, bid, "SELL") / 100

        print(f"{name}:")
        print(f"  True Prob: {true_prob:.2%}, Bid: {bid:.2%}, Ask: {ask:.2%}")

        if buy_edge > min_edge_threshold:
            # Good buy opportunity
            dollars, shares = calculate_position_size(
                true_probability=true_prob,
                market_price=ask,
                side="BUY",
                bankroll=bankroll,
                kelly_fraction_multiplier=0.5,  # Half Kelly
                edge_upper_bound=0.05,
            )
            print(f"  ✅ BUY: Edge={buy_edge:.2%}, Position=${dollars:,.2f} ({shares:,} shares)")

        elif sell_edge > min_edge_threshold:
            # Good sell opportunity
            dollars, shares = calculate_position_size(
                true_probability=true_prob,
                market_price=bid,
                side="SELL",
                bankroll=bankroll,
                kelly_fraction_multiplier=0.5,  # Half Kelly
                edge_upper_bound=0.05,
            )
            print(f"  ✅ SELL: Edge={sell_edge:.2%}, Position=${dollars:,.2f} ({shares:,} shares)")

        else:
            print(f"  ⏭️  SKIP: Insufficient edge (Buy: {buy_edge:.2%}, Sell: {sell_edge:.2%})")

        print()


def main():
    """Run all examples."""
    example_1_basic_calculation()
    example_2_position_sizing()
    example_3_multiple_strategies()
    example_4_edge_calculation()
    example_5_automated_trading()

    print("=" * 80)
    print("For more advanced usage, see:")
    print("  - utils/kelly_functions.py (core functions)")
    print("  - strategies/kelly.py (strategy implementation)")
    print("  - models/order_request.py (KellyParams model)")
    print("=" * 80)


if __name__ == "__main__":
    main()
