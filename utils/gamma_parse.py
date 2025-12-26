#!/usr/bin/env python3
"""
Polymarket API Parser
Fetches market data and displays it in a readable format
"""

import json

import requests


def fetch_market_data(url: str) -> dict:
    """Fetch market data from API"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None


def parse_token_ids(token_ids_str: str) -> list[str]:
    """Parse clobTokenIds from JSON string"""
    try:
        return json.loads(token_ids_str)
    except json.JSONDecodeError:
        return []


def format_price(price: str) -> str:
    """Format price for display"""
    try:
        return f"{float(price):.3f}"
    except (ValueError, TypeError):
        return price


def display_market_summary(data: dict):
    """Display high-level market summary"""
    print("=" * 80)
    print(f"MARKET: {data.get('title', 'N/A')}")
    print("=" * 80)
    print(f"ID: {data.get('id')}")
    print(f"Slug: {data.get('slug')}")
    print(f"Status: {'Closed' if data.get('closed') else 'Active'}")
    print(f"Total Volume: ${float(data.get('volume', 0)):,.2f}")
    print(f"Open Interest: ${float(data.get('openInterest', 0)):,.2f}")
    print(f"Neg Risk Market ID: {data.get('negRiskMarketID', 'N/A')}")
    print()


def display_sub_markets(markets: list[dict]):
    """Display sub-market details"""
    print("SUB-MARKETS:")
    print("-" * 80)

    for i, market in enumerate(markets, 1):
        print(f"\n[{i}] {market.get('groupItemTitle', 'N/A')}")
        print(f"    Question: {market.get('question', 'N/A')}")
        print(f"    Market ID: {market.get('id')}")
        print(f"    Condition ID: {market.get('conditionId')}")
        print(f"    Status: {'Closed' if market.get('closed') else 'Active'}")

        # Outcomes and prices
        try:
            outcomes = json.loads(market.get("outcomes", "[]"))
            prices = json.loads(market.get("outcomePrices", "[]"))
            print(f"    Outcomes: {', '.join(outcomes)}")
            print(f"    Prices: {', '.join([format_price(p) for p in prices])}")
        except json.JSONDecodeError:
            pass

        # Token IDs
        token_ids = parse_token_ids(market.get("clobTokenIds", "[]"))
        if token_ids:
            print("    Token IDs:")
            print(f"      Yes: {token_ids[0]}")
            print(f"      No:  {token_ids[1]}")

        # Trading info
        print(f"    Volume: ${float(market.get('volume', 0)):,.2f}")
        print(f"    Last Trade Price: {format_price(market.get('lastTradePrice', '0'))}")

        if market.get("bestBid"):
            print(f"    Best Bid: {format_price(market.get('bestBid'))}")
        if market.get("bestAsk"):
            print(f"    Best Ask: {format_price(market.get('bestAsk'))}")

        # Price changes
        if market.get("oneDayPriceChange"):
            print(f"    24h Change: {float(market.get('oneDayPriceChange', 0)) * 100:+.2f}%")


def create_token_lookup(markets: list[dict]) -> dict[str, dict]:
    """Create a lookup table for easy access"""
    lookup = {}
    for market in markets:
        name = market.get("groupItemTitle")
        token_ids = parse_token_ids(market.get("clobTokenIds", "[]"))
        if name and token_ids:
            lookup[name] = {
                "id": market.get("id"),
                "token_yes": token_ids[0],
                "token_no": token_ids[1],
                "condition_id": market.get("conditionId"),
                "slug": market.get("slug"),
            }
    return lookup


def display_token_lookup(lookup: dict[str, dict]):
    """Display token lookup table"""
    print("\n" + "=" * 80)
    print("TOKEN LOOKUP TABLE")
    print("=" * 80)
    for name, info in lookup.items():
        print(f"\n{name}:")
        print(f"  Market ID: {info['id']}")
        print(f"  Token Yes: {info['token_yes']}")
        print(f"  Token No:  {info['token_no']}")


def main():
    # Get URL from user
    print("Polymarket API Parser")
    print("-" * 80)
    url = input("Enter API URL (or press Enter for example): ").strip()

    # Default to example URL if none provided
    if not url:
        url = "https://gamma-api.polymarket.com/markets/27824"
        print(f"Using example: {url}")

    print(f"\nFetching data from: {url}\n")

    # Fetch and parse data
    data = fetch_market_data(url)
    if not data:
        return

    # Display data
    display_market_summary(data)

    markets = data.get("markets", [])
    if markets:
        display_sub_markets(markets)

        # Create and display lookup table
        lookup = create_token_lookup(markets)
        display_token_lookup(lookup)

        # Export option
        print("\n" + "=" * 80)
        export = input("Export token lookup as JSON? (y/n): ").strip().lower()
        if export == "y":
            filename = f"market_{data.get('id')}_tokens.json"
            with open(filename, "w") as f:
                json.dump(lookup, f, indent=2)
            print(f"Exported to: {filename}")
    else:
        print("No sub-markets found")


if __name__ == "__main__":
    main()
