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

import logging
from typing import TYPE_CHECKING, Any

from tiger_mcp.safety.checks import (
    AccountInfo,
    OrderParams,
    PositionInfo,
    SafetyResult,
    run_safety_checks,
)
from tiger_mcp.server import mcp

if TYPE_CHECKING:
    from tiger_mcp.api.tiger_client import TigerClient
    from tiger_mcp.config import Settings
    from tiger_mcp.safety.state import DailyState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level dependencies, set by init() during server startup.
# ---------------------------------------------------------------------------

_client: TigerClient | None = None
_state: DailyState | None = None
_config: Settings | None = None


def init(
    client: TigerClient,
    state: DailyState,
    config: Settings | None = None,
) -> None:
    """Set the module-level TigerClient, DailyState, and config.

    Parameters
    ----------
    client:
        An initialised ``TigerClient`` instance.
    state:
        A ``DailyState`` instance for safety checks on modifications.
    config:
        Optional ``Settings`` with safety-check limits.  When ``None``
        a permissive default (all limits disabled) is used.
    """
    global _client, _state, _config  # noqa: PLW0603
    _client = client
    _state = state
    _config = config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_effective_config() -> Any:
    """Return the module-level config, or a permissive fallback.

    When ``_config`` has not been set (e.g. during testing), returns a
    namespace with all safety limits disabled (set to ``0``).
    """
    if _config is not None:
        return _config

    from types import SimpleNamespace

    return SimpleNamespace(
        max_order_value=0.0,
        daily_loss_limit=0.0,
        max_position_pct=0.0,
    )


def _needs_safety_checks(
    detail: dict[str, Any],
    quantity: int | None,
    limit_price: float | None,
) -> bool:
    """Determine whether safety checks should run for this modification.

    Safety checks run only when a BUY order's risk exposure is increasing:
    - Quantity is increasing (more shares to buy)
    - Limit price is increasing (higher cost per share)

    SELL order modifications and risk-reducing changes (quantity decrease,
    price decrease) skip safety checks.
    """
    action = detail.get("action", "")
    if action != "BUY":
        return False

    original_qty = detail.get("quantity", 0)
    original_price = detail.get("limit_price")

    # Quantity increasing
    if quantity is not None and quantity > original_qty:
        return True

    # Limit price increasing on a BUY order
    if (
        limit_price is not None
        and original_price is not None
        and limit_price > original_price
    ):
        return True

    return False


def _format_safety_result(result: SafetyResult) -> str:
    """Format a SafetyResult into human-readable text.

    Errors are listed under a ``SAFETY ERRORS`` heading and warnings
    under ``SAFETY WARNINGS``.  Returns an empty string when there are
    no issues.
    """
    lines: list[str] = []

    if result.errors:
        lines.append("SAFETY ERRORS:")
        for err in result.errors:
            lines.append(f"  - {err}")

    if result.warnings:
        lines.append("SAFETY WARNINGS:")
        for warn in result.warnings:
            lines.append(f"  - {warn}")

    return "\n".join(lines)


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


async def _run_modify_safety_checks(
    client: Any,
    state: Any,
    detail: dict[str, Any],
    quantity: int | None,
    limit_price: float | None,
) -> SafetyResult:
    """Fetch market data and run full safety checks for an order modification.

    Builds an ``OrderParams`` representing the modified order state and
    runs ``run_safety_checks()`` against it.

    Parameters
    ----------
    client:
        The ``TigerClient`` instance for fetching market/account data.
    state:
        The ``DailyState`` tracker.
    detail:
        Current order detail dict from ``get_order_detail``.
    quantity:
        New quantity (or ``None`` to keep existing).
    limit_price:
        New limit price (or ``None`` to keep existing).

    Returns
    -------
    SafetyResult
        The combined result of all safety checks.
    """
    symbol = detail.get("symbol", "")
    action = detail.get("action", "BUY")
    order_type = detail.get("order_type", "LMT")
    effective_qty = quantity if quantity is not None else detail.get("quantity", 0)
    effective_price = (
        limit_price if limit_price is not None
        else detail.get("limit_price")
    )
    stop_price = detail.get("aux_price")

    # Fetch quote, account, and positions
    quote = await client.get_quote(symbol)
    assets = await client.get_assets()
    positions = await client.get_positions()

    last_price = quote.get("latest_price")

    order_params = OrderParams(
        symbol=symbol,
        action=action,
        quantity=effective_qty,
        order_type=order_type,
        limit_price=effective_price,
        stop_price=stop_price,
        last_price=last_price,
    )
    account_info = AccountInfo(
        cash_balance=assets.get("cash", 0.0),
        net_liquidation=assets.get("net_liquidation", 0.0),
    )
    position_infos = [
        PositionInfo(
            symbol=p.get("symbol", ""),
            quantity=p.get("quantity", 0),
        )
        for p in positions
    ]

    config = _get_effective_config()

    return run_safety_checks(
        order=order_params,
        account=account_info,
        positions=position_infos,
        config=config,
        state=state,
    )


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

    When the modification increases risk on a BUY order (quantity increase
    or limit price increase), full safety checks are run.  If any safety
    error is detected, the modification is blocked.  Safety warnings are
    included in the response but do not prevent modification.

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
    if _client is None or _state is None:
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

    # Run full safety checks if the modification increases risk on a BUY.
    safety_result: SafetyResult | None = None
    if _needs_safety_checks(detail, quantity, limit_price):
        try:
            safety_result = await _run_modify_safety_checks(
                _client, _state, detail, quantity, limit_price,
            )
        except Exception as exc:
            return (
                f"Error: Could not fetch market data for safety checks "
                f"on order {order_id}. {exc}"
            )

        # Block if safety errors are found.
        if not safety_result.passed:
            lines: list[str] = [
                "Modification BLOCKED by safety checks",
                "======================================",
                f"  Order ID: {order_id}",
                f"  Symbol: {detail.get('symbol', 'N/A')}",
                "",
            ]
            safety_text = _format_safety_result(safety_result)
            if safety_text:
                lines.append(safety_text)
            return "\n".join(lines)

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

    # Append safety warnings if any.
    if safety_result is not None and safety_result.warnings:
        lines.append("")
        safety_text = _format_safety_result(safety_result)
        if safety_text:
            lines.append(safety_text)

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
