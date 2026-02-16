"""Pre-trade safety checks for Tiger Brokers MCP server (TASK-006).

Runs six independent checks against every order before submission:
  1. Block short selling
  2. Buying power verification
  3. Maximum order value
  4. Position concentration (warning)
  5. Daily loss limit
  6. Duplicate order detection (warning)

All checks run to completion -- errors and warnings are never
short-circuited so the caller sees every issue at once.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tiger_mcp.config import Settings
from tiger_mcp.safety.state import DailyState

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class SafetyResult:
    """Outcome of the pre-trade safety gate.

    Attributes:
        passed: ``True`` when no blocking errors were found.
        errors: List of human-readable error strings (block the order).
        warnings: List of human-readable warnings (informational only).
    """

    passed: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class OrderParams:
    """Parameters describing an order to be checked.

    Attributes:
        symbol: Ticker symbol (e.g. ``"AAPL"``).
        action: ``"BUY"`` or ``"SELL"``.
        quantity: Number of shares.
        order_type: One of ``MKT``, ``LMT``, ``STP``, ``STP_LMT``, ``TRAIL``.
        limit_price: Limit price for limit orders, or ``None``.
        stop_price: Stop price for stop orders, or ``None``.
        last_price: Last traded price, used for market-order cost estimation.
    """

    symbol: str
    action: str
    quantity: int
    order_type: str
    limit_price: float | None = None
    stop_price: float | None = None
    last_price: float | None = None


@dataclass
class AccountInfo:
    """Pre-fetched account data for safety checks.

    Attributes:
        cash_balance: Available cash in the account.
        net_liquidation: Total account net liquidation value.
    """

    cash_balance: float
    net_liquidation: float


@dataclass
class PositionInfo:
    """Per-symbol position snapshot.

    Attributes:
        symbol: Ticker symbol.
        quantity: Number of shares held.
    """

    symbol: str
    quantity: int


# ---------------------------------------------------------------------------
# Cost estimation helper
# ---------------------------------------------------------------------------

_BUYING_POWER_BUFFER = 1.01  # 1% safety margin for buying power check


def _estimate_price(order: OrderParams) -> float | None:
    """Return the best available price estimate for an order.

    Prefers ``limit_price`` when set; falls back to ``last_price``.
    Returns ``None`` when neither is available.
    """
    if order.limit_price is not None:
        return order.limit_price
    return order.last_price


# ---------------------------------------------------------------------------
# Individual check functions
# ---------------------------------------------------------------------------


def _check_short_selling(
    order: OrderParams,
    positions: list[PositionInfo],
    errors: list[str],
) -> None:
    """Check 1: Block short selling.

    If the action is SELL, verify the account holds enough shares of
    the symbol to cover the order quantity.
    """
    if order.action != "SELL":
        return

    held = 0
    for pos in positions:
        if pos.symbol == order.symbol:
            held = pos.quantity
            break

    if held <= 0:
        errors.append(
            f"Short selling blocked: no position in {order.symbol}"
        )
    elif order.quantity > held:
        errors.append(
            f"Short selling blocked: order quantity {order.quantity} "
            f"exceeds held shares {held} for {order.symbol}"
        )


def _check_buying_power(
    order: OrderParams,
    account: AccountInfo,
    errors: list[str],
) -> None:
    """Check 2: Verify the account has enough cash for a BUY order.

    Estimated cost includes a 1% buffer to account for slippage and
    fees.
    """
    if order.action != "BUY":
        return

    price = _estimate_price(order)
    if price is None:
        return  # Cannot estimate without a price

    cost = order.quantity * price * _BUYING_POWER_BUFFER
    if cost > account.cash_balance:
        errors.append(
            f"Insufficient buying power: estimated cost ${cost:,.2f} "
            f"(incl. 1% buffer) exceeds cash balance ${account.cash_balance:,.2f}"
        )


def _check_max_order_value(
    order: OrderParams,
    config: Settings,
    errors: list[str],
) -> None:
    """Check 3: Ensure order value does not exceed the configured maximum."""
    if config.max_order_value <= 0:
        return  # Disabled

    price = _estimate_price(order)
    if price is None:
        return

    order_value = order.quantity * price
    if order_value > config.max_order_value:
        errors.append(
            f"Max order value exceeded: ${order_value:,.2f} > "
            f"limit ${config.max_order_value:,.2f}"
        )


def _check_position_concentration(
    order: OrderParams,
    account: AccountInfo,
    config: Settings,
    warnings: list[str],
) -> None:
    """Check 4: Warn if the order creates excessive position concentration.

    Fires a *warning* (not an error) when the order value exceeds
    ``max_position_pct * net_liquidation``.
    """
    if config.max_position_pct <= 0:
        return  # Disabled

    price = _estimate_price(order)
    if price is None:
        return

    order_value = order.quantity * price
    limit = config.max_position_pct * account.net_liquidation
    if order_value > limit:
        pct = config.max_position_pct * 100
        warnings.append(
            f"Position concentration warning: order value ${order_value:,.2f} "
            f"exceeds {pct:.1f}% of net liquidation (${limit:,.2f})"
        )


def _check_daily_loss_limit(
    config: Settings,
    state: DailyState,
    errors: list[str],
) -> None:
    """Check 5: Block trading if daily realized losses exceed the limit.

    Triggered when ``get_daily_pnl() < -daily_loss_limit`` (strictly
    less than, so being exactly at the limit does not block).
    """
    if config.daily_loss_limit <= 0:
        return  # Disabled

    daily_pnl = state.get_daily_pnl()
    if daily_pnl < -config.daily_loss_limit:
        errors.append(
            f"Daily loss limit exceeded: realized P&L ${daily_pnl:,.2f} "
            f"breaches -${config.daily_loss_limit:,.2f} limit"
        )


def _check_duplicate_order(
    order: OrderParams,
    state: DailyState,
    warnings: list[str],
) -> None:
    """Check 6: Warn if an identical order was submitted recently.

    Uses ``DailyState.make_fingerprint`` and ``has_recent_order`` to
    detect potential duplicates within the default time window.
    """
    fingerprint = DailyState.make_fingerprint(
        symbol=order.symbol,
        action=order.action,
        quantity=order.quantity,
        order_type=order.order_type,
        limit_price=order.limit_price,
    )
    if state.has_recent_order(fingerprint):
        warnings.append(
            f"Duplicate order detected: a similar {order.action} order "
            f"for {order.quantity} {order.symbol} was submitted recently"
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_safety_checks(
    order: OrderParams,
    account: AccountInfo,
    positions: list[PositionInfo],
    config: Settings,
    state: DailyState,
) -> SafetyResult:
    """Run all pre-trade safety checks and return the combined result.

    Every check is executed regardless of earlier failures so that the
    caller receives the complete list of issues.

    Args:
        order: The order to validate.
        account: Current account balances.
        positions: Current portfolio positions.
        config: Server configuration with safety limits.
        state: Daily state tracker for P&L and dedup.

    Returns:
        A ``SafetyResult`` with ``passed=True`` only when no errors
        were found.
    """
    errors: list[str] = []
    warnings: list[str] = []

    # 1. Block short selling
    _check_short_selling(order, positions, errors)

    # 2. Buying power check
    _check_buying_power(order, account, errors)

    # 3. Max order value
    _check_max_order_value(order, config, errors)

    # 4. Position concentration (warning)
    _check_position_concentration(order, account, config, warnings)

    # 5. Daily loss limit
    _check_daily_loss_limit(config, state, errors)

    # 6. Duplicate detection (warning)
    _check_duplicate_order(order, state, warnings)

    return SafetyResult(
        passed=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )
