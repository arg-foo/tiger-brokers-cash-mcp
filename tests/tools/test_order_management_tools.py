"""Tests for order management MCP tools (modify_order, cancel_order, cancel_all_orders).

All tests mock TigerClient so no real API calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tiger_mcp.tools.orders import management as order_mgmt_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Create a mock TigerClient with async methods."""
    client = AsyncMock()
    return client


@pytest.fixture()
def mock_state() -> MagicMock:
    """Create a mock DailyState."""
    state = MagicMock()
    return state


@pytest.fixture(autouse=True)
def _init_module(mock_client: AsyncMock, mock_state: MagicMock) -> None:
    """Inject the mock client and state into the management module before each test."""
    order_mgmt_mod.init(mock_client, mock_state)


# ---------------------------------------------------------------------------
# modify_order
# ---------------------------------------------------------------------------


class TestModifyOrder:
    """Tests for the modify_order MCP tool."""

    async def test_modify_order_change_quantity(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should succeed when changing the quantity."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        mock_client.get_assets.return_value = {
            "cash": 500000.0,
            "net_liquidation": 1000000.0,
        }
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        mock_client.get_order_detail.assert_awaited_once_with(order_id=12345)
        mock_client.modify_order.assert_awaited_once_with(
            order_id=12345, quantity=200, limit_price=None, stop_price=None
        )
        assert "12345" in result
        assert "modified" in result.lower() or "Modified" in result

    async def test_modify_order_change_limit_price(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should succeed when changing the limit price."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, limit_price=155.0
        )

        mock_client.modify_order.assert_awaited_once_with(
            order_id=12345, quantity=None, limit_price=155.0, stop_price=None
        )
        assert "12345" in result
        assert "modified" in result.lower() or "Modified" in result

    async def test_modify_order_no_changes_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order with all params None should return an error message."""
        result = await order_mgmt_mod.modify_order(order_id=12345)

        assert "error" in result.lower()
        # Should NOT have called the API since no modifications were requested
        mock_client.get_order_detail.assert_not_awaited()
        mock_client.modify_order.assert_not_awaited()

    async def test_modify_nonexistent_order_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order for a non-existent order should return an error message."""
        mock_client.get_order_detail.side_effect = RuntimeError(
            "get_order_detail failed: Order not found"
        )

        result = await order_mgmt_mod.modify_order(
            order_id=99999, quantity=50
        )

        assert "error" in result.lower()
        assert "99999" in result

    async def test_modify_order_includes_order_details(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order response should include order details."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        mock_client.get_assets.return_value = {
            "cash": 500000.0,
            "net_liquidation": 1000000.0,
        }
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200, limit_price=155.0
        )

        assert "AAPL" in result
        assert "12345" in result

    async def test_modify_order_api_failure_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should return error when the modify API call fails."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        mock_client.get_assets.return_value = {
            "cash": 500000.0,
            "net_liquidation": 1000000.0,
        }
        mock_client.modify_order.side_effect = RuntimeError(
            "modify_order failed: Network error"
        )

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        assert "error" in result.lower()
        assert "12345" in result

    async def test_modify_quantity_increase_fetches_account_data(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should fetch account data when quantity increases."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        mock_client.get_assets.return_value = {
            "cash": 50000.0,
            "net_liquidation": 100000.0,
        }
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        # Should have fetched account data for buying power check
        mock_client.get_assets.assert_awaited_once()
        assert "modified" in result.lower() or "Modified" in result

    async def test_modify_quantity_decrease_skips_buying_power_check(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should skip buying power check when quantity decreases."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=50
        )

        # Should NOT have fetched account data
        mock_client.get_assets.assert_not_awaited()
        assert "modified" in result.lower() or "Modified" in result

    async def test_modify_quantity_increase_insufficient_buying_power(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should include warning when buying power is insufficient."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        # Cash is less than what the increased quantity would cost
        # 200 shares * $150 * 1.01 buffer = $30,300 but only $100 cash
        mock_client.get_assets.return_value = {
            "cash": 100.0,
            "net_liquidation": 100.0,
        }
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        # Should still succeed (modify happens) but include a warning
        assert "modified" in result.lower() or "Modified" in result
        assert "buying power" in result.lower() or "warning" in result.lower()


# ---------------------------------------------------------------------------
# cancel_order
# ---------------------------------------------------------------------------


class TestCancelOrder:
    """Tests for the cancel_order MCP tool."""

    async def test_cancel_order_success(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """cancel_order should return confirmation when successful."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        mock_client.cancel_order.return_value = {
            "order_id": 12345,
            "cancelled": True,
            "result": None,
        }

        result = await order_mgmt_mod.cancel_order(order_id=12345)

        mock_client.get_order_detail.assert_awaited_once_with(order_id=12345)
        mock_client.cancel_order.assert_awaited_once_with(order_id=12345)
        assert "12345" in result
        assert "cancel" in result.lower()

    async def test_cancel_order_includes_order_details(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """cancel_order response should include order symbol and details."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        mock_client.cancel_order.return_value = {
            "order_id": 12345,
            "cancelled": True,
            "result": None,
        }

        result = await order_mgmt_mod.cancel_order(order_id=12345)

        assert "AAPL" in result

    async def test_cancel_already_cancelled_order_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """cancel_order for an already-cancelled order should return an error."""
        mock_client.get_order_detail.side_effect = RuntimeError(
            "cancel_order failed: Order already cancelled"
        )

        result = await order_mgmt_mod.cancel_order(order_id=12345)

        assert "error" in result.lower()
        assert "12345" in result

    async def test_cancel_order_api_failure_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """cancel_order should return error when the cancel API call fails."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 0,
            "limit_price": 150.0,
            "status": "NEW",
        }
        mock_client.cancel_order.side_effect = RuntimeError(
            "cancel_order failed: Network error"
        )

        result = await order_mgmt_mod.cancel_order(order_id=12345)

        assert "error" in result.lower()
        assert "12345" in result


# ---------------------------------------------------------------------------
# cancel_all_orders
# ---------------------------------------------------------------------------


class TestCancelAllOrders:
    """Tests for the cancel_all_orders MCP tool."""

    async def test_cancel_all_with_open_orders(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """cancel_all_orders should return count and IDs when orders are cancelled."""
        mock_client.cancel_all_orders.return_value = [
            {"order_id": 111, "cancelled": True, "result": None},
            {"order_id": 222, "cancelled": True, "result": None},
            {"order_id": 333, "cancelled": True, "result": None},
        ]

        result = await order_mgmt_mod.cancel_all_orders()

        mock_client.cancel_all_orders.assert_awaited_once()
        assert "3" in result
        assert "111" in result
        assert "222" in result
        assert "333" in result

    async def test_cancel_all_with_no_orders(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """cancel_all_orders with no open orders should return appropriate message."""
        mock_client.cancel_all_orders.return_value = []

        result = await order_mgmt_mod.cancel_all_orders()

        assert result == "No open orders to cancel."

    async def test_cancel_all_api_failure_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """cancel_all_orders should return error when the API call fails."""
        mock_client.cancel_all_orders.side_effect = RuntimeError(
            "cancel_all_orders failed: Network error"
        )

        result = await order_mgmt_mod.cancel_all_orders()

        assert "error" in result.lower()


# ---------------------------------------------------------------------------
# Module-level client access pattern
# ---------------------------------------------------------------------------


class TestClientAccessPattern:
    """Test the module-level _client, _state, and init() pattern."""

    def test_init_function_exists(self) -> None:
        """The module should expose an init(client, state) function."""
        assert callable(order_mgmt_mod.init)

    def test_init_sets_client(
        self, mock_client: AsyncMock, mock_state: MagicMock
    ) -> None:
        """init() should set the module-level _client."""
        order_mgmt_mod.init(mock_client, mock_state)
        assert order_mgmt_mod._client is mock_client

    def test_init_sets_state(
        self, mock_client: AsyncMock, mock_state: MagicMock
    ) -> None:
        """init() should set the module-level _state."""
        order_mgmt_mod.init(mock_client, mock_state)
        assert order_mgmt_mod._state is mock_state


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


class TestMcpToolRegistration:
    """Verify the tools are registered with @mcp.tool() decorator."""

    def test_modify_order_is_async(self) -> None:
        """modify_order should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(order_mgmt_mod.modify_order)

    def test_cancel_order_is_async(self) -> None:
        """cancel_order should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(order_mgmt_mod.cancel_order)

    def test_cancel_all_orders_is_async(self) -> None:
        """cancel_all_orders should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(order_mgmt_mod.cancel_all_orders)
