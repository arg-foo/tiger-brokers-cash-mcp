"""Integration tests for TASK-012: server wiring and tool registration.

Verifies that:
- All 14 tools are registered with the FastMCP server instance.
- Tool modules are importable and register their tools at import time.
- main() creates TigerClient / DailyState and calls init() on each module.
- The server can be imported without real credentials (no side effects).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_registered_tool_names() -> set[str]:
    """Return the set of tool names registered on the module-level mcp."""
    from tiger_mcp.server import mcp

    tools = mcp._tool_manager.list_tools()
    return {t.name for t in tools}


# ---------------------------------------------------------------------------
# Tool registration verification
# ---------------------------------------------------------------------------


class TestToolRegistration:
    """Verify all 14 tools are registered with the MCP server instance."""

    def test_all_14_tools_registered(self) -> None:
        """Importing the server module should result in 14 registered tools."""
        tool_names = _get_registered_tool_names()
        assert len(tool_names) == 14, (
            f"Expected 14 tools to be registered, got {len(tool_names)}. "
            f"Tool names: {sorted(tool_names)}"
        )

    def test_account_tools_registered(self) -> None:
        """The four account tools must be registered."""
        tool_names = _get_registered_tool_names()
        expected = {
            "get_account_summary",
            "get_buying_power",
            "get_positions",
            "get_transaction_history",
        }
        assert expected.issubset(tool_names), (
            f"Missing account tools: {expected - tool_names}"
        )

    def test_market_data_tools_registered(self) -> None:
        """The three market data tools must be registered."""
        tool_names = _get_registered_tool_names()
        expected = {
            "get_stock_quote",
            "get_stock_quotes",
            "get_stock_bars",
        }
        assert expected.issubset(tool_names), (
            f"Missing market data tools: {expected - tool_names}"
        )

    def test_order_query_tools_registered(self) -> None:
        """The two order query tools must be registered."""
        tool_names = _get_registered_tool_names()
        expected = {
            "get_open_orders",
            "get_order_detail",
        }
        assert expected.issubset(tool_names), (
            f"Missing order query tools: {expected - tool_names}"
        )

    def test_order_execution_tools_registered(self) -> None:
        """The two order execution tools must be registered."""
        tool_names = _get_registered_tool_names()
        expected = {
            "preview_stock_order",
            "place_stock_order",
        }
        assert expected.issubset(tool_names), (
            f"Missing order execution tools: {expected - tool_names}"
        )

    def test_order_management_tools_registered(self) -> None:
        """The three order management tools must be registered."""
        tool_names = _get_registered_tool_names()
        expected = {
            "modify_order",
            "cancel_order",
            "cancel_all_orders",
        }
        assert expected.issubset(tool_names), (
            f"Missing order management tools: {expected - tool_names}"
        )


# ---------------------------------------------------------------------------
# Import ordering
# ---------------------------------------------------------------------------


class TestImportOrdering:
    """Verify imports do not cause circular dependency issues."""

    def test_server_module_importable_without_credentials(self) -> None:
        """Importing tiger_mcp.server must work without env credentials."""
        import tiger_mcp.server  # noqa: F401

    def test_tool_modules_importable(self) -> None:
        """All tool modules must be importable after the server module."""
        import tiger_mcp.tools.account.tools  # noqa: F401
        import tiger_mcp.tools.market_data.tools  # noqa: F401
        import tiger_mcp.tools.orders.execution  # noqa: F401
        import tiger_mcp.tools.orders.management  # noqa: F401
        import tiger_mcp.tools.orders.query  # noqa: F401

    def test_mcp_instance_is_same_across_all_modules(self) -> None:
        """All tool modules must reference the same mcp instance from server."""
        # The tools import mcp from tiger_mcp.server at module level,
        # so they all share the same instance.
        import tiger_mcp.tools.account.tools as account_mod
        import tiger_mcp.tools.market_data.tools as market_mod
        import tiger_mcp.tools.orders.execution as exec_mod
        import tiger_mcp.tools.orders.management as mgmt_mod
        import tiger_mcp.tools.orders.query as query_mod
        from tiger_mcp.server import mcp as server_mcp

        assert account_mod.mcp is server_mcp
        assert market_mod.mcp is server_mcp
        assert exec_mod.mcp is server_mcp
        assert query_mod.mcp is server_mcp
        assert mgmt_mod.mcp is server_mcp


# ---------------------------------------------------------------------------
# main() wiring
# ---------------------------------------------------------------------------


class TestMainWiring:
    """Verify main() creates dependencies and calls init() on tool modules."""

    @patch("tiger_mcp.server.mcp")
    @patch("tiger_mcp.tools.orders.management.init")
    @patch("tiger_mcp.tools.orders.execution.init")
    @patch("tiger_mcp.tools.orders.query.init")
    @patch("tiger_mcp.tools.market_data.tools.init")
    @patch("tiger_mcp.tools.account.tools.init")
    @patch("tiger_mcp.server.TigerClient")
    @patch("tiger_mcp.server.DailyState")
    @patch("tiger_mcp.server.Settings.from_env")
    async def test_main_creates_client_and_state(
        self,
        mock_from_env: MagicMock,
        mock_daily_state_cls: MagicMock,
        mock_tiger_client_cls: MagicMock,
        mock_account_init: MagicMock,
        mock_market_init: MagicMock,
        mock_query_init: MagicMock,
        mock_exec_init: MagicMock,
        mock_mgmt_init: MagicMock,
        mock_mcp: MagicMock,
    ) -> None:
        """main() should create TigerClient and DailyState, and call init()."""
        from tiger_mcp.server import main

        mock_settings = MagicMock()
        mock_settings.tiger_id = "test_id"
        mock_settings.sandbox = True
        mock_settings.state_dir = "/tmp/test-state"
        mock_from_env.return_value = mock_settings

        mock_client = AsyncMock()
        mock_tiger_client_cls.return_value = mock_client

        mock_state = MagicMock()
        mock_daily_state_cls.return_value = mock_state

        mock_mcp.run_stdio_async = AsyncMock()

        await main()

        # Verify TigerClient was created with settings
        mock_tiger_client_cls.assert_called_once_with(mock_settings)

        # Verify DailyState was created with state_dir
        mock_daily_state_cls.assert_called_once_with(mock_settings.state_dir)

        # Verify all init() functions were called with correct dependencies
        mock_account_init.assert_called_once_with(mock_client)
        mock_market_init.assert_called_once_with(mock_client)
        mock_query_init.assert_called_once_with(mock_client)
        mock_exec_init.assert_called_once_with(
            mock_client, mock_state, mock_settings,
        )
        mock_mgmt_init.assert_called_once_with(
            mock_client, mock_state, mock_settings,
        )

    @patch("tiger_mcp.server.mcp")
    @patch("tiger_mcp.tools.orders.management.init")
    @patch("tiger_mcp.tools.orders.execution.init")
    @patch("tiger_mcp.tools.orders.query.init")
    @patch("tiger_mcp.tools.market_data.tools.init")
    @patch("tiger_mcp.tools.account.tools.init")
    @patch("tiger_mcp.server.TigerClient")
    @patch("tiger_mcp.server.DailyState")
    @patch("tiger_mcp.server.Settings.from_env")
    async def test_main_runs_mcp_server(
        self,
        mock_from_env: MagicMock,
        mock_daily_state_cls: MagicMock,
        mock_tiger_client_cls: MagicMock,
        mock_account_init: MagicMock,
        mock_market_init: MagicMock,
        mock_query_init: MagicMock,
        mock_exec_init: MagicMock,
        mock_mgmt_init: MagicMock,
        mock_mcp: MagicMock,
    ) -> None:
        """main() should call mcp.run_stdio_async() to start the server."""
        from tiger_mcp.server import main

        mock_settings = MagicMock()
        mock_settings.tiger_id = "test_id"
        mock_settings.sandbox = True
        mock_settings.state_dir = "/tmp/test-state"
        mock_from_env.return_value = mock_settings
        mock_tiger_client_cls.return_value = AsyncMock()
        mock_daily_state_cls.return_value = MagicMock()
        mock_mcp.run_stdio_async = AsyncMock()

        await main()

        mock_mcp.run_stdio_async.assert_awaited_once()
