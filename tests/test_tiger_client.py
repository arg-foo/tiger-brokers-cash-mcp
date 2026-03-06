"""Tests for the TigerClient API wrapper.

All tests mock the tigeropen SDK so no real API calls are made.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from tiger_mcp.api.tiger_client import _parse_order_id
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
            "tiger_mcp.api.tiger_client.build_client_config",
            return_value=MagicMock(),
        ),
        patch(
            "tiger_mcp.api.tiger_client.TradeClient",
            return_value=mock_trade_client,
        ),
        patch(
            "tiger_mcp.api.tiger_client.QuoteClient",
            return_value=mock_quote_client,
        ),
    ):
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

        Configuration is delegated to ``build_client_config()`` which
        ensures ``sandbox_debug=False``.
        """
        mock_cfg = MagicMock()
        with (
            patch(
                "tiger_mcp.api.tiger_client.build_client_config",
                return_value=mock_cfg,
            ) as mock_build,
            patch("tiger_mcp.api.tiger_client.TradeClient") as mock_trade_cls,
            patch("tiger_mcp.api.tiger_client.QuoteClient") as mock_quote_cls,
        ):
            from tiger_mcp.api.tiger_client import TigerClient

            TigerClient(settings)

            # build_client_config called with settings
            mock_build.assert_called_once_with(settings)

            # Both clients created with the returned config
            mock_trade_cls.assert_called_once_with(mock_cfg)
            mock_quote_cls.assert_called_once_with(mock_cfg)

    def test_constructor_delegates_to_build_client_config(
        self, settings: Settings
    ) -> None:
        """Constructor should delegate all config setup to build_client_config."""
        mock_cfg = MagicMock()
        with (
            patch(
                "tiger_mcp.api.tiger_client.build_client_config",
                return_value=mock_cfg,
            ) as mock_build,
            patch("tiger_mcp.api.tiger_client.TradeClient"),
            patch("tiger_mcp.api.tiger_client.QuoteClient"),
        ):
            from tiger_mcp.api.tiger_client import TigerClient

            TigerClient(settings)

            mock_build.assert_called_once_with(settings)


# ---------------------------------------------------------------------------
# build_client_config factory
# ---------------------------------------------------------------------------


class TestBuildClientConfig:
    """Test the shared build_client_config factory."""

    def test_sandbox_debug_false(self, settings: Settings) -> None:
        """build_client_config must always set sandbox_debug=False."""
        with (
            patch(
                "tiger_mcp.api.config_factory.TigerOpenClientConfig"
            ) as mock_config_cls,
        ):
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg

            from tiger_mcp.api.config_factory import build_client_config

            build_client_config(settings)

            mock_config_cls.assert_called_once_with(sandbox_debug=False)

    def test_reads_private_key(self, settings: Settings) -> None:
        """build_client_config should read the private key file content."""
        with (
            patch(
                "tiger_mcp.api.config_factory.TigerOpenClientConfig"
            ) as mock_config_cls,
        ):
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg

            from tiger_mcp.api.config_factory import build_client_config

            build_client_config(settings)

            assert mock_cfg.private_key == "fake-key-content"

    def test_sets_language_en_us(self, settings: Settings) -> None:
        """build_client_config should set the language to English US."""
        with (
            patch(
                "tiger_mcp.api.config_factory.TigerOpenClientConfig"
            ) as mock_config_cls,
        ):
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg

            from tigeropen.common.consts import Language

            from tiger_mcp.api.config_factory import build_client_config

            build_client_config(settings)

            assert mock_cfg.language == Language.en_US

    def test_sets_tiger_id_and_account(self, settings: Settings) -> None:
        """build_client_config should set tiger_id and account."""
        with (
            patch(
                "tiger_mcp.api.config_factory.TigerOpenClientConfig"
            ) as mock_config_cls,
        ):
            mock_cfg = MagicMock()
            mock_config_cls.return_value = mock_cfg

            from tiger_mcp.api.config_factory import build_client_config

            build_client_config(settings)

            assert mock_cfg.tiger_id == "test-id"
            assert mock_cfg.account == "test-account"
            assert mock_cfg.license == "TBSG"


# ---------------------------------------------------------------------------
# Async wrapping (_run_sync helper)
# ---------------------------------------------------------------------------


