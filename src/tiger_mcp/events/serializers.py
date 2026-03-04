"""Event serializers for Tiger Brokers push events."""

from __future__ import annotations

from typing import Any

from tiger_mcp.events.models import (
    ORDER_STATUS_FIELD_NAMES,
    ORDER_STATUS_STR_FIELDS,
    TRANSACTION_FIELD_NAMES,
    TRANSACTION_STR_FIELDS,
)

_MISSING = object()


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
    for attr in ORDER_STATUS_FIELD_NAMES:
        val = getattr(frame, attr, _MISSING)
        if val is not _MISSING:
            if attr in ORDER_STATUS_STR_FIELDS and val is not None:
                val = str(val)
            result[attr] = val
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
    for attr in TRANSACTION_FIELD_NAMES:
        val = getattr(frame, attr, _MISSING)
        if val is not _MISSING:
            if attr in TRANSACTION_STR_FIELDS and val is not None:
                val = str(val)
            result[attr] = val
    return result
