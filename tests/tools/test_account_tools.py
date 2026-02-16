"""Tests for the account MCP tools.

Each tool is tested with a mocked TigerClient to verify:
- Response formatting (currency values, field presence)
- Error handling (API errors produce descriptive messages)
- Edge cases (empty positions, missing data)
- Parameter filtering (transaction history filters)
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Create a mock TigerClient with async methods."""
    client = AsyncMock()
    return client


@pytest.fixture(autouse=True)
def _patch_client(mock_client: AsyncMock) -> Any:
    """Patch the module-level _client in the tools module for every test."""
    with patch(
        "tiger_mcp.tools.account.tools._client", mock_client
    ):
        yield


# ---------------------------------------------------------------------------
# get_account_summary
# ---------------------------------------------------------------------------


class TestGetAccountSummary:
    """Test the get_account_summary MCP tool."""

    async def test_returns_formatted_account_summary(
        self, mock_client: AsyncMock
    ) -> None:
        """Tool should return formatted text with cash, buying power, P&L, NLV."""
        mock_client.get_assets.return_value = {
            "cash": 50000.0,
            "buying_power": 100000.0,
            "realized_pnl": 1234.56,
            "unrealized_pnl": -567.89,
            "net_liquidation": 150000.0,
        }

        from tiger_mcp.tools.account.tools import get_account_summary

        result = await get_account_summary()

        assert "$50,000.00" in result
        assert "$100,000.00" in result
        assert "$1,234.56" in result
        assert "-$567.89" in result
        assert "$150,000.00" in result

    async def test_contains_all_required_labels(
        self, mock_client: AsyncMock
    ) -> None:
        """Tool output should contain descriptive labels for each field."""
        mock_client.get_assets.return_value = {
            "cash": 10000.0,
            "buying_power": 20000.0,
            "realized_pnl": 0.0,
            "unrealized_pnl": 0.0,
            "net_liquidation": 30000.0,
        }

        from tiger_mcp.tools.account.tools import get_account_summary

        result = await get_account_summary()

        # Check that key labels are present (case-insensitive)
        result_lower = result.lower()
        assert "cash" in result_lower
        assert "buying power" in result_lower
        assert "net liquidation" in result_lower

    async def test_handles_api_error(
        self, mock_client: AsyncMock
    ) -> None:
        """When the API raises an error, tool should return a descriptive message."""
        mock_client.get_assets.side_effect = RuntimeError(
            "get_assets failed: API connection refused"
        )

        from tiger_mcp.tools.account.tools import get_account_summary

        result = await get_account_summary()

        assert "error" in result.lower()
        assert "API connection refused" in result

    async def test_handles_missing_fields_gracefully(
        self, mock_client: AsyncMock
    ) -> None:
        """When some fields are missing from API response, tool should not crash."""
        mock_client.get_assets.return_value = {
            "cash": 50000.0,
            # Other fields missing
        }

        from tiger_mcp.tools.account.tools import get_account_summary

        result = await get_account_summary()

        # Should still contain cash value and not raise
        assert "$50,000.00" in result


# ---------------------------------------------------------------------------
# get_buying_power
# ---------------------------------------------------------------------------


class TestGetBuyingPower:
    """Test the get_buying_power MCP tool."""

    async def test_returns_buying_power_value(
        self, mock_client: AsyncMock
    ) -> None:
        """Tool should return available buying power as formatted currency."""
        mock_client.get_assets.return_value = {
            "cash": 75000.0,
            "buying_power": 75000.0,
        }

        from tiger_mcp.tools.account.tools import get_buying_power

        result = await get_buying_power()

        assert "$75,000.00" in result

    async def test_contains_buying_power_label(
        self, mock_client: AsyncMock
    ) -> None:
        """Output should contain a descriptive label."""
        mock_client.get_assets.return_value = {
            "cash": 50000.0,
            "buying_power": 50000.0,
        }

        from tiger_mcp.tools.account.tools import get_buying_power

        result = await get_buying_power()

        assert "buying power" in result.lower()

    async def test_includes_cash_context(
        self, mock_client: AsyncMock
    ) -> None:
        """Output should include cash balance for context."""
        mock_client.get_assets.return_value = {
            "cash": 60000.0,
            "buying_power": 60000.0,
        }

        from tiger_mcp.tools.account.tools import get_buying_power

        result = await get_buying_power()

        assert "cash" in result.lower()
        assert "$60,000.00" in result

    async def test_handles_api_error(
        self, mock_client: AsyncMock
    ) -> None:
        """When the API raises an error, tool should return a descriptive message."""
        mock_client.get_assets.side_effect = RuntimeError(
            "get_assets failed: timeout"
        )

        from tiger_mcp.tools.account.tools import get_buying_power

        result = await get_buying_power()

        assert "error" in result.lower()
        assert "timeout" in result


# ---------------------------------------------------------------------------
# get_positions
# ---------------------------------------------------------------------------


