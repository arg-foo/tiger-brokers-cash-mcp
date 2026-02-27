"""Event serializers for Tiger Brokers push events."""

from __future__ import annotations

from typing import Any

_MISSING = object()


def serialize_order_status(frame: Any) -> dict[str, Any]:
    """Convert a PushClient OrderStatusData frame to a JSON-serializable dict.

    Uses defensive ``getattr`` pattern (matching the existing
    ``_order_to_dict`` pattern in ``tiger_client.py``) to handle
    potentially missing fields on protobuf objects.

    Fields with falsy values (``0``, ``0.0``, ``False``, ``""``) are
    preserved — only truly missing attributes are omitted.

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
    for attr in (
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
    ):
        val = getattr(frame, attr, _MISSING)
        if val is not _MISSING:
            result[attr] = val
    return result
