#!/usr/bin/env python3
"""Kelly Criterion Calculator CLI for Prediction Markets.

Command-line interface for calculating optimal bet sizing using the Kelly criterion.
The core calculation functions are in utils/kelly_functions.py and can be imported
directly for programmatic use in automated trading strategies.

Usage:
    # Single price analysis (BUY)
    python -m utils.kelly_calculator --price 0.45 --true-prob 0.60 --side BUY

    # Bid-Ask analysis (automatic side selection)
    python -m utils.kelly_calculator --bid 0.44 --ask 0.46 --true-prob 0.60

    # With custom bankroll and edge bound
    python -m utils.kelly_calculator --price 0.30 --true-prob 0.50 --bankroll 5000 --edge-upper-bound 0.10
"""

import argparse

from utils.kelly_functions import calculate_edge, calculate_kelly_fraction


def format_percentage(value: float) -> str:
    """Format a decimal as percentage."""
    return f"{value * 100:.2f}%"


def format_currency(value: float) -> str:
    """Format as currency."""
    return f"${value:,.2f}"


def display_kelly_analysis(
    true_probability: float,
    market_price: float,
    side: str,
    bankroll: float = 1000.0,
    edge_upper_bound: float = 0.05,
):
    """Display comprehensive Kelly analysis.

    Args:
        true_probability: Your estimated true probability
        market_price: Current market price
        side: "BUY" or "SELL"
        bankroll: Your available bankroll
        edge_upper_bound: Maximum edge to use in calculation (default: 0.05 = 5%)
    """
    print("=" * 80)
    print("KELLY CRITERION ANALYSIS")
    print("=" * 80)
    print(f"Side: {side.upper()}")
    print(f"Market Price: {format_percentage(market_price)}")
    print(f"Your True Probability: {format_percentage(true_probability)}")
    print(f"Bankroll: {format_currency(bankroll)}")
    print(f"Edge Upper Bound: {format_percentage(edge_upper_bound)}")
    print()

    # Calculate edge
    edge = calculate_edge(true_probability, market_price, side)
    print(f"Expected Value (Edge): {edge:+.2f}%")

    if edge <= 0:
        print("\n⚠️  WARNING: No edge detected! This is a -EV bet.")
        print("Kelly criterion recommends: DO NOT BET")
        return

    print("✅ Positive edge detected")

    # Check if edge exceeds upper bound
    if edge / 100 > edge_upper_bound:
        print(f"⚠️  Edge ({edge:.2f}%) exceeds upper bound ({edge_upper_bound * 100:.2f}%)")
        print(f"   Kelly calculation will use capped edge of {edge_upper_bound * 100:.2f}%")

    print()

    # Calculate full Kelly with edge upper bound
    kelly_full = calculate_kelly_fraction(true_probability, market_price, side, edge_upper_bound)

    if kelly_full == 0:
        print("Kelly criterion recommends: DO NOT BET (0% of bankroll)")
        return

    print("RECOMMENDED BET SIZES:")
    print("-" * 80)
    print(f"{'Strategy':<20} {'% of Bankroll':<20} {'Bet Size':<20} {'# Shares':<15}")
    print("-" * 80)

    # Calculate for different Kelly fractions
    kelly_fractions = [
        ("Full Kelly", 1.0),
        ("Half Kelly (1/2)", 0.5),
        ("Quarter Kelly (1/4)", 0.25),
        ("Tenth Kelly (1/10)", 0.1),
    ]

    for name, fraction in kelly_fractions:
        adjusted_kelly = kelly_full * fraction
        bet_amount = bankroll * adjusted_kelly
        num_shares = int(bet_amount / market_price) if market_price > 0 else 0

        print(
            f"{name:<20} {format_percentage(adjusted_kelly):<20} "
            f"{format_currency(bet_amount):<20} {num_shares:<15,}"
        )

    print("-" * 80)
    print()
    print("💡 RECOMMENDATIONS:")
    print("   - Full Kelly maximizes long-term growth but has high variance")
    print("   - Half Kelly (1/2) is recommended for most bettors (lower risk)")
    print("   - Quarter Kelly (1/4) is very conservative")
    print("   - Tenth Kelly (1/10) is extremely conservative")
    print()


