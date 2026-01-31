"""Core Kelly criterion calculation functions for prediction markets.

These functions provide the mathematical foundation for Kelly criterion betting
and can be imported directly for programmatic use in trading strategies.
"""


def calculate_edge(true_probability: float, market_price: float, side: str = "BUY") -> float:
    """Calculate expected value (edge) of the bet.

    Edge represents the percentage advantage you have over the market price.
    Positive edge means the bet is profitable in expectation.

    Args:
        true_probability: Your estimated true probability (0-1)
        market_price: Current market price (0-1)
        side: "BUY" or "SELL"

    Returns:
        Edge as a percentage (e.g., 5.0 for 5% edge)
    """
    if side.upper() == "BUY":
        # When buying: edge = true_prob - market_price
        # You win if outcome happens (prob = true_probability)
        # You pay market_price, get 1 if win
        # Expected value: true_prob * (1 - market_price) - (1 - true_prob) * market_price
        # Simplified: true_prob - market_price
        edge = true_probability - market_price
    else:  # SELL
        # When selling: edge = market_price - (1 - true_probability)
        # You win if outcome doesn't happen (prob = 1 - true_probability)
        # You receive market_price, pay 1 if lose
        # Expected value: (1 - true_prob) * market_price - true_prob * (1 - market_price)
        # Simplified: market_price - (1 - true_prob) = market_price + true_prob - 1
        edge = market_price - (1 - true_probability)

    # Return as percentage
    return edge * 100


def calculate_kelly_fraction(
    true_probability: float,
    market_price: float,
    side: str = "BUY",
    edge_upper_bound: float = 0.05,
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
        edge_upper_bound: Maximum edge to use in calculation (default: 0.05 = 5%)
                         Caps the edge to prevent over-betting on high-edge opportunities

    Returns:
        Kelly fraction (0-1)
    """
    # Calculate current edge
    edge = calculate_edge(true_probability, market_price, side) / 100  # Convert to decimal

    # Apply edge upper bound if needed
    adjusted_probability = true_probability
    if edge > edge_upper_bound:
        # Cap the edge and derive the adjusted probability
        # For BUY: edge = true_prob - market_price
        # For SELL: edge = market_price - (1 - true_prob) = market_price + true_prob - 1
        if side.upper() == "BUY":
            adjusted_probability = market_price + edge_upper_bound
        else:  # SELL
            adjusted_probability = 1 - market_price + edge_upper_bound

        # Clamp to valid probability range
        adjusted_probability = max(0.0, min(1.0, adjusted_probability))

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
    # Use adjusted probability that respects edge upper bound
    loss_probability = 1 - adjusted_probability
    kelly_fraction = (odds * adjusted_probability - loss_probability) / odds

    # Clamp to [0, 1] - never bet negative or more than 100%
    kelly_fraction = max(0.0, min(1.0, kelly_fraction))

    return kelly_fraction


def calculate_position_size(
    true_probability: float,
    market_price: float,
    side: str,
    bankroll: float,
    kelly_fraction_multiplier: float = 1.0,
    edge_upper_bound: float = 0.05,
) -> tuple[float, int]:
    """Calculate position size in dollars and shares.

    Args:
        true_probability: Your estimated true probability (0-1)
        market_price: Current market price (0-1)
        side: "BUY" or "SELL"
        bankroll: Available capital
        kelly_fraction_multiplier: Fraction of Kelly to use (e.g., 0.25 for quarter Kelly)
        edge_upper_bound: Maximum edge to use in calculation (default: 0.05 = 5%)

    Returns:
        Tuple of (position_dollars, position_shares)
    """
    # Calculate Kelly fraction
    kelly = calculate_kelly_fraction(true_probability, market_price, side, edge_upper_bound)

    # Apply multiplier (for fractional Kelly)
    adjusted_kelly = kelly * kelly_fraction_multiplier

    # Calculate position size in dollars
    position_dollars = bankroll * adjusted_kelly

    # Calculate position size in shares
    # For prediction markets: shares = dollars / price
    if market_price == 0:
        position_shares = 0
    else:
        position_shares = int(position_dollars / market_price)

    return position_dollars, position_shares


def calculate_fractional_kelly_sizes(
    true_probability: float,
    market_price: float,
    side: str,
    bankroll: float,
    edge_upper_bound: float = 0.05,
) -> dict[str, tuple[float, float, int]]:
    """Calculate position sizes for common fractional Kelly strategies.

    Args:
        true_probability: Your estimated true probability (0-1)
        market_price: Current market price (0-1)
        side: "BUY" or "SELL"
        bankroll: Available capital
        edge_upper_bound: Maximum edge to use in calculation (default: 0.05 = 5%)

    Returns:
        Dictionary mapping strategy name to (kelly_fraction, dollars, shares):
        - "full": Full Kelly (1.0x)
        - "half": Half Kelly (0.5x)
        - "quarter": Quarter Kelly (0.25x)
        - "tenth": Tenth Kelly (0.1x)
    """
    strategies = {
        "full": 1.0,
        "half": 0.5,
        "quarter": 0.25,
        "tenth": 0.1,
    }

    results = {}
    for name, multiplier in strategies.items():
        dollars, shares = calculate_position_size(
            true_probability,
            market_price,
            side,
            bankroll,
            kelly_fraction_multiplier=multiplier,
            edge_upper_bound=edge_upper_bound,
        )

        # Calculate the actual Kelly fraction used
        kelly = calculate_kelly_fraction(true_probability, market_price, side, edge_upper_bound)
        effective_kelly = kelly * multiplier

        results[name] = (effective_kelly, dollars, shares)

    return results
