"""Tests for order management MCP tools (modify_order, cancel_order, cancel_all_orders).

All tests mock TigerClient so no real API calls are made.
"""

from __future__ import annotations

from types import SimpleNamespace
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
    # Default: no recent orders (no duplicates)
    state.has_recent_order.return_value = False
    return state


@pytest.fixture()
def mock_config() -> SimpleNamespace:
    """Create a permissive mock config with all safety limits disabled."""
    return SimpleNamespace(
        max_order_value=0.0,
        daily_loss_limit=0.0,
        max_position_pct=0.0,
    )


@pytest.fixture(autouse=True)
def _init_module(
    mock_client: AsyncMock,
    mock_state: MagicMock,
    mock_config: SimpleNamespace,
) -> None:
    """Inject the mock client, state, and config into the management module."""
    order_mgmt_mod.init(mock_client, mock_state, mock_config)


def _make_buy_order_detail(
    *,
    order_id: int = 12345,
    symbol: str = "AAPL",
    quantity: int = 100,
    limit_price: float = 150.0,
    order_type: str = "LMT",
) -> dict:
    """Helper to build a standard BUY order detail dict."""
    return {
        "order_id": order_id,
        "symbol": symbol,
        "action": "BUY",
        "order_type": order_type,
        "quantity": quantity,
        "filled": 0,
        "limit_price": limit_price,
        "status": "NEW",
    }


def _make_sell_order_detail(
    *,
    order_id: int = 12345,
    symbol: str = "AAPL",
    quantity: int = 100,
    limit_price: float = 150.0,
    order_type: str = "LMT",
) -> dict:
    """Helper to build a standard SELL order detail dict."""
    return {
        "order_id": order_id,
        "symbol": symbol,
        "action": "SELL",
        "order_type": order_type,
        "quantity": quantity,
        "filled": 0,
        "limit_price": limit_price,
        "status": "NEW",
    }


