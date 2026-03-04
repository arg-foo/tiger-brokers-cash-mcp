"""Event serializers for Tiger Brokers push events."""

from __future__ import annotations

from typing import Any

_MISSING = object()

# Fields to extract from OrderStatusData protobuf.
# Uses the exact camelCase names from the protobuf definition.
_ORDER_STATUS_FIELDS: tuple[str, ...] = (
    # Identity
    "id",
    "account",
    "symbol",
    "identifier",
    "name",
    # Contract details
    "secType",
    "market",
    "currency",
    "multiplier",
    "expiry",
    "strike",
    "right",
    # Order parameters
    "action",
    "orderType",
    "timeInForce",
    "isLong",
    "outsideRth",
    "totalQuantity",
    "totalQuantityScale",
    "limitPrice",
    "stopPrice",
    "totalCashAmount",
    # Fill data
    "filledQuantity",
    "filledQuantityScale",
    "avgFillPrice",
    "filledCashAmount",
    "commissionAndFee",
    "realizedPnl",
    # Status
    "status",
    "replaceStatus",
    "cancelStatus",
    "canModify",
    "canCancel",
    "liquidation",
    "errorMsg",
    # Timestamps
    "openTime",
    "timestamp",
    # Metadata
    "source",
    "userMark",
    "segType",
    "attrDesc",
    "gst",
)


# Fields to extract from OrderTransactionData protobuf.
# Uses the exact camelCase names from the protobuf definition.
_TRANSACTION_FIELDS: tuple[str, ...] = (
    # Identity
    "id",
    "orderId",
    "account",
    "symbol",
    "identifier",
    # Contract details
    "multiplier",
    "action",
    "market",
    "currency",
    "segType",
    "secType",
    # Fill data
    "filledPrice",
    "filledQuantity",
    # Timestamps
    "createTime",
    "updateTime",
    "transactTime",
    "timestamp",
)


def serialize_order_status(frame: Any) -> dict[str, Any]:
    """Convert a PushClient OrderStatusData frame to a JSON-serializable dict.

    Uses defensive ``getattr`` pattern to handle potentially missing
    fields on protobuf objects. Field names match the protobuf
    definition exactly (camelCase).

    Fields with falsy values (``0``, ``0.0``, ``False``, ``""``) are
    preserved — only truly missing attributes are omitted.

    The ``id`` field is converted to a string to prevent JSON integer
    precision loss in JavaScript-based consumers.

    Parameters
    ----------
    frame:
        An ``OrderStatusData`` object from the Tiger PushClient callback.

    Returns
    -------
    dict[str, Any]
        A plain dict with all present fields extracted from the frame.
    """
    result: dict[str, Any] = {}
    for attr in _ORDER_STATUS_FIELDS:
        val = getattr(frame, attr, _MISSING)
        if val is not _MISSING:
            result[attr] = val
    if "id" in result:
        result["id"] = str(result["id"])
    return result


def serialize_transaction(frame: Any) -> dict[str, Any]:
    """Convert a PushClient OrderTransactionData frame to a JSON-serializable dict.

    Uses defensive ``getattr`` pattern to handle potentially missing
    fields on protobuf objects. Field names match the protobuf
    definition exactly (camelCase).

    Fields with falsy values (``0``, ``0.0``, ``False``, ``""``) are
    preserved — only truly missing attributes are omitted.

    The ``id`` and ``orderId`` fields are converted to strings to prevent
    JSON integer precision loss in JavaScript-based consumers.

    Parameters
    ----------
    frame:
        An ``OrderTransactionData`` object from the Tiger PushClient callback.

    Returns
    -------
    dict[str, Any]
        A plain dict with all present fields extracted from the frame.
    """
    result: dict[str, Any] = {}
    for attr in _TRANSACTION_FIELDS:
        val = getattr(frame, attr, _MISSING)
        if val is not _MISSING:
            result[attr] = val
    for key in ("id", "orderId"):
        if key in result:
            result[key] = str(result[key])
    return result
