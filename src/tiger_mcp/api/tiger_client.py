"""Tiger API client wrapping the tigeropen SDK.

Provides an async interface over the synchronous tigeropen ``TradeClient``
and ``QuoteClient`` by running all blocking SDK calls in a thread-pool
executor.  Quote data is cached for 30 seconds to reduce API load.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import time
from typing import Any

from tigeropen.common.consts import BarPeriod, Language, OrderStatus
from tigeropen.common.util.contract_utils import stock_contract
from tigeropen.common.util.order_utils import (
    limit_order,
    market_order,
    stop_limit_order,
    stop_order,
)
from tigeropen.quote.quote_client import QuoteClient
from tigeropen.tiger_open_config import TigerOpenClientConfig
from tigeropen.trade.trade_client import TradeClient

from tiger_mcp.config import Settings

logger = logging.getLogger(__name__)

# How long (seconds) quote data is considered fresh.
_QUOTE_CACHE_TTL: float = 30.0

# Bar-period lookup from user-facing strings to SDK enums.
_BAR_PERIOD_MAP: dict[str, BarPeriod] = {
    "1min": BarPeriod.ONE_MINUTE,
    "3min": BarPeriod.THREE_MINUTES,
    "5min": BarPeriod.FIVE_MINUTES,
    "10min": BarPeriod.TEN_MINUTES,
    "15min": BarPeriod.FIFTEEN_MINUTES,
    "30min": BarPeriod.HALF_HOUR,
    "45min": BarPeriod.FORTY_FIVE_MINUTES,
    "60min": BarPeriod.ONE_HOUR,
    "2hour": BarPeriod.TWO_HOURS,
    "3hour": BarPeriod.THREE_HOURS,
    "4hour": BarPeriod.FOUR_HOURS,
    "6hour": BarPeriod.SIX_HOURS,
    "day": BarPeriod.DAY,
    "week": BarPeriod.WEEK,
    "month": BarPeriod.MONTH,
    "year": BarPeriod.YEAR,
}

# Order states that indicate an order is still active / open.
_OPEN_ORDER_STATES = [
    OrderStatus.NEW,
    OrderStatus.HELD,
    OrderStatus.PENDING_NEW,
    OrderStatus.PARTIALLY_FILLED,
]


class TigerClient:
    """Async wrapper around the tigeropen Trade and Quote clients.

    All SDK calls are dispatched to a thread-pool executor so they do not
    block the asyncio event loop.

    Parameters
    ----------
    config:
        A ``Settings`` instance providing credentials and runtime options.
    """

    def __init__(self, config: Settings) -> None:
        client_config = TigerOpenClientConfig(sandbox_debug=False)
        client_config.private_key = config.private_key_path.read_text()
        client_config.tiger_id = config.tiger_id
        client_config.account = config.tiger_account
        client_config.language = Language.en_US

        self._trade_client = TradeClient(client_config)
        self._quote_client = QuoteClient(client_config)
        self._account = config.tiger_account

        # Simple dict-based cache:  key -> (value, monotonic_timestamp)
        self._quote_cache: dict[str, tuple[Any, float]] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _run_sync(self, func: Any, *args: Any) -> Any:
        """Run a synchronous *func* in the default thread-pool executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, functools.partial(func, *args))

    def _build_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> Any:
        """Build a tigeropen ``Order`` object for the given parameters.

        Raises
        ------
        ValueError
            If *order_type* is not one of ``market``, ``limit``, ``stop``,
            or ``stop_limit``.
        """
        contract = stock_contract(symbol=symbol, currency="USD")

        if order_type == "market":
            return market_order(
                account=self._account,
                contract=contract,
                action=action,
                quantity=quantity,
            )
        if order_type == "limit":
            return limit_order(
                account=self._account,
                contract=contract,
                action=action,
                quantity=quantity,
                limit_price=limit_price,
            )
        if order_type == "stop":
            return stop_order(
                account=self._account,
                contract=contract,
                action=action,
                quantity=quantity,
                aux_price=stop_price,
            )
        if order_type == "stop_limit":
            return stop_limit_order(
                account=self._account,
                contract=contract,
                action=action,
                quantity=quantity,
                limit_price=limit_price,
                aux_price=stop_price,
            )

        msg = f"Unsupported order type: {order_type!r}"
        raise ValueError(msg)

    def _cache_key(self, prefix: str, *parts: Any) -> str:
        """Build a string cache key from a prefix and variable parts."""
        return f"{prefix}:{':'.join(str(p) for p in parts)}"

    def _get_cached(self, key: str) -> Any | None:
        """Return cached value if it exists and is not expired."""
        entry = self._quote_cache.get(key)
        if entry is None:
            return None
        value, ts = entry
        if time.monotonic() - ts > _QUOTE_CACHE_TTL:
            del self._quote_cache[key]
            return None
        return value

    def _set_cached(self, key: str, value: Any) -> None:
        """Store *value* in the cache with the current timestamp."""
        self._quote_cache[key] = (value, time.monotonic())

    @staticmethod
    def _order_to_dict(order: Any) -> dict[str, Any]:
        """Convert a tigeropen Order object to a plain dict."""
        result: dict[str, Any] = {}
        for attr in (
            "id",
            "order_id",
            "symbol",
            "action",
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
        ):
            val = getattr(order, attr, None)
            if val is not None:
                result[attr] = val
        return result

    @staticmethod
    def _position_to_dict(pos: Any) -> dict[str, Any]:
        """Convert a tigeropen Position object to a plain dict."""
        result: dict[str, Any] = {}
        for attr in (
            "symbol",
            "quantity",
            "average_cost",
            "market_price",
            "market_value",
            "unrealized_pnl",
            "realized_pnl",
        ):
            val = getattr(pos, attr, None)
            if val is not None:
                result[attr] = val
        return result

    # ------------------------------------------------------------------
    # Account methods
    # ------------------------------------------------------------------

    async def get_assets(self) -> dict[str, Any]:
        """Retrieve account asset summary.

        Returns a dict with account-level financial data such as
        net liquidation value, cash balance, etc.
        """
        try:
            assets = await self._run_sync(self._trade_client.get_assets)
            return assets.summary()
        except Exception as exc:
            msg = f"get_assets failed: {exc}"
            raise RuntimeError(msg) from exc

    async def get_positions(self) -> list[dict[str, Any]]:
        """Retrieve all current positions.

        Returns a list of dicts, one per position.  Returns an empty
        list when there are no positions.
        """
        try:
            positions = await self._run_sync(
                self._trade_client.get_positions,
            )
            if positions is None:
                return []
            return [self._position_to_dict(p) for p in positions]
        except Exception as exc:
            msg = f"get_positions failed: {exc}"
            raise RuntimeError(msg) from exc

    async def get_order_transactions(
        self,
        symbol: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retrieve filled order transactions (trade history).

        Parameters
        ----------
        symbol:
            Filter by ticker symbol.
        start_date:
            Start date string for the query range.
        end_date:
            End date string for the query range.
        limit:
            Maximum number of records to return.
        """
        try:
            kwargs: dict[str, Any] = {}
            if symbol is not None:
                kwargs["symbol"] = symbol
            if start_date is not None:
                kwargs["start_time"] = start_date
            if end_date is not None:
                kwargs["end_time"] = end_date

            orders = await self._run_sync(
                functools.partial(
                    self._trade_client.get_filled_orders, **kwargs
                ),
            )
            if orders is None:
                return []
            result = [self._order_to_dict(o) for o in orders]
            return result[:limit]
        except Exception as exc:
            msg = f"get_order_transactions failed: {exc}"
            raise RuntimeError(msg) from exc

    # ------------------------------------------------------------------
    # Order methods
    # ------------------------------------------------------------------

    async def preview_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> dict[str, Any]:
        """Preview an order without placing it.

        Returns a dict with estimated commission, margin impact, etc.
        """
        try:
            order = self._build_order(
                symbol, action, quantity, order_type, limit_price, stop_price
            )
            preview = await self._run_sync(
                self._trade_client.preview_order, order
            )
            if hasattr(preview, "__dict__"):
                return vars(preview)
            return {"preview": preview}
        except Exception as exc:
            msg = f"preview_order failed: {exc}"
            raise RuntimeError(msg) from exc

    async def place_order(
        self,
        symbol: str,
        action: str,
        quantity: int,
        order_type: str,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> dict[str, Any]:
        """Place an order and return the order ID.

        Returns a dict containing at minimum ``{"order_id": <int>}``.
        """
        try:
            order = self._build_order(
                symbol, action, quantity, order_type, limit_price, stop_price
            )
            order_id = await self._run_sync(
                self._trade_client.place_order, order
            )
            return {
                "order_id": order_id,
                "symbol": symbol,
                "action": action,
                "quantity": quantity,
                "order_type": order_type,
            }
        except Exception as exc:
            msg = f"place_order failed: {exc}"
            raise RuntimeError(msg) from exc

    async def modify_order(
        self,
        order_id: int,
        quantity: int | None = None,
        limit_price: float | None = None,
        stop_price: float | None = None,
    ) -> dict[str, Any]:
        """Modify an existing order.

        Fetches the current order, then applies the requested changes.
        """
        try:
            order = await self._run_sync(
                functools.partial(
                    self._trade_client.get_order, id=order_id
                ),
            )

            kwargs: dict[str, Any] = {}
            if quantity is not None:
                kwargs["quantity"] = quantity
            if limit_price is not None:
                kwargs["limit_price"] = limit_price
            if stop_price is not None:
                kwargs["aux_price"] = stop_price

            result = await self._run_sync(
                functools.partial(
                    self._trade_client.modify_order, order, **kwargs
                ),
            )
            return {"order_id": order_id, "modified": True, "result": result}
        except Exception as exc:
            msg = f"modify_order failed: {exc}"
            raise RuntimeError(msg) from exc

    async def cancel_order(self, order_id: int) -> dict[str, Any]:
        """Cancel a single order by its ID."""
        try:
            result = await self._run_sync(
                functools.partial(
                    self._trade_client.cancel_order, id=order_id
                ),
            )
            return {"order_id": order_id, "cancelled": True, "result": result}
        except Exception as exc:
            msg = f"cancel_order failed: {exc}"
            raise RuntimeError(msg) from exc

    async def cancel_all_orders(self) -> list[dict[str, Any]]:
        """Cancel all open orders.

        Fetches open orders first, then cancels each one individually.
        Returns a list of cancellation results.
        """
        try:
            open_orders = await self._run_sync(
                functools.partial(
                    self._trade_client.get_orders, states=_OPEN_ORDER_STATES
                ),
            )
            if not open_orders:
                return []

            results: list[dict[str, Any]] = []
            for order in open_orders:
                cancel_result = await self._run_sync(
                    functools.partial(
                        self._trade_client.cancel_order, id=order.id
                    ),
                )
                results.append(
                    {
                        "order_id": order.id,
                        "cancelled": True,
                        "result": cancel_result,
                    }
                )
            return results
        except Exception as exc:
            msg = f"cancel_all_orders failed: {exc}"
            raise RuntimeError(msg) from exc

    async def get_open_orders(
        self, symbol: str | None = None
    ) -> list[dict[str, Any]]:
        """Get all currently open orders, optionally filtered by symbol."""
        try:
            kwargs: dict[str, Any] = {"states": _OPEN_ORDER_STATES}
            if symbol is not None:
                kwargs["symbol"] = symbol

            orders = await self._run_sync(
                functools.partial(self._trade_client.get_orders, **kwargs),
            )
            if orders is None:
                return []
            return [self._order_to_dict(o) for o in orders]
        except Exception as exc:
            msg = f"get_open_orders failed: {exc}"
            raise RuntimeError(msg) from exc

    async def get_order_detail(self, order_id: int) -> dict[str, Any]:
        """Get detailed information about a specific order."""
        try:
            order = await self._run_sync(
                functools.partial(
                    self._trade_client.get_order, id=order_id
                ),
            )
            return self._order_to_dict(order)
        except Exception as exc:
            msg = f"get_order_detail failed: {exc}"
            raise RuntimeError(msg) from exc

    # ------------------------------------------------------------------
    # Quote methods (with caching)
    # ------------------------------------------------------------------

    async def get_quote(self, symbol: str) -> dict[str, Any]:
        """Get a real-time quote for a single symbol.

        Results are cached for 30 seconds.
        """
        cache_key = self._cache_key("quote", symbol)
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            df = await self._run_sync(
                self._quote_client.get_stock_briefs, [symbol]
            )
            records = df.to_dict(orient="records")
            result = records[0] if records else {}
            self._set_cached(cache_key, result)
            return result
        except Exception as exc:
            msg = f"get_quote failed: {exc}"
            raise RuntimeError(msg) from exc

    async def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Get real-time quotes for multiple symbols.

        Results are cached for 30 seconds.  The cache key is based on the
        sorted symbol list so that order does not matter.
        """
        cache_key = self._cache_key("quotes", *sorted(symbols))
        cached = self._get_cached(cache_key)
        if cached is not None:
            return cached

        try:
            df = await self._run_sync(
                self._quote_client.get_stock_briefs, symbols
            )
            result = df.to_dict(orient="records")
            self._set_cached(cache_key, result)
            return result
        except Exception as exc:
            msg = f"get_quotes failed: {exc}"
            raise RuntimeError(msg) from exc

    async def get_bars(
        self,
        symbol: str,
        period: str,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get historical OHLCV bars for a symbol.

        Parameters
        ----------
        symbol:
            Ticker symbol.
        period:
            Bar period string, e.g. ``"day"``, ``"1min"``, ``"week"``.
        limit:
            Maximum number of bars to return.

        Note: Bar data is NOT cached.
        """
        try:
            bar_period = _BAR_PERIOD_MAP.get(period, period)
            df = await self._run_sync(
                functools.partial(
                    self._quote_client.get_bars,
                    symbols=symbol,
                    period=bar_period,
                    limit=limit,
                ),
            )
            return df.to_dict(orient="records")
        except Exception as exc:
            msg = f"get_bars failed: {exc}"
            raise RuntimeError(msg) from exc