def _setup_quote_and_positions(
    mock_client: AsyncMock,
    *,
    latest_price: float = 150.0,
    cash: float = 500_000.0,
    net_liquidation: float = 1_000_000.0,
    positions: list[dict] | None = None,
) -> None:
    """Configure mock_client with quote, account, and position data."""
    mock_client.get_quote.return_value = {"latest_price": latest_price}
    mock_client.get_assets.return_value = {
        "cash": cash,
        "net_liquidation": net_liquidation,
    }
    mock_client.get_positions.return_value = positions or []


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
        mock_client.get_order_detail.return_value = _make_buy_order_detail()
        _setup_quote_and_positions(mock_client)
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
        mock_client.get_order_detail.return_value = _make_buy_order_detail()
        _setup_quote_and_positions(mock_client)
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
        mock_client.get_order_detail.return_value = _make_buy_order_detail()
        _setup_quote_and_positions(mock_client)
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
        mock_client.get_order_detail.return_value = _make_buy_order_detail()
        _setup_quote_and_positions(mock_client)
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
        """modify_order should fetch account data when quantity increases on BUY."""
        mock_client.get_order_detail.return_value = _make_buy_order_detail()
        _setup_quote_and_positions(
            mock_client, cash=50000.0, net_liquidation=100000.0,
        )
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        # Should have fetched account data for safety checks
        mock_client.get_assets.assert_awaited_once()
        assert "modified" in result.lower() or "Modified" in result

    async def test_modify_quantity_decrease_skips_safety_checks(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should skip safety checks when quantity decreases."""
        mock_client.get_order_detail.return_value = _make_buy_order_detail()
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
        mock_client.get_quote.assert_not_awaited()
        mock_client.get_positions.assert_not_awaited()
        assert "modified" in result.lower() or "Modified" in result

    async def test_modify_quantity_increase_insufficient_buying_power(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should block when buying power is insufficient."""
        mock_client.get_order_detail.return_value = _make_buy_order_detail()
        # Cash is less than what the increased quantity would cost
        # 200 shares * $150 * 1.01 buffer = $30,300 but only $100 cash
        _setup_quote_and_positions(
            mock_client, cash=100.0, net_liquidation=100.0,
        )

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        # Should block the modification due to safety error
        assert "blocked" in result.lower() or "error" in result.lower()
        assert "buying power" in result.lower() or "Insufficient" in result
        # Should NOT have called modify_order since safety check failed
        mock_client.modify_order.assert_not_awaited()


class TestModifyOrderFullSafetyChecks:
    """Tests for full safety checks in modify_order."""

    async def test_safety_checks_run_on_quantity_increase_buy(
        self,
        mock_client: AsyncMock,
        mock_state: MagicMock,
    ) -> None:
        """modify_order should run full safety checks when quantity increases on BUY."""
        mock_client.get_order_detail.return_value = _make_buy_order_detail(
            quantity=100, limit_price=150.0,
        )
        _setup_quote_and_positions(mock_client)
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        # Should have fetched quote, account, and positions
        mock_client.get_quote.assert_awaited_once()
        mock_client.get_assets.assert_awaited_once()
        mock_client.get_positions.assert_awaited_once()
        assert "Modified" in result

    async def test_safety_checks_run_on_price_increase_buy(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should run safety checks when limit price increases on BUY."""
        mock_client.get_order_detail.return_value = _make_buy_order_detail(
            quantity=100, limit_price=150.0,
        )
        _setup_quote_and_positions(mock_client)
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, limit_price=200.0
        )

        # Safety checks should have been triggered for price change on BUY
        mock_client.get_quote.assert_awaited_once()
        mock_client.get_assets.assert_awaited_once()
        mock_client.get_positions.assert_awaited_once()
        assert "Modified" in result

    async def test_safety_checks_block_on_error(
        self,
        mock_client: AsyncMock,
        mock_config: SimpleNamespace,
    ) -> None:
        """modify_order should block modification when safety checks produce errors."""
        # Set max_order_value so that the modified order exceeds it
        mock_config.max_order_value = 10_000.0  # 200 * $150 = $30,000 > $10,000

        mock_client.get_order_detail.return_value = _make_buy_order_detail(
            quantity=100, limit_price=150.0,
        )
        _setup_quote_and_positions(mock_client)

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        # Should block - the order value of $30,000 exceeds limit of $10,000
        assert "blocked" in result.lower() or "error" in result.lower()
        mock_client.modify_order.assert_not_awaited()

    async def test_safety_checks_allow_with_warnings(
        self,
        mock_client: AsyncMock,
        mock_config: SimpleNamespace,
    ) -> None:
        """modify_order should proceed when safety checks produce only warnings."""
        # Set concentration limit so that a warning fires but no error
        mock_config.max_position_pct = 0.05  # 5%

        mock_client.get_order_detail.return_value = _make_buy_order_detail(
            quantity=100, limit_price=150.0,
        )
        # Order value: 200 * 150 = $30,000 which is 3% of $1M
        # But limit is 5% so: $30,000 > 5% * $1M = $50,000? No.
        # Need net_liquidation to be small so the warning fires.
        # 200 * 150 = $30,000 > 5% * $100,000 = $5,000 => warning fires
        _setup_quote_and_positions(
            mock_client,
            cash=500_000.0,
            net_liquidation=100_000.0,
        )
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        # Should succeed but include a warning
        assert "Modified" in result
        mock_client.modify_order.assert_awaited_once()
        assert "warning" in result.lower() or "concentration" in result.lower()

    async def test_safety_checks_skip_for_sell_order(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should skip safety checks for SELL orders."""
        mock_client.get_order_detail.return_value = _make_sell_order_detail(
            quantity=100,
        )
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        # Should NOT fetch quote/account/positions for SELL orders
        mock_client.get_quote.assert_not_awaited()
        mock_client.get_assets.assert_not_awaited()
        mock_client.get_positions.assert_not_awaited()
        assert "Modified" in result

    async def test_safety_checks_skip_for_price_decrease_buy(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should skip safety checks when limit price decreases on BUY."""
        mock_client.get_order_detail.return_value = _make_buy_order_detail(
            quantity=100, limit_price=150.0,
        )
        mock_client.modify_order.return_value = {
            "order_id": 12345,
            "modified": True,
            "result": None,
        }

        result = await order_mgmt_mod.modify_order(
            order_id=12345, limit_price=100.0
        )

        # Lowering price is not increasing risk; skip safety checks
        mock_client.get_quote.assert_not_awaited()
        mock_client.get_assets.assert_not_awaited()
        mock_client.get_positions.assert_not_awaited()
        assert "Modified" in result

    async def test_safety_data_fetch_failure_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """modify_order should return error when market data fetch fails."""
        mock_client.get_order_detail.return_value = _make_buy_order_detail()
        mock_client.get_quote.side_effect = RuntimeError("Quote fetch failed")

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        assert "error" in result.lower()
        mock_client.modify_order.assert_not_awaited()

    async def test_safety_checks_daily_loss_limit_blocks(
        self,
        mock_client: AsyncMock,
        mock_state: MagicMock,
        mock_config: SimpleNamespace,
    ) -> None:
        """modify_order should block when daily loss limit is breached."""
        mock_config.daily_loss_limit = 1000.0
        # P&L is below the loss limit
        mock_state.get_daily_pnl.return_value = -1500.0

        mock_client.get_order_detail.return_value = _make_buy_order_detail()
        _setup_quote_and_positions(mock_client)

        result = await order_mgmt_mod.modify_order(
            order_id=12345, quantity=200
        )

        assert "blocked" in result.lower() or "error" in result.lower()
        assert "loss" in result.lower() or "limit" in result.lower()
        mock_client.modify_order.assert_not_awaited()

    async def test_init_accepts_config_parameter(
        self,
        mock_client: AsyncMock,
        mock_state: MagicMock,
        mock_config: SimpleNamespace,
    ) -> None:
        """init() should accept and store a config parameter."""
        order_mgmt_mod.init(mock_client, mock_state, mock_config)
        assert order_mgmt_mod._config is mock_config

    async def test_init_config_defaults_to_none(
        self,
        mock_client: AsyncMock,
        mock_state: MagicMock,
    ) -> None:
        """init() should default config to None when not provided."""
        order_mgmt_mod.init(mock_client, mock_state)
        assert order_mgmt_mod._config is None


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
