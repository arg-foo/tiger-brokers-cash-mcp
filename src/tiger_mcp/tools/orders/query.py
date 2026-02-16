"""MCP tools for querying order status and details.

Provides two tools:

- ``get_open_orders`` -- list currently open orders with optional symbol filter.
- ``get_order_detail`` -- retrieve full details for a single order by ID.

Client access pattern
---------------------
A module-level ``_client`` reference is set via the ``init(client)`` function
during server startup.  Tool functions use this reference to call the
:class:`~tiger_mcp.api.tiger_client.TigerClient` API wrapper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tiger_mcp.server import mcp

if TYPE_CHECKING:
    from tiger_mcp.api.tiger_client import TigerClient

# ---------------------------------------------------------------------------
# Module-level client reference
# ---------------------------------------------------------------------------

_client: TigerClient | None = None


def init(client: TigerClient) -> None:
    """Set the module-level TigerClient instance.

    Called once during server initialisation so that tool functions can
    access the shared client without requiring dependency injection on
    every call.
    """
    global _client  # noqa: PLW0603
    _client = client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _format_order_line(order: dict[str, Any]) -> str:
    """Format a single open-order dict into a readable text line."""
    order_id = order.get("order_id", "N/A")
    symbol = order.get("symbol", "N/A")
    action = order.get("action", "N/A")
    quantity = order.get("quantity", "N/A")
    filled = order.get("filled", 0)
    order_type = order.get("order_type", "N/A")
    limit_price = order.get("limit_price")
    status = order.get("status", "N/A")
    submitted_at = order.get("trade_time", "N/A")

    price_str = str(limit_price) if limit_price is not None else "N/A"

    return (
        f"Order {order_id}: {symbol} {action} {quantity} "
        f"(filled {filled}) | type={order_type} limit={price_str} "
        f"status={status} submitted={submitted_at}"
    )


def _format_order_detail(detail: dict[str, Any]) -> str:
    """Format a full order detail dict into readable multi-line text."""
    lines: list[str] = ["Order Detail", "=" * 40]

    field_labels = [
        ("order_id", "Order ID"),
        ("symbol", "Symbol"),
        ("action", "Action"),
        ("order_type", "Order Type"),
        ("quantity", "Quantity"),
        ("filled", "Filled Quantity"),
        ("avg_fill_price", "Avg Fill Price"),
        ("limit_price", "Limit Price"),
        ("aux_price", "Stop Price"),
        ("status", "Status"),
        ("remaining", "Remaining"),
        ("trade_time", "Trade Time"),
        ("commission", "Commission"),
    ]

    for key, label in field_labels:
        value = detail.get(key)
        if value is not None:
            lines.append(f"  {label}: {value}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_open_orders(symbol: str = "") -> str:
    """List currently open orders, optionally filtered by symbol.

    Parameters
    ----------
    symbol:
        Optional ticker symbol to filter by.  If empty, all open orders
        are returned.  The symbol is automatically uppercased.

    Returns
    -------
    str
        A human-readable text listing of open orders, or
        ``"No open orders."`` if there are none.
    """
    if _client is None:
        msg = "Client not initialised; call init() first."
        raise RuntimeError(msg)

    # Convert empty string to None; uppercase if provided.
    stripped = symbol.strip()
    effective_symbol: str | None = stripped.upper() if stripped else None

    orders = await _client.get_open_orders(symbol=effective_symbol)

    if not orders:
        return "No open orders."

    lines = [_format_order_line(o) for o in orders]
    return "\n".join(lines)


@mcp.tool()
async def get_order_detail(order_id: int) -> str:
    """Retrieve full details for a single order.

    Parameters
    ----------
    order_id:
        The numeric order identifier.

    Returns
    -------
    str
        A human-readable text block with all order fields including
        fills, average fill price, and commissions.  Returns an error
        message if the order cannot be found.
    """
    if _client is None:
        msg = "Client not initialised; call init() first."
        raise RuntimeError(msg)

    try:
        detail = await _client.get_order_detail(order_id=order_id)
    except Exception:
        return (
            f"Error: Could not retrieve order {order_id}. "
            "Please verify the order ID is correct."
        )

    return _format_order_detail(detail)
