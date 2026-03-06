"""MCP tools for OCA (One-Cancels-All) and bracket order execution.

Provides two tools:

- ``place_oca_order``       -- submit an OCA SELL order after running all
  safety checks.
- ``place_bracket_order``   -- submit a bracket BUY order after running all
  safety checks.

Client and state access pattern
-------------------------------
Module-level ``_client``, ``_state``, and ``_config``
references are set via the ``init(client, state, config)``
function during server startup.
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
from tiger_mcp.tools.orders._helpers import (
    fetch_safety_data,
    format_safety_result,
    get_effective_config,
)

if TYPE_CHECKING:
    from tiger_mcp.api.tiger_client import TigerClient
    from tiger_mcp.config import Settings

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
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_oca_params(
    symbol: str,
    quantity: int,
    tp_limit_price: float,
    sl_stop_price: float,
    sl_limit_price: float,
) -> str | None:
    """Validate OCA order parameters.

    Returns an error string when validation fails, or ``None`` when all
    parameters are acceptable.
    """
    if not symbol or not symbol.strip():
        return "Invalid symbol: symbol must be non-empty."

    if symbol != symbol.upper():
        return "Invalid symbol: symbol must be uppercase."

    if quantity <= 0:
        return f"Invalid quantity: {quantity}. Must be a positive integer."

    if tp_limit_price <= 0:
        return "Invalid price: tp_limit_price must be greater than 0."

    if sl_stop_price <= 0:
        return "Invalid price: sl_stop_price must be greater than 0."

    if sl_limit_price <= 0:
        return "Invalid price: sl_limit_price must be greater than 0."

    if tp_limit_price <= sl_stop_price:
        return (
            "Invalid price relationship: take-profit price "
            f"(${tp_limit_price:,.2f}) must be greater than "
            f"stop-loss stop price (${sl_stop_price:,.2f})."
        )

    if sl_stop_price < sl_limit_price:
        return (
            "Invalid price relationship: sl_stop_price "
            f"(${sl_stop_price:,.2f}) must be >= "
            f"sl_limit_price (${sl_limit_price:,.2f})."
        )

    return None


def _validate_bracket_params(
    symbol: str,
    quantity: int,
    entry_limit_price: float,
    tp_limit_price: float,
    sl_stop_price: float,
    sl_limit_price: float,
) -> str | None:
    """Validate bracket order parameters.

    Returns an error string when validation fails, or ``None`` when all
    parameters are acceptable.
    """
    if not symbol or not symbol.strip():
        return "Invalid symbol: symbol must be non-empty."

    if symbol != symbol.upper():
        return "Invalid symbol: symbol must be uppercase."

    if quantity <= 0:
        return f"Invalid quantity: {quantity}. Must be a positive integer."

    if entry_limit_price <= 0:
        return "Invalid price: entry_limit_price must be greater than 0."

    if tp_limit_price <= 0:
        return "Invalid price: tp_limit_price must be greater than 0."

    if sl_stop_price <= 0:
        return "Invalid price: sl_stop_price must be greater than 0."

    if sl_limit_price <= 0:
        return "Invalid price: sl_limit_price must be greater than 0."

    if tp_limit_price <= entry_limit_price:
        return (
            "Invalid price relationship: take-profit price "
            f"(${tp_limit_price:,.2f}) must be greater than "
            f"entry limit price (${entry_limit_price:,.2f})."
        )

    if entry_limit_price <= sl_stop_price:
        return (
            "Invalid price relationship: entry limit price "
            f"(${entry_limit_price:,.2f}) must be greater than "
            f"stop-loss stop price (${sl_stop_price:,.2f})."
        )

    if sl_stop_price < sl_limit_price:
        return (
            "Invalid price relationship: sl_stop_price "
            f"(${sl_stop_price:,.2f}) must be >= "
            f"sl_limit_price (${sl_limit_price:,.2f})."
        )

    return None


# ---------------------------------------------------------------------------
# Safety helpers
# ---------------------------------------------------------------------------


def _check_position(
    positions: list[dict[str, Any]],
    symbol: str,
    quantity: int,
) -> str | None:
    """Check that a position exists for symbol with sufficient shares.

    Returns an error string if the position check fails, or ``None``
    if the position is adequate.
    """
    held = 0
    for pos in positions:
        if pos.get("symbol") == symbol:
            held = pos.get("quantity", 0)
            break

    if held <= 0:
        return (
            f"No position found for {symbol}. "
            "OCA orders require an existing long position."
        )

    if quantity > held:
        return f"OCA quantity {quantity} exceeds held shares {held} for {symbol}."

    return None


def _build_and_run_safety(
    state: DailyState,
    assets: dict[str, Any],
    positions: list[dict[str, Any]],
    symbol: str,
    action: str,
    quantity: int,
    order_type: str,
    limit_price: float | None,
) -> SafetyResult:
    """Run all safety checks using pre-fetched data."""
    order_params = OrderParams(
        symbol=symbol,
        action=action,
        quantity=quantity,
        order_type=order_type,
        limit_price=limit_price,
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

    config = get_effective_config(_config)

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
async def place_oca_order(
    symbol: str,
    quantity: int,
    tp_limit_price: float,
    sl_stop_price: float,
    sl_limit_price: float,
) -> str:
    """Place an OCA (One-Cancels-All) SELL order after running all safety checks.

    Creates a pair of SELL legs -- a take-profit limit order and a
    stop-loss stop-limit order -- that protect an existing long position.
    When one leg fills, the other is automatically cancelled.

    Validates parameters, checks that a sufficient position exists,
    runs all safety checks, and submits the order.  If any safety
    *error* is detected the order is NOT placed.  Safety *warnings*
    are included in the response but do not block submission.

    Parameters
    ----------
    symbol:
        Ticker symbol (e.g. ``"AAPL"``). Must be uppercase.
    quantity:
        Number of shares. Must be a positive integer and <= held shares.
    tp_limit_price:
        Take-profit limit price. Must be > sl_stop_price.
    sl_stop_price:
        Stop-loss trigger price. Must be >= sl_limit_price.
    sl_limit_price:
        Stop-loss limit price (execution floor).

    Returns
    -------
    str
        On success: order_id, sub_ids, and any warnings.
        On safety error: error messages explaining why the order was
        blocked.
    """
    if _client is None or _state is None:
        return "Error: module not initialised. Call init() first."

    # 1. Validate parameters
    validation_error = _validate_oca_params(
        symbol,
        quantity,
        tp_limit_price,
        sl_stop_price,
        sl_limit_price,
    )
    if validation_error:
        return f"Error: {validation_error}"

    # 2. Fetch data and check position
    try:
        assets, positions = await fetch_safety_data(_client)
    except Exception as exc:
        return f"Error fetching market data: {exc}"

    position_error = _check_position(positions, symbol, quantity)
    if position_error:
        return f"Error: {position_error}"

    # 3. Run safety checks
    try:
        safety_result = _build_and_run_safety(
            _state,
            assets,
            positions,
            symbol,
            "SELL",
            quantity,
            "OCA",
            tp_limit_price,
        )
    except Exception as exc:
        return f"Error running safety checks: {exc}"

    # 4. If safety errors exist, block the order
    if not safety_result.passed:
        lines: list[str] = [
            "OCA Order BLOCKED by safety checks",
            "===================================",
        ]
        safety_text = format_safety_result(safety_result)
        if safety_text:
            lines.append("")
            lines.append(safety_text)
        return "\n".join(lines)

    # 5. Place the order
    try:
        order_result = await _client.place_oca_order(
            symbol=symbol,
            quantity=quantity,
            tp_limit_price=tp_limit_price,
            sl_stop_price=sl_stop_price,
            sl_limit_price=sl_limit_price,
        )
    except Exception as exc:
        return f"Error placing OCA order: {exc}"

    # 6. Record fingerprint in DailyState
    fingerprint = DailyState.make_fingerprint(
        symbol=symbol,
        action="SELL",
        quantity=quantity,
        order_type="OCA",
        limit_price=sl_limit_price,
    )
    _state.record_order(fingerprint)

    order_id = order_result.get("order_id", "N/A")
    sub_ids = order_result.get("sub_ids", [])

    # 7. Format success response
    lines = [
        "OCA Order Placed Successfully",
        "=============================",
        f"  Order ID:    {order_id}",
        f"  Sub IDs:     {', '.join(sub_ids) if sub_ids else 'N/A'}",
        f"  Symbol:      {symbol}",
        "  Action:      SELL",
        f"  Quantity:    {quantity}",
    ]

    safety_text = format_safety_result(safety_result)
    if safety_text:
        lines.append("")
        lines.append(safety_text)

    return "\n".join(lines)


@mcp.tool()
async def place_bracket_order(
    symbol: str,
    quantity: int,
    entry_limit_price: float,
    tp_limit_price: float,
    sl_stop_price: float,
    sl_limit_price: float,
) -> str:
    """Place a bracket BUY order after running all safety checks.

    Creates a BUY entry order with attached take-profit and stop-loss
    legs.  When the entry fills, the TP and SL legs become active as
    an OCA pair.

    Validates parameters, runs all safety checks, and submits the
    order.  If any safety *error* is detected the order is NOT placed.
    Safety *warnings* are included in the response but do not block
    submission.

    Parameters
    ----------
    symbol:
        Ticker symbol (e.g. ``"AAPL"``). Must be uppercase.
    quantity:
        Number of shares. Must be a positive integer.
    entry_limit_price:
        Entry limit price for the BUY order.
    tp_limit_price:
        Take-profit limit price. Must be > entry_limit_price.
    sl_stop_price:
        Stop-loss trigger price. Must be < entry_limit_price.
    sl_limit_price:
        Stop-loss limit price (execution floor). Must be <= sl_stop_price.

    Returns
    -------
    str
        On success: order_id, sub_ids, and any warnings.
        On safety error: error messages explaining why the order was
        blocked.
    """
    if _client is None or _state is None:
        return "Error: module not initialised. Call init() first."

    # 1. Validate parameters
    validation_error = _validate_bracket_params(
        symbol,
        quantity,
        entry_limit_price,
        tp_limit_price,
        sl_stop_price,
        sl_limit_price,
    )
    if validation_error:
        return f"Error: {validation_error}"

    # 2. Fetch data and run safety checks
    try:
        assets, positions = await fetch_safety_data(_client)
    except Exception as exc:
        return f"Error fetching market data: {exc}"

    try:
        safety_result = _build_and_run_safety(
            _state,
            assets,
            positions,
            symbol,
            "BUY",
            quantity,
            "BRACKET",
            entry_limit_price,
        )
    except Exception as exc:
        return f"Error running safety checks: {exc}"

    # 3. If safety errors exist, block the order
    if not safety_result.passed:
        lines: list[str] = [
            "Bracket Order BLOCKED by safety checks",
            "=======================================",
        ]
        safety_text = format_safety_result(safety_result)
        if safety_text:
            lines.append("")
            lines.append(safety_text)
        return "\n".join(lines)

    # 4. Place the order
    try:
        order_result = await _client.place_bracket_order(
            symbol=symbol,
            quantity=quantity,
            entry_limit_price=entry_limit_price,
            tp_limit_price=tp_limit_price,
            sl_stop_price=sl_stop_price,
            sl_limit_price=sl_limit_price,
        )
    except Exception as exc:
        return f"Error placing bracket order: {exc}"

    # 5. Record fingerprint in DailyState
    fingerprint = DailyState.make_fingerprint(
        symbol=symbol,
        action="BUY",
        quantity=quantity,
        order_type="BRACKET",
        limit_price=entry_limit_price,
    )
    _state.record_order(fingerprint)

    order_id = order_result.get("order_id", "N/A")
    sub_ids = order_result.get("sub_ids", [])

    # 6. Format success response
    lines = [
        "Bracket Order Placed Successfully",
        "=================================",
        f"  Order ID:    {order_id}",
        f"  Sub IDs:     {', '.join(sub_ids) if sub_ids else 'N/A'}",
        f"  Symbol:      {symbol}",
        "  Action:      BUY",
        f"  Quantity:    {quantity}",
    ]

    safety_text = format_safety_result(safety_result)
    if safety_text:
        lines.append("")
        lines.append(safety_text)

    return "\n".join(lines)
