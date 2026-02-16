"""Tests for market data MCP tools.

Covers get_stock_quote, get_stock_quotes, and get_stock_bars with
mocked TigerClient, including parameter validation, response formatting,
and error handling.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Return a mock TigerClient with pre-configured return values."""
    client = AsyncMock()

    # Default single-quote response
    client.get_quote.return_value = {
        "symbol": "AAPL",
        "latest_price": 185.50,
        "bid_price": 185.45,
        "ask_price": 185.55,
        "volume": 45_123_456,
        "change": 2.30,
        "change_ratio": 0.0125,
        "open": 183.20,
        "high": 186.00,
        "low": 182.90,
        "prev_close": 183.20,
    }

    # Default multi-quote response
    client.get_quotes.return_value = [
        {
            "symbol": "AAPL",
            "latest_price": 185.50,
            "bid_price": 185.45,
            "ask_price": 185.55,
            "volume": 45_123_456,
            "change": 2.30,
            "change_ratio": 0.0125,
        },
        {
            "symbol": "GOOGL",
            "latest_price": 141.80,
            "bid_price": 141.75,
            "ask_price": 141.85,
            "volume": 22_456_789,
            "change": -1.20,
            "change_ratio": -0.0084,
        },
    ]

    # Default bars response
    client.get_bars.return_value = [
        {
            "time": "2025-01-15",
            "open": 183.20,
            "high": 186.00,
            "low": 182.90,
            "close": 185.50,
            "volume": 45_123_456,
        },
        {
            "time": "2025-01-16",
            "open": 185.50,
            "high": 187.20,
            "low": 184.80,
            "close": 186.80,
            "volume": 38_567_123,
        },
    ]

    return client


@pytest.fixture(autouse=True)
def _init_market_tools(mock_client: AsyncMock) -> None:
    """Initialize the market data tools module with the mock client."""
    from tiger_mcp.tools.market_data.tools import init

    init(mock_client)


# ---------------------------------------------------------------------------
# get_stock_quote tests
# ---------------------------------------------------------------------------


class TestGetStockQuote:
    """Tests for the get_stock_quote MCP tool."""

    async def test_returns_formatted_quote(self, mock_client: AsyncMock) -> None:
        """get_stock_quote returns a human-readable formatted string."""
        from tiger_mcp.tools.market_data.tools import get_stock_quote

        result = await get_stock_quote(symbol="AAPL")

        mock_client.get_quote.assert_awaited_once_with("AAPL")
        assert "AAPL" in result
        assert "185.50" in result

    async def test_contains_bid_ask(self, mock_client: AsyncMock) -> None:
        """Result includes bid and ask prices."""
        from tiger_mcp.tools.market_data.tools import get_stock_quote

        result = await get_stock_quote(symbol="AAPL")

        assert "185.45" in result
        assert "185.55" in result

    async def test_contains_volume(self, mock_client: AsyncMock) -> None:
        """Result includes volume information."""
        from tiger_mcp.tools.market_data.tools import get_stock_quote

        result = await get_stock_quote(symbol="AAPL")

        assert "45,123,456" in result or "45123456" in result

    async def test_contains_change(self, mock_client: AsyncMock) -> None:
        """Result includes change and change percentage."""
        from tiger_mcp.tools.market_data.tools import get_stock_quote

        result = await get_stock_quote(symbol="AAPL")

        assert "2.30" in result or "2.3" in result
        # Percentage should be present (1.25%)
        assert "1.25" in result

    async def test_symbol_uppercased(self, mock_client: AsyncMock) -> None:
        """Lowercase symbols should be uppercased automatically."""
        from tiger_mcp.tools.market_data.tools import get_stock_quote

        await get_stock_quote(symbol="aapl")

        mock_client.get_quote.assert_awaited_once_with("AAPL")

    async def test_symbol_trimmed(self, mock_client: AsyncMock) -> None:
        """Whitespace around the symbol should be trimmed."""
        from tiger_mcp.tools.market_data.tools import get_stock_quote

        await get_stock_quote(symbol="  AAPL  ")

        mock_client.get_quote.assert_awaited_once_with("AAPL")

    async def test_empty_symbol_raises(self) -> None:
        """Empty symbol string should raise ValueError."""
        from tiger_mcp.tools.market_data.tools import get_stock_quote

        with pytest.raises(ValueError, match="[Ss]ymbol"):
            await get_stock_quote(symbol="")

    async def test_whitespace_only_symbol_raises(self) -> None:
        """Symbol that is only whitespace should raise ValueError."""
        from tiger_mcp.tools.market_data.tools import get_stock_quote

        with pytest.raises(ValueError, match="[Ss]ymbol"):
            await get_stock_quote(symbol="   ")

    async def test_client_error_propagates(self, mock_client: AsyncMock) -> None:
        """RuntimeError from TigerClient should propagate to caller."""
        from tiger_mcp.tools.market_data.tools import get_stock_quote

        mock_client.get_quote.side_effect = RuntimeError("API error")

        with pytest.raises(RuntimeError, match="API error"):
            await get_stock_quote(symbol="AAPL")


