"""Tests for the TigerClient API wrapper.

All tests mock the tigeropen SDK so no real API calls are made.
"""

from __future__ import annotations

import inspect
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tiger_mcp.config import Settings

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_key_file(tmp_path: Path) -> Path:
    """Create a temporary file to act as a private key."""
    key_file = tmp_path / "private.pem"
    key_file.write_text("fake-key-content")
    return key_file


@pytest.fixture()
def settings(tmp_key_file: Path) -> Settings:
    """Create a Settings instance for testing."""
    return Settings(
        tiger_id="test-id",
        tiger_account="test-account",
        private_key_path=tmp_key_file,
    )


@pytest.fixture()
def mock_trade_client() -> MagicMock:
    """Create a mock TradeClient."""
    return MagicMock()


@pytest.fixture()
def mock_quote_client() -> MagicMock:
    """Create a mock QuoteClient."""
    return MagicMock()


@pytest.fixture()
def tiger_client(
    settings: Settings,
    mock_trade_client: MagicMock,
    mock_quote_client: MagicMock,
) -> Any:
    """Create a TigerClient with mocked SDK clients."""
    with (
        patch(
            "tiger_mcp.api.tiger_client.TigerOpenClientConfig"
        ) as mock_config_cls,
        patch(
            "tiger_mcp.api.tiger_client.TradeClient",
            return_value=mock_trade_client,
        ),
        patch(
            "tiger_mcp.api.tiger_client.QuoteClient",
            return_value=mock_quote_client,
        ),
    ):
        mock_config_cls.return_value = MagicMock()
        from tiger_mcp.api.tiger_client import TigerClient

        client = TigerClient(settings)

    # Attach mocks for assertions
    client._trade_client = mock_trade_client
    client._quote_client = mock_quote_client
    return client


# ---------------------------------------------------------------------------
# Construction & Authentication
# ---------------------------------------------------------------------------


class TestTigerClientConstruction:
    """Test TigerClient initialisation and auth setup."""

    def test_constructor_creates_trade_and_quote_clients(
        self, settings: Settings
    ) -> None:
        """TigerClient should create both TradeClient and QuoteClient.

        ``sandbox_debug`` must always be ``False``. Paper (simulation) accounts
        use the same production API endpoint as live accounts -- the account type
        is determined by the account ID, not by any SDK flag.
        ``sandbox_debug=True`` routes requests to a deprecated Tiger test
        endpoint that is no longer maintained.
        """
        with (
            patch(
                "tiger_mcp.api.tiger_client.TigerOpenClientConfig"
            ) as mock_config_cls,
            patch(
                "tiger_mcp.api.tiger_client.TradeClient"
            ) as mock_trade_cls,
            patch(
                "tiger_mcp.api.tiger_client.QuoteClient"
            ) as mock_quote_cls,
        ):
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg

            from tiger_mcp.api.tiger_client import TigerClient

            TigerClient(settings)

            # Config setup
            mock_config_cls.assert_called_once_with(sandbox_debug=False)
            assert mock_cfg.tiger_id == "test-id"
            assert mock_cfg.account == "test-account"

            # Both clients created
            mock_trade_cls.assert_called_once_with(mock_cfg)
            mock_quote_cls.assert_called_once_with(mock_cfg)

    def test_constructor_reads_private_key(
        self, settings: Settings
    ) -> None:
        """Constructor should read the private key file content."""
        with (
            patch(
                "tiger_mcp.api.tiger_client.TigerOpenClientConfig"
            ) as mock_config_cls,
            patch("tiger_mcp.api.tiger_client.TradeClient"),
            patch("tiger_mcp.api.tiger_client.QuoteClient"),
        ):
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg

            from tiger_mcp.api.tiger_client import TigerClient

            TigerClient(settings)

            assert mock_cfg.private_key == "fake-key-content"

    def test_constructor_sets_language_en_us(
        self, settings: Settings
    ) -> None:
        """Constructor should set the language to English US."""
        with (
            patch(
                "tiger_mcp.api.tiger_client.TigerOpenClientConfig"
            ) as mock_config_cls,
            patch("tiger_mcp.api.tiger_client.TradeClient"),
            patch("tiger_mcp.api.tiger_client.QuoteClient"),
        ):
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg

            from tigeropen.common.consts import Language

            from tiger_mcp.api.tiger_client import TigerClient

            TigerClient(settings)

            assert mock_cfg.language == Language.en_US


