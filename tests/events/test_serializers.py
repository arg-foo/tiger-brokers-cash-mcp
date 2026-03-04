"""Tests for event serializers.

Verifies that ``serialize_order_status`` correctly converts PushClient
``OrderStatusData`` protobuf objects to JSON-serializable dicts using
the defensive ``getattr`` pattern with correct camelCase field names.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import orjson
import pytest

from tiger_mcp.events.models import (
    ORDER_STATUS_FIELD_NAMES,
    TRANSACTION_FIELD_NAMES,
)
from tiger_mcp.events.serializers import (
    serialize_order_status,
    serialize_transaction,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def full_frame() -> MagicMock:
    """Return a mock frame with all recognized fields populated."""
    frame = MagicMock(spec=list(ORDER_STATUS_FIELD_NAMES))
    # Identity
    frame.id = 12345
    frame.account = "DU12345"
    frame.symbol = "AAPL"
    frame.identifier = "AAPL"
    frame.name = "Apple Inc"
    # Contract details
    frame.secType = "STK"
    frame.market = "US"
    frame.currency = "USD"
    frame.multiplier = 1
    frame.expiry = ""
    frame.strike = ""
    frame.right = ""
    # Order parameters
    frame.action = "BUY"
    frame.orderType = "LMT"
    frame.timeInForce = "DAY"
    frame.isLong = True
    frame.outsideRth = False
    frame.totalQuantity = 100
    frame.totalQuantityScale = 0
    frame.limitPrice = 176.00
    frame.stopPrice = 0.0
    frame.totalCashAmount = 0.0
    # Fill data
    frame.filledQuantity = 100
    frame.filledQuantityScale = 0
    frame.avgFillPrice = 175.50
    frame.filledCashAmount = 17550.0
    frame.commissionAndFee = 1.99
    frame.realizedPnl = 0.0
    # Status
    frame.status = "FILLED"
    frame.replaceStatus = ""
    frame.cancelStatus = ""
    frame.canModify = False
    frame.canCancel = False
    frame.liquidation = False
    frame.errorMsg = ""
    # Timestamps
    frame.openTime = 1700000000000
    frame.timestamp = 1700000060000
    # Metadata
    frame.source = "OpenApi"
    frame.userMark = ""
    frame.segType = "S"
    frame.attrDesc = ""
    frame.gst = 0.0
    return frame


@pytest.fixture()
def partial_frame() -> MagicMock:
    """Return a mock frame with only core fields populated."""
    frame = MagicMock(spec=["id", "symbol", "action", "status"])
    frame.id = 99999
    frame.symbol = "TSLA"
    frame.action = "SELL"
    frame.status = "PendingNew"
    return frame


@pytest.fixture()
def empty_frame() -> MagicMock:
    """Return a mock frame with no recognized attributes."""
    frame = MagicMock(spec=[])
    return frame


@pytest.fixture()
def full_transaction_frame() -> MagicMock:
    """Return a mock transaction frame with all 17 recognized fields populated."""
    frame = MagicMock(spec=list(TRANSACTION_FIELD_NAMES))
    # Identity
    frame.id = 98765
    frame.orderId = 12345
    frame.account = "DU12345"
    frame.symbol = "AAPL"
    frame.identifier = "AAPL"
    # Contract details
    frame.multiplier = 1.0
    frame.action = "BUY"
    frame.market = "US"
    frame.currency = "USD"
    frame.segType = "S"
    frame.secType = "STK"
    # Fill data
    frame.filledPrice = 175.50
    frame.filledQuantity = 20
    # Timestamps
    frame.createTime = 1700000000000
    frame.updateTime = 1700000050000
    frame.transactTime = 1700000060000
    frame.timestamp = 1700000060000
    return frame


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSerializeOrderStatus:
    """Tests for the ``serialize_order_status`` function."""

    def test_serialize_all_fields(self, full_frame: MagicMock) -> None:
        """When the frame has all recognized fields, all appear in result."""
        result = serialize_order_status(full_frame)

        # Identity (id is converted to string to prevent JS precision loss)
        assert result["id"] == "12345"
        assert result["account"] == "DU12345"
        assert result["symbol"] == "AAPL"
        assert result["identifier"] == "AAPL"
        assert result["name"] == "Apple Inc"
        # Contract
        assert result["secType"] == "STK"
        assert result["market"] == "US"
        assert result["currency"] == "USD"
        assert result["multiplier"] == 1
        # Order
        assert result["action"] == "BUY"
        assert result["orderType"] == "LMT"
        assert result["timeInForce"] == "DAY"
        assert result["totalQuantity"] == 100
        assert result["limitPrice"] == 176.00
        # Fill data
        assert result["filledQuantity"] == 100
        assert result["avgFillPrice"] == 175.50
        assert result["filledCashAmount"] == 17550.0
        assert result["commissionAndFee"] == pytest.approx(1.99)
        # Status
        assert result["status"] == "FILLED"
        # Timestamps
        assert result["openTime"] == 1700000000000
        assert result["timestamp"] == 1700000060000
        # All fields present
        assert len(result) == len(ORDER_STATUS_FIELD_NAMES)

    def test_serialize_missing_fields_omitted(self) -> None:
        """Attributes not present on the frame are silently omitted."""
        frame = MagicMock(spec=["id", "symbol"])
        frame.id = 1
        frame.symbol = "GOOG"

        result = serialize_order_status(frame)

        assert result["id"] == "1"
        assert "symbol" in result
        assert "account" not in result
        assert "action" not in result
        assert "status" not in result
        assert "orderType" not in result
        assert "totalQuantity" not in result

    def test_serialize_none_fields_included(self) -> None:
        """Attributes explicitly set to None are included in result."""
        frame = MagicMock(spec=["id", "symbol", "action", "limitPrice"])
        frame.id = 42
        frame.symbol = "MSFT"
        frame.action = None
        frame.limitPrice = None

        result = serialize_order_status(frame)

        assert result["id"] == "42"
        assert result["symbol"] == "MSFT"
        assert result["action"] is None
        assert result["limitPrice"] is None

    def test_serialize_partial_fields(self, partial_frame: MagicMock) -> None:
        """Only fields present on the frame appear in the result."""
        result = serialize_order_status(partial_frame)

        assert result == {
            "id": "99999",
            "symbol": "TSLA",
            "action": "SELL",
            "status": "PendingNew",
        }
        assert set(result.keys()) == {"id", "symbol", "action", "status"}

    def test_serialize_empty_frame(self, empty_frame: MagicMock) -> None:
        """A frame with no recognized attributes produces an empty dict."""
        result = serialize_order_status(empty_frame)

        assert result == {}
        assert isinstance(result, dict)

    def test_result_is_json_serializable(self, full_frame: MagicMock) -> None:
        """The result dict can be serialized with orjson without error."""
        result = serialize_order_status(full_frame)

        serialized = orjson.dumps(result)
        assert isinstance(serialized, bytes)

        deserialized = orjson.loads(serialized)
        assert deserialized == result

    def test_zero_and_falsy_values_preserved(self) -> None:
        """Zero, 0.0, False, and empty string are preserved (not dropped)."""
        frame = MagicMock(
            spec=[
                "filledQuantity",
                "stopPrice",
                "avgFillPrice",
                "action",
                "outsideRth",
            ]
        )
        frame.filledQuantity = 0
        frame.stopPrice = 0.0
        frame.avgFillPrice = 0.0
        frame.action = ""
        frame.outsideRth = False

        result = serialize_order_status(frame)

        assert result["filledQuantity"] == 0
        assert result["stopPrice"] == 0.0
        assert result["avgFillPrice"] == 0.0
        assert result["action"] == ""
        assert result["outsideRth"] is False

    def test_numeric_fields_preserved(self) -> None:
        """Integer and float values are preserved with exact types.

        Note: ``id`` is converted to string for JS precision safety.
        """
        frame = MagicMock(
            spec=[
                "id",
                "totalQuantity",
                "filledQuantity",
                "avgFillPrice",
                "limitPrice",
                "stopPrice",
                "commissionAndFee",
            ]
        )
        frame.id = 11111
        frame.totalQuantity = 500
        frame.filledQuantity = 250
        frame.avgFillPrice = 99.9999
        frame.limitPrice = 100.00
        frame.stopPrice = 98.50
        frame.commissionAndFee = 2.50

        result = serialize_order_status(frame)

        assert isinstance(result["id"], str)
        assert result["id"] == "11111"
        assert isinstance(result["totalQuantity"], int)
        assert result["totalQuantity"] == 500
        assert isinstance(result["filledQuantity"], int)
        assert result["filledQuantity"] == 250
        assert isinstance(result["avgFillPrice"], float)
        assert result["avgFillPrice"] == 99.9999
        assert isinstance(result["limitPrice"], float)
        assert result["limitPrice"] == 100.00
        assert isinstance(result["stopPrice"], float)
        assert result["stopPrice"] == 98.50

    def test_id_converted_to_string_for_js_precision(self) -> None:
        """id must be a string to prevent JavaScript Number precision loss."""
        large_id = 2**53 + 1  # exceeds JS Number.MAX_SAFE_INTEGER
        frame = MagicMock(spec=["id"])
        frame.id = large_id

        result = serialize_order_status(frame)

        assert isinstance(result["id"], str)
        assert result["id"] == str(large_id)

    def test_id_none_is_not_coerced_to_string_none(self) -> None:
        """id=None must be preserved as None, not converted to the string 'None'."""
        frame = MagicMock(spec=["id", "symbol"])
        frame.id = None
        frame.symbol = "AAPL"

        result = serialize_order_status(frame)

        assert result["id"] is None
        assert result["symbol"] == "AAPL"

    def test_partial_fill_scenario(self) -> None:
        """Verify cumulative fill fields for a partially filled order."""
        frame = MagicMock(
            spec=[
                "id",
                "symbol",
                "action",
                "status",
                "totalQuantity",
                "filledQuantity",
                "avgFillPrice",
            ]
        )
        frame.id = 55555
        frame.symbol = "AAPL"
        frame.action = "BUY"
        frame.status = "PARTIALLY_FILLED"
        frame.totalQuantity = 100
        frame.filledQuantity = 40  # Cumulative: 20 + 20
        frame.avgFillPrice = 175.25

        result = serialize_order_status(frame)

        assert result["id"] == "55555"
        assert result["totalQuantity"] == 100
        assert result["filledQuantity"] == 40
        assert result["avgFillPrice"] == 175.25
        assert result["status"] == "PARTIALLY_FILLED"


# ---------------------------------------------------------------------------
# Transaction serializer tests
# ---------------------------------------------------------------------------


class TestSerializeTransaction:
    """Tests for the ``serialize_transaction`` function."""

    def test_serialize_all_fields(
        self, full_transaction_frame: MagicMock
    ) -> None:
        """When the frame has all 17 recognized fields, all appear in result."""
        result = serialize_transaction(full_transaction_frame)

        # Identity (id and orderId are converted to strings for JS precision safety)
        assert result["id"] == "98765"
        assert result["orderId"] == "12345"
        assert result["account"] == "DU12345"
        assert result["symbol"] == "AAPL"
        assert result["identifier"] == "AAPL"
        # Contract details
        assert result["multiplier"] == 1.0
        assert result["action"] == "BUY"
        assert result["market"] == "US"
        assert result["currency"] == "USD"
        assert result["segType"] == "S"
        assert result["secType"] == "STK"
        # Fill data
        assert result["filledPrice"] == 175.50
        assert result["filledQuantity"] == 20
        # Timestamps
        assert result["createTime"] == 1700000000000
        assert result["updateTime"] == 1700000050000
        assert result["transactTime"] == 1700000060000
        assert result["timestamp"] == 1700000060000
        # All 17 fields present
        assert len(result) == 17
        assert len(result) == len(TRANSACTION_FIELD_NAMES)

    def test_serialize_missing_fields_omitted(self) -> None:
        """Attributes not present on the frame are silently omitted."""
        frame = MagicMock(spec=["id", "orderId", "symbol"])
        frame.id = 1
        frame.orderId = 2
        frame.symbol = "GOOG"

        result = serialize_transaction(frame)

        assert result["id"] == "1"
        assert result["orderId"] == "2"
        assert "symbol" in result
        assert "account" not in result
        assert "action" not in result
        assert "filledPrice" not in result
        assert "filledQuantity" not in result
        assert "transactTime" not in result

    def test_serialize_none_fields_included(self) -> None:
        """Attributes explicitly set to None are included in result."""
        frame = MagicMock(spec=["id", "symbol", "action", "filledPrice"])
        frame.id = 42
        frame.symbol = "MSFT"
        frame.action = None
        frame.filledPrice = None

        result = serialize_transaction(frame)

        assert result["id"] == "42"
        assert result["symbol"] == "MSFT"
        assert result["action"] is None
        assert result["filledPrice"] is None

    def test_serialize_falsy_values_preserved(self) -> None:
        """Zero, 0.0, False, and empty string are preserved (not dropped)."""
        frame = MagicMock(
            spec=[
                "filledQuantity",
                "filledPrice",
                "multiplier",
                "action",
                "segType",
            ]
        )
        frame.filledQuantity = 0
        frame.filledPrice = 0.0
        frame.multiplier = False
        frame.action = ""
        frame.segType = ""

        result = serialize_transaction(frame)

        assert result["filledQuantity"] == 0
        assert result["filledPrice"] == 0.0
        assert result["multiplier"] is False
        assert result["action"] == ""
        assert result["segType"] == ""

    def test_numeric_fields_preserved(self) -> None:
        """Integer and float values are preserved with exact types.

        Note: ``id`` and ``orderId`` are converted to strings for JS
        precision safety.
        """
        frame = MagicMock(
            spec=[
                "id",
                "orderId",
                "filledPrice",
                "filledQuantity",
                "multiplier",
                "createTime",
                "updateTime",
                "transactTime",
                "timestamp",
            ]
        )
        frame.id = 11111
        frame.orderId = 22222
        frame.filledPrice = 99.9999
        frame.filledQuantity = 250
        frame.multiplier = 1.0
        frame.createTime = 1700000000000
        frame.updateTime = 1700000050000
        frame.transactTime = 1700000060000
        frame.timestamp = 1700000060000

        result = serialize_transaction(frame)

        assert isinstance(result["id"], str)
        assert result["id"] == "11111"
        assert isinstance(result["orderId"], str)
        assert result["orderId"] == "22222"
        assert isinstance(result["filledPrice"], float)
        assert result["filledPrice"] == 99.9999
        assert isinstance(result["filledQuantity"], int)
        assert result["filledQuantity"] == 250
        assert isinstance(result["multiplier"], float)
        assert result["multiplier"] == 1.0
        assert isinstance(result["createTime"], int)
        assert result["createTime"] == 1700000000000
        assert isinstance(result["updateTime"], int)
        assert result["updateTime"] == 1700000050000
        assert isinstance(result["transactTime"], int)
        assert result["transactTime"] == 1700000060000
        assert isinstance(result["timestamp"], int)
        assert result["timestamp"] == 1700000060000

    def test_id_fields_converted_to_string_for_js_precision(self) -> None:
        """id and orderId must be strings to prevent JS Number precision loss."""
        large_id = 2**53 + 1
        frame = MagicMock(spec=["id", "orderId"])
        frame.id = large_id
        frame.orderId = large_id + 1

        result = serialize_transaction(frame)

        assert isinstance(result["id"], str)
        assert result["id"] == str(large_id)
        assert isinstance(result["orderId"], str)
        assert result["orderId"] == str(large_id + 1)

    def test_id_none_is_not_coerced_to_string_none(self) -> None:
        """id=None and orderId=None must be preserved as None."""
        frame = MagicMock(spec=["id", "orderId", "symbol"])
        frame.id = None
        frame.orderId = None
        frame.symbol = "AAPL"

        result = serialize_transaction(frame)

        assert result["id"] is None
        assert result["orderId"] is None
        assert result["symbol"] == "AAPL"

    def test_result_is_json_serializable(
        self, full_transaction_frame: MagicMock
    ) -> None:
        """The result dict can be serialized with orjson without error."""
        result = serialize_transaction(full_transaction_frame)

        serialized = orjson.dumps(result)
        assert isinstance(serialized, bytes)

        deserialized = orjson.loads(serialized)
        assert deserialized == result

    def test_partial_fill_scenario(self) -> None:
        """Per-execution fill data with filledPrice and filledQuantity."""
        frame = MagicMock(
            spec=[
                "id",
                "orderId",
                "symbol",
                "action",
                "filledPrice",
                "filledQuantity",
                "transactTime",
            ]
        )
        frame.id = 90001
        frame.orderId = 55555
        frame.symbol = "TSLA"
        frame.action = "BUY"
        frame.filledPrice = 242.75
        frame.filledQuantity = 20
        frame.transactTime = 1700000060000

        result = serialize_transaction(frame)

        assert result["id"] == "90001"
        assert result["orderId"] == "55555"
        assert result["symbol"] == "TSLA"
        assert result["action"] == "BUY"
        assert result["filledPrice"] == 242.75
        assert result["filledQuantity"] == 20
        assert result["transactTime"] == 1700000060000
        assert len(result) == 7
