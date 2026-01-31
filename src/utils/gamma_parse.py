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


def format_market_as_markdown(data: dict, markets: list[dict]) -> str:
    """Format market data as markdown table.

    Args:
        data: Main market data
        markets: List of sub-markets

    Returns:
        Markdown formatted string
    """
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    lines.append(f"## Market Update - {timestamp}\n")
    lines.append(f"**{data.get('title', 'N/A')}**\n")
    lines.append(f"- Market ID: `{data.get('id')}`")
    lines.append(f"- Status: {'🔴 Closed' if data.get('closed') else '🟢 Active'}")
    lines.append(f"- Volume: ${float(data.get('volume', 0)):,.2f}")
    lines.append(f"- Open Interest: ${float(data.get('openInterest', 0)):,.2f}\n")

    # Table header
    lines.append(
        "| Sub-Market | Question | Best Bid | Best Ask | Last Price | 24h Change | Volume |"
    )
    lines.append(
        "|------------|----------|----------|----------|------------|------------|--------|"
    )

    # Table rows
    for market in markets:
        name = market.get("groupItemTitle", "N/A")
        question = market.get("question", "N/A")
        question = question[:50] + "..." if len(question) > 50 else question

        best_bid = format_price(market.get("bestBid", "0"))
        best_ask = format_price(market.get("bestAsk", "0"))
        last_price = format_price(market.get("lastTradePrice", "0"))

        price_change = float(market.get("oneDayPriceChange", 0)) * 100
        change_str = f"{price_change:+.2f}%" if price_change != 0 else "0.00%"

        volume = f"${float(market.get('volume', 0)):,.0f}"

        lines.append(
            f"| {name} | {question} | {best_bid} | {best_ask} | {last_price} | {change_str} | {volume} |"
        )

    # Add Token ID reference section with full IDs
    lines.append("\n### Token IDs (Copy from here)\n")

    for market in markets:
        name = market.get("groupItemTitle", "N/A")
        token_ids = parse_token_ids(market.get("clobTokenIds", "[]"))

        if token_ids and len(token_ids) >= 2:
            lines.append("<details>")
            lines.append(f"<summary><strong>{name}</strong></summary>")
            lines.append("")
            lines.append("**YES Token:**")
            lines.append("```")
            lines.append(token_ids[0])
            lines.append("```")
            lines.append("")
            lines.append("**NO Token:**")
            lines.append("```")
            lines.append(token_ids[1])
            lines.append("```")
            lines.append("")
            lines.append(f"Market ID: `{market.get('id')}`")
            lines.append("")
            lines.append("</details>")
            lines.append("")

    lines.append("\n---\n")
    return "\n".join(lines)


def prepend_to_markdown_file(content: str, filename: str = "market_data.md"):
    """Prepend content to a markdown file (adds to top).

    Args:
        content: Markdown content to prepend
        filename: Output filename
    """
    from pathlib import Path

    filepath = Path(filename)

    # Read existing content if file exists
    existing_content = ""
    if filepath.exists():
        existing_content = filepath.read_text()

    # Write new content at top, followed by existing content
    with open(filepath, "w") as f:
        f.write(content)
        if existing_content:
            f.write(existing_content)

    print(f"✅ Data prepended to: {filename}")


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

        # Export options
        print("\n" + "=" * 80)
        print("Export Options:")
        print("  1. Export token lookup as JSON")
        print("  2. Save to markdown table (prepends to file)")
        print("  3. Both")
        print("  4. Skip")

        choice = input("Select option (1-4): ").strip()

        if choice in ["1", "3"]:
            filename = f"market_{data.get('id')}_tokens.json"
            with open(filename, "w") as f:
                json.dump(lookup, f, indent=2)
            print(f"✅ JSON exported to: {filename}")

        if choice in ["2", "3"]:
            markdown_content = format_market_as_markdown(data, markets)
            output_file = input("Enter markdown filename (default: market_data.md): ").strip()
            if not output_file:
                output_file = "market_data.md"
            prepend_to_markdown_file(markdown_content, output_file)
    else:
        print("No sub-markets found")


if __name__ == "__main__":
    main()