# ---------------------------------------------------------------------------
# Async wrapping (_run_sync helper)
# ---------------------------------------------------------------------------


class TestAsyncWrapping:
    """Test that all methods are async coroutines using run_in_executor."""

    def test_all_public_methods_are_coroutines(
        self, tiger_client: Any
    ) -> None:
        """Every public method (except helpers) should be a coroutine."""
        public_methods = [
            "get_assets",
            "get_positions",
            "get_order_transactions",
            "preview_order",
            "place_order",
            "modify_order",
            "cancel_order",
            "cancel_all_orders",
            "get_open_orders",
            "get_order_detail",
            "get_quote",
            "get_quotes",
            "get_bars",
        ]
        for method_name in public_methods:
            method = getattr(tiger_client, method_name)
            assert inspect.iscoroutinefunction(method), (
                f"{method_name} should be a coroutine function"
            )


# ---------------------------------------------------------------------------
# Account methods
# ---------------------------------------------------------------------------


class TestAccountMethods:
    """Test account-related async methods."""

    async def test_get_assets_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_assets() should call TradeClient.get_assets() and return dict."""
        mock_assets = MagicMock()
        mock_assets.summary.return_value = {
            "net_liquidation": 100_000.0,
            "cash": 50_000.0,
        }
        mock_trade_client.get_assets.return_value = mock_assets

        result = await tiger_client.get_assets()

        mock_trade_client.get_assets.assert_called_once()
        assert isinstance(result, dict)

    async def test_get_positions_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_positions() should call TradeClient.get_positions()."""
        mock_pos = MagicMock()
        mock_pos.symbol = "AAPL"
        mock_pos.quantity = 10
        mock_trade_client.get_positions.return_value = [mock_pos]

        result = await tiger_client.get_positions()

        mock_trade_client.get_positions.assert_called_once()
        assert isinstance(result, list)

    async def test_get_positions_empty(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_positions() should handle empty position list."""
        mock_trade_client.get_positions.return_value = []

        result = await tiger_client.get_positions()

        assert result == []

    async def test_get_positions_none_returns_empty_list(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_positions() should handle None from SDK gracefully."""
        mock_trade_client.get_positions.return_value = None

        result = await tiger_client.get_positions()

        assert result == []

    async def test_get_order_transactions_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_order_transactions() should call get_filled_orders()."""
        mock_order = MagicMock()
        mock_trade_client.get_filled_orders.return_value = [mock_order]

        result = await tiger_client.get_order_transactions()

        mock_trade_client.get_filled_orders.assert_called_once()
        assert isinstance(result, list)

    async def test_get_order_transactions_with_params(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_order_transactions() should pass filter parameters."""
        mock_trade_client.get_filled_orders.return_value = []

        await tiger_client.get_order_transactions(
            symbol="AAPL",
            start_date="2024-01-01",
            end_date="2024-12-31",
            limit=25,
        )

        call_kwargs = mock_trade_client.get_filled_orders.call_args
        assert call_kwargs is not None


# ---------------------------------------------------------------------------
# Order methods
# ---------------------------------------------------------------------------


class TestOrderMethods:
    """Test order-related async methods."""

    async def test_preview_order_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """preview_order() should create an order and call preview_order()."""
        mock_trade_client.preview_order.return_value = MagicMock()

        result = await tiger_client.preview_order(
            symbol="AAPL",
            action="BUY",
            quantity=10,
            order_type="market",
        )

        mock_trade_client.preview_order.assert_called_once()
        assert isinstance(result, dict)

    async def test_place_order_market(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """place_order() with market order type should work."""
        mock_trade_client.place_order.return_value = 12345

        result = await tiger_client.place_order(
            symbol="AAPL",
            action="BUY",
            quantity=10,
            order_type="market",
        )

        mock_trade_client.place_order.assert_called_once()
        assert isinstance(result, dict)
        assert result["order_id"] == 12345

    async def test_place_order_limit(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """place_order() with limit order type should pass limit_price."""
        mock_trade_client.place_order.return_value = 12346

        result = await tiger_client.place_order(
            symbol="AAPL",
            action="BUY",
            quantity=10,
            order_type="limit",
            limit_price=150.0,
        )

        mock_trade_client.place_order.assert_called_once()
        assert result["order_id"] == 12346

    async def test_place_order_stop(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """place_order() with stop order type should pass stop_price."""
        mock_trade_client.place_order.return_value = 12347

        result = await tiger_client.place_order(
            symbol="AAPL",
            action="SELL",
            quantity=5,
            order_type="stop",
            stop_price=140.0,
        )

        mock_trade_client.place_order.assert_called_once()
        assert result["order_id"] == 12347

    async def test_place_order_stop_limit(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """place_order() with stop_limit order type."""
        mock_trade_client.place_order.return_value = 12348

        result = await tiger_client.place_order(
            symbol="AAPL",
            action="SELL",
            quantity=5,
            order_type="stop_limit",
            limit_price=139.0,
            stop_price=140.0,
        )

        mock_trade_client.place_order.assert_called_once()
        assert result["order_id"] == 12348

    async def test_modify_order_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """modify_order() should call TradeClient.modify_order()."""
        mock_trade_client.modify_order.return_value = 12345
        mock_trade_client.get_order.return_value = MagicMock()

        result = await tiger_client.modify_order(
            order_id=12345,
            quantity=20,
            limit_price=155.0,
        )

        mock_trade_client.modify_order.assert_called_once()
        assert isinstance(result, dict)

    async def test_cancel_order_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """cancel_order() should call TradeClient.cancel_order()."""
        mock_trade_client.cancel_order.return_value = 12345

        result = await tiger_client.cancel_order(order_id=12345)

        mock_trade_client.cancel_order.assert_called_once()
        assert isinstance(result, dict)
        assert result["order_id"] == 12345

    async def test_cancel_all_orders_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """cancel_all_orders() should get open orders and cancel each."""
        mock_order1 = MagicMock()
        mock_order1.id = 111
        mock_order2 = MagicMock()
        mock_order2.id = 222
        mock_trade_client.get_orders.return_value = [mock_order1, mock_order2]
        mock_trade_client.cancel_order.return_value = None

        result = await tiger_client.cancel_all_orders()

        assert isinstance(result, list)

    async def test_get_open_orders_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_open_orders() should fetch orders with active states."""
        mock_order = MagicMock()
        mock_trade_client.get_orders.return_value = [mock_order]

        result = await tiger_client.get_open_orders()

        mock_trade_client.get_orders.assert_called_once()
        assert isinstance(result, list)

    async def test_get_open_orders_with_symbol_filter(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_open_orders() should pass symbol filter."""
        mock_trade_client.get_orders.return_value = []

        await tiger_client.get_open_orders(symbol="AAPL")

        call_kwargs = mock_trade_client.get_orders.call_args
        assert call_kwargs is not None

    async def test_get_order_detail_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_order_detail() should call TradeClient.get_order()."""
        mock_order = MagicMock()
        mock_order.id = 12345
        mock_trade_client.get_order.return_value = mock_order

        result = await tiger_client.get_order_detail(order_id=12345)

        mock_trade_client.get_order.assert_called_once()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Quote methods
# ---------------------------------------------------------------------------


class TestQuoteMethods:
    """Test market data / quote async methods."""

    async def test_get_quote_calls_sdk(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """get_quote() should call QuoteClient.get_stock_briefs()."""
        df = pd.DataFrame(
            [{"symbol": "AAPL", "latest_price": 150.0, "volume": 1_000_000}]
        )
        mock_quote_client.get_stock_briefs.return_value = df

        result = await tiger_client.get_quote("AAPL")

        mock_quote_client.get_stock_briefs.assert_called_once()
        assert isinstance(result, dict)
        assert result["symbol"] == "AAPL"

    async def test_get_quotes_calls_sdk(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """get_quotes() should call QuoteClient.get_stock_briefs()."""
        df = pd.DataFrame(
            [
                {"symbol": "AAPL", "latest_price": 150.0},
                {"symbol": "GOOGL", "latest_price": 170.0},
            ]
        )
        mock_quote_client.get_stock_briefs.return_value = df

        result = await tiger_client.get_quotes(["AAPL", "GOOGL"])

        mock_quote_client.get_stock_briefs.assert_called_once()
        assert isinstance(result, list)
        assert len(result) == 2

    async def test_get_bars_calls_sdk(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """get_bars() should call QuoteClient.get_bars()."""
        df = pd.DataFrame(
            [
                {"time": "2024-01-01", "open": 148.0, "close": 150.0},
                {"time": "2024-01-02", "open": 150.0, "close": 152.0},
            ]
        )
        mock_quote_client.get_bars.return_value = df

        result = await tiger_client.get_bars("AAPL", "day", limit=50)

        mock_quote_client.get_bars.assert_called_once()
        assert isinstance(result, list)
        assert len(result) == 2

    async def test_get_bars_with_different_periods(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """get_bars() should accept various period strings."""
        df = pd.DataFrame([{"time": "2024-01-01", "open": 148.0}])
        mock_quote_client.get_bars.return_value = df

        # Should not raise for valid period
        await tiger_client.get_bars("AAPL", "day")
        await tiger_client.get_bars("AAPL", "week")
        await tiger_client.get_bars("AAPL", "1min")


# ---------------------------------------------------------------------------
# Quote caching
# ---------------------------------------------------------------------------


class TestQuoteCache:
    """Test that quote data is cached for 30 seconds."""

    async def test_get_quote_caches_result(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """Second call within 30s should return cached data, not call SDK."""
        df = pd.DataFrame(
            [{"symbol": "AAPL", "latest_price": 150.0}]
        )
        mock_quote_client.get_stock_briefs.return_value = df

        result1 = await tiger_client.get_quote("AAPL")
        result2 = await tiger_client.get_quote("AAPL")

        # SDK should only be called once
        assert mock_quote_client.get_stock_briefs.call_count == 1
        assert result1 == result2

    async def test_get_quote_cache_expires(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """After 30 seconds the cache should expire and hit API again."""
        df = pd.DataFrame(
            [{"symbol": "AAPL", "latest_price": 150.0}]
        )
        mock_quote_client.get_stock_briefs.return_value = df

        await tiger_client.get_quote("AAPL")

        # Simulate cache expiry by manipulating timestamps
        for key in tiger_client._quote_cache:
            tiger_client._quote_cache[key] = (
                tiger_client._quote_cache[key][0],
                time.monotonic() - 31,
            )

        await tiger_client.get_quote("AAPL")

        assert mock_quote_client.get_stock_briefs.call_count == 2

    async def test_get_quotes_caches_result(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """get_quotes() should also use caching."""
        df = pd.DataFrame(
            [
                {"symbol": "AAPL", "latest_price": 150.0},
                {"symbol": "GOOGL", "latest_price": 170.0},
            ]
        )
        mock_quote_client.get_stock_briefs.return_value = df

        await tiger_client.get_quotes(["AAPL", "GOOGL"])
        await tiger_client.get_quotes(["AAPL", "GOOGL"])

        assert mock_quote_client.get_stock_briefs.call_count == 1

    async def test_get_quotes_cache_expires(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """get_quotes() cache should expire after 30 seconds."""
        df = pd.DataFrame(
            [{"symbol": "AAPL", "latest_price": 150.0}]
        )
        mock_quote_client.get_stock_briefs.return_value = df

        await tiger_client.get_quotes(["AAPL"])

        for key in tiger_client._quote_cache:
            tiger_client._quote_cache[key] = (
                tiger_client._quote_cache[key][0],
                time.monotonic() - 31,
            )

        await tiger_client.get_quotes(["AAPL"])

        assert mock_quote_client.get_stock_briefs.call_count == 2

    async def test_different_symbols_not_cached_together(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """Different symbols should have separate cache entries."""
        df_aapl = pd.DataFrame(
            [{"symbol": "AAPL", "latest_price": 150.0}]
        )
        df_googl = pd.DataFrame(
            [{"symbol": "GOOGL", "latest_price": 170.0}]
        )
        mock_quote_client.get_stock_briefs.side_effect = [df_aapl, df_googl]

        await tiger_client.get_quote("AAPL")
        await tiger_client.get_quote("GOOGL")

        assert mock_quote_client.get_stock_briefs.call_count == 2

    async def test_bars_are_not_cached(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """get_bars() should NOT cache results."""
        df = pd.DataFrame(
            [{"time": "2024-01-01", "open": 148.0}]
        )
        mock_quote_client.get_bars.return_value = df

        await tiger_client.get_bars("AAPL", "day")
        await tiger_client.get_bars("AAPL", "day")

        assert mock_quote_client.get_bars.call_count == 2


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test that SDK exceptions are wrapped into RuntimeError."""

    async def test_get_assets_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from get_assets() should become RuntimeError."""
        mock_trade_client.get_assets.side_effect = Exception(
            "API connection failed"
        )

        with pytest.raises(RuntimeError, match="get_assets.*API connection failed"):
            await tiger_client.get_assets()

    async def test_place_order_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from place_order() should become RuntimeError."""
        mock_trade_client.place_order.side_effect = Exception(
            "Insufficient funds"
        )

        with pytest.raises(RuntimeError, match="place_order.*Insufficient funds"):
            await tiger_client.place_order(
                symbol="AAPL",
                action="BUY",
                quantity=10,
                order_type="market",
            )

    async def test_get_quote_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """SDK exception from get_quote() should become RuntimeError."""
        mock_quote_client.get_stock_briefs.side_effect = Exception(
            "Symbol not found"
        )

        with pytest.raises(RuntimeError, match="get_quote.*Symbol not found"):
            await tiger_client.get_quote("INVALID")

    async def test_cancel_order_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from cancel_order() should become RuntimeError."""
        mock_trade_client.cancel_order.side_effect = Exception(
            "Order not found"
        )

        with pytest.raises(RuntimeError, match="cancel_order.*Order not found"):
            await tiger_client.cancel_order(order_id=99999)

    async def test_modify_order_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from modify_order() should become RuntimeError."""
        mock_trade_client.get_order.side_effect = Exception(
            "Order not found"
        )

        with pytest.raises(RuntimeError, match="modify_order.*Order not found"):
            await tiger_client.modify_order(
                order_id=99999,
                quantity=20,
            )

    async def test_get_bars_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """SDK exception from get_bars() should become RuntimeError."""
        mock_quote_client.get_bars.side_effect = Exception(
            "Invalid period"
        )

        with pytest.raises(RuntimeError, match="get_bars.*Invalid period"):
            await tiger_client.get_bars("AAPL", "invalid_period")

    async def test_get_order_detail_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from get_order_detail() should become RuntimeError."""
        mock_trade_client.get_order.side_effect = Exception(
            "Connection timeout"
        )

        with pytest.raises(
            RuntimeError, match="get_order_detail.*Connection timeout"
        ):
            await tiger_client.get_order_detail(order_id=12345)


# ---------------------------------------------------------------------------
# _build_order helper
# ---------------------------------------------------------------------------


class TestBuildOrder:
    """Test the _build_order helper method."""

    def test_build_market_order(self, tiger_client: Any) -> None:
        """_build_order with market type should use market_order utility."""
        with patch(
            "tiger_mcp.api.tiger_client.market_order"
        ) as mock_market_order:
            mock_market_order.return_value = MagicMock()
            tiger_client._build_order(
                symbol="AAPL",
                action="BUY",
                quantity=10,
                order_type="market",
            )
            mock_market_order.assert_called_once()

    def test_build_limit_order(self, tiger_client: Any) -> None:
        """_build_order with limit type should use limit_order utility."""
        with patch(
            "tiger_mcp.api.tiger_client.limit_order"
        ) as mock_limit_order:
            mock_limit_order.return_value = MagicMock()
            tiger_client._build_order(
                symbol="AAPL",
                action="BUY",
                quantity=10,
                order_type="limit",
                limit_price=150.0,
            )
            mock_limit_order.assert_called_once()

    def test_build_stop_order(self, tiger_client: Any) -> None:
        """_build_order with stop type should use stop_order utility."""
        with patch(
            "tiger_mcp.api.tiger_client.stop_order"
        ) as mock_stop_order:
            mock_stop_order.return_value = MagicMock()
            tiger_client._build_order(
                symbol="AAPL",
                action="SELL",
                quantity=5,
                order_type="stop",
                stop_price=140.0,
            )
            mock_stop_order.assert_called_once()

    def test_build_stop_limit_order(self, tiger_client: Any) -> None:
        """_build_order with stop_limit type should use stop_limit_order."""
        with patch(
            "tiger_mcp.api.tiger_client.stop_limit_order"
        ) as mock_sl_order:
            mock_sl_order.return_value = MagicMock()
            tiger_client._build_order(
                symbol="AAPL",
                action="SELL",
                quantity=5,
                order_type="stop_limit",
                limit_price=139.0,
                stop_price=140.0,
            )
            mock_sl_order.assert_called_once()

    def test_build_unknown_order_type_raises(
        self, tiger_client: Any
    ) -> None:
        """_build_order with unknown order type should raise ValueError."""
        with pytest.raises(ValueError, match="(?i)unsupported.*order.*type"):
            tiger_client._build_order(
                symbol="AAPL",
                action="BUY",
                quantity=10,
                order_type="trailing_stop",
            )
