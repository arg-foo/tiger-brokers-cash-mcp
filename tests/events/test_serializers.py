"""Tests for event serializers.

Verifies that ``serialize_order_status`` correctly converts PushClient
``OrderStatusData`` protobuf objects to JSON-serializable dicts using
the defensive ``getattr`` pattern.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import orjson
import pytest

from tiger_mcp.events.serializers import serialize_order_status

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# All fields that the serializer is expected to extract.
ALL_FIELDS: tuple[str, ...] = (
    "id",
    "account",
    "symbol",
    "action",
    "status",
    "order_type",
    "total_quantity",
    "filled_quantity",
    "avg_fill_price",
    "limit_price",
    "stop_price",
    "timestamp",
    "order_id",
    "currency",
    "remaining",
    "trade_time",
    "name",
    "latestPrice",
)


@pytest.fixture()
def full_frame() -> MagicMock:
    """Return a mock frame with all recognized fields populated."""
    frame = MagicMock(spec=ALL_FIELDS)
    frame.id = 12345
    frame.account = "DU12345"
    frame.symbol = "AAPL"
    frame.action = "BUY"
    frame.status = "Filled"
    frame.order_type = "LMT"
    frame.total_quantity = 100
    frame.filled_quantity = 100
    frame.avg_fill_price = 175.50
    frame.limit_price = 176.00
    frame.stop_price = 174.00
    frame.timestamp = 1700000000000
    frame.order_id = 67890
    frame.currency = "USD"
    frame.remaining = 0
    frame.trade_time = "2024-01-15 10:30:00"
    frame.name = "Apple Inc"
    frame.latestPrice = 175.75
    return frame


@pytest.fixture()
def partial_frame() -> MagicMock:
    """Return a mock frame with only a subset of fields populated."""
    frame = MagicMock(spec=["id", "symbol", "action", "status"])
    frame.id = 99999
    frame.symbol = "TSLA"
    frame.action = "SELL"
    frame.status = "PendingNew"
    return frame


@pytest.fixture()
def empty_frame() -> MagicMock:
    """Return a mock frame with no recognized attributes."""
    # spec=[] means no attributes exist on this mock
    frame = MagicMock(spec=[])
    return frame


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSerializeOrderStatus:
    """Tests for the ``serialize_order_status`` function."""

    def test_serialize_all_fields(self, full_frame: MagicMock) -> None:
        """When the frame has all recognized fields, all appear in result."""
        result = serialize_order_status(full_frame)

        assert result["id"] == 12345
        assert result["account"] == "DU12345"
        assert result["symbol"] == "AAPL"
        assert result["action"] == "BUY"
        assert result["status"] == "Filled"
        assert result["order_type"] == "LMT"
        assert result["total_quantity"] == 100
        assert result["filled_quantity"] == 100
        assert result["avg_fill_price"] == 175.50
        assert result["limit_price"] == 176.00
        assert result["stop_price"] == 174.00
        assert result["timestamp"] == 1700000000000
        assert result["order_id"] == 67890
        assert result["currency"] == "USD"
        assert result["remaining"] == 0
        assert result["trade_time"] == "2024-01-15 10:30:00"
        assert result["name"] == "Apple Inc"
        assert result["latestPrice"] == 175.75
        assert len(result) == len(ALL_FIELDS)

    def test_serialize_missing_fields_omitted(self) -> None:
        """Attributes not present on the frame are silently omitted."""
        frame = MagicMock(spec=["id", "symbol"])
        frame.id = 1
        frame.symbol = "GOOG"

        result = serialize_order_status(frame)

        assert "id" in result
        assert "symbol" in result
        # Fields that don't exist on the frame must not appear
        assert "account" not in result
        assert "action" not in result
        assert "status" not in result
        assert "order_type" not in result
        assert "total_quantity" not in result

    def test_serialize_none_fields_included(self) -> None:
        """Attributes explicitly set to None are included in result."""
        frame = MagicMock(spec=["id", "symbol", "action", "limit_price"])
        frame.id = 42
        frame.symbol = "MSFT"
        frame.action = None
        frame.limit_price = None

        result = serialize_order_status(frame)

        assert result["id"] == 42
        assert result["symbol"] == "MSFT"
        # None values are now included (attribute exists on the frame)
        assert result["action"] is None
        assert result["limit_price"] is None

    def test_serialize_partial_fields(self, partial_frame: MagicMock) -> None:
        """Only fields present on the frame appear in the result."""
        result = serialize_order_status(partial_frame)

        assert result == {
            "id": 99999,
            "symbol": "TSLA",
            "action": "SELL",
            "status": "PendingNew",
        }
        # Verify no extra keys leaked in
        assert set(result.keys()) == {"id", "symbol", "action", "status"}

    def test_serialize_empty_frame(self, empty_frame: MagicMock) -> None:
        """A frame with no recognized attributes produces an empty dict."""
        result = serialize_order_status(empty_frame)

        assert result == {}
        assert isinstance(result, dict)

    def test_result_is_json_serializable(self, full_frame: MagicMock) -> None:
        """The result dict can be serialized with orjson without error."""
        result = serialize_order_status(full_frame)

        # orjson.dumps returns bytes; should not raise
        serialized = orjson.dumps(result)
        assert isinstance(serialized, bytes)

        # Round-trip: deserialize and verify equality
        deserialized = orjson.loads(serialized)
        assert deserialized == result

    def test_zero_and_falsy_values_preserved(self) -> None:
        """Zero, 0.0, False, and empty string are preserved (not dropped)."""
        frame = MagicMock(
            spec=[
                "filled_quantity",
                "remaining",
                "avg_fill_price",
                "action",
                "status",
            ]
        )
        frame.filled_quantity = 0
        frame.remaining = 0
        frame.avg_fill_price = 0.0
        frame.action = ""
        frame.status = False

        result = serialize_order_status(frame)

        assert result["filled_quantity"] == 0
        assert result["remaining"] == 0
        assert result["avg_fill_price"] == 0.0
        assert result["action"] == ""
        assert result["status"] is False

    def test_numeric_fields_preserved(self) -> None:
        """Integer and float values are preserved with exact types."""
        frame = MagicMock(
            spec=[
                "id",
                "total_quantity",
                "filled_quantity",
                "avg_fill_price",
                "limit_price",
                "stop_price",
                "remaining",
                "latestPrice",
            ]
        )
        frame.id = 11111
        frame.total_quantity = 500
        frame.filled_quantity = 250
        frame.avg_fill_price = 99.9999
        frame.limit_price = 100.00
        frame.stop_price = 98.50
        frame.remaining = 250
        frame.latestPrice = 99.75

        result = serialize_order_status(frame)

        # Integers remain ints
        assert isinstance(result["id"], int)
        assert result["id"] == 11111
        assert isinstance(result["total_quantity"], int)
        assert result["total_quantity"] == 500
        assert isinstance(result["filled_quantity"], int)
        assert result["filled_quantity"] == 250
        assert isinstance(result["remaining"], int)
        assert result["remaining"] == 250

        # Floats remain floats with exact values
        assert isinstance(result["avg_fill_price"], float)
        assert result["avg_fill_price"] == 99.9999
        assert isinstance(result["limit_price"], float)
        assert result["limit_price"] == 100.00
        assert isinstance(result["stop_price"], float)
        assert result["stop_price"] == 98.50
        assert isinstance(result["latestPrice"], float)
        assert result["latestPrice"] == 99.75