def calculate_bid_ask_analysis(
    bid: float,
    ask: float,
    true_probability: float,
    bankroll: float = 1000.0,
    edge_upper_bound: float = 0.05,
):
    """Analyze Kelly for both bid and ask prices.

    Args:
        bid: Best bid price (where you can SELL)
        ask: Best ask price (where you can BUY)
        true_probability: Your estimated true probability
        bankroll: Your available bankroll
        edge_upper_bound: Maximum edge to use in calculation (default: 0.05 = 5%)
    """
    print("=" * 80)
    print("BID-ASK KELLY ANALYSIS")
    print("=" * 80)
    print(f"Best Bid: {format_percentage(bid)} (you can SELL here)")
    print(f"Best Ask: {format_percentage(ask)} (you can BUY here)")
    print(f"Spread: {format_percentage(ask - bid)}")
    print(f"Mid-price: {format_percentage((bid + ask) / 2)}")
    print(f"Your True Probability: {format_percentage(true_probability)}")
    print()

    # Determine which side to bet
    if true_probability > ask:
        print(
            f"✅ RECOMMENDATION: BUY (your estimate {format_percentage(true_probability)} > ask {format_percentage(ask)})"
        )
        print()
        display_kelly_analysis(true_probability, ask, "BUY", bankroll, edge_upper_bound)
    elif true_probability < bid:
        print(
            f"✅ RECOMMENDATION: SELL (your estimate {format_percentage(true_probability)} < bid {format_percentage(bid)})"
        )
        print()
        display_kelly_analysis(true_probability, bid, "SELL", bankroll, edge_upper_bound)
    else:
        print(
            f"⚠️  NO BET: Your estimate {format_percentage(true_probability)} is within the spread"
        )
        print("   Market is fairly priced - no edge available")
        print()


def main():
    """Command-line interface for Kelly calculator."""
    parser = argparse.ArgumentParser(
        description="Kelly Criterion Calculator for Prediction Markets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Single price analysis (BUY)
  %(prog)s --price 0.45 --true-prob 0.60 --side BUY

  # Single price analysis (SELL)
  %(prog)s --price 0.55 --true-prob 0.40 --side SELL

  # Bid-ask analysis (automatic side selection)
  %(prog)s --bid 0.44 --ask 0.46 --true-prob 0.60

  # With custom bankroll
  %(prog)s --price 0.30 --true-prob 0.50 --side BUY --bankroll 5000

  # Percentage format (converts to decimal)
  %(prog)s --price 45 --true-prob 60 --side BUY

Notes:
  - Prices can be decimals (0.45) or percentages (45)
  - Use --side for --price mode; --bid/--ask mode auto-selects
        """,
    )

    parser.add_argument(
        "--price",
        type=float,
        help="Execution price (0-1 or 0-100 if percentage)",
    )
    parser.add_argument(
        "--bid",
        type=float,
        help="Best bid price (0-1 or 0-100 if percentage). Use with --ask.",
    )
    parser.add_argument(
        "--ask",
        type=float,
        help="Best ask price (0-1 or 0-100 if percentage). Use with --bid.",
    )
    parser.add_argument(
        "--true-prob",
        type=float,
        required=True,
        help="Your estimated true probability (0-1 or 0-100)",
    )
    parser.add_argument(
        "--side",
        choices=["BUY", "SELL", "buy", "sell"],
        help="Order side: BUY or SELL (required with --price)",
    )
    parser.add_argument(
        "--bankroll",
        type=float,
        default=1000.0,
        help="Your available bankroll (default: $1000)",
    )
    parser.add_argument(
        "--edge-upper-bound",
        type=float,
        default=0.05,
        help=(
            "Maximum edge to use in Kelly calculation (default: 0.05 = 5%%). "
            "Caps edge to prevent over-betting."
        ),
    )

    args = parser.parse_args()

    # Convert percentages to decimals if needed
    def normalize_prob(p: float) -> float:
        return p / 100 if p > 1 else p

    true_prob = normalize_prob(args.true_prob)
    edge_bound = normalize_prob(args.edge_upper_bound)

    # Validate probability range
    if not 0 <= true_prob <= 1:
        print("Error: true-prob must be between 0-1 or 0-100")
        return

    # Validate edge upper bound
    if not 0 < edge_bound <= 1:
        print("Error: edge-upper-bound must be between 0-1 or 0-100")
        return

    # Bid/ask mode
    if args.bid is not None or args.ask is not None:
        if args.bid is None or args.ask is None:
            print("Error: Must provide both --bid and --ask")
            return

        bid = normalize_prob(args.bid)
        ask = normalize_prob(args.ask)

        if not 0 <= bid <= 1 or not 0 <= ask <= 1:
            print("Error: bid and ask must be between 0-1 or 0-100")
            return

        if bid >= ask:
            print("Error: bid must be less than ask")
            return

        calculate_bid_ask_analysis(bid, ask, true_prob, args.bankroll, edge_bound)
        return

    # Single price mode
    if args.price is not None:
        if not args.side:
            print("Error: --side is required when using --price")
            return

        price = normalize_prob(args.price)

        if not 0 <= price <= 1:
            print("Error: price must be between 0-1 or 0-100")
            return

        display_kelly_analysis(true_prob, price, args.side.upper(), args.bankroll, edge_bound)
        return

    print("Error: Must provide either --price or both --bid and --ask")
    parser.print_help()


if __name__ == "__main__":
    main()
