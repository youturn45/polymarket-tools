"""Live integration tests for MarketMonitor (opt-in)."""

import os

import pytest

from api.polymarket_client import PolymarketClient
from config.settings import load_config
from core.market_monitor import MarketMonitor


TOKEN_ID = "62595435619678438799673612599999067112702849851098967060818869994133628780778"


@pytest.mark.integration
def test_live_market_monitor_snapshot(tmp_path):
    """Fetch a live snapshot for a real token and persist it."""
    if os.getenv("RUN_LIVE_TESTS") != "1":
        pytest.skip("Set RUN_LIVE_TESTS=1 to run live integration tests")

    if not os.getenv("POLYMARKET_PRIVATE_KEY"):
        pytest.skip("POLYMARKET_PRIVATE_KEY is required for live tests")

    config = load_config()
    client = PolymarketClient(config=config)

    db_path = tmp_path / "market_live.db"
    monitor = MarketMonitor(client, TOKEN_ID, db_path=str(db_path))

    snapshot = monitor.fetch_and_store_snapshot(depth_levels=5)

    assert snapshot.token_id == TOKEN_ID
    assert snapshot.best_bid > 0
    assert snapshot.best_ask > 0
    assert len(snapshot.bids) == 5
    assert len(snapshot.asks) == 5

    stored = monitor.get_latest_snapshot_from_db()
    assert stored is not None
    assert stored["token_id"] == TOKEN_ID
    assert stored["best_bid"] == snapshot.best_bid
    assert stored["best_ask"] == snapshot.best_ask
    assert stored["bids"]
    assert stored["asks"]