class TestAsyncWrapping:
    """Test that all methods are async coroutines using run_in_executor."""

    def test_all_public_methods_are_coroutines(self, tiger_client: Any) -> None:
        """Every public method (except helpers) should be a coroutine."""
        public_methods = [
            "get_assets",
            "get_positions",
            "get_filled_orders",
            "preview_order",
            "place_order",
            "modify_order",
            "cancel_order",
            "cancel_all_orders",
            "get_open_orders",
            "get_order_detail",
            "get_bars",
            "place_oca_order",
            "place_bracket_order",
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
        mock_pos.contract.symbol = "AAPL"
        mock_pos.quantity = 10
        mock_trade_client.get_positions.return_value = [mock_pos]

        result = await tiger_client.get_positions()

        mock_trade_client.get_positions.assert_called_once()
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["symbol"] == "AAPL"
        assert result[0]["quantity"] == 10

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

    async def test_position_with_no_contract_omits_symbol(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """Position with contract=None should produce a dict without 'symbol'.

        Covers the ``if contract is not None`` guard in ``_position_to_dict``.
        """
        mock_pos = MagicMock()
        mock_pos.contract = None
        mock_pos.quantity = 5
        mock_pos.average_cost = 100.0
        # Ensure the remaining numeric attrs are absent so we control the dict
        mock_pos.market_price = None
        mock_pos.market_value = None
        mock_pos.unrealized_pnl = None
        mock_pos.realized_pnl = None
        mock_trade_client.get_positions.return_value = [mock_pos]

        result = await tiger_client.get_positions()

        assert len(result) == 1
        assert "symbol" not in result[0]
        assert result[0]["quantity"] == 5
        assert result[0]["average_cost"] == 100.0

    async def test_position_with_contract_symbol_none_omits_symbol(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """Position where contract.symbol is None should omit 'symbol'.

        Covers the inner ``if symbol is not None`` guard in
        ``_position_to_dict``.
        """
        mock_pos = MagicMock()
        mock_pos.contract.symbol = None
        mock_pos.quantity = 3
        mock_pos.average_cost = None
        mock_pos.market_price = 200.0
        mock_pos.market_value = None
        mock_pos.unrealized_pnl = None
        mock_pos.realized_pnl = None
        mock_trade_client.get_positions.return_value = [mock_pos]

        result = await tiger_client.get_positions()

        assert len(result) == 1
        assert "symbol" not in result[0]
        assert result[0]["quantity"] == 3
        assert result[0]["market_price"] == 200.0

    async def test_get_filled_orders_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_filled_orders() should call get_filled_orders()."""
        mock_order = MagicMock()
        mock_trade_client.get_filled_orders.return_value = [mock_order]

        result = await tiger_client.get_filled_orders()

        mock_trade_client.get_filled_orders.assert_called_once()
        assert isinstance(result, list)

    async def test_get_filled_orders_with_params(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """get_filled_orders() should pass filter parameters."""
        mock_trade_client.get_filled_orders.return_value = []

        await tiger_client.get_filled_orders(
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
            order_type="limit",
            limit_price=150.0,
        )

        mock_trade_client.preview_order.assert_called_once()
        assert isinstance(result, dict)

    async def test_place_order_limit(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """place_order() with limit order type should pass limit_price."""

        def _set_order_id(order: Any) -> None:
            order.id = 12346

        mock_trade_client.place_order.side_effect = _set_order_id

        result = await tiger_client.place_order(
            symbol="AAPL",
            action="BUY",
            quantity=10,
            order_type="limit",
            limit_price=150.0,
        )

        mock_trade_client.place_order.assert_called_once()
        assert result["order_id"] == "12346"

    async def test_place_order_stop_limit(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """place_order() with stop_limit order type."""

        def _set_order_id(order: Any) -> None:
            order.id = 12348

        mock_trade_client.place_order.side_effect = _set_order_id

        result = await tiger_client.place_order(
            symbol="AAPL",
            action="SELL",
            quantity=5,
            order_type="stop_limit",
            limit_price=139.0,
            stop_price=140.0,
        )

        mock_trade_client.place_order.assert_called_once()
        assert result["order_id"] == "12348"

    async def test_modify_order_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """modify_order() should call TradeClient.modify_order()."""
        mock_trade_client.modify_order.return_value = 12345
        mock_trade_client.get_order.return_value = MagicMock()

        result = await tiger_client.modify_order(
            order_id="12345",
            quantity=20,
            limit_price=155.0,
        )

        mock_trade_client.modify_order.assert_called_once()
        assert isinstance(result, dict)

    async def test_modify_order_preserves_gtc_time_in_force(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """modify_order() must set time_in_force='GTC' on the fetched order.

        Without this, the SDK may silently revert a GTC order back to DAY
        when the modification is applied.
        """
        mock_order = MagicMock()
        mock_order.time_in_force = "DAY"  # Simulate SDK default
        mock_trade_client.get_order.return_value = mock_order
        mock_trade_client.modify_order.return_value = 12345

        await tiger_client.modify_order(
            order_id="12345",
            quantity=20,
            limit_price=155.0,
        )

        # The order passed to modify_order must have time_in_force set to GTC
        passed_order = mock_trade_client.modify_order.call_args[0][0]
        assert passed_order.time_in_force == "GTC", (
            "modify_order must explicitly set time_in_force='GTC' "
            "to prevent silent reversion to DAY"
        )

    async def test_cancel_order_calls_sdk(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """cancel_order() should call TradeClient.cancel_order()."""
        mock_trade_client.cancel_order.return_value = 12345

        result = await tiger_client.cancel_order(order_id="12345")

        mock_trade_client.cancel_order.assert_called_once()
        assert isinstance(result, dict)
        assert result["order_id"] == "12345"

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

        result = await tiger_client.get_order_detail(order_id="12345")

        mock_trade_client.get_order.assert_called_once()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Quote methods
# ---------------------------------------------------------------------------


class TestQuoteMethods:
    """Test market data / quote async methods."""

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
    """Test that bar data is not cached."""

    async def test_bars_are_not_cached(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """get_bars() should NOT cache results."""
        df = pd.DataFrame([{"time": "2024-01-01", "open": 148.0}])
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
        mock_trade_client.get_assets.side_effect = Exception("API connection failed")

        with pytest.raises(RuntimeError, match="get_assets.*API connection failed"):
            await tiger_client.get_assets()

    async def test_place_order_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from place_order() should become RuntimeError."""
        mock_trade_client.place_order.side_effect = Exception("Insufficient funds")

        with pytest.raises(RuntimeError, match="place_order.*Insufficient funds"):
            await tiger_client.place_order(
                symbol="AAPL",
                action="BUY",
                quantity=10,
                order_type="limit",
                limit_price=150.0,
            )

    async def test_cancel_order_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from cancel_order() should become RuntimeError."""
        mock_trade_client.cancel_order.side_effect = Exception("Order not found")

        with pytest.raises(RuntimeError, match="cancel_order.*Order not found"):
            await tiger_client.cancel_order(order_id="99999")

    async def test_modify_order_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from modify_order() should become RuntimeError."""
        mock_trade_client.get_order.side_effect = Exception("Order not found")

        with pytest.raises(RuntimeError, match="modify_order.*Order not found"):
            await tiger_client.modify_order(
                order_id="99999",
                quantity=20,
            )

    async def test_get_bars_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_quote_client: MagicMock,
    ) -> None:
        """SDK exception from get_bars() should become RuntimeError."""
        mock_quote_client.get_bars.side_effect = Exception("Invalid period")

        with pytest.raises(RuntimeError, match="get_bars.*Invalid period"):
            await tiger_client.get_bars("AAPL", "invalid_period")

    async def test_get_order_detail_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from get_order_detail() should become RuntimeError."""
        mock_trade_client.get_order.side_effect = Exception("Connection timeout")

        with pytest.raises(RuntimeError, match="get_order_detail.*Connection timeout"):
            await tiger_client.get_order_detail(order_id="12345")


# ---------------------------------------------------------------------------
# _build_order helper
# ---------------------------------------------------------------------------


class TestBuildOrder:
    """Test the _build_order helper method."""

    def test_build_limit_order(self, tiger_client: Any) -> None:
        """_build_order with limit type should use limit_order utility."""
        with patch("tiger_mcp.api.tiger_client.limit_order") as mock_limit_order:
            mock_limit_order.return_value = MagicMock()
            tiger_client._build_order(
                symbol="AAPL",
                action="BUY",
                quantity=10,
                order_type="limit",
                limit_price=150.0,
            )
            mock_limit_order.assert_called_once()
            call_kwargs = mock_limit_order.call_args.kwargs
            assert call_kwargs["time_in_force"] == "GTC", (
                "limit_order must be called with time_in_force='GTC'"
            )

    def test_build_stop_limit_order(self, tiger_client: Any) -> None:
        """_build_order with stop_limit type should use stop_limit_order."""
        with patch("tiger_mcp.api.tiger_client.stop_limit_order") as mock_sl_order:
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
            call_kwargs = mock_sl_order.call_args.kwargs
            assert call_kwargs["time_in_force"] == "GTC", (
                "stop_limit_order must be called with time_in_force='GTC'"
            )

    def test_build_unknown_order_type_raises(self, tiger_client: Any) -> None:
        """_build_order with unknown order type should raise ValueError."""
        with pytest.raises(ValueError, match="(?i)unsupported.*order.*type"):
            tiger_client._build_order(
                symbol="AAPL",
                action="BUY",
                quantity=10,
                order_type="trailing_stop",
            )


# ---------------------------------------------------------------------------
# _parse_order_id helper
# ---------------------------------------------------------------------------


class TestParseOrderId:
    """Test the _parse_order_id module-level helper."""

    def test_parse_order_id_valid(self) -> None:
        """_parse_order_id should convert a valid numeric string to int."""
        assert _parse_order_id("12345") == 12345

    def test_parse_order_id_non_numeric(self) -> None:
        """_parse_order_id should raise ValueError for non-numeric input."""
        with pytest.raises(ValueError, match="numeric string"):
            _parse_order_id("abc")

    def test_parse_order_id_empty(self) -> None:
        """_parse_order_id should raise ValueError for empty string."""
        with pytest.raises(ValueError, match="numeric string"):
            _parse_order_id("")

    def test_parse_order_id_negative(self) -> None:
        """_parse_order_id should raise ValueError for negative values."""
        with pytest.raises(ValueError, match="positive integer"):
            _parse_order_id("-1")


# ---------------------------------------------------------------------------
# _order_to_dict ID field conversion
# ---------------------------------------------------------------------------


class TestOrderToDictIdConversion:
    """Test that _order_to_dict converts ID fields to str."""

    def test_order_to_dict_converts_id_fields_to_str(self, tiger_client: Any) -> None:
        """_order_to_dict should convert id and order_id to str."""
        from tiger_mcp.api.tiger_client import TigerClient

        mock_order = MagicMock()
        mock_order.id = 99999
        mock_order.order_id = 99999
        mock_order.symbol = "AAPL"
        for attr in (
            "order_type",
            "quantity",
            "filled",
            "avg_fill_price",
            "limit_price",
            "aux_price",
            "status",
            "remaining",
            "trade_time",
            "commission",
            "action",
        ):
            setattr(mock_order, attr, None)

        result = TigerClient._order_to_dict(mock_order)

        assert result["id"] == "99999"
        assert isinstance(result["id"], str)
        assert result["order_id"] == "99999"
        assert isinstance(result["order_id"], str)
        assert result["symbol"] == "AAPL"  # non-ID field stays as-is


# ---------------------------------------------------------------------------
# OCA & Bracket order methods
# ---------------------------------------------------------------------------


class TestOcaBracketOrders:
    """Test OCA and bracket order client methods."""

    async def test_build_oca_order_calls_oca_order_util(
        self,
        tiger_client: Any,
    ) -> None:
        """_build_oca_order should call oca_order with correct params."""
        with (
            patch("tiger_mcp.api.tiger_client.oca_order") as mock_oca,
            patch("tiger_mcp.api.tiger_client.order_leg") as mock_leg,
        ):
            mock_leg.side_effect = lambda *a, **kw: MagicMock()
            mock_oca.return_value = MagicMock()

            tiger_client._build_oca_order(
                symbol="AAPL",
                quantity=100,
                tp_limit_price=160.0,
                sl_stop_price=140.0,
                sl_limit_price=138.0,
            )

            mock_oca.assert_called_once()
            call_kwargs = mock_oca.call_args.kwargs
            assert call_kwargs["action"] == "SELL"
            assert call_kwargs["quantity"] == 100

    async def test_build_bracket_order_calls_limit_order_with_legs(
        self,
        tiger_client: Any,
    ) -> None:
        """_build_bracket_order should call limit_order_with_legs."""
        with (
            patch(
                "tiger_mcp.api.tiger_client.limit_order_with_legs",
            ) as mock_bracket,
            patch("tiger_mcp.api.tiger_client.order_leg") as mock_leg,
        ):
            mock_leg.side_effect = lambda *a, **kw: MagicMock()
            mock_bracket.return_value = MagicMock()

            tiger_client._build_bracket_order(
                symbol="AAPL",
                quantity=100,
                entry_limit_price=150.0,
                tp_limit_price=160.0,
                sl_stop_price=140.0,
                sl_limit_price=138.0,
            )

            mock_bracket.assert_called_once()
            call_kwargs = mock_bracket.call_args.kwargs
            assert call_kwargs["action"] == "BUY"
            assert call_kwargs["quantity"] == 100
            assert call_kwargs["limit_price"] == 150.0

    async def test_place_oca_order_returns_order_and_sub_ids(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """place_oca_order should return dict with order_id and sub_ids."""
        with (
            patch("tiger_mcp.api.tiger_client.oca_order") as mock_oca,
            patch("tiger_mcp.api.tiger_client.order_leg"),
        ):
            mock_order = MagicMock()
            mock_order.id = 12345
            leg1 = MagicMock()
            leg1.id = 12346
            leg2 = MagicMock()
            leg2.id = 12347
            mock_order.order_legs = [leg1, leg2]
            mock_oca.return_value = mock_order

            result = await tiger_client.place_oca_order(
                symbol="AAPL",
                quantity=100,
                tp_limit_price=160.0,
                sl_stop_price=140.0,
                sl_limit_price=138.0,
            )

            assert result["order_id"] == "12345"
            assert result["sub_ids"] == ["12346", "12347"]
            assert result["action"] == "SELL"

    async def test_place_bracket_order_returns_order_and_sub_ids(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """place_bracket_order should return dict with order_id and sub_ids."""
        with (
            patch(
                "tiger_mcp.api.tiger_client.limit_order_with_legs",
            ) as mock_bracket,
            patch("tiger_mcp.api.tiger_client.order_leg"),
        ):
            mock_order = MagicMock()
            mock_order.id = 22345
            leg1 = MagicMock()
            leg1.id = 22346
            leg2 = MagicMock()
            leg2.id = 22347
            mock_order.order_legs = [leg1, leg2]
            mock_bracket.return_value = mock_order

            result = await tiger_client.place_bracket_order(
                symbol="AAPL",
                quantity=100,
                entry_limit_price=150.0,
                tp_limit_price=160.0,
                sl_stop_price=140.0,
                sl_limit_price=138.0,
            )

            assert result["order_id"] == "22345"
            assert result["sub_ids"] == ["22346", "22347"]
            assert result["action"] == "BUY"

    async def test_place_oca_order_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from place_oca_order should become RuntimeError."""
        with (
            patch("tiger_mcp.api.tiger_client.oca_order") as mock_oca,
            patch("tiger_mcp.api.tiger_client.order_leg"),
        ):
            mock_oca.return_value = MagicMock()
            mock_trade_client.place_order.side_effect = Exception("OCA failed")

            with pytest.raises(RuntimeError, match="place_oca_order.*OCA failed"):
                await tiger_client.place_oca_order(
                    symbol="AAPL",
                    quantity=100,
                    tp_limit_price=160.0,
                    sl_stop_price=140.0,
                    sl_limit_price=138.0,
                )

    async def test_place_bracket_order_error_wraps_exception(
        self,
        tiger_client: Any,
        mock_trade_client: MagicMock,
    ) -> None:
        """SDK exception from place_bracket_order should become RuntimeError."""
        with (
            patch(
                "tiger_mcp.api.tiger_client.limit_order_with_legs",
            ) as mock_bracket,
            patch("tiger_mcp.api.tiger_client.order_leg"),
        ):
            mock_bracket.return_value = MagicMock()
            mock_trade_client.place_order.side_effect = Exception("Bracket failed")

            with pytest.raises(
                RuntimeError, match="place_bracket_order.*Bracket failed"
            ):
                await tiger_client.place_bracket_order(
                    symbol="AAPL",
                    quantity=100,
                    entry_limit_price=150.0,
                    tp_limit_price=160.0,
                    sl_stop_price=140.0,
                    sl_limit_price=138.0,
                )
