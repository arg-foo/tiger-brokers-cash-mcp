"""Account MCP tools for the Tiger Brokers server.

Provides four tools for querying account-level information:

- ``get_account_summary`` -- cash balance, buying power, P&L, NLV
- ``get_buying_power``    -- focused buying power with cash context
- ``get_positions``       -- current holdings with unrealized P&L
- ``get_transaction_history`` -- execution history (fills)

The tools require a ``TigerClient`` instance, which is injected via the
module-level ``init()`` function during server startup.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tiger_mcp.server import mcp

if TYPE_CHECKING:
    from tiger_mcp.api.tiger_client import TigerClient

# ---------------------------------------------------------------------------
# Module-level client reference, set by init() during server startup.
# ---------------------------------------------------------------------------

_client: TigerClient | None = None


def init(client: TigerClient) -> None:
    """Set the module-level TigerClient used by all account tools.

    Parameters
    ----------
    client:
        An initialised ``TigerClient`` instance.
    """
    global _client  # noqa: PLW0603
    _client = client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_currency(value: float) -> str:
    """Format a float as US-dollar currency with 2 decimal places.

    Negative values are rendered as ``-$1,234.56``.
    """
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def _check_client() -> str | None:
    """Return an error message if the client is not initialized, else None."""
    if _client is None:
        return "Error: TigerClient is not initialized. Server setup incomplete."
    return None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_account_summary() -> str:
    """Get account summary with cash, buying power, P&L, and NLV.

    Returns a formatted text overview of the account's financial status.
    """
    err = _check_client()
    if err:
        return err

    try:
        assets: dict[str, Any] = await _client.get_assets()  # type: ignore[union-attr]
    except Exception as exc:
        return f"Error retrieving account summary: {exc}"

    cash = assets.get("cash", 0.0)
    buying_power = assets.get("buying_power", 0.0)
    realized_pnl = assets.get("realized_pnl", 0.0)
    unrealized_pnl = assets.get("unrealized_pnl", 0.0)
    net_liquidation = assets.get("net_liquidation", 0.0)

    lines = [
        "Account Summary",
        "===============",
        f"  Cash Balance:       {_fmt_currency(cash)}",
        f"  Buying Power:       {_fmt_currency(buying_power)}",
        f"  Realized P&L:       {_fmt_currency(realized_pnl)}",
        f"  Unrealized P&L:     {_fmt_currency(unrealized_pnl)}",
        f"  Net Liquidation:    {_fmt_currency(net_liquidation)}",
    ]
    return "\n".join(lines)


@mcp.tool()
async def get_buying_power() -> str:
    """Get available buying power with cash balance context.

    Returns a focused view of available funds for placing new orders.
    """
    err = _check_client()
    if err:
        return err

    try:
        assets: dict[str, Any] = await _client.get_assets()  # type: ignore[union-attr]
    except Exception as exc:
        return f"Error retrieving buying power: {exc}"

    cash = assets.get("cash", 0.0)
    buying_power = assets.get("buying_power", 0.0)

    lines = [
        "Buying Power",
        "============",
        f"  Available Buying Power:  {_fmt_currency(buying_power)}",
        f"  Cash Balance:            {_fmt_currency(cash)}",
    ]
    return "\n".join(lines)


@mcp.tool()
async def get_positions() -> str:
    """Get current portfolio holdings with unrealized P&L.

    Returns details for each position: symbol, quantity, average cost,
    market value, unrealized P&L, and P&L percentage.  Returns
    'No positions found.' when the portfolio is empty.
    """
    err = _check_client()
    if err:
        return err

    try:
        positions: list[dict[str, Any]] = await _client.get_positions()  # type: ignore[union-attr]
    except Exception as exc:
        return f"Error retrieving positions: {exc}"

    if not positions:
        return "No positions found."

    lines: list[str] = ["Current Positions", "================="]
    for pos in positions:
        symbol = pos.get("symbol", "N/A")
        quantity = pos.get("quantity", 0)
        avg_cost = pos.get("average_cost", 0.0)
        market_value = pos.get("market_value", 0.0)
        unrealized_pnl = pos.get("unrealized_pnl", 0.0)

        # Calculate P&L percentage based on cost basis
        cost_basis = avg_cost * quantity if avg_cost and quantity else 0.0
        pnl_pct = (unrealized_pnl / cost_basis * 100) if cost_basis != 0.0 else 0.0

        lines.append("")
        lines.append(f"  {symbol}")
        lines.append(f"    Quantity:        {quantity}")
        lines.append(f"    Avg Cost:        {_fmt_currency(avg_cost)}")
        lines.append(f"    Market Value:    {_fmt_currency(market_value)}")
        pnl_str = _fmt_currency(unrealized_pnl)
        lines.append(f"    Unrealized P&L:  {pnl_str} ({pnl_pct:.2f}%)")

    return "\n".join(lines)


@mcp.tool()
async def get_transaction_history(
    symbol: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    limit: int = 50,
) -> str:
    """Get execution history (filled orders).

    Parameters
    ----------
    symbol:
        Optional ticker symbol to filter transactions.
    start_date:
        Optional start date for the query range (YYYY-MM-DD).
    end_date:
        Optional end date for the query range (YYYY-MM-DD).
    limit:
        Maximum number of transactions to return (default 50).

    Returns formatted execution history with trade details.
    """
    err = _check_client()
    if err:
        return err

    try:
        transactions: list[dict[str, Any]] = await _client.get_order_transactions(  # type: ignore[union-attr]
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
        )
    except Exception as exc:
        return f"Error retrieving transaction history: {exc}"

    if not transactions:
        return "No transactions found."

    lines: list[str] = ["Transaction History", "==================="]
    for txn in transactions:
        txn_symbol = txn.get("symbol", "N/A")
        action = txn.get("action", "N/A")
        quantity = txn.get("quantity", 0)
        filled = txn.get("filled", 0)
        avg_fill_price = txn.get("avg_fill_price", 0.0)
        trade_time = txn.get("trade_time", "N/A")
        commission = txn.get("commission", 0.0)

        lines.append("")
        lines.append(f"  {txn_symbol} - {action}")
        lines.append(f"    Quantity:    {quantity} (filled: {filled})")
        lines.append(f"    Fill Price:  ${avg_fill_price:,.2f}")
        lines.append(f"    Time:        {trade_time}")
        lines.append(f"    Commission:  ${commission:,.2f}")

    return "\n".join(lines)
