#!/usr/bin/env python3
"""Launch the Polymarket trading dashboard.

This script starts a web server that displays:
- Current open orders with fill status
- Position summary and exposure
- Recent trades

The dashboard auto-refreshes every 10 seconds and opens automatically in your browser.
"""

import argparse
import sys

from dashboard.app import run_dashboard


def main():
    """Main entry point for the dashboard."""
    parser = argparse.ArgumentParser(description="Polymarket Trading Dashboard")
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=5000,
        help="Port to bind to (default: 5000)",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Don't open browser automatically",
    )

    args = parser.parse_args()

    try:
        print("=" * 60)
        print("Polymarket Trading Dashboard")
        print("=" * 60)
        print(f"\nStarting server at http://{args.host}:{args.port}")
        print("\nFeatures:")
        print("  - Real-time order monitoring")
        print("  - Position and exposure tracking")
        print("  - Trade history")
        print("  - Auto-refresh every 10 seconds")
        print("\nPress Ctrl+C to stop the server")
        print("=" * 60)
        print()

        run_dashboard(
            host=args.host,
            port=args.port,
            open_browser=not args.no_browser,
        )

    except KeyboardInterrupt:
        print("\n\nShutting down dashboard...")
        sys.exit(0)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
