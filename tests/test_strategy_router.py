"""Tests for strategy router."""

from unittest.mock import Mock

import pytest

from models.enums import OrderSide
from models.order import StrategyParams
from models.order_request import OrderRequest, StrategyType
from strategies.router import StrategyRouter


def test_strategy_router_initialization():
    """Test StrategyRouter initialization."""
    client = Mock()
    logger = Mock()

    router = StrategyRouter(client, logger=logger)

    assert router.client == client
    assert router.logger == logger


def test_create_order_from_iceberg_request():
    """Test creating Order from iceberg OrderRequest."""
    client = Mock()
    router = StrategyRouter(client)

    request = OrderRequest(
        market_id="market-123",
        token_id="token-456",
        side=OrderSide.BUY,
        strategy_type=StrategyType.ICEBERG,
        total_size=1000,
        max_price=0.60,
        min_price=0.40,
        iceberg_params=StrategyParams(initial_tranche_size=200),
    )

    order = router.create_order_from_request(request)

    assert order.market_id == "market-123"
    assert order.token_id == "token-456"
    assert order.side == OrderSide.BUY
    assert order.total_size == 1000
    assert order.max_price == 0.60
    assert order.min_price == 0.40
    # Target price should be mid-point
    assert order.target_price == 0.50


def test_create_order_generates_id():
    """Test that order ID is generated."""
    client = Mock()
    router = StrategyRouter(client)

    request = OrderRequest(
        market_id="market-123",
        token_id="token-456",
        side=OrderSide.BUY,
        strategy_type=StrategyType.ICEBERG,
        total_size=1000,
        max_price=0.60,
        min_price=0.40,
        iceberg_params=StrategyParams(),
    )

    order = router.create_order_from_request(request)

    # Order ID should be generated with strategy prefix
    assert order.order_id.startswith("iceberg-")
    assert len(order.order_id) > 8  # Has hash suffix


def test_unknown_strategy_raises_error():
    """Test that unknown strategy type raises ValueError."""
    client = Mock()
    router = StrategyRouter(client)

    # Create request with invalid strategy
    request = Mock()
    request.strategy_type = Mock()
    request.strategy_type.value = "invalid_strategy"
    request.side = Mock()
    request.side.value = "BUY"
    request.total_size = 1000
    request.min_price = 0.40
    request.max_price = 0.60

    with pytest.raises(ValueError, match="Unknown strategy type"):
        # Need to use asyncio for async method
        import asyncio

        asyncio.run(router.execute_order(request))
