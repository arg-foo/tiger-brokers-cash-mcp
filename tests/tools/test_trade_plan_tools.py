"""Tests for trade plan MCP tools (get_trade_plans, mark_order_filled).

All tests mock TradePlanStore so no real disk I/O is performed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tiger_mcp.safety.trade_plan_store import Modification, TradePlan
from tiger_mcp.tools.orders import trade_plans as trade_plans_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_trade_plans() -> MagicMock:
    """Create a mock TradePlanStore."""
    return MagicMock()


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Create a mock TigerClient."""
    return AsyncMock()


@pytest.fixture(autouse=True)
def _init_module(
    mock_trade_plans: MagicMock,
    mock_client: AsyncMock,
) -> None:
    """Inject mock dependencies into the trade_plans module."""
    trade_plans_mod.init(mock_trade_plans, mock_client)


def _make_active_plan(
    *,
    order_id: int = 12345,
    symbol: str = "AAPL",
    action: str = "BUY",
    quantity: int = 100,
    order_type: str = "LMT",
    limit_price: float | None = 150.0,
    stop_price: float | None = None,
    reason: str = "Bullish thesis",
    modifications: list[Modification] | None = None,
) -> TradePlan:
    """Build an active TradePlan for testing."""
    return TradePlan(
        order_id=order_id,
        symbol=symbol,
        action=action,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
        stop_price=stop_price,
        reason=reason,
        status="active",
        created_at="2026-02-20T10:00:00",
        modified_at=None,
        archived_at=None,
        archive_reason=None,
        modifications=modifications or [],
    )


def _make_archived_plan(**kwargs) -> TradePlan:
    """Build an archived TradePlan for testing."""
    plan = _make_active_plan(**kwargs)
    plan.status = "archived"
    plan.archived_at = "2026-02-20T12:00:00"
    plan.archive_reason = "filled"
    return plan


# ---------------------------------------------------------------------------
# get_trade_plans
# ---------------------------------------------------------------------------


class TestGetTradePlans:
    """Tests for the get_trade_plans MCP tool."""

    async def test_returns_no_plans_message(
        self,
        mock_trade_plans: MagicMock,
    ) -> None:
        """get_trade_plans should return message when no active plans."""
        mock_trade_plans.get_active_plans.return_value = {}

        result = await trade_plans_mod.get_trade_plans()

        assert "No active trade plans" in result

    async def test_returns_single_active_plan(
        self,
        mock_trade_plans: MagicMock,
    ) -> None:
        """get_trade_plans should format a single active plan."""
        plan = _make_active_plan()
        mock_trade_plans.get_active_plans.return_value = {"12345": plan}

        result = await trade_plans_mod.get_trade_plans()

        assert "12345" in result
        assert "AAPL" in result
        assert "BUY" in result
        assert "Bullish thesis" in result
        assert "Active Trade Plans (1)" in result

    async def test_returns_multiple_active_plans(
        self,
        mock_trade_plans: MagicMock,
    ) -> None:
        """get_trade_plans should format multiple active plans."""
        plans = {
            "12345": _make_active_plan(order_id=12345, symbol="AAPL"),
            "67890": _make_active_plan(
                order_id=67890, symbol="GOOG", reason="GOOG undervalued",
            ),
        }
        mock_trade_plans.get_active_plans.return_value = plans

        result = await trade_plans_mod.get_trade_plans()

        assert "Active Trade Plans (2)" in result
        assert "AAPL" in result
        assert "GOOG" in result
        assert "GOOG undervalued" in result

    async def test_includes_modification_details(
        self,
        mock_trade_plans: MagicMock,
    ) -> None:
        """get_trade_plans should show modification details."""
        mod = Modification(
            timestamp="2026-02-20T11:00:00",
            changes={"quantity": 200},
            reason="Increasing position",
        )
        plan = _make_active_plan(modifications=[mod])
        mock_trade_plans.get_active_plans.return_value = {"12345": plan}

        result = await trade_plans_mod.get_trade_plans()

        assert "Modifications: 1" in result
        assert "quantity=200" in result
        assert "Increasing position" in result

    async def test_includes_limit_and_stop_prices(
        self,
        mock_trade_plans: MagicMock,
    ) -> None:
        """get_trade_plans should include limit and stop prices."""
        plan = _make_active_plan(limit_price=150.0, stop_price=145.0)
        mock_trade_plans.get_active_plans.return_value = {"12345": plan}

        result = await trade_plans_mod.get_trade_plans()

        assert "150.00" in result
        assert "145.00" in result


