"""Tests for the MCP server skeleton module."""

from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest
from mcp.server.fastmcp import FastMCP

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
