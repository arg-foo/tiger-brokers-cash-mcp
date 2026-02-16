"""Tests for order query MCP tools (get_open_orders, get_order_detail).

All tests mock TigerClient so no real API calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from tiger_mcp.tools.orders import query as order_query_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Create a mock TigerClient with async methods."""
    client = AsyncMock()
    return client


@pytest.fixture(autouse=True)
def _init_module(mock_client: AsyncMock) -> None:
    """Inject the mock client into the order query module before each test."""
    order_query_mod.init(mock_client)


# ---------------------------------------------------------------------------
# get_open_orders
# ---------------------------------------------------------------------------


class TestGetOpenOrders:
    """Tests for the get_open_orders MCP tool."""

    async def test_returns_formatted_text_with_orders(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """get_open_orders should return readable text when orders exist."""
        mock_client.get_open_orders.return_value = [
            {
                "order_id": 12345,
                "symbol": "AAPL",
                "action": "BUY",
                "quantity": 100,
                "filled": 50,
                "order_type": "limit",
                "limit_price": 150.0,
                "status": "PARTIALLY_FILLED",
                "trade_time": "2026-02-16 10:30:00",
            },
            {
                "order_id": 67890,
                "symbol": "GOOGL",
                "action": "SELL",
                "quantity": 20,
                "filled": 0,
                "order_type": "market",
                "limit_price": None,
                "status": "NEW",
                "trade_time": "2026-02-16 11:00:00",
            },
        ]

        result = await order_query_mod.get_open_orders(symbol="")

        mock_client.get_open_orders.assert_awaited_once_with(symbol=None)
        assert "12345" in result
        assert "AAPL" in result
        assert "BUY" in result
        assert "100" in result
        assert "50" in result
        assert "limit" in result
        assert "150.0" in result
        assert "PARTIALLY_FILLED" in result
        assert "67890" in result
        assert "GOOGL" in result

    async def test_symbol_filter_uppercased(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """get_open_orders should uppercase the symbol filter before calling client."""
        mock_client.get_open_orders.return_value = [
            {
                "order_id": 12345,
                "symbol": "AAPL",
                "action": "BUY",
                "quantity": 100,
                "filled": 0,
                "order_type": "limit",
                "limit_price": 150.0,
                "status": "NEW",
                "trade_time": "2026-02-16 10:30:00",
            },
        ]

        result = await order_query_mod.get_open_orders(symbol="aapl")

        mock_client.get_open_orders.assert_awaited_once_with(symbol="AAPL")
        assert "AAPL" in result

    async def test_empty_symbol_passes_none(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """get_open_orders with empty string symbol should pass None to client."""
        mock_client.get_open_orders.return_value = []

        await order_query_mod.get_open_orders(symbol="")

        mock_client.get_open_orders.assert_awaited_once_with(symbol=None)

    async def test_empty_list_returns_no_open_orders_message(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """get_open_orders should return 'No open orders.' when list is empty."""
        mock_client.get_open_orders.return_value = []

        result = await order_query_mod.get_open_orders(symbol="")

        assert result == "No open orders."

    async def test_default_symbol_is_empty_string(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """get_open_orders should have symbol default to empty string."""
        mock_client.get_open_orders.return_value = []

        result = await order_query_mod.get_open_orders()

        mock_client.get_open_orders.assert_awaited_once_with(symbol=None)
        assert result == "No open orders."


# ---------------------------------------------------------------------------
# get_order_detail
# ---------------------------------------------------------------------------


class TestGetOrderDetail:
    """Tests for the get_order_detail MCP tool."""

    async def test_returns_formatted_detail(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """get_order_detail should return all order fields as readable text."""
        mock_client.get_order_detail.return_value = {
            "order_id": 12345,
            "symbol": "AAPL",
            "action": "BUY",
            "order_type": "limit",
            "quantity": 100,
            "filled": 75,
            "avg_fill_price": 149.50,
            "limit_price": 150.0,
            "aux_price": None,
            "status": "PARTIALLY_FILLED",
            "remaining": 25,
            "trade_time": "2026-02-16 10:30:00",
            "commission": 1.99,
        }

        result = await order_query_mod.get_order_detail(order_id=12345)

        mock_client.get_order_detail.assert_awaited_once_with(order_id=12345)
        assert "12345" in result
        assert "AAPL" in result
        assert "BUY" in result
        assert "limit" in result
        assert "100" in result
        assert "75" in result
        assert "149.5" in result
        assert "150.0" in result
        assert "PARTIALLY_FILLED" in result
        assert "25" in result
        assert "1.99" in result

    async def test_invalid_order_id_returns_error_message(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """get_order_detail should return a clear error for invalid order_id."""
        mock_client.get_order_detail.side_effect = RuntimeError(
            "get_order_detail failed: Order not found"
        )

        result = await order_query_mod.get_order_detail(order_id=99999)

        assert "error" in result.lower() or "Error" in result
        assert "99999" in result

    async def test_shows_all_order_fields(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """get_order_detail should display all available order fields."""
        mock_client.get_order_detail.return_value = {
            "order_id": 55555,
            "symbol": "TSLA",
            "action": "SELL",
            "order_type": "market",
            "quantity": 50,
            "filled": 50,
            "avg_fill_price": 245.30,
            "limit_price": None,
            "aux_price": None,
            "status": "FILLED",
            "remaining": 0,
            "trade_time": "2026-02-16 14:00:00",
            "commission": 2.50,
        }

        result = await order_query_mod.get_order_detail(order_id=55555)

        assert "55555" in result
        assert "TSLA" in result
        assert "SELL" in result
        assert "market" in result
        assert "50" in result
        assert "245.3" in result
        assert "FILLED" in result
        assert "2.5" in result


# ---------------------------------------------------------------------------
# Module-level client access pattern
# ---------------------------------------------------------------------------


class TestClientAccessPattern:
    """Test the module-level _client and init() pattern."""

    def test_init_function_exists(self) -> None:
        """The module should expose an init(client) function."""
        assert callable(order_query_mod.init)

    def test_init_sets_client(self, mock_client: AsyncMock) -> None:
        """init() should set the module-level _client."""
        order_query_mod.init(mock_client)
        assert order_query_mod._client is mock_client


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


class TestMcpToolRegistration:
    """Verify the tools are registered with @mcp.tool() decorator."""

    def test_get_open_orders_is_async(self) -> None:
        """get_open_orders should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(order_query_mod.get_open_orders)

    def test_get_order_detail_is_async(self) -> None:
        """get_order_detail should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(order_query_mod.get_order_detail)
