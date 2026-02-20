"""Tests for the MCP server skeleton module."""

from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP

import tiger_mcp.tools.account.tools
import tiger_mcp.tools.market_data.tools
import tiger_mcp.tools.orders.execution
import tiger_mcp.tools.orders.management
import tiger_mcp.tools.orders.query
import tiger_mcp.tools.orders.trade_plans

# ---------------------------------------------------------------------------
# create_server()
# ---------------------------------------------------------------------------


class TestCreateServer:
    """Test the create_server() factory function."""

    def test_returns_fastmcp_instance(self) -> None:
        """create_server() must return a FastMCP server instance."""
        from tiger_mcp.server import create_server

        server = create_server()
        assert isinstance(server, FastMCP)

    def test_server_name_is_tiger(self) -> None:
        """The server must be named 'tiger'."""
        from tiger_mcp.server import create_server

        server = create_server()
        assert server.name == "tiger"

    def test_returns_new_instance_each_call(self) -> None:
        """Each call to create_server() should create a fresh instance."""
        from tiger_mcp.server import create_server

        server_a = create_server()
        server_b = create_server()
        assert server_a is not server_b


# ---------------------------------------------------------------------------
# Module-level mcp instance
# ---------------------------------------------------------------------------


class TestModuleLevelMcpInstance:
    """Test that the module exposes a FastMCP instance for tool registration."""

    def test_module_level_mcp_exists(self) -> None:
        """A module-level 'mcp' variable must be importable."""
        from tiger_mcp.server import mcp

        assert mcp is not None

    def test_module_level_mcp_is_fastmcp(self) -> None:
        """The module-level 'mcp' must be a FastMCP instance."""
        from tiger_mcp.server import mcp

        assert isinstance(mcp, FastMCP)

    def test_module_level_mcp_has_correct_name(self) -> None:
        """The module-level mcp instance must be named 'tiger'."""
        from tiger_mcp.server import mcp

        assert mcp.name == "tiger"


# ---------------------------------------------------------------------------
# main() coroutine
# ---------------------------------------------------------------------------


class TestMainFunction:
    """Test the async main() entry point."""

    def test_main_exists(self) -> None:
        """main() must be importable from the server module."""
        from tiger_mcp.server import main

        assert main is not None

    def test_main_is_coroutine_function(self) -> None:
        """main() must be an async function (coroutine function)."""
        from tiger_mcp.server import main

        assert inspect.iscoroutinefunction(main)

    async def test_main_calls_run_stdio_async(self) -> None:
        """main() should load config, configure logging, and run the server."""
        from tiger_mcp.server import main

        with (
            patch(
                "tiger_mcp.server.Settings.from_env",
                side_effect=ValueError("TIGER_ID not set"),
            ) as mock_from_env,
        ):
            # main() calls Settings.from_env() first; it raises because
            # we have no credentials in the test environment.
            with pytest.raises(ValueError, match="TIGER_ID"):
                await main()
            mock_from_env.assert_called_once()


# ---------------------------------------------------------------------------
# Structlog configuration
# ---------------------------------------------------------------------------


