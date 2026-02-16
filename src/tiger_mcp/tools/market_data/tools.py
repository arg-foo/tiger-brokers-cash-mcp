"""Market data MCP tools for the Tiger Brokers server.

Provides three tools for retrieving stock market data:

- ``get_stock_quote`` -- real-time quote for a single symbol
- ``get_stock_quotes`` -- real-time quotes for multiple symbols
- ``get_stock_bars`` -- historical OHLCV bars for a symbol

All tools require the module to be initialised with a ``TigerClient``
instance via the :func:`init` function before first use.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tiger_mcp.server import mcp

if TYPE_CHECKING:
    from tiger_mcp.api.tiger_client import TigerClient

# ---------------------------------------------------------------------------
# Module-level client (set via init)
# ---------------------------------------------------------------------------

_client: TigerClient | None = None

# ---------------------------------------------------------------------------
# Valid bar periods and their SDK-level mappings
# ---------------------------------------------------------------------------

_VALID_PERIODS = ("1d", "1w", "1m", "3m", "6m", "1y")

_PERIOD_TO_SDK: dict[str, str] = {
    "1d": "day",
    "1w": "week",
    "1m": "month",
    "3m": "month",
    "6m": "month",
    "1y": "year",
}

# Maximum symbols allowed in a single get_stock_quotes call.
_MAX_SYMBOLS = 50


def init(client: TigerClient) -> None:
    """Initialise the market data tools with a TigerClient instance."""
    global _client  # noqa: PLW0603
    _client = client


def _require_client() -> TigerClient:
    """Return the module-level client or raise if not initialised."""
    if _client is None:
        msg = "Market data tools not initialised. Call init(client) first."
        raise RuntimeError(msg)
    return _client


def _validate_symbol(symbol: str) -> str:
    """Validate and normalise a single ticker symbol.

    Returns the uppercased, stripped symbol.

    Raises
    ------
    ValueError
        If the symbol is empty or whitespace-only.
    """
    symbol = symbol.strip().upper()
    if not symbol:
        msg = "Symbol must not be empty."
        raise ValueError(msg)
    return symbol


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _fmt_price(value: object) -> str:
    """Format a price value to 2 decimal places if numeric."""
    if isinstance(value, (int, float)):
        return f"{value:.2f}"
    return str(value)


def _format_quote(data: dict) -> str:
    """Format a single quote dict into an LLM-readable string."""
    symbol = data.get("symbol", "N/A")
    price = data.get("latest_price", "N/A")
    bid = data.get("bid_price", "N/A")
    ask = data.get("ask_price", "N/A")
    volume = data.get("volume", "N/A")
    change = data.get("change", "N/A")
    change_ratio = data.get("change_ratio", "N/A")

    volume_str = f"{volume:,}" if isinstance(volume, (int, float)) else str(volume)
    change_pct = (
        f"{change_ratio * 100:.2f}%"
        if isinstance(change_ratio, (int, float))
        else str(change_ratio)
    )

    lines = [
        f"Symbol: {symbol}",
        f"Last Price: {_fmt_price(price)}",
        f"Change: {_fmt_price(change)} ({change_pct})",
        f"Bid: {_fmt_price(bid)}  |  Ask: {_fmt_price(ask)}",
        f"Volume: {volume_str}",
    ]

    # Include optional fields if present
    optional = [
        ("Open", "open"),
        ("High", "high"),
        ("Low", "low"),
        ("Prev Close", "prev_close"),
    ]
    for label, key in optional:
        val = data.get(key)
        if val is not None:
            lines.append(f"{label}: {_fmt_price(val)}")

    return "\n".join(lines)


def _format_bars(symbol: str, bars: list[dict]) -> str:
    """Format OHLCV bars as a compact table-like text."""
    if not bars:
        return f"No bar data available for {symbol}."

    header = (
        f"{'Date':<12} {'Open':>10} {'High':>10} "
        f"{'Low':>10} {'Close':>10} {'Volume':>14}"
    )
    separator = "-" * len(header)

    lines = [
        f"Historical Bars for {symbol}",
        "",
        header,
        separator,
    ]

    for bar in bars:
        date = str(bar.get("time", "N/A"))
        o = _fmt_price(bar.get("open", "N/A"))
        h = _fmt_price(bar.get("high", "N/A"))
        lo = _fmt_price(bar.get("low", "N/A"))
        c = _fmt_price(bar.get("close", "N/A"))
        v = bar.get("volume", "N/A")

        vol_str = f"{v:,}" if isinstance(v, (int, float)) else str(v)
        lines.append(
            f"{date:<12} {o:>10} {h:>10} {lo:>10} {c:>10} {vol_str:>14}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_stock_quote(symbol: str) -> str:
    """Get a real-time stock quote for a single ticker symbol.

    Parameters
    ----------
    symbol:
        Stock ticker symbol (e.g. ``AAPL``, ``GOOGL``).

    Returns
    -------
    str
        A human-readable formatted quote showing last price, bid/ask,
        volume, change, and change percentage.
    """
    symbol = _validate_symbol(symbol)
    client = _require_client()
    data = await client.get_quote(symbol)
    return _format_quote(data)


@mcp.tool()
async def get_stock_quotes(symbols: str) -> str:
    """Get real-time stock quotes for multiple ticker symbols.

    Parameters
    ----------
    symbols:
        Comma-separated list of ticker symbols (e.g. ``AAPL,GOOGL,MSFT``).
        Maximum 50 symbols per request.

    Returns
    -------
    str
        Formatted quotes for each requested symbol.
    """
    # Parse, clean, uppercase, deduplicate
    raw_parts = symbols.split(",")
    symbol_list: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        s = part.strip().upper()
        if s and s not in seen:
            symbol_list.append(s)
            seen.add(s)

    if not symbol_list:
        msg = "Symbols list must not be empty."
        raise ValueError(msg)

    if len(symbol_list) > _MAX_SYMBOLS:
        msg = f"Too many symbols ({len(symbol_list)}). Maximum is {_MAX_SYMBOLS} (50)."
        raise ValueError(msg)

    client = _require_client()
    quotes = await client.get_quotes(symbol_list)

    sections = [_format_quote(q) for q in quotes]
    return "\n\n---\n\n".join(sections)


@mcp.tool()
async def get_stock_bars(
    symbol: str,
    period: str,
    limit: int = 100,
) -> str:
    """Get historical OHLCV price bars for a stock.

    Parameters
    ----------
    symbol:
        Stock ticker symbol (e.g. ``AAPL``).
    period:
        Bar period. Allowed values: ``1d``, ``1w``, ``1m``, ``3m``,
        ``6m``, ``1y``.
    limit:
        Maximum number of bars to return (default 100).

    Returns
    -------
    str
        A compact table of date, open, high, low, close, and volume.
    """
    symbol = _validate_symbol(symbol)

    if period not in _VALID_PERIODS:
        allowed = ", ".join(_VALID_PERIODS)
        msg = f"Invalid period {period!r}. Allowed period values: {allowed}"
        raise ValueError(msg)

    sdk_period = _PERIOD_TO_SDK[period]
    client = _require_client()
    bars = await client.get_bars(symbol, sdk_period, limit)
    return _format_bars(symbol, bars)
