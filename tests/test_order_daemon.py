"""Tests for order daemon."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest

from core.order_daemon import OrderDaemon
from models.enums import OrderSide, OrderStatus
from models.order import Order, StrategyParams
from models.order_request import OrderRequest, StrategyType


def test_order_daemon_initialization():
    """Test OrderDaemon initialization."""
    client = Mock()

    daemon = OrderDaemon(client)

    assert daemon.client == client
    assert not daemon.is_running()
    assert daemon.get_queue_size() == 0


def test_order_daemon_custom_queue_size():
    """Test OrderDaemon with custom queue size."""
    client = Mock()

    daemon = OrderDaemon(client, max_queue_size=50)

    assert daemon._queue.maxsize == 50


def test_start_daemon():
    """Test starting the daemon."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        await daemon.start()

        assert daemon.is_running()
        assert daemon._worker_task is not None

        # Clean up
        await daemon.stop()

    asyncio.run(run_test())


def test_start_daemon_already_running():
    """Test starting daemon when already running raises error."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        await daemon.start()

        # Try to start again
        with pytest.raises(RuntimeError, match="already running"):
            await daemon.start()

        # Clean up
        await daemon.stop()

    asyncio.run(run_test())


def test_stop_daemon():
    """Test stopping the daemon."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        await daemon.start()
        assert daemon.is_running()

        await daemon.stop()
        assert not daemon.is_running()

    asyncio.run(run_test())


def test_stop_daemon_not_running():
    """Test stopping daemon when not running."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        # Should not raise, just log warning
        await daemon.stop()

    asyncio.run(run_test())


def test_submit_order():
    """Test submitting an order to the queue."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        await daemon.start()

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

        await daemon.submit_order(request)

        assert daemon.get_queue_size() == 1

        # Clean up
        await daemon.stop()

    asyncio.run(run_test())


def test_submit_order_not_running():
    """Test submitting order when daemon not running raises error."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

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

        with pytest.raises(RuntimeError, match="not running"):
            await daemon.submit_order(request)

    asyncio.run(run_test())


def test_get_completed_orders():
    """Test getting completed orders."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        # Add some completed orders
        order1 = Order(
            order_id="order-1",
            market_id="market-1",
            token_id="token-1",
            side=OrderSide.BUY,
            total_size=1000,
            target_price=0.45,
            max_price=0.50,
            min_price=0.40,
        )
        order1.update_status(OrderStatus.COMPLETED)

        daemon._completed_orders.append(order1)

        completed = daemon.get_completed_orders()
        assert len(completed) == 1
        assert completed[0].order_id == "order-1"

    asyncio.run(run_test())


def test_get_failed_orders():
    """Test getting failed orders."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        # Add some failed orders
        order1 = Order(
            order_id="order-1",
            market_id="market-1",
            token_id="token-1",
            side=OrderSide.BUY,
            total_size=1000,
            target_price=0.45,
            max_price=0.50,
            min_price=0.40,
        )
        order1.update_status(OrderStatus.FAILED)

        daemon._failed_orders.append(order1)

        failed = daemon.get_failed_orders()
        assert len(failed) == 1
        assert failed[0].order_id == "order-1"

    asyncio.run(run_test())


def test_clear_history():
    """Test clearing order history."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        # Add some orders
        order1 = Order(
            order_id="order-1",
            market_id="market-1",
            token_id="token-1",
            side=OrderSide.BUY,
            total_size=1000,
            target_price=0.45,
            max_price=0.50,
            min_price=0.40,
        )

        daemon._completed_orders.append(order1)
        daemon._failed_orders.append(order1)

        daemon.clear_history()

        assert len(daemon.get_completed_orders()) == 0
        assert len(daemon.get_failed_orders()) == 0

    asyncio.run(run_test())


def test_context_manager():
    """Test using daemon as async context manager."""

    async def run_test():
        client = Mock()

        async with OrderDaemon(client) as daemon:
            assert daemon.is_running()

        # Should be stopped after exiting context
        assert not daemon.is_running()

    asyncio.run(run_test())


def test_wait_for_completion():
    """Test waiting for queue to complete."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        await daemon.start()

        # Empty queue should complete immediately
        result = await daemon.wait_for_completion(timeout=1.0)
        assert result is True

        await daemon.stop()

    asyncio.run(run_test())


def test_wait_for_completion_not_running():
    """Test wait_for_completion when daemon not running raises error."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        with pytest.raises(RuntimeError, match="not running"):
            await daemon.wait_for_completion()

    asyncio.run(run_test())


def test_process_queue_integration():
    """Test processing orders from queue (integration test)."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        # Mock the router's execute_order method
        completed_order = Order(
            order_id="order-1",
            market_id="market-1",
            token_id="token-1",
            side=OrderSide.BUY,
            total_size=1000,
            target_price=0.45,
            max_price=0.50,
            min_price=0.40,
        )
        completed_order.update_status(OrderStatus.COMPLETED)
        completed_order.record_fill(1000)

        # Mock router
        daemon._router.execute_order = AsyncMock(return_value=completed_order)

        await daemon.start()

        # Submit order
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

        await daemon.submit_order(request)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Check that order was processed
        completed = daemon.get_completed_orders()
        assert len(completed) == 1
        assert completed[0].status == OrderStatus.COMPLETED

        await daemon.stop()

    asyncio.run(run_test())


def test_process_queue_failed_order():
    """Test processing failed order."""

    async def run_test():
        client = Mock()
        daemon = OrderDaemon(client)

        # Mock the router's execute_order method to return failed order
        failed_order = Order(
            order_id="order-1",
            market_id="market-1",
            token_id="token-1",
            side=OrderSide.BUY,
            total_size=1000,
            target_price=0.45,
            max_price=0.50,
            min_price=0.40,
        )
        failed_order.update_status(OrderStatus.FAILED)

        # Mock router
        daemon._router.execute_order = AsyncMock(return_value=failed_order)

        await daemon.start()

        # Submit order
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

        await daemon.submit_order(request)

        # Wait for processing
        await asyncio.sleep(0.5)

        # Check that order was tracked as failed
        failed = daemon.get_failed_orders()
        assert len(failed) == 1
        assert failed[0].status == OrderStatus.FAILED

        await daemon.stop()

    asyncio.run(run_test())