class TestGetPositions:
    """Test the get_positions MCP tool."""

    async def test_returns_formatted_positions(
        self, mock_client: AsyncMock
    ) -> None:
        """Tool should return formatted text with position details."""
        mock_client.get_positions.return_value = [
            {
                "symbol": "AAPL",
                "quantity": 100,
                "average_cost": 150.25,
                "market_value": 17500.0,
                "unrealized_pnl": 2475.0,
            },
            {
                "symbol": "GOOGL",
                "quantity": 50,
                "average_cost": 140.00,
                "market_value": 8000.0,
                "unrealized_pnl": 1000.0,
            },
        ]

        from tiger_mcp.tools.account.tools import get_positions

        result = await get_positions()

        assert "AAPL" in result
        assert "GOOGL" in result
        assert "100" in result
        assert "50" in result

    async def test_empty_portfolio_message(
        self, mock_client: AsyncMock
    ) -> None:
        """When no positions, tool should return 'No positions found.'"""
        mock_client.get_positions.return_value = []

        from tiger_mcp.tools.account.tools import get_positions

        result = await get_positions()

        assert result == "No positions found."

    async def test_includes_pnl_percentage(
        self, mock_client: AsyncMock
    ) -> None:
        """Output should include unrealized P&L percentage for each position."""
        mock_client.get_positions.return_value = [
            {
                "symbol": "AAPL",
                "quantity": 100,
                "average_cost": 150.00,
                "market_value": 17500.0,
                "unrealized_pnl": 2500.0,
            },
        ]

        from tiger_mcp.tools.account.tools import get_positions

        result = await get_positions()

        # P&L % = unrealized_pnl / (average_cost * quantity) * 100
        # = 2500 / (150 * 100) * 100 = 16.67%
        assert "16.67%" in result

    async def test_includes_market_value(
        self, mock_client: AsyncMock
    ) -> None:
        """Output should include market value formatted as currency."""
        mock_client.get_positions.return_value = [
            {
                "symbol": "TSLA",
                "quantity": 10,
                "average_cost": 200.00,
                "market_value": 2500.0,
                "unrealized_pnl": 500.0,
            },
        ]

        from tiger_mcp.tools.account.tools import get_positions

        result = await get_positions()

        assert "$2,500.00" in result

    async def test_handles_api_error(
        self, mock_client: AsyncMock
    ) -> None:
        """When the API raises an error, tool should return a descriptive message."""
        mock_client.get_positions.side_effect = RuntimeError(
            "get_positions failed: connection lost"
        )

        from tiger_mcp.tools.account.tools import get_positions

        result = await get_positions()

        assert "error" in result.lower()
        assert "connection lost" in result

    async def test_handles_missing_pnl_field(
        self, mock_client: AsyncMock
    ) -> None:
        """When unrealized_pnl is missing, tool should handle gracefully."""
        mock_client.get_positions.return_value = [
            {
                "symbol": "MSFT",
                "quantity": 25,
                "average_cost": 300.00,
            },
        ]

        from tiger_mcp.tools.account.tools import get_positions

        result = await get_positions()

        # Should still display the symbol and not crash
        assert "MSFT" in result


# ---------------------------------------------------------------------------
# get_transaction_history
# ---------------------------------------------------------------------------


