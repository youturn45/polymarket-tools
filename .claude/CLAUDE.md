# Polymarket Tools - AI Quickstart

Short, command-first notes for working in this repo. Deeper docs live in `docs/`.

## Quick Commands

```bash
# Install deps
uv pip install -e .

# Run examples
uv run python scripts/examples/example2_track_order.py --token-id YOUR_TOKEN_ID --side BUY --price 0.50 --size 100

# Run dashboard
uv run python scripts/run_dashboard.py

# Utility helpers
just --list
just gamma
just kelly-buy 0.45 0.60 1000

# Tests
uv run pytest
```

## Where To Look

- `docs/CONFIG.md` for configuration, env vars, and secrets handling
- `docs/architecture/system-design.md` for system structure and flows
- `docs/SECURITY.md` for key handling and safe-ops guidelines
