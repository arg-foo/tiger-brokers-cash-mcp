"""Tests for OCA and bracket order MCP tools.

All tests mock TigerClient, DailyState, and safety checks so no real API
calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tiger_mcp.safety.checks import SafetyResult
from tiger_mcp.tools.orders import oca as oca_mod

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Create a mock TigerClient with async methods."""
    client = AsyncMock()
    # Default account assets
    client.get_assets.return_value = {
        "cash": 100_000.0,
        "net_liquidation": 200_000.0,
    }
    # Default positions (holding 100 AAPL)
    client.get_positions.return_value = [
        {"symbol": "AAPL", "quantity": 100},
    ]
    # Default preview
    client.preview_oca_order.return_value = {
        "estimated_cost": 0.0,
        "commission": 1.99,
    }
    client.preview_bracket_order.return_value = {
        "estimated_cost": 15_000.0,
        "commission": 1.99,
    }
    # Default place order
    client.place_oca_order.return_value = {
        "order_id": "12345",
        "sub_ids": ["12346", "12347"],
        "symbol": "AAPL",
        "action": "SELL",
        "quantity": 100,
    }
    client.place_bracket_order.return_value = {
        "order_id": "22345",
        "sub_ids": ["22346", "22347"],
        "symbol": "AAPL",
        "action": "BUY",
        "quantity": 100,
    }
    return client


@pytest.fixture()
def mock_state() -> MagicMock:
    """Create a mock DailyState."""
    state = MagicMock()
    state.record_order = MagicMock()
    return state


@pytest.fixture(autouse=True)
def _init_module(
    mock_client: AsyncMock,
    mock_state: MagicMock,
) -> None:
    """Inject mock client and state into the oca module."""
    oca_mod.init(mock_client, mock_state)


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
# OCA parameter validation
# ---------------------------------------------------------------------------


