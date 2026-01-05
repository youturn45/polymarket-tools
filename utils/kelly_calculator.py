#!/usr/bin/env python3
"""
Kelly Criterion Calculator for Prediction Markets

Calculate optimal bet sizing using the Kelly criterion.
"""

import argparse


def calculate_kelly_fraction(
    true_probability: float,
    market_price: float,
    side: str = "BUY",
) -> float:
    """Calculate Kelly fraction for a prediction market bet.

    For prediction markets:
    - If buying YES at price p: odds = (1 - p) / p
    - If selling YES at price p: odds = p / (1 - p)

    Kelly formula: f* = (b*p - q) / b
    where:
    - f* = fraction of bankroll to bet
    - b = odds (payout per dollar risked)
    - p = win probability (your true belief)
    - q = loss probability (1 - p)

    Args:
        true_probability: Your estimated true probability (0-1)
        market_price: Current market price (0-1)
        side: "BUY" or "SELL"

    Returns:
        Kelly fraction (0-1)
    """
    # Calculate odds based on side
    if side.upper() == "BUY":
        # Buying at price p, pays out 1 if win
        # Odds: how much you win per dollar risked
        # Win: (1 - p), Risk: p, Odds: (1 - p) / p
        if market_price == 0:
            return 0.0
        odds = (1 - market_price) / market_price
    else:  # SELL
        # Selling at price p
        # Win: p, Risk: (1 - p), Odds: p / (1 - p)
        if market_price == 1:
            return 0.0
        odds = market_price / (1 - market_price)

    # Kelly formula: f* = (odds * win_prob - loss_prob) / odds
    loss_probability = 1 - true_probability
    kelly_fraction = (odds * true_probability - loss_probability) / odds

    # Clamp to [0, 1] - never bet negative or more than 100%
    kelly_fraction = max(0.0, min(1.0, kelly_fraction))

    return kelly_fraction


def calculate_edge(true_probability: float, market_price: float, side: str = "BUY") -> float:
    """Calculate expected value (edge) of the bet.

    Args:
        true_probability: Your estimated true probability
        market_price: Current market price
        side: "BUY" or "SELL"

    Returns:
        Expected value as percentage
    """
    if side.upper() == "BUY":
        # Expected value = (win_prob * payout) - (loss_prob * cost)
        # Payout = 1 - price, Cost = price
        ev = (true_probability * (1 - market_price)) - ((1 - true_probability) * market_price)
    else:  # SELL
        ev = (true_probability * market_price) - ((1 - true_probability) * (1 - market_price))

    return ev * 100  # Return as percentage


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
):
    """Display comprehensive Kelly analysis.

    Args:
        true_probability: Your estimated true probability
        market_price: Current market price
        side: "BUY" or "SELL"
        bankroll: Your available bankroll
    """
    print("=" * 80)
    print("KELLY CRITERION ANALYSIS")
    print("=" * 80)
    print(f"Side: {side.upper()}")
    print(f"Market Price: {format_percentage(market_price)}")
    print(f"Your True Probability: {format_percentage(true_probability)}")
    print(f"Bankroll: {format_currency(bankroll)}")
    print()

    # Calculate edge
    edge = calculate_edge(true_probability, market_price, side)
    print(f"Expected Value (Edge): {edge:+.2f}%")

    if edge <= 0:
        print("\n⚠️  WARNING: No edge detected! This is a -EV bet.")
        print("Kelly criterion recommends: DO NOT BET")
        return

    print("✅ Positive edge detected")
    print()

    # Calculate full Kelly
    kelly_full = calculate_kelly_fraction(true_probability, market_price, side)

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
    bid: float, ask: float, true_probability: float, bankroll: float = 1000.0
):
    """Analyze Kelly for both bid and ask prices.

    Args:
        bid: Best bid price (where you can SELL)
        ask: Best ask price (where you can BUY)
        true_probability: Your estimated true probability
        bankroll: Your available bankroll
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
        display_kelly_analysis(true_probability, ask, "BUY", bankroll)
    elif true_probability < bid:
        print(
            f"✅ RECOMMENDATION: SELL (your estimate {format_percentage(true_probability)} < bid {format_percentage(bid)})"
        )
        print()
        display_kelly_analysis(true_probability, bid, "SELL", bankroll)
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

  # Bid-Ask analysis (automatic side selection)
  %(prog)s --bid 0.44 --ask 0.46 --true-prob 0.60

  # With custom bankroll
  %(prog)s --price 0.30 --true-prob 0.50 --bankroll 5000

  # Percentage format (converts to decimal)
  %(prog)s --bid 44 --ask 46 --true-prob 60

Notes:
  - Prices can be decimals (0.45) or percentages (45)
  - Use --bid and --ask for bid-ask spread analysis
  - Use --price for single price analysis
        """,
    )

    parser.add_argument(
        "--price",
        type=float,
        help="Market price (0-1 or 0-100 if percentage)",
    )
    parser.add_argument(
        "--bid",
        type=float,
        help="Best bid price (where you can SELL)",
    )
    parser.add_argument(
        "--ask",
        type=float,
        help="Best ask price (where you can BUY)",
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
        default="BUY",
        help="Which side to bet (only used with --price)",
    )
    parser.add_argument(
        "--bankroll",
        type=float,
        default=1000.0,
        help="Your available bankroll (default: $1000)",
    )

    args = parser.parse_args()

    # Convert percentages to decimals if needed
    def normalize_prob(p: float) -> float:
        return p / 100 if p > 1 else p

    true_prob = normalize_prob(args.true_prob)

    # Validate probability range
    if not 0 <= true_prob <= 1:
        print("Error: true-prob must be between 0-1 or 0-100")
        return

    # Check if we have bid-ask or single price
    if args.bid is not None and args.ask is not None:
        bid = normalize_prob(args.bid)
        ask = normalize_prob(args.ask)

        if not 0 <= bid <= 1 or not 0 <= ask <= 1:
            print("Error: bid and ask must be between 0-1 or 0-100")
            return

        if bid >= ask:
            print("Error: bid must be less than ask")
            return

        calculate_bid_ask_analysis(bid, ask, true_prob, args.bankroll)

    elif args.price is not None:
        price = normalize_prob(args.price)

        if not 0 <= price <= 1:
            print("Error: price must be between 0-1 or 0-100")
            return

        display_kelly_analysis(true_prob, price, args.side.upper(), args.bankroll)

    else:
        print("Error: Must provide either --price or both --bid and --ask")
        parser.print_help()
        return


if __name__ == "__main__":
    main()