# ---------------------------------------------------------------------------
# mark_order_filled
# ---------------------------------------------------------------------------


class TestMarkOrderFilled:
    """Tests for the mark_order_filled MCP tool."""

    async def test_mark_filled_success(
        self,
        mock_trade_plans: MagicMock,
    ) -> None:
        """mark_order_filled should archive the plan as filled."""
        plan = _make_active_plan()
        mock_trade_plans.get_plan.return_value = plan

        result = await trade_plans_mod.mark_order_filled(order_id=12345)

        mock_trade_plans.archive.assert_called_once_with(
            order_id=12345, reason="filled", archive_reason="filled",
        )
        assert "Archived" in result or "archived" in result.lower()
        assert "12345" in result
        assert "AAPL" in result

    async def test_mark_filled_with_reason(
        self,
        mock_trade_plans: MagicMock,
    ) -> None:
        """mark_order_filled should use custom reason when provided."""
        plan = _make_active_plan()
        mock_trade_plans.get_plan.return_value = plan

        result = await trade_plans_mod.mark_order_filled(
            order_id=12345, reason="Filled at $152.30",
        )

        mock_trade_plans.archive.assert_called_once_with(
            order_id=12345, reason="filled", archive_reason="Filled at $152.30",
        )
        assert "Filled at $152.30" in result

    async def test_mark_filled_nonexistent_plan(
        self,
        mock_trade_plans: MagicMock,
    ) -> None:
        """mark_order_filled should return error for unknown order."""
        mock_trade_plans.get_plan.return_value = None

        result = await trade_plans_mod.mark_order_filled(order_id=99999)

        assert "error" in result.lower() or "Error" in result
        assert "99999" in result
        mock_trade_plans.archive.assert_not_called()

    async def test_mark_filled_already_archived(
        self,
        mock_trade_plans: MagicMock,
    ) -> None:
        """mark_order_filled should return message for already-archived plan."""
        plan = _make_archived_plan()
        mock_trade_plans.get_plan.return_value = plan

        result = await trade_plans_mod.mark_order_filled(order_id=12345)

        assert "already archived" in result.lower()
        mock_trade_plans.archive.assert_not_called()


# ---------------------------------------------------------------------------
# Module-level init pattern
# ---------------------------------------------------------------------------


class TestClientAccessPattern:
    """Test the module-level init() pattern."""

    def test_init_function_exists(self) -> None:
        """The module should expose an init() function."""
        assert callable(trade_plans_mod.init)

    def test_init_sets_trade_plans(
        self, mock_trade_plans: MagicMock
    ) -> None:
        """init() should set the module-level _trade_plans."""
        trade_plans_mod.init(mock_trade_plans)
        assert trade_plans_mod._trade_plans is mock_trade_plans

    def test_init_sets_client(
        self, mock_trade_plans: MagicMock, mock_client: AsyncMock
    ) -> None:
        """init() should set the module-level _client."""
        trade_plans_mod.init(mock_trade_plans, mock_client)
        assert trade_plans_mod._client is mock_client


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


class TestMcpToolRegistration:
    """Verify the tools are registered with @mcp.tool() decorator."""

    def test_get_trade_plans_is_async(self) -> None:
        """get_trade_plans should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(trade_plans_mod.get_trade_plans)

    def test_mark_order_filled_is_async(self) -> None:
        """mark_order_filled should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(trade_plans_mod.mark_order_filled)