# ---------------------------------------------------------------------------
# get_stock_quotes tests
# ---------------------------------------------------------------------------


class TestGetStockQuotes:
    """Tests for the get_stock_quotes MCP tool."""

    async def test_returns_formatted_multi_quote(
        self, mock_client: AsyncMock
    ) -> None:
        """get_stock_quotes returns formatted text for multiple symbols."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        result = await get_stock_quotes(symbols="AAPL,GOOGL")

        mock_client.get_quotes.assert_awaited_once_with(["AAPL", "GOOGL"])
        assert "AAPL" in result
        assert "GOOGL" in result

    async def test_contains_prices_for_each_symbol(
        self, mock_client: AsyncMock
    ) -> None:
        """Each symbol section should contain price data."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        result = await get_stock_quotes(symbols="AAPL,GOOGL")

        assert "185.50" in result
        assert "141.80" in result

    async def test_parses_with_whitespace(self, mock_client: AsyncMock) -> None:
        """Whitespace around symbols in the comma-separated string is trimmed."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        await get_stock_quotes(symbols="  AAPL , GOOGL  ")

        mock_client.get_quotes.assert_awaited_once_with(["AAPL", "GOOGL"])

    async def test_uppercases_symbols(self, mock_client: AsyncMock) -> None:
        """Lowercase symbols should be uppercased."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        await get_stock_quotes(symbols="aapl,googl")

        mock_client.get_quotes.assert_awaited_once_with(["AAPL", "GOOGL"])

    async def test_empty_string_raises(self) -> None:
        """Empty symbols string should raise ValueError."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        with pytest.raises(ValueError, match="[Ss]ymbol"):
            await get_stock_quotes(symbols="")

    async def test_whitespace_only_raises(self) -> None:
        """Whitespace-only symbols string should raise ValueError."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        with pytest.raises(ValueError, match="[Ss]ymbol"):
            await get_stock_quotes(symbols="   ")

    async def test_too_many_symbols_raises(self) -> None:
        """More than 50 symbols should raise ValueError."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        # 51 symbols
        symbols = ",".join(f"SYM{i}" for i in range(51))

        with pytest.raises(ValueError, match="50"):
            await get_stock_quotes(symbols=symbols)

    async def test_exactly_50_symbols_allowed(
        self, mock_client: AsyncMock
    ) -> None:
        """Exactly 50 symbols should be accepted without error."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        symbols_list = [f"SYM{i}" for i in range(50)]
        mock_client.get_quotes.return_value = [
            {"symbol": s, "latest_price": 100.0, "bid_price": 99.0,
             "ask_price": 101.0, "volume": 1000, "change": 0.5,
             "change_ratio": 0.005}
            for s in symbols_list
        ]

        await get_stock_quotes(symbols=",".join(symbols_list))

        assert mock_client.get_quotes.await_count == 1

    async def test_deduplicates_symbols(self, mock_client: AsyncMock) -> None:
        """Duplicate symbols should be removed."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        mock_client.get_quotes.return_value = [
            {
                "symbol": "AAPL",
                "latest_price": 185.50,
                "bid_price": 185.45,
                "ask_price": 185.55,
                "volume": 45_123_456,
                "change": 2.30,
                "change_ratio": 0.0125,
            },
        ]

        await get_stock_quotes(symbols="AAPL,aapl,AAPL")

        # Should be called with deduplicated list
        call_args = mock_client.get_quotes.call_args[0][0]
        assert call_args == ["AAPL"]

    async def test_filters_empty_entries(self, mock_client: AsyncMock) -> None:
        """Empty entries from trailing commas should be filtered out."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        mock_client.get_quotes.return_value = [
            {
                "symbol": "AAPL",
                "latest_price": 185.50,
                "bid_price": 185.45,
                "ask_price": 185.55,
                "volume": 45_123_456,
                "change": 2.30,
                "change_ratio": 0.0125,
            },
        ]

        await get_stock_quotes(symbols="AAPL,,")

        call_args = mock_client.get_quotes.call_args[0][0]
        assert call_args == ["AAPL"]

    async def test_client_error_propagates(self, mock_client: AsyncMock) -> None:
        """RuntimeError from TigerClient should propagate."""
        from tiger_mcp.tools.market_data.tools import get_stock_quotes

        mock_client.get_quotes.side_effect = RuntimeError("API error")

        with pytest.raises(RuntimeError, match="API error"):
            await get_stock_quotes(symbols="AAPL,GOOGL")


