"""Order management MCP tools for the Tiger Brokers server.

Provides three tools for managing existing orders:

- ``modify_order``      -- modify quantity, limit price, or stop price
- ``cancel_order``      -- cancel a single order by ID
- ``cancel_all_orders`` -- cancel all open orders at once

The tools require a ``TigerClient`` instance and a ``DailyState`` instance,
which are injected via the module-level ``init()`` function during server
startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tiger_mcp.server import mcp

if TYPE_CHECKING:
    from tiger_mcp.api.tiger_client import TigerClient
    from tiger_mcp.safety.state import DailyState

# ---------------------------------------------------------------------------
# Module-level dependencies, set by init() during server startup.
# ---------------------------------------------------------------------------

_client: TigerClient | None = None
_state: DailyState | None = None


def init(client: TigerClient, state: DailyState) -> None:
    """Set the module-level TigerClient and DailyState used by management tools.

    Parameters
    ----------
    client:
        An initialised ``TigerClient`` instance.
    state:
        A ``DailyState`` instance for safety checks on modifications.
    """
    global _client, _state  # noqa: PLW0603
    _client = client
    _state = state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_BUYING_POWER_BUFFER = 1.01  # 1% safety margin


async def _check_buying_power_for_increase(
    client: Any,
    detail: dict[str, Any],
    new_quantity: int,
) -> str | None:
    """Check buying power when order quantity is increased.

    Returns a warning string if the additional cost exceeds available
    cash, or ``None`` if buying power is sufficient.

    Only applies to BUY orders with a limit price.  The check uses a
    1% buffer on the estimated additional cost.
    """
    original_qty = detail.get("quantity", 0)
    if new_quantity <= original_qty:
        return None

    action = detail.get("action", "")
    if action != "BUY":
        return None

    price = detail.get("limit_price")
    if price is None:
        return None

    additional_qty = new_quantity - original_qty
    additional_cost = additional_qty * price * _BUYING_POWER_BUFFER

    try:
        assets = await client.get_assets()
    except Exception:
        return (
            "Warning: Could not verify buying power. "
            "Proceeding with modification."
        )

    cash = assets.get("cash", 0.0)
    if additional_cost > cash:
        return (
            f"Warning: Insufficient buying power for quantity increase. "
            f"Additional cost ${additional_cost:,.2f} "
            f"(incl. 1% buffer) exceeds cash ${cash:,.2f}."
        )

    return None


def _format_order_summary(detail: dict[str, Any]) -> str:
    """Format an order detail dict into a concise summary string."""
    lines: list[str] = []

    field_labels = [
        ("order_id", "Order ID"),
        ("symbol", "Symbol"),
        ("action", "Action"),
        ("order_type", "Order Type"),
        ("quantity", "Quantity"),
        ("filled", "Filled"),
        ("limit_price", "Limit Price"),
        ("aux_price", "Stop Price"),
        ("status", "Status"),
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
async def modify_order(
    order_id: int,
    quantity: int | None = None,
    limit_price: float | None = None,
    stop_price: float | None = None,
) -> str:
    """Modify an existing order's quantity, limit price, or stop price.

    At least one modification parameter must be provided.  Fetches the
    current order to validate it exists and is modifiable before applying
    changes.

    Parameters
    ----------
    order_id:
        The numeric order identifier to modify.
    quantity:
        New order quantity (number of shares).  Pass ``None`` to leave
        unchanged.
    limit_price:
        New limit price.  Pass ``None`` to leave unchanged.
    stop_price:
        New stop price.  Pass ``None`` to leave unchanged.

    Returns
    -------
    str
        A human-readable confirmation with updated order details, or an
        error message if the modification fails.
    """
    if _client is None:
        return "Error: TigerClient is not initialized. Server setup incomplete."

    # Validate at least one modification parameter is provided.
    if quantity is None and limit_price is None and stop_price is None:
        return (
            "Error: No modification parameters provided. "
            "Specify at least one of: quantity, limit_price, stop_price."
        )

    # Fetch current order details to validate it exists and is modifiable.
    try:
        detail: dict[str, Any] = await _client.get_order_detail(
            order_id=order_id,
        )
    except Exception:
        return (
            f"Error: Could not retrieve order {order_id}. "
            "Please verify the order ID is correct."
        )

    # Run buying power check if quantity is increased.
    warnings: list[str] = []
    if quantity is not None:
        bp_warning = await _check_buying_power_for_increase(
            _client, detail, quantity,
        )
        if bp_warning is not None:
            warnings.append(bp_warning)

    # Apply the modification.
    try:
        await _client.modify_order(
            order_id=order_id,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=stop_price,
        )
    except Exception:
        return (
            f"Error: Failed to modify order {order_id}. "
            "The order may no longer be modifiable."
        )

    # Build response with order details and modification summary.
    modifications: list[str] = []
    if quantity is not None:
        modifications.append(f"quantity={quantity}")
    if limit_price is not None:
        modifications.append(f"limit_price={limit_price}")
    if stop_price is not None:
        modifications.append(f"stop_price={stop_price}")

    symbol = detail.get("symbol", "N/A")
    mod_str = ", ".join(modifications)

    lines = [
        "Order Modified Successfully",
        "===========================",
        f"  Order ID: {order_id}",
        f"  Symbol: {symbol}",
        f"  Changes: {mod_str}",
        "",
        "Original Order:",
        _format_order_summary(detail),
    ]

    if warnings:
        lines.append("")
        for warning in warnings:
            lines.append(warning)

    return "\n".join(lines)


@mcp.tool()
async def cancel_order(order_id: int) -> str:
    """Cancel a single order by its ID.

    Validates the order exists by fetching its detail before attempting
    cancellation.

    Parameters
    ----------
    order_id:
        The numeric order identifier to cancel.

    Returns
    -------
    str
        A human-readable cancellation confirmation with order details,
        or an error message if cancellation fails.
    """
    if _client is None:
        return "Error: TigerClient is not initialized. Server setup incomplete."

    # Fetch order detail to validate it exists and is cancellable.
    try:
        detail: dict[str, Any] = await _client.get_order_detail(
            order_id=order_id,
        )
    except Exception:
        return (
            f"Error: Could not retrieve order {order_id}. "
            "Please verify the order ID is correct."
        )

    # Cancel the order.
    try:
        await _client.cancel_order(order_id=order_id)
    except Exception:
        return (
            f"Error: Failed to cancel order {order_id}. "
            "The order may already be cancelled or filled."
        )

    symbol = detail.get("symbol", "N/A")
    action = detail.get("action", "N/A")
    quantity = detail.get("quantity", "N/A")
    order_type = detail.get("order_type", "N/A")

    lines = [
        "Order Cancelled Successfully",
        "============================",
        f"  Order ID: {order_id}",
        f"  Symbol: {symbol}",
        f"  Action: {action}",
        f"  Quantity: {quantity}",
        f"  Order Type: {order_type}",
    ]
    return "\n".join(lines)


@mcp.tool()
async def cancel_all_orders() -> str:
    """Cancel all open orders.

    Returns the count and IDs of cancelled orders, or a message if
    there are no open orders to cancel.

    Returns
    -------
    str
        A human-readable summary of cancelled orders, or
        ``"No open orders to cancel."`` if there are none.
    """
    if _client is None:
        return "Error: TigerClient is not initialized. Server setup incomplete."

    try:
        results: list[dict[str, Any]] = await _client.cancel_all_orders()
    except Exception:
        return "Error: Failed to cancel orders. Please try again."

    if not results:
        return "No open orders to cancel."

    order_ids = [str(r.get("order_id", "N/A")) for r in results]
    count = len(results)

    lines = [
        "All Orders Cancelled",
        "====================",
        f"  Cancelled: {count} order(s)",
        f"  Order IDs: {', '.join(order_ids)}",
    ]
    return "\n".join(lines)
