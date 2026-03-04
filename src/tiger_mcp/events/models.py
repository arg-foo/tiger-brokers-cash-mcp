"""Pydantic models for Tiger Brokers push event schemas.

These models serve as the single source of truth for:
- Field names and types used by serializers
- JSON schemas committed under ``schemas/events/``
- Runtime validation (optional, not on the hot path)

Run ``python -m tiger_mcp.events.models`` to regenerate the JSON schema
files under ``schemas/events/``.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Inner payload models (protobuf field mirrors)
# ---------------------------------------------------------------------------


class OrderStatusPayload(BaseModel):
    """Payload for order status change events.

    Fields mirror the ``OrderStatusData`` protobuf exactly (camelCase).
    All fields are optional because protobuf objects may omit any attribute.
    """

    # Identity
    id: str | None = None
    account: str | None = None
    symbol: str | None = None
    identifier: str | None = None
    name: str | None = None
    # Contract details
    secType: str | None = None
    market: str | None = None
    currency: str | None = None
    multiplier: float | None = None
    expiry: str | None = None
    strike: str | None = None
    right: str | None = None
    # Order parameters
    action: str | None = None
    orderType: str | None = None
    timeInForce: str | None = None
    isLong: bool | None = None
    outsideRth: bool | None = None
    totalQuantity: int | None = None
    totalQuantityScale: int | None = None
    limitPrice: float | None = None
    stopPrice: float | None = None
    totalCashAmount: float | None = None
    # Fill data
    filledQuantity: int | None = None
    filledQuantityScale: int | None = None
    avgFillPrice: float | None = None
    filledCashAmount: float | None = None
    commissionAndFee: float | None = None
    realizedPnl: float | None = None
    # Status
    status: str | None = None
    replaceStatus: str | None = None
    cancelStatus: str | None = None
    canModify: bool | None = None
    canCancel: bool | None = None
    liquidation: bool | None = None
    errorMsg: str | None = None
    # Timestamps
    openTime: int | None = None
    timestamp: int | None = None
    # Metadata
    source: str | None = None
    userMark: str | None = None
    segType: str | None = None
    attrDesc: str | None = None
    gst: float | None = None


class TransactionPayload(BaseModel):
    """Payload for order transaction (execution/fill) events.

    Fields mirror the ``OrderTransactionData`` protobuf exactly (camelCase).
    All fields are optional because protobuf objects may omit any attribute.
    """

    # Identity
    id: str | None = None
    orderId: str | None = None
    account: str | None = None
    symbol: str | None = None
    identifier: str | None = None
    # Contract details
    multiplier: float | None = None
    action: str | None = None
    market: str | None = None
    currency: str | None = None
    segType: str | None = None
    secType: str | None = None
    # Fill data
    filledPrice: float | None = None
    filledQuantity: int | None = None
    # Timestamps
    createTime: int | None = None
    updateTime: int | None = None
    transactTime: int | None = None
    timestamp: int | None = None


# ---------------------------------------------------------------------------
# Outer envelope models (Redis stream entry structure)
# ---------------------------------------------------------------------------


class OrderStatusEvent(BaseModel):
    """Full Redis stream event for order status changes."""

    model_config = ConfigDict(json_schema_extra={
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "tiger-events-order",
    })

    account: str = Field(description="Tiger Brokers account identifier.")
    timestamp: str | None = Field(
        default=None,
        description=(
            "Event timestamp from Tiger Brokers"
            " (epoch milliseconds as string)."
        ),
    )
    received_at: str = Field(
        description="ISO 8601 timestamp when the event was received by the subscriber.",
        json_schema_extra={"format": "date-time"},
    )
    payload: str = Field(
        description="JSON-encoded order status payload.",
        json_schema_extra={
            "contentMediaType": "application/json",
            "contentSchema": OrderStatusPayload.model_json_schema(),
        },
    )


class TransactionEvent(BaseModel):
    """Full Redis stream event for transaction (execution/fill) changes."""

    model_config = ConfigDict(json_schema_extra={
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "tiger-events-transaction",
    })

    account: str = Field(description="Tiger Brokers account identifier.")
    timestamp: str | None = Field(
        default=None,
        description=(
            "Event timestamp from Tiger Brokers"
            " (epoch milliseconds as string)."
        ),
    )
    received_at: str = Field(
        description="ISO 8601 timestamp when the event was received by the subscriber.",
        json_schema_extra={"format": "date-time"},
    )
    payload: str = Field(
        description="JSON-encoded transaction payload.",
        json_schema_extra={
            "contentMediaType": "application/json",
            "contentSchema": TransactionPayload.model_json_schema(),
        },
    )


# ---------------------------------------------------------------------------
# Pre-computed exports for serializers
# ---------------------------------------------------------------------------

ORDER_STATUS_FIELD_NAMES: tuple[str, ...] = tuple(
    OrderStatusPayload.model_fields.keys()
)
TRANSACTION_FIELD_NAMES: tuple[str, ...] = tuple(
    TransactionPayload.model_fields.keys()
)

ORDER_STATUS_STR_FIELDS: frozenset[str] = frozenset({"id"})
TRANSACTION_STR_FIELDS: frozenset[str] = frozenset({"id", "orderId"})


# ---------------------------------------------------------------------------
# Schema generation (CLI entry point)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from pathlib import Path

    schema_dir = Path(__file__).resolve().parents[3] / "schemas" / "events"
    schema_dir.mkdir(parents=True, exist_ok=True)
    for name, model in [
        ("order", OrderStatusEvent),
        ("transaction", TransactionEvent),
    ]:
        (schema_dir / f"{name}.json").write_text(
            json.dumps(model.model_json_schema(), indent=2) + "\n"
        )
    print("Schemas written to", schema_dir)