# ---------------------------------------------------------------------------
# get_stock_bars tests
# ---------------------------------------------------------------------------


class TestGetStockBars:
    """Tests for the get_stock_bars MCP tool."""

    async def test_returns_formatted_bars(self, mock_client: AsyncMock) -> None:
        """get_stock_bars returns formatted OHLCV table text."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        result = await get_stock_bars(symbol="AAPL", period="1d")

        mock_client.get_bars.assert_awaited_once_with("AAPL", "day", 100)
        assert "AAPL" in result

    async def test_contains_ohlcv_data(self, mock_client: AsyncMock) -> None:
        """Result should contain open, high, low, close, volume columns."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        result = await get_stock_bars(symbol="AAPL", period="1d")

        # Check for OHLCV header-like labels
        result_lower = result.lower()
        assert "open" in result_lower
        assert "high" in result_lower
        assert "close" in result_lower
        assert "volume" in result_lower

    async def test_contains_bar_values(self, mock_client: AsyncMock) -> None:
        """Result should contain actual bar values from the mock data."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        result = await get_stock_bars(symbol="AAPL", period="1d")

        assert "183.20" in result
        assert "186.00" in result
        assert "185.50" in result

    async def test_custom_limit(self, mock_client: AsyncMock) -> None:
        """Custom limit parameter is passed to the client."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        await get_stock_bars(symbol="AAPL", period="1d", limit=50)

        mock_client.get_bars.assert_awaited_once_with("AAPL", "day", 50)

    async def test_default_limit_is_100(self, mock_client: AsyncMock) -> None:
        """Default limit should be 100."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        await get_stock_bars(symbol="AAPL", period="1d")

        mock_client.get_bars.assert_awaited_once_with("AAPL", "day", 100)

    async def test_valid_periods(self, mock_client: AsyncMock) -> None:
        """All valid period values should be accepted without error."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        valid_periods = ["1d", "1w", "1m", "3m", "6m", "1y"]

        for period in valid_periods:
            mock_client.get_bars.reset_mock()
            await get_stock_bars(symbol="AAPL", period=period)
            assert mock_client.get_bars.await_count == 1

    async def test_invalid_period_raises(self) -> None:
        """Invalid period string should raise ValueError."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        with pytest.raises(ValueError, match="[Pp]eriod"):
            await get_stock_bars(symbol="AAPL", period="2d")

    async def test_invalid_period_shows_allowed_values(self) -> None:
        """Error message for invalid period should list allowed values."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        with pytest.raises(ValueError, match="1d") as exc_info:
            await get_stock_bars(symbol="AAPL", period="invalid")

        error_msg = str(exc_info.value)
        assert "1w" in error_msg
        assert "1y" in error_msg

    async def test_empty_symbol_raises(self) -> None:
        """Empty symbol should raise ValueError."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        with pytest.raises(ValueError, match="[Ss]ymbol"):
            await get_stock_bars(symbol="", period="1d")

    async def test_symbol_uppercased(self, mock_client: AsyncMock) -> None:
        """Lowercase symbol should be uppercased."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        await get_stock_bars(symbol="aapl", period="1d")

        mock_client.get_bars.assert_awaited_once_with("AAPL", "day", 100)

    async def test_symbol_trimmed(self, mock_client: AsyncMock) -> None:
        """Whitespace around symbol should be trimmed."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        await get_stock_bars(symbol="  AAPL  ", period="1d")

        mock_client.get_bars.assert_awaited_once_with("AAPL", "day", 100)

    async def test_empty_bars_result(self, mock_client: AsyncMock) -> None:
        """Empty bars list should return a message rather than crash."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        mock_client.get_bars.return_value = []

        result = await get_stock_bars(symbol="AAPL", period="1d")

        assert "no" in result.lower() or "empty" in result.lower() or "AAPL" in result

    async def test_client_error_propagates(self, mock_client: AsyncMock) -> None:
        """RuntimeError from TigerClient should propagate."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        mock_client.get_bars.side_effect = RuntimeError("API error")

        with pytest.raises(RuntimeError, match="API error"):
            await get_stock_bars(symbol="AAPL", period="1d")


# ---------------------------------------------------------------------------
# Tool registration tests
# ---------------------------------------------------------------------------


class TestToolRegistration:
    """Verify tools are properly registered with the MCP server."""

    def test_tools_are_decorated(self) -> None:
        """All three tool functions should be importable."""
        from tiger_mcp.tools.market_data.tools import (
            get_stock_bars,
            get_stock_quote,
            get_stock_quotes,
        )

        assert callable(get_stock_quote)
        assert callable(get_stock_quotes)
        assert callable(get_stock_bars)

    def test_init_function_exists(self) -> None:
        """The init function should exist and accept a client argument."""
        from tiger_mcp.tools.market_data.tools import init

        assert callable(init)

    def test_module_has_client_variable(self) -> None:
        """Module should expose a _client variable after init."""
        import tiger_mcp.tools.market_data.tools as mod

        assert hasattr(mod, "_client")


# ---------------------------------------------------------------------------
# Period mapping tests
# ---------------------------------------------------------------------------


class TestPeriodMapping:
    """Verify period string to SDK period mapping."""

    async def test_1d_maps_to_day(self, mock_client: AsyncMock) -> None:
        """Period '1d' should map to 'day' for the TigerClient."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        await get_stock_bars(symbol="AAPL", period="1d")

        mock_client.get_bars.assert_awaited_once_with("AAPL", "day", 100)

    async def test_1w_maps_to_week(self, mock_client: AsyncMock) -> None:
        """Period '1w' should map to 'week' for the TigerClient."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        await get_stock_bars(symbol="AAPL", period="1w")

        mock_client.get_bars.assert_awaited_once_with("AAPL", "week", 100)

    async def test_1m_maps_to_month(self, mock_client: AsyncMock) -> None:
        """Period '1m' should map to 'month' for the TigerClient."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        await get_stock_bars(symbol="AAPL", period="1m")

        mock_client.get_bars.assert_awaited_once_with("AAPL", "month", 100)

    async def test_1y_maps_to_year(self, mock_client: AsyncMock) -> None:
        """Period '1y' should map to 'year' for the TigerClient."""
        from tiger_mcp.tools.market_data.tools import get_stock_bars

        await get_stock_bars(symbol="AAPL", period="1y")

        mock_client.get_bars.assert_awaited_once_with("AAPL", "year", 100)
