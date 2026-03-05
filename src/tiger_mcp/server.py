"""MCP server skeleton for the Tiger Brokers cash-account trading server.

This module creates and configures the FastMCP server instance.  Tool
modules register handlers by importing the module-level ``mcp`` instance::

    from tiger_mcp.server import mcp

    @mcp.tool()
    async def my_tool(...) -> ...: ...

The ``main()`` async entry point loads configuration, sets up structured
logging (directed to *stderr* so that *stdout* remains free for the
MCP JSON-RPC transport), and starts the server.
"""

from __future__ import annotations

import logging
import sys

import structlog
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from tiger_mcp.config import Settings

# ---------------------------------------------------------------------------
# Server factory
# ---------------------------------------------------------------------------


def create_server() -> FastMCP:
    """Create and return a new FastMCP server instance named ``tiger``."""
    return FastMCP("tiger")


# ---------------------------------------------------------------------------
# Module-level FastMCP instance -- importable by tool modules for
# registering @mcp.tool() handlers.
# ---------------------------------------------------------------------------

mcp: FastMCP = create_server()

# ---------------------------------------------------------------------------
# Custom HTTP routes
# ---------------------------------------------------------------------------


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request):  # noqa: ARG001
    """Return a simple JSON health-check response.

    This endpoint is public (no MCP auth required) and is useful for
    container orchestrators, load-balancers, and monitoring probes.
    """
    from starlette.responses import JSONResponse

    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Tool registration -- importing these modules triggers @mcp.tool()
# decorators, registering all 16 tools with the ``mcp`` instance.
#
# IMPORTANT: These imports MUST come after ``mcp`` is defined above
# to avoid circular import errors.
# ---------------------------------------------------------------------------

import tiger_mcp.tools.account.tools  # noqa: E402, F401, I001
import tiger_mcp.tools.market_data.tools  # noqa: E402, F401, I001
import tiger_mcp.tools.orders.execution  # noqa: E402, F401, I001
import tiger_mcp.tools.orders.management  # noqa: E402, F401, I001
import tiger_mcp.tools.orders.oca  # noqa: E402, F401, I001
import tiger_mcp.tools.orders.query  # noqa: E402, F401, I001
from tiger_mcp.api.tiger_client import TigerClient  # noqa: E402, I001
from tiger_mcp.safety.state import DailyState  # noqa: E402, I001

# ---------------------------------------------------------------------------
# Structlog configuration
# ---------------------------------------------------------------------------


def configure_logging() -> None:
    """Configure structlog to render structured log output to stderr.

    This is critical: stdout is reserved for the MCP JSON-RPC transport
    protocol, so all human-readable / debug logging MUST go to stderr.
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


# ---------------------------------------------------------------------------
# DNS rebinding protection
# ---------------------------------------------------------------------------

# 0.0.0.0 is a bind-all address, not a true loopback, but when used as the
# listen address with no explicit allowed hosts we default to loopback
# variants so that local development works out-of-the-box.  For non-local
# access, operators must set MCP_ALLOWED_HOSTS explicitly.
_LOCALHOST_ALIASES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _build_transport_security(
    settings: Settings,
) -> TransportSecuritySettings:
    """Build transport security settings for DNS rebinding protection.

    When ``settings.mcp_allowed_hosts`` is non-empty, those values are used
    directly.  Otherwise the allowed hosts are auto-derived from
    ``settings.mcp_host``: localhost aliases get all common loopback
    variants, while non-local hosts get a ``host:*`` wildcard-port pattern.
    """
    if settings.mcp_allowed_hosts:
        allowed_hosts = list(settings.mcp_allowed_hosts)
    elif settings.mcp_host in _LOCALHOST_ALIASES:
        allowed_hosts = ["localhost:*", "127.0.0.1:*", "[::1]:*"]
    else:
        allowed_hosts = [f"{settings.mcp_host}:*"]

    allowed_origins = [f"http://{h}" for h in allowed_hosts] + [
        f"https://{h}" for h in allowed_hosts
    ]

    return TransportSecuritySettings(
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )


# ---------------------------------------------------------------------------
# Async entry point
# ---------------------------------------------------------------------------


async def main() -> None:
    """Async entry point for the Tiger Brokers MCP server.

    Performs the following steps in order:

    1. Load runtime configuration from environment variables.
    2. Configure structured logging to stderr.
    3. Create TigerClient and DailyState instances.
    4. Inject dependencies into all tool modules via their init() functions.
    5. Optionally start the event subscription subsystem (PushClient → Redis).
    6. Run the MCP server over the configured transport (stdio or streamable-http).
    7. Clean up the event subsystem on shutdown.
    """
    settings = Settings.from_env()
    configure_logging()

    logger = structlog.get_logger()
    logger.info(
        "tiger_mcp_starting",
        tiger_id=settings.tiger_id,
    )

    # Create shared dependencies
    client = TigerClient(settings)
    state = DailyState(settings.state_dir)

    # Wire dependencies into tool modules
    tiger_mcp.tools.account.tools.init(client)
    tiger_mcp.tools.market_data.tools.init(client)
    tiger_mcp.tools.orders.query.init(client)
    tiger_mcp.tools.orders.execution.init(client, state, settings)
    tiger_mcp.tools.orders.management.init(client, state, settings)
    tiger_mcp.tools.orders.oca.init(client, state, settings)

    logger.info(
        "tiger_mcp_tools_initialized",
        tool_count=len(mcp._tool_manager.list_tools()),
    )

    # Optionally start event subscription (Tiger PushClient → Redis Streams)
    push_subscriber = None
    if settings.events_enabled:
        from tiger_mcp.events.publisher import RedisStreamPublisher
        from tiger_mcp.events.subscriber import PushSubscriber

        publisher = RedisStreamPublisher(
            redis_url=settings.redis_url,
            stream_prefix=settings.redis_stream_prefix,
            maxlen=settings.redis_stream_maxlen,
        )
        try:
            publisher.connect()
        except Exception as exc:
            logger.critical(
                "redis_connect_failed_at_startup",
                error=str(exc),
            )
            raise
        push_subscriber = PushSubscriber(
            settings=settings,
            publisher=publisher,
        )
        try:
            push_subscriber.start()
        except Exception:
            publisher.close()
            raise
        logger.info("tiger_events_started")

    try:
        if settings.mcp_transport == "streamable-http":
            mcp.settings.host = settings.mcp_host
            mcp.settings.port = settings.mcp_port
            mcp.settings.transport_security = _build_transport_security(settings)
            if settings.mcp_host == "0.0.0.0" and not settings.mcp_allowed_hosts:
                logger.warning(
                    "dns_rebinding_loopback_only",
                    msg=(
                        "MCP_HOST is 0.0.0.0 with no MCP_ALLOWED_HOSTS; "
                        "only loopback clients will be accepted. "
                        "Set MCP_ALLOWED_HOSTS for external access."
                    ),
                )
            await mcp.run_streamable_http_async()
        else:
            await mcp.run_stdio_async()
    finally:
        if push_subscriber is not None:
            push_subscriber.stop()
            logger.info("tiger_events_stopped")