class TestGetTransactionHistory:
    """Test the get_transaction_history MCP tool."""

    async def test_returns_formatted_transactions(
        self, mock_client: AsyncMock
    ) -> None:
        """Tool should return formatted execution history."""
        mock_client.get_order_transactions.return_value = [
            {
                "symbol": "AAPL",
                "action": "BUY",
                "quantity": 100,
                "filled": 100,
                "avg_fill_price": 150.50,
                "trade_time": "2026-01-15 10:30:00",
                "commission": 1.99,
            },
        ]

        from tiger_mcp.tools.account.tools import get_transaction_history

        result = await get_transaction_history()

        assert "AAPL" in result
        assert "BUY" in result
        assert "150.50" in result

    async def test_empty_transaction_history(
        self, mock_client: AsyncMock
    ) -> None:
        """When no transactions found, tool should return descriptive message."""
        mock_client.get_order_transactions.return_value = []

        from tiger_mcp.tools.account.tools import get_transaction_history

        result = await get_transaction_history()

        assert "no" in result.lower() and "transaction" in result.lower()

    async def test_passes_symbol_filter(
        self, mock_client: AsyncMock
    ) -> None:
        """Tool should pass symbol filter to TigerClient."""
        mock_client.get_order_transactions.return_value = []

        from tiger_mcp.tools.account.tools import get_transaction_history

        await get_transaction_history(symbol="AAPL")

        mock_client.get_order_transactions.assert_called_once_with(
            symbol="AAPL",
            start_date=None,
            end_date=None,
            limit=50,
        )

    async def test_passes_date_filters(
        self, mock_client: AsyncMock
    ) -> None:
        """Tool should pass date range filters to TigerClient."""
        mock_client.get_order_transactions.return_value = []

        from tiger_mcp.tools.account.tools import get_transaction_history

        await get_transaction_history(
            start_date="2026-01-01",
            end_date="2026-01-31",
        )

        mock_client.get_order_transactions.assert_called_once_with(
            symbol=None,
            start_date="2026-01-01",
            end_date="2026-01-31",
            limit=50,
        )

    async def test_passes_limit_parameter(
        self, mock_client: AsyncMock
    ) -> None:
        """Tool should pass limit parameter to TigerClient."""
        mock_client.get_order_transactions.return_value = []

        from tiger_mcp.tools.account.tools import get_transaction_history

        await get_transaction_history(limit=10)

        mock_client.get_order_transactions.assert_called_once_with(
            symbol=None,
            start_date=None,
            end_date=None,
            limit=10,
        )

    async def test_passes_all_filters_combined(
        self, mock_client: AsyncMock
    ) -> None:
        """Tool should pass all filters together to TigerClient."""
        mock_client.get_order_transactions.return_value = []

        from tiger_mcp.tools.account.tools import get_transaction_history

        await get_transaction_history(
            symbol="TSLA",
            start_date="2026-02-01",
            end_date="2026-02-15",
            limit=25,
        )

        mock_client.get_order_transactions.assert_called_once_with(
            symbol="TSLA",
            start_date="2026-02-01",
            end_date="2026-02-15",
            limit=25,
        )

    async def test_handles_api_error(
        self, mock_client: AsyncMock
    ) -> None:
        """When the API raises an error, tool should return a descriptive message."""
        mock_client.get_order_transactions.side_effect = RuntimeError(
            "get_order_transactions failed: server error"
        )

        from tiger_mcp.tools.account.tools import get_transaction_history

        result = await get_transaction_history()

        assert "error" in result.lower()
        assert "server error" in result

    async def test_multiple_transactions_formatted(
        self, mock_client: AsyncMock
    ) -> None:
        """Multiple transactions should each be formatted and separated."""
        mock_client.get_order_transactions.return_value = [
            {
                "symbol": "AAPL",
                "action": "BUY",
                "quantity": 50,
                "filled": 50,
                "avg_fill_price": 148.00,
                "trade_time": "2026-01-10 09:30:00",
                "commission": 1.50,
            },
            {
                "symbol": "AAPL",
                "action": "SELL",
                "quantity": 25,
                "filled": 25,
                "avg_fill_price": 155.00,
                "trade_time": "2026-01-12 14:00:00",
                "commission": 1.25,
            },
        ]

        from tiger_mcp.tools.account.tools import get_transaction_history

        result = await get_transaction_history()

        assert "BUY" in result
        assert "SELL" in result
        assert "148.00" in result
        assert "155.00" in result


# ---------------------------------------------------------------------------
# Client not initialized
# ---------------------------------------------------------------------------


class TestClientNotInitialized:
    """Test behavior when the client has not been initialized."""

    async def test_get_account_summary_without_client(self) -> None:
        """Tool should return error message when client is not initialized."""
        with patch(
            "tiger_mcp.tools.account.tools._client", None
        ):
            from tiger_mcp.tools.account.tools import get_account_summary

            result = await get_account_summary()

            assert "error" in result.lower()
            assert "not initialized" in result.lower()

    async def test_get_buying_power_without_client(self) -> None:
        """Tool should return error message when client is not initialized."""
        with patch(
            "tiger_mcp.tools.account.tools._client", None
        ):
            from tiger_mcp.tools.account.tools import get_buying_power

            result = await get_buying_power()

            assert "error" in result.lower()
            assert "not initialized" in result.lower()

    async def test_get_positions_without_client(self) -> None:
        """Tool should return error message when client is not initialized."""
        with patch(
            "tiger_mcp.tools.account.tools._client", None
        ):
            from tiger_mcp.tools.account.tools import get_positions

            result = await get_positions()

            assert "error" in result.lower()
            assert "not initialized" in result.lower()

    async def test_get_transaction_history_without_client(self) -> None:
        """Tool should return error message when client is not initialized."""
        with patch(
            "tiger_mcp.tools.account.tools._client", None
        ):
            from tiger_mcp.tools.account.tools import get_transaction_history

            result = await get_transaction_history()

            assert "error" in result.lower()
            assert "not initialized" in result.lower()


# ---------------------------------------------------------------------------
# init() function
# ---------------------------------------------------------------------------


class TestInit:
    """Test the init() function that sets the module-level client."""

    def test_init_sets_client(self) -> None:
        """init() should set the module-level _client variable."""
        mock = AsyncMock()

        import tiger_mcp.tools.account.tools as tools_module

        tools_module.init(mock)

        assert tools_module._client is mock

    def test_init_replaces_existing_client(self) -> None:
        """init() should replace any existing client."""
        mock1 = AsyncMock()
        mock2 = AsyncMock()

        import tiger_mcp.tools.account.tools as tools_module

        tools_module.init(mock1)
        tools_module.init(mock2)

        assert tools_module._client is mock2
