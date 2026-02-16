"""MCP tools for order execution (preview and place).

Provides two tools:

- ``preview_stock_order`` -- dry-run an order to see estimated cost,
  commission, and safety-check results without submitting it.
- ``place_stock_order``   -- submit an order after running all safety
  checks.  Blocked if any safety *error* is detected; warnings are
  surfaced but do not prevent submission.

Client and state access pattern
-------------------------------
Module-level ``_client``, ``_state``, and ``_config`` references are
set via the ``init(client, state, config)`` function during server
startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tiger_mcp.safety.checks import (
    AccountInfo,
    OrderParams,
    PositionInfo,
    SafetyResult,
    run_safety_checks,
)
from tiger_mcp.safety.state import DailyState
from tiger_mcp.server import mcp

if TYPE_CHECKING:
    from tiger_mcp.api.tiger_client import TigerClient
    from tiger_mcp.config import Settings

# ---------------------------------------------------------------------------
# Module-level dependencies, set by init() during server startup.
# ---------------------------------------------------------------------------

_client: TigerClient | None = None
_state: DailyState | None = None
_config: Settings | None = None

# ---------------------------------------------------------------------------
# Valid values for user-facing parameters.
# ---------------------------------------------------------------------------

_VALID_ACTIONS = frozenset({"BUY", "SELL"})
_VALID_ORDER_TYPES = frozenset(
    {"MKT", "LMT", "STP", "STP_LMT", "TRAIL"},
)

# Map user-facing order type abbreviations to the strings expected by
# TigerClient._build_order.
_ORDER_TYPE_MAP: dict[str, str] = {
    "MKT": "market",
    "LMT": "limit",
    "STP": "stop",
    "STP_LMT": "stop_limit",
    "TRAIL": "trail",
}


def init(
    client: TigerClient,
    state: DailyState,
    config: Settings | None = None,
) -> None:
    """Set the module-level dependencies.

    Called once during server initialisation so that tool functions can
    access the shared client, state, and configuration.

    Parameters
    ----------
    client:
        An initialised ``TigerClient`` instance.
    state:
        The ``DailyState`` tracker for fingerprint recording.
    config:
        Optional ``Settings`` with safety-check limits.  When ``None``
        a permissive default (all limits disabled) is used.
    """
    global _client, _state, _config  # noqa: PLW0603
    _client = client
    _state = state
    _config = config


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _validate_order_params(
    symbol: str,
    action: str,
    quantity: int,
    order_type: str,
    limit_price: float | None,
    stop_price: float | None,
) -> str | None:
    """Validate order parameters.

    Returns an error string when validation fails, or ``None`` when all
    parameters are acceptable.

    Checks:
    - symbol is non-empty and uppercase
    - action is BUY or SELL
    - quantity is a positive integer
    - order_type is one of MKT, LMT, STP, STP_LMT, TRAIL
    - limit_price is required for LMT and STP_LMT
    - stop_price is required for STP and STP_LMT
    """
    if not symbol or not symbol.strip():
        return "Invalid symbol: symbol must be non-empty."

    if symbol != symbol.upper():
        return "Invalid symbol: symbol must be uppercase."

    if action not in _VALID_ACTIONS:
        return (
            f"Invalid action: {action!r}. Must be BUY or SELL."
        )

    if quantity <= 0:
        return (
            f"Invalid quantity: {quantity}. "
            "Must be a positive integer."
        )

    if order_type not in _VALID_ORDER_TYPES:
        return (
            f"Invalid order_type: {order_type!r}. Must be one "
            f"of: {', '.join(sorted(_VALID_ORDER_TYPES))}."
        )

    if order_type in ("LMT", "STP_LMT") and limit_price is None:
        return (
            f"limit_price is required for {order_type} orders."
        )

    if order_type in ("STP", "STP_LMT") and stop_price is None:
        return (
            f"stop_price is required for {order_type} orders."
        )

    return None


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


async def _fetch_safety_data(
    client: TigerClient,
    symbol: str,
) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """Fetch quote, account, and position data from TigerClient.

    Returns
    -------
    tuple
        ``(quote_data, account_data, positions_data)``
    """
    quote = await client.get_quote(symbol)
    assets = await client.get_assets()
    positions = await client.get_positions()
    return quote, assets, positions


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


async def _build_and_run_safety(
    client: TigerClient,
    state: DailyState,
    symbol: str,
    action: str,
    quantity: int,
    order_type: str,
    limit_price: float | None,
    stop_price: float | None,
) -> tuple[SafetyResult, float | None]:
    """Fetch data and run all safety checks.

    Returns
    -------
    tuple
        ``(safety_result, last_price)`` where ``last_price`` is the
        latest quote price (may be ``None``).
    """
    quote, assets, positions = await _fetch_safety_data(
        client, symbol,
    )
    last_price = quote.get("latest_price")

    order_params = OrderParams(
        symbol=symbol,
        action=action,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
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

    safety_result = run_safety_checks(
        order=order_params,
        account=account_info,
        positions=position_infos,
        config=config,
        state=state,
    )

    return safety_result, last_price


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def preview_stock_order(
    symbol: str,
    action: str,
    quantity: int,
    order_type: str,
    limit_price: float | None = None,
    stop_price: float | None = None,
) -> str:
    """Preview a stock order without executing it.

    Validates parameters, runs all six safety checks, and fetches a
    cost estimate from the broker.  The order is NOT submitted.

    Parameters
    ----------
    symbol:
        Ticker symbol (e.g. ``"AAPL"``). Must be uppercase.
    action:
        ``"BUY"`` or ``"SELL"``.
    quantity:
        Number of shares. Must be a positive integer.
    order_type:
        One of ``MKT``, ``LMT``, ``STP``, ``STP_LMT``, ``TRAIL``.
    limit_price:
        Required for ``LMT`` and ``STP_LMT`` orders.
    stop_price:
        Required for ``STP`` and ``STP_LMT`` orders.

    Returns
    -------
    str
        Human-readable preview with estimated cost, commission, and
        any safety check results (errors and warnings).
    """
    if _client is None or _state is None:
        return (
            "Error: module not initialised. Call init() first."
        )

    # 1. Validate parameters
    validation_error = _validate_order_params(
        symbol, action, quantity, order_type,
        limit_price, stop_price,
    )
    if validation_error:
        return f"Error: {validation_error}"

    # 2. Fetch data and run safety checks
    try:
        safety_result, last_price = await _build_and_run_safety(
            _client, _state, symbol, action, quantity,
            order_type, limit_price, stop_price,
        )
    except Exception as exc:
        return f"Error fetching market data: {exc}"

    # 3. Fetch cost preview from broker
    client_order_type = _ORDER_TYPE_MAP.get(
        order_type, order_type,
    )
    try:
        preview = await _client.preview_order(
            symbol=symbol,
            action=action,
            quantity=quantity,
            order_type=client_order_type,
            limit_price=limit_price,
            stop_price=stop_price,
        )
    except Exception as exc:
        return f"Error previewing order: {exc}"

    # 4. Format response
    estimated_cost = preview.get("estimated_cost", "N/A")
    commission = preview.get("commission", "N/A")

    lines: list[str] = [
        "Order Preview",
        "=============",
        f"  Symbol:          {symbol}",
        f"  Action:          {action}",
        f"  Quantity:        {quantity}",
        f"  Order Type:      {order_type}",
    ]
    if limit_price is not None:
        lines.append(f"  Limit Price:     ${limit_price:,.2f}")
    if stop_price is not None:
        lines.append(f"  Stop Price:      ${stop_price:,.2f}")
    if last_price is not None:
        lines.append(f"  Last Price:      ${last_price:,.2f}")
    lines.append("")

    if isinstance(estimated_cost, (int, float)):
        lines.append(
            f"  Estimated Cost:  ${estimated_cost:,.2f}",
        )
    else:
        lines.append(f"  Estimated Cost:  {estimated_cost}")

    if isinstance(commission, (int, float)):
        lines.append(f"  Commission:      ${commission:,.2f}")
    else:
        lines.append(f"  Commission:      {commission}")

    safety_text = _format_safety_result(safety_result)
    if safety_text:
        lines.append("")
        lines.append(safety_text)

    return "\n".join(lines)


@mcp.tool()
async def place_stock_order(
    symbol: str,
    action: str,
    quantity: int,
    order_type: str,
    limit_price: float | None = None,
    stop_price: float | None = None,
) -> str:
    """Place a stock order after running all safety checks.

    Validates parameters, runs all six safety checks, and submits the
    order to the broker.  If any safety *error* is detected the order
    is NOT placed.  Safety *warnings* are included in the response but
    do not block submission.

    Parameters
    ----------
    symbol:
        Ticker symbol (e.g. ``"AAPL"``). Must be uppercase.
    action:
        ``"BUY"`` or ``"SELL"``.
    quantity:
        Number of shares. Must be a positive integer.
    order_type:
        One of ``MKT``, ``LMT``, ``STP``, ``STP_LMT``, ``TRAIL``.
    limit_price:
        Required for ``LMT`` and ``STP_LMT`` orders.
    stop_price:
        Required for ``STP`` and ``STP_LMT`` orders.

    Returns
    -------
    str
        On success: order_id, status, fill details, and any warnings.
        On safety error: error messages explaining why the order was
        blocked.
    """
    if _client is None or _state is None:
        return (
            "Error: module not initialised. Call init() first."
        )

    # 1. Validate parameters
    validation_error = _validate_order_params(
        symbol, action, quantity, order_type,
        limit_price, stop_price,
    )
    if validation_error:
        return f"Error: {validation_error}"

    # 2. Fetch data and run safety checks
    try:
        safety_result, _ = await _build_and_run_safety(
            _client, _state, symbol, action, quantity,
            order_type, limit_price, stop_price,
        )
    except Exception as exc:
        return f"Error fetching market data: {exc}"

    # 3. If safety errors exist, block the order
    if not safety_result.passed:
        lines: list[str] = [
            "Order BLOCKED by safety checks",
            "==============================",
        ]
        safety_text = _format_safety_result(safety_result)
        if safety_text:
            lines.append("")
            lines.append(safety_text)
        return "\n".join(lines)

    # 4. Place the order
    client_order_type = _ORDER_TYPE_MAP.get(
        order_type, order_type,
    )
    try:
        order_result = await _client.place_order(
            symbol=symbol,
            action=action,
            quantity=quantity,
            order_type=client_order_type,
            limit_price=limit_price,
            stop_price=stop_price,
        )
    except Exception as exc:
        return f"Error placing order: {exc}"

    # 5. Record fingerprint in DailyState
    fingerprint = DailyState.make_fingerprint(
        symbol=symbol,
        action=action,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
    )
    _state.record_order(fingerprint)

    # 6. Format success response
    order_id = order_result.get("order_id", "N/A")
    o_symbol = order_result.get("symbol", symbol)
    o_action = order_result.get("action", action)
    o_qty = order_result.get("quantity", quantity)
    o_type = order_result.get("order_type", order_type)

    lines = [
        "Order Placed Successfully",
        "=========================",
        f"  Order ID:    {order_id}",
        f"  Symbol:      {o_symbol}",
        f"  Action:      {o_action}",
        f"  Quantity:    {o_qty}",
        f"  Order Type:  {o_type}",
    ]

    safety_text = _format_safety_result(safety_result)
    if safety_text:
        lines.append("")
        lines.append(safety_text)

    return "\n".join(lines)