class TestValidateOcaParams:
    """Tests for _validate_oca_params helper."""

    def test_valid_params_return_none(self) -> None:
        result = oca_mod._validate_oca_params(
            "AAPL",
            100,
            160.0,
            140.0,
            138.0,
        )
        assert result is None

    def test_empty_symbol_returns_error(self) -> None:
        result = oca_mod._validate_oca_params(
            "",
            100,
            160.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "symbol" in result.lower()

    def test_lowercase_symbol_returns_error(self) -> None:
        result = oca_mod._validate_oca_params(
            "aapl",
            100,
            160.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "uppercase" in result.lower()

    def test_zero_quantity_returns_error(self) -> None:
        result = oca_mod._validate_oca_params(
            "AAPL",
            0,
            160.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "quantity" in result.lower()

    def test_negative_quantity_returns_error(self) -> None:
        result = oca_mod._validate_oca_params(
            "AAPL",
            -5,
            160.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "quantity" in result.lower()

    def test_tp_limit_price_lte_sl_stop_price_returns_error(self) -> None:
        result = oca_mod._validate_oca_params(
            "AAPL",
            100,
            140.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "take-profit" in result.lower() or "tp_limit_price" in result.lower()

    def test_sl_stop_price_lt_sl_limit_price_returns_error(self) -> None:
        result = oca_mod._validate_oca_params(
            "AAPL",
            100,
            160.0,
            138.0,
            140.0,
        )
        assert result is not None
        assert "stop" in result.lower() or "sl_stop_price" in result.lower()

    def test_tp_limit_price_zero_returns_error(self) -> None:
        result = oca_mod._validate_oca_params(
            "AAPL",
            100,
            0.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "price" in result.lower()

    def test_sl_stop_price_zero_returns_error(self) -> None:
        result = oca_mod._validate_oca_params(
            "AAPL",
            100,
            160.0,
            0.0,
            138.0,
        )
        assert result is not None
        assert "price" in result.lower()

    def test_sl_limit_price_zero_returns_error(self) -> None:
        result = oca_mod._validate_oca_params(
            "AAPL",
            100,
            160.0,
            140.0,
            0.0,
        )
        assert result is not None
        assert "price" in result.lower()

    def test_sl_stop_price_equals_sl_limit_price_is_valid(self) -> None:
        """sl_stop_price == sl_limit_price is valid (stop equals limit)."""
        result = oca_mod._validate_oca_params(
            "AAPL",
            100,
            160.0,
            140.0,
            140.0,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Bracket parameter validation
# ---------------------------------------------------------------------------


class TestValidateBracketParams:
    """Tests for _validate_bracket_params helper."""

    def test_valid_params_return_none(self) -> None:
        result = oca_mod._validate_bracket_params(
            "AAPL",
            100,
            150.0,
            160.0,
            140.0,
            138.0,
        )
        assert result is None

    def test_empty_symbol_returns_error(self) -> None:
        result = oca_mod._validate_bracket_params(
            "",
            100,
            150.0,
            160.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "symbol" in result.lower()

    def test_lowercase_symbol_returns_error(self) -> None:
        result = oca_mod._validate_bracket_params(
            "aapl",
            100,
            150.0,
            160.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "uppercase" in result.lower()

    def test_zero_quantity_returns_error(self) -> None:
        result = oca_mod._validate_bracket_params(
            "AAPL",
            0,
            150.0,
            160.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "quantity" in result.lower()

    def test_tp_limit_price_lte_entry_returns_error(self) -> None:
        result = oca_mod._validate_bracket_params(
            "AAPL",
            100,
            150.0,
            150.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "take-profit" in result.lower() or "tp_limit_price" in result.lower()

    def test_entry_lte_sl_stop_price_returns_error(self) -> None:
        result = oca_mod._validate_bracket_params(
            "AAPL",
            100,
            150.0,
            160.0,
            150.0,
            148.0,
        )
        assert result is not None
        assert "entry" in result.lower() or "entry_limit_price" in result.lower()

    def test_sl_stop_price_lt_sl_limit_price_returns_error(self) -> None:
        result = oca_mod._validate_bracket_params(
            "AAPL",
            100,
            150.0,
            160.0,
            138.0,
            140.0,
        )
        assert result is not None
        assert "stop" in result.lower() or "sl_stop_price" in result.lower()

    def test_entry_limit_price_zero_returns_error(self) -> None:
        result = oca_mod._validate_bracket_params(
            "AAPL",
            100,
            0.0,
            160.0,
            140.0,
            138.0,
        )
        assert result is not None
        assert "price" in result.lower()

    def test_sl_stop_equals_sl_limit_is_valid(self) -> None:
        """sl_stop_price == sl_limit_price is valid."""
        result = oca_mod._validate_bracket_params(
            "AAPL",
            100,
            150.0,
            160.0,
            140.0,
            140.0,
        )
        assert result is None


# ---------------------------------------------------------------------------
# preview_oca_order
# ---------------------------------------------------------------------------


class TestPreviewOcaOrder:
    """Tests for the preview_oca_order MCP tool."""

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_valid_preview_with_position(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview with valid params and existing position returns output."""
        mock_safety.return_value = _safety_passed()

        result = await oca_mod.preview_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert isinstance(result, str)
        assert "AAPL" in result
        mock_client.preview_oca_order.assert_awaited_once()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_preview_with_safety_errors_still_returns_preview(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview should show safety errors but still return preview data."""
        mock_safety.return_value = _safety_failed(
            errors=["Some safety error"],
        )

        result = await oca_mod.preview_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "Some safety error" in result
        mock_client.preview_oca_order.assert_awaited_once()

    async def test_invalid_params_returns_error_without_api_call(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """Preview with invalid params returns error without calling API."""
        result = await oca_mod.preview_oca_order(
            symbol="AAPL",
            quantity=0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "error" in result.lower() or "Error" in result
        mock_client.preview_oca_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_check_uses_oca_order_type(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Safety check should use 'OCA' order_type, not 'LMT'."""
        mock_safety.return_value = _safety_passed()

        await oca_mod.preview_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        mock_safety.assert_called_once()
        order_params = mock_safety.call_args.kwargs.get(
            "order",
            mock_safety.call_args[0][0] if mock_safety.call_args[0] else None,
        )
        assert order_params.order_type == "OCA"

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_check_uses_tp_limit_price(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Safety check should use tp_limit_price for conservative estimation."""
        mock_safety.return_value = _safety_passed()

        await oca_mod.preview_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        mock_safety.assert_called_once()
        order_params = mock_safety.call_args.kwargs.get(
            "order",
            mock_safety.call_args[0][0] if mock_safety.call_args[0] else None,
        )
        assert order_params.limit_price == 160.0

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_api_error_returns_error_message(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview should return error message if TigerClient raises."""
        mock_safety.return_value = _safety_passed()
        mock_client.preview_oca_order.side_effect = RuntimeError("API failed")

        result = await oca_mod.preview_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "error" in result.lower() or "Error" in result

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_no_position_for_symbol_returns_error(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview should return error when no position exists for symbol."""
        mock_client.get_positions.return_value = []

        result = await oca_mod.preview_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "position" in result.lower()
        mock_client.preview_oca_order.assert_not_awaited()


# ---------------------------------------------------------------------------
# place_oca_order
# ---------------------------------------------------------------------------


class TestPlaceOcaOrder:
    """Tests for the place_oca_order MCP tool."""

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_valid_sell_with_position_succeeds(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place OCA SELL with position succeeds."""
        mock_safety.return_value = _safety_passed()

        result = await oca_mod.place_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "12345" in result
        mock_client.place_oca_order.assert_awaited_once()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_no_position_blocks_order(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place OCA should block when no position exists."""
        mock_client.get_positions.return_value = []

        result = await oca_mod.place_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "position" in result.lower()
        mock_client.place_oca_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_quantity_exceeds_held_shares_blocks_order(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place OCA should block when quantity > held shares."""
        mock_client.get_positions.return_value = [
            {"symbol": "AAPL", "quantity": 50},
        ]

        result = await oca_mod.place_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "position" in result.lower() or "exceeds" in result.lower()
        mock_client.place_oca_order.assert_not_awaited()

    async def test_invalid_params_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """Place OCA with invalid params returns error."""
        result = await oca_mod.place_oca_order(
            symbol="",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "error" in result.lower() or "Error" in result
        mock_client.place_oca_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_errors_block_order(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place OCA should block when safety errors exist."""
        mock_safety.return_value = _safety_failed(
            errors=["Daily loss limit exceeded"],
        )

        result = await oca_mod.place_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "Daily loss limit exceeded" in result
        mock_client.place_oca_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_warnings_pass_through(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place OCA should proceed with warnings (no errors)."""
        mock_safety.return_value = _safety_passed(
            warnings=["Duplicate order detected"],
        )

        result = await oca_mod.place_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "12345" in result
        assert "Duplicate order detected" in result
        mock_client.place_oca_order.assert_awaited_once()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_api_error_returns_error_message(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place OCA should return error message when API raises."""
        mock_safety.return_value = _safety_passed()
        mock_client.place_oca_order.side_effect = RuntimeError("API failed")

        result = await oca_mod.place_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "error" in result.lower() or "Error" in result

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_check_uses_oca_order_type(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Safety check should use 'OCA' order_type for fingerprint consistency."""
        mock_safety.return_value = _safety_passed()

        await oca_mod.place_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        mock_safety.assert_called_once()
        order_params = mock_safety.call_args.kwargs.get(
            "order",
            mock_safety.call_args[0][0] if mock_safety.call_args[0] else None,
        )
        assert order_params.order_type == "OCA"

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_check_uses_tp_limit_price(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Safety check should use tp_limit_price for conservative estimation."""
        mock_safety.return_value = _safety_passed()

        await oca_mod.place_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        mock_safety.assert_called_once()
        order_params = mock_safety.call_args.kwargs.get(
            "order",
            mock_safety.call_args[0][0] if mock_safety.call_args[0] else None,
        )
        assert order_params.limit_price == 160.0

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_fingerprint_recorded_on_success(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
        mock_state: MagicMock,
    ) -> None:
        """place_oca_order should record fingerprint in DailyState on success."""
        mock_safety.return_value = _safety_passed()

        await oca_mod.place_oca_order(
            symbol="AAPL",
            quantity=100,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        mock_state.record_order.assert_called_once()
        fingerprint_arg = mock_state.record_order.call_args[0][0]
        assert isinstance(fingerprint_arg, str)
        assert len(fingerprint_arg) > 0


# ---------------------------------------------------------------------------
# preview_bracket_order
# ---------------------------------------------------------------------------


class TestPreviewBracketOrder:
    """Tests for the preview_bracket_order MCP tool."""

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_valid_preview_returns_formatted_output(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview with valid params returns formatted output."""
        mock_safety.return_value = _safety_passed()

        result = await oca_mod.preview_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert isinstance(result, str)
        assert "AAPL" in result
        mock_client.preview_bracket_order.assert_awaited_once()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_check_uses_bracket_order_type(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Safety check should use 'BRACKET' order_type, not 'LMT'."""
        mock_safety.return_value = _safety_passed()

        await oca_mod.preview_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        mock_safety.assert_called_once()
        order_params = mock_safety.call_args.kwargs.get(
            "order",
            mock_safety.call_args[0][0] if mock_safety.call_args[0] else None,
        )
        assert order_params.order_type == "BRACKET"

    async def test_invalid_params_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """Preview bracket with invalid params returns error."""
        result = await oca_mod.preview_bracket_order(
            symbol="AAPL",
            quantity=0,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "error" in result.lower() or "Error" in result
        mock_client.preview_bracket_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_api_error_returns_error_message(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Preview should return error message if TigerClient raises."""
        mock_safety.return_value = _safety_passed()
        mock_client.preview_bracket_order.side_effect = RuntimeError(
            "API failed",
        )

        result = await oca_mod.preview_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "error" in result.lower() or "Error" in result


# ---------------------------------------------------------------------------
# place_bracket_order
# ---------------------------------------------------------------------------


class TestPlaceBracketOrder:
    """Tests for the place_bracket_order MCP tool."""

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_valid_buy_succeeds(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place bracket BUY with valid params succeeds."""
        mock_safety.return_value = _safety_passed()

        result = await oca_mod.place_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "22345" in result
        mock_client.place_bracket_order.assert_awaited_once()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_check_uses_bracket_order_type(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Safety check should use 'BRACKET' order_type for fingerprint consistency."""
        mock_safety.return_value = _safety_passed()

        await oca_mod.place_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        mock_safety.assert_called_once()
        order_params = mock_safety.call_args.kwargs.get(
            "order",
            mock_safety.call_args[0][0] if mock_safety.call_args[0] else None,
        )
        assert order_params.order_type == "BRACKET"

    async def test_invalid_params_returns_error(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """Place bracket with invalid params returns error."""
        result = await oca_mod.place_bracket_order(
            symbol="",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "error" in result.lower() or "Error" in result
        mock_client.place_bracket_order.assert_not_awaited()

    async def test_price_relationship_validation(
        self,
        mock_client: AsyncMock,
    ) -> None:
        """tp > entry > sl must hold."""
        # tp <= entry
        result = await oca_mod.place_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=160.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )
        assert "error" in result.lower() or "Error" in result

        # entry <= sl_stop
        result = await oca_mod.place_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=140.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )
        assert "error" in result.lower() or "Error" in result

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_errors_block_order(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place bracket should block when safety errors exist."""
        mock_safety.return_value = _safety_failed(
            errors=["Insufficient buying power"],
        )

        result = await oca_mod.place_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "Insufficient buying power" in result
        mock_client.place_bracket_order.assert_not_awaited()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_safety_warnings_pass_through(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place bracket should proceed with warnings (no errors)."""
        mock_safety.return_value = _safety_passed(
            warnings=["Position concentration warning"],
        )

        result = await oca_mod.place_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "22345" in result
        assert "Position concentration warning" in result
        mock_client.place_bracket_order.assert_awaited_once()

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_api_error_returns_error_message(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
    ) -> None:
        """Place bracket should return error message when API raises."""
        mock_safety.return_value = _safety_passed()
        mock_client.place_bracket_order.side_effect = RuntimeError("API failed")

        result = await oca_mod.place_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        assert "error" in result.lower() or "Error" in result

    @patch("tiger_mcp.tools.orders.oca.run_safety_checks")
    async def test_fingerprint_recorded_on_success(
        self,
        mock_safety: MagicMock,
        mock_client: AsyncMock,
        mock_state: MagicMock,
    ) -> None:
        """place_bracket_order should record fingerprint on success."""
        mock_safety.return_value = _safety_passed()

        await oca_mod.place_bracket_order(
            symbol="AAPL",
            quantity=100,
            entry_limit_price=150.0,
            tp_limit_price=160.0,
            sl_stop_price=140.0,
            sl_limit_price=138.0,
        )

        mock_state.record_order.assert_called_once()
        fingerprint_arg = mock_state.record_order.call_args[0][0]
        assert isinstance(fingerprint_arg, str)
        assert len(fingerprint_arg) > 0


# ---------------------------------------------------------------------------
# Module-level client/state access pattern
# ---------------------------------------------------------------------------


class TestBuildAndRunSafety:
    """Tests for _build_and_run_safety helper."""

    def test_build_and_run_safety_is_not_async(self) -> None:
        """_build_and_run_safety should be a regular (sync) function."""
        import inspect

        assert not inspect.iscoroutinefunction(oca_mod._build_and_run_safety)


class TestClientAccessPattern:
    """Test the module-level _client/_state and init() pattern."""

    def test_init_function_exists(self) -> None:
        assert callable(oca_mod.init)

    def test_init_sets_client(self, mock_client: AsyncMock) -> None:
        oca_mod.init(mock_client, MagicMock())
        assert oca_mod._client is mock_client

    def test_init_sets_state(self, mock_state: MagicMock) -> None:
        oca_mod.init(AsyncMock(), mock_state)
        assert oca_mod._state is mock_state


# ---------------------------------------------------------------------------
# MCP tool registration
# ---------------------------------------------------------------------------


class TestMcpToolRegistration:
    """Verify the tools are registered with @mcp.tool() decorator."""

    def test_preview_oca_order_is_async(self) -> None:
        import inspect

        assert inspect.iscoroutinefunction(oca_mod.preview_oca_order)

    def test_place_oca_order_is_async(self) -> None:
        import inspect

        assert inspect.iscoroutinefunction(oca_mod.place_oca_order)

    def test_preview_bracket_order_is_async(self) -> None:
        import inspect

        assert inspect.iscoroutinefunction(oca_mod.preview_bracket_order)

    def test_place_bracket_order_is_async(self) -> None:
        import inspect

        assert inspect.iscoroutinefunction(oca_mod.place_bracket_order)
