"""Tests for order execution MCP tools (preview_stock_order, place_stock_order).

All tests mock TigerClient, DailyState, and safety checks so no real API
calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tiger_mcp.safety.checks import SafetyResult
from tiger_mcp.tools.orders import execution as execution_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Create a mock TigerClient with async methods."""
    client = AsyncMock()
    # Default quote response
    client.get_quote.return_value = {"latest_price": 150.0}
    # Default account assets
    client.get_assets.return_value = {
        "cash": 100_000.0,
        "net_liquidation": 200_000.0,
    }
    # Default positions (empty)
    client.get_positions.return_value = []
    # Default preview
    client.preview_order.return_value = {
        "estimated_cost": 15_000.0,
        "commission": 1.99,
    }
    # Default place order
    client.place_order.return_value = {
        "order_id": 12345,
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 100,
        "order_type": "market",
    }
    return client


@pytest.fixture()
def mock_state() -> MagicMock:
    """Create a mock DailyState."""
    state = MagicMock()
    state.record_order = MagicMock()
    return state


@pytest.fixture(autouse=True)
def _init_module(mock_client: AsyncMock, mock_state: MagicMock) -> None:
    """Inject mock client and state into the execution module before each test."""
    execution_mod.init(mock_client, mock_state)


def _safety_passed(
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> SafetyResult:
    """Build a SafetyResult that passed (no errors)."""
    return SafetyResult(
        passed=True,
        errors=errors or [],
        warnings=warnings or [],
    )


def _safety_failed(
    errors: list[str],
    warnings: list[str] | None = None,
) -> SafetyResult:
    """Build a SafetyResult that failed (has errors)."""
    return SafetyResult(
        passed=False,
        errors=errors,
        warnings=warnings or [],
    )


# ---------------------------------------------------------------------------
# Parameter validation
# ---------------------------------------------------------------------------


class TestValidateOrderParams:
    """Tests for _validate_order_params helper."""

    def test_valid_buy_market_order(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 100, "MKT", None, None,
        )
        assert result is None

    def test_valid_sell_limit_order(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "SELL", 50, "LMT", 150.0, None,
        )
        assert result is None

    def test_valid_stop_order(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 10, "STP", None, 145.0,
        )
        assert result is None

    def test_valid_stop_limit_order(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 10, "STP_LMT", 150.0, 145.0,
        )
        assert result is None

    def test_valid_trail_order(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 10, "TRAIL", None, None,
        )
        assert result is None

    def test_empty_symbol(self) -> None:
        result = execution_mod._validate_order_params(
            "", "BUY", 100, "MKT", None, None,
        )
        assert result is not None
        assert "symbol" in result.lower()

    def test_lowercase_symbol_rejected(self) -> None:
        result = execution_mod._validate_order_params(
            "aapl", "BUY", 100, "MKT", None, None,
        )
        assert result is not None
        assert "uppercase" in result.lower()

    def test_invalid_action(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "SHORT", 100, "MKT", None, None,
        )
        assert result is not None
        assert "action" in result.lower()

    def test_negative_quantity(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", -10, "MKT", None, None,
        )
        assert result is not None
        assert "quantity" in result.lower()

    def test_zero_quantity(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 0, "MKT", None, None,
        )
        assert result is not None
        assert "quantity" in result.lower()

    def test_invalid_order_type(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 100, "FOK", None, None,
        )
        assert result is not None
        assert "order_type" in result.lower()

    def test_limit_price_required_for_lmt(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 100, "LMT", None, None,
        )
        assert result is not None
        assert "limit_price" in result.lower()

    def test_limit_price_required_for_stp_lmt(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 100, "STP_LMT", None, 145.0,
        )
        assert result is not None
        assert "limit_price" in result.lower()

    def test_stop_price_required_for_stp(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 100, "STP", None, None,
        )
        assert result is not None
        assert "stop_price" in result.lower()

    def test_stop_price_required_for_stp_lmt(self) -> None:
        result = execution_mod._validate_order_params(
            "AAPL", "BUY", 100, "STP_LMT", 150.0, None,
        )
        assert result is not None
        assert "stop_price" in result.lower()


# ---------------------------------------------------------------------------
# preview_stock_order
# ---------------------------------------------------------------------------


class TestPreviewStockOrder:
    """Tests for the preview_stock_order MCP tool."""

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_preview_valid_market_order(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview a valid BUY MKT order returns estimated cost and commission."""
        mock_safety.return_value = _safety_passed()

        result = await execution_mod.preview_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        assert "15,000.00" in result or "15000" in result
        assert "1.99" in result
        mock_client.get_quote.assert_awaited_once_with("AAPL")
        mock_client.preview_order.assert_awaited_once()

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_preview_with_safety_errors_still_returns_preview(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview should show safety errors but still return cost estimate."""
        mock_safety.return_value = _safety_failed(
            errors=["Insufficient buying power: estimated cost exceeds cash"],
        )

        result = await execution_mod.preview_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        # Should still contain preview data
        assert "15,000.00" in result or "15000" in result
        # Should also contain safety errors
        assert "Insufficient buying power" in result

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_preview_with_safety_warnings(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview should show safety warnings."""
        mock_safety.return_value = _safety_passed(
            warnings=["Position concentration warning: order value exceeds limit"],
        )

        result = await execution_mod.preview_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        assert "Position concentration warning" in result

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_preview_limit_order(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview a LMT order with limit_price."""
        mock_safety.return_value = _safety_passed()

        result = await execution_mod.preview_stock_order(
            symbol="AAPL", action="BUY", quantity=100,
            order_type="LMT", limit_price=148.0,
        )

        assert isinstance(result, str)
        mock_client.preview_order.assert_awaited_once()

    async def test_preview_invalid_params_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """Preview with invalid params returns error without calling API."""
        result = await execution_mod.preview_stock_order(
            symbol="AAPL", action="SHORT", quantity=100, order_type="MKT",
        )

        assert "error" in result.lower() or "Error" in result
        mock_client.get_quote.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_preview_api_error_returns_error_message(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview should return error message if TigerClient raises."""
        mock_client.get_quote.side_effect = RuntimeError("API connection failed")

        result = await execution_mod.preview_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        assert "error" in result.lower() or "Error" in result

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_preview_calls_all_safety_checks(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview should call run_safety_checks with correct parameters."""
        mock_safety.return_value = _safety_passed()

        await execution_mod.preview_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        mock_safety.assert_called_once()
        call_kwargs = mock_safety.call_args
        kw = call_kwargs[1]
        order_param = kw.get("order") if kw else call_kwargs[0][0]
        assert order_param.symbol == "AAPL"
        assert order_param.action == "BUY"
        assert order_param.quantity == 100


# ---------------------------------------------------------------------------
# place_stock_order
# ---------------------------------------------------------------------------


class TestPlaceStockOrder:
    """Tests for the place_stock_order MCP tool."""

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_success(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place a valid order when all safety checks pass."""
        mock_safety.return_value = _safety_passed()

        result = await execution_mod.place_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        assert "12345" in result
        mock_client.place_order.assert_awaited_once()

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_blocked_by_safety_error(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place order should NOT place when safety errors exist."""
        mock_safety.return_value = _safety_failed(
            errors=["Short selling blocked: no position in AAPL"],
        )

        result = await execution_mod.place_stock_order(
            symbol="AAPL", action="SELL", quantity=100, order_type="MKT",
        )

        assert "Short selling blocked" in result
        mock_client.place_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_with_warnings_proceeds(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place order should proceed when only warnings exist (no errors)."""
        dup_warn = (
            "Duplicate order detected: "
            "a similar order was submitted recently"
        )
        mock_safety.return_value = _safety_passed(warnings=[dup_warn])

        result = await execution_mod.place_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        assert "12345" in result
        assert "Duplicate order detected" in result
        mock_client.place_order.assert_awaited_once()

    async def test_place_order_invalid_params_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """Place order with invalid params returns error without calling API."""
        result = await execution_mod.place_stock_order(
            symbol="AAPL", action="BUY", quantity=-10, order_type="MKT",
        )

        assert "error" in result.lower() or "Error" in result
        mock_client.place_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_records_fingerprint(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
        mock_state: MagicMock,
    ) -> None:
        """place_stock_order should record fingerprint in DailyState on success."""
        mock_safety.return_value = _safety_passed()

        await execution_mod.place_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        mock_state.record_order.assert_called_once()
        fingerprint_arg = mock_state.record_order.call_args[0][0]
        assert isinstance(fingerprint_arg, str)
        assert len(fingerprint_arg) > 0

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_does_not_record_fingerprint_on_safety_error(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
        mock_state: MagicMock,
    ) -> None:
        """place_stock_order should NOT record fingerprint when safety blocks order."""
        mock_safety.return_value = _safety_failed(
            errors=["Insufficient buying power"],
        )

        await execution_mod.place_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        mock_state.record_order.assert_not_called()

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_api_error_returns_error_message(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """place_stock_order should return error message when API raises."""
        mock_safety.return_value = _safety_passed()
        mock_client.place_order.side_effect = RuntimeError("Order submission failed")

        result = await execution_mod.place_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        assert "error" in result.lower() or "Error" in result

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_missing_limit_price(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place LMT order without limit_price should return validation error."""
        result = await execution_mod.place_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="LMT",
        )

        assert "limit_price" in result.lower()
        mock_client.place_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_missing_stop_price(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place STP order without stop_price should return validation error."""
        result = await execution_mod.place_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="STP",
        )

        assert "stop_price" in result.lower()
        mock_client.place_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_returns_order_details(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Successful place_stock_order should include order_id, status in result."""
        mock_safety.return_value = _safety_passed()
        mock_client.place_order.return_value = {
            "order_id": 99999,
            "symbol": "TSLA",
            "action": "BUY",
            "quantity": 50,
            "order_type": "limit",
        }

        result = await execution_mod.place_stock_order(
            symbol="TSLA", action="BUY", quantity=50,
            order_type="LMT", limit_price=200.0,
        )

        assert "99999" in result
        assert "TSLA" in result

    @patch("tiger_mcp.tools.orders.execution.run_safety_checks")
    async def test_place_order_multiple_safety_errors(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Multiple safety errors should all appear in the result."""
        mock_safety.return_value = _safety_failed(
            errors=[
                "Insufficient buying power: estimated cost exceeds cash",
                "Max order value exceeded: order too large",
            ],
        )

        result = await execution_mod.place_stock_order(
            symbol="AAPL", action="BUY", quantity=100, order_type="MKT",
        )

        assert "Insufficient buying power" in result
        assert "Max order value exceeded" in result
        mock_client.place_order.assert_not_awaited()


# ---------------------------------------------------------------------------
# Format safety result
# ---------------------------------------------------------------------------


class TestFormatSafetyResult:
    """Tests for _format_safety_result helper."""

    def test_format_empty_result(self) -> None:
        """Empty safety result should produce minimal output."""
        result = execution_mod._format_safety_result(_safety_passed())
        assert isinstance(result, str)

    def test_format_with_errors(self) -> None:
        """Errors should appear in the formatted text."""
        sr = _safety_failed(errors=["Error one", "Error two"])
        result = execution_mod._format_safety_result(sr)
        assert "Error one" in result
        assert "Error two" in result

    def test_format_with_warnings(self) -> None:
        """Warnings should appear in the formatted text."""
        sr = _safety_passed(warnings=["Warning one"])
        result = execution_mod._format_safety_result(sr)
        assert "Warning one" in result

    def test_format_with_both_errors_and_warnings(self) -> None:
        """Both errors and warnings should appear."""
        sr = _safety_failed(
            errors=["An error occurred"],
            warnings=["A warning issued"],
        )
        result = execution_mod._format_safety_result(sr)
        assert "An error occurred" in result
        assert "A warning issued" in result


# ---------------------------------------------------------------------------
# Module-level client/state access pattern
# ---------------------------------------------------------------------------


class TestClientAccessPattern:
    """Test the module-level _client/_state and init() pattern."""

    def test_init_function_exists(self) -> None:
        """The module should expose an init(client, state) function."""
        assert callable(execution_mod.init)

    def test_init_sets_client(self, mock_client: AsyncMock) -> None:
        """init() should set the module-level _client."""
        execution_mod.init(mock_client, MagicMock())
        assert execution_mod._client is mock_client

    def test_init_sets_state(self, mock_state: MagicMock) -> None:
        """init() should set the module-level _state."""
        execution_mod.init(AsyncMock(), mock_state)
        assert execution_mod._state is mock_state


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


class TestMcpToolRegistration:
    """Verify the tools are registered with @mcp.tool() decorator."""

    def test_preview_stock_order_is_async(self) -> None:
        """preview_stock_order should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(execution_mod.preview_stock_order)

    def test_place_stock_order_is_async(self) -> None:
        """place_stock_order should be an async function."""
        import inspect

        assert inspect.iscoroutinefunction(execution_mod.place_stock_order)