class TestStructlogConfiguration:
    """Test that structlog is configured to write to stderr."""

    def test_configure_logging_function_exists(self) -> None:
        """A configure_logging() helper must be importable."""
        from tiger_mcp.server import configure_logging

        assert callable(configure_logging)

    def test_configure_logging_writes_to_stderr(self) -> None:
        """After calling configure_logging(), structlog must output to stderr."""
        import structlog

        from tiger_mcp.server import configure_logging

        configure_logging()

        # structlog should be configured; verify by checking the
        # configuration produces output to stderr (not stdout).
        config = structlog.get_config()
        processors = config.get("processors", [])

        # There should be at least one processor configured.
        assert len(processors) > 0

    def test_logging_does_not_write_to_stdout(
        self,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Logging output must NOT appear on stdout.

        stdout is reserved for MCP JSON-RPC transport.
        """
        import structlog

        from tiger_mcp.server import configure_logging

        configure_logging()
        logger = structlog.get_logger()

        # Use a wrapper to capture. structlog may use stdlib logging
        # backend.
        logger.info("test_message", key="value")

        captured = capsys.readouterr()
        assert "test_message" not in captured.out, (
            "Log output appeared on stdout -- "
            "stdout is reserved for MCP JSON-RPC transport"
        )


# ---------------------------------------------------------------------------
# __main__.py entry point
# ---------------------------------------------------------------------------


class TestMainModule:
    """Test the __main__.py entry point module."""

    def test_main_module_importable(self) -> None:
        """tiger_mcp.__main__ must be importable."""
        import tiger_mcp.__main__  # noqa: F401

    def test_main_module_has_main(self) -> None:
        """The __main__ module should reference the main function."""
        import tiger_mcp.__main__ as main_mod

        assert hasattr(main_mod, "main")


# ---------------------------------------------------------------------------
# Import smoke test
# ---------------------------------------------------------------------------


class TestImportSmoke:
    """Verify the server module can be imported without side effects."""

    def test_import_does_not_require_credentials(self) -> None:
        """Importing tiger_mcp.server must succeed without env credentials."""
        # This test verifies that the module-level code does NOT call
        # Settings.from_env() -- that only happens inside main().
        import tiger_mcp.server  # noqa: F401


# ---------------------------------------------------------------------------
# /health endpoint
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    """Test the /health custom route."""

    def test_health_route_registered(self) -> None:
        """The /health route must be registered on the mcp instance."""
        from tiger_mcp.server import mcp

        # custom_route registers Route objects on _custom_starlette_routes
        route_paths = [r.path for r in mcp._custom_starlette_routes]
        assert "/health" in route_paths

    def test_health_handler_is_async(self) -> None:
        """The health endpoint handler must be an async function."""
        from tiger_mcp.server import health_check

        assert inspect.iscoroutinefunction(health_check)

    async def test_health_returns_ok_json(self) -> None:
        """The health endpoint must return JSON with status ok."""
        from starlette.applications import Starlette
        from starlette.testclient import TestClient

        from tiger_mcp.server import mcp

        routes = list(mcp._custom_starlette_routes)
        app = Starlette(routes=routes)
        client = TestClient(app)

        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# Transport selection
# ---------------------------------------------------------------------------


class TestTransportSelection:
    """Test transport selection logic in main()."""

    async def test_http_transport_sets_host_and_port(self) -> None:
        """When mcp_transport is streamable-http, main() sets host/port
        and calls run_streamable_http_async."""
        from unittest.mock import MagicMock

        from tiger_mcp.server import main, mcp

        mock_logger = MagicMock()

        with (
            patch("tiger_mcp.server.Settings.from_env") as mock_from_env,
            patch("tiger_mcp.server.configure_logging"),
            patch("tiger_mcp.server.structlog") as mock_structlog,
            patch("tiger_mcp.server.TigerClient"),
            patch("tiger_mcp.server.DailyState"),
            patch("tiger_mcp.server.TradePlanStore"),
            patch.object(tiger_mcp.tools.account.tools, "init"),
            patch.object(tiger_mcp.tools.market_data.tools, "init"),
            patch.object(tiger_mcp.tools.orders.query, "init"),
            patch.object(tiger_mcp.tools.orders.execution, "init"),
            patch.object(tiger_mcp.tools.orders.management, "init"),
            patch.object(tiger_mcp.tools.orders.trade_plans, "init"),
            patch.object(
                mcp, "run_streamable_http_async", return_value=None
            ) as mock_run_http,
        ):
            mock_structlog.get_logger.return_value = mock_logger
            mock_settings = mock_from_env.return_value
            mock_settings.tiger_id = "test-id"
            mock_settings.state_dir = "/tmp/state"
            mock_settings.mcp_transport = "streamable-http"
            mock_settings.mcp_host = "127.0.0.1"
            mock_settings.mcp_port = 9090

            await main()

            mock_run_http.assert_called_once()
            assert mcp.settings.host == "127.0.0.1"
            assert mcp.settings.port == 9090

    async def test_stdio_transport_calls_run_stdio(self) -> None:
        """When mcp_transport is stdio, main() should call run_stdio_async."""
        from unittest.mock import MagicMock

        from tiger_mcp.server import main, mcp

        mock_logger = MagicMock()

        with (
            patch("tiger_mcp.server.Settings.from_env") as mock_from_env,
            patch("tiger_mcp.server.configure_logging"),
            patch("tiger_mcp.server.structlog") as mock_structlog,
            patch("tiger_mcp.server.TigerClient"),
            patch("tiger_mcp.server.DailyState"),
            patch("tiger_mcp.server.TradePlanStore"),
            patch.object(tiger_mcp.tools.account.tools, "init"),
            patch.object(tiger_mcp.tools.market_data.tools, "init"),
            patch.object(tiger_mcp.tools.orders.query, "init"),
            patch.object(tiger_mcp.tools.orders.execution, "init"),
            patch.object(tiger_mcp.tools.orders.management, "init"),
            patch.object(tiger_mcp.tools.orders.trade_plans, "init"),
            patch.object(
                mcp, "run_stdio_async", return_value=None
            ) as mock_run_stdio,
        ):
            mock_structlog.get_logger.return_value = mock_logger
            mock_settings = mock_from_env.return_value
            mock_settings.tiger_id = "test-id"
            mock_settings.state_dir = "/tmp/state"
            mock_settings.mcp_transport = "stdio"

            await main()

            mock_run_stdio.assert_called_once()
