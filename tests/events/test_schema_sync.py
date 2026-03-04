"""Tests that committed JSON schemas stay in sync with Pydantic models.

Two test groups:
1. Schema staleness guard — ensures the committed JSON files under
   ``schemas/events/`` match what the Pydantic models generate.
2. Field count sanity — ensures payload models have the expected number
   of fields matching the protobuf definitions.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from tiger_mcp.events.models import (
    OrderStatusEvent,
    OrderStatusPayload,
    TransactionEvent,
    TransactionPayload,
)

# Resolve the schemas directory relative to the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_DIR = _REPO_ROOT / "schemas" / "events"


# ---------------------------------------------------------------------------
# Schema staleness guard
# ---------------------------------------------------------------------------


class TestSchemaStaleness:
    """Verify committed JSON schema files match Pydantic model output."""

    @pytest.mark.parametrize(
        ("schema_file", "model"),
        [
            ("order.json", OrderStatusEvent),
            ("transaction.json", TransactionEvent),
        ],
        ids=["order", "transaction"],
    )
    def test_committed_schema_matches_model(
        self, schema_file: str, model: type
    ) -> None:
        """The committed schema file must be identical to model_json_schema().

        If this test fails, run:
            uv run python -m tiger_mcp.events.models
        to regenerate the schema files.
        """
        schema_path = _SCHEMA_DIR / schema_file
        assert schema_path.exists(), (
            f"Schema file not found: {schema_path}. "
            "Run: uv run python -m tiger_mcp.events.models"
        )

        committed = json.loads(schema_path.read_text())
        generated = model.model_json_schema()

        assert committed == generated, (
            f"Committed {schema_file} is stale. "
            "Run: uv run python -m tiger_mcp.events.models"
        )


# ---------------------------------------------------------------------------
# Field count sanity
# ---------------------------------------------------------------------------


class TestFieldCountSanity:
    """Verify payload models have the expected number of protobuf fields."""

    def test_order_status_payload_has_42_fields(self) -> None:
        """OrderStatusPayload must have exactly 42 fields matching the protobuf."""
        assert len(OrderStatusPayload.model_fields) == 42, (
            f"Expected 42 fields, got {len(OrderStatusPayload.model_fields)}. "
            "Verify against OrderStatusData protobuf and update the model."
        )

    def test_transaction_payload_has_17_fields(self) -> None:
        """TransactionPayload must have exactly 17 fields matching the protobuf."""
        assert len(TransactionPayload.model_fields) == 17, (
            f"Expected 17 fields, got {len(TransactionPayload.model_fields)}. "
            "Verify against OrderTransactionData protobuf and update the model."
        )


# ---------------------------------------------------------------------------
# Typed payload verification
# ---------------------------------------------------------------------------


class TestTypedPayload:
    """Verify envelope models use typed Pydantic payload fields (not str)."""

    # -- Round-trip construction ----------------------------------------

    def test_order_status_event_round_trip(self) -> None:
        """OrderStatusEvent accepts an OrderStatusPayload object and exposes its fields."""
        payload = OrderStatusPayload(
            id="123",
            account="DU001",
            symbol="AAPL",
            status="Filled",
            filledQuantity=100,
            avgFillPrice=174.50,
        )
        event = OrderStatusEvent(
            account="DU001",
            timestamp="1700000000000",
            received_at="2024-01-01T00:00:00Z",
            payload=payload,
        )

        assert isinstance(event.payload, OrderStatusPayload)
        assert event.payload.id == "123"
        assert event.payload.symbol == "AAPL"
        assert event.payload.status == "Filled"
        assert event.payload.filledQuantity == 100
        assert event.payload.avgFillPrice == 174.50

    def test_transaction_event_round_trip(self) -> None:
        """TransactionEvent accepts a TransactionPayload object and exposes its fields."""
        payload = TransactionPayload(
            id="456",
            orderId="789",
            account="DU001",
            symbol="TSLA",
            filledPrice=250.00,
            filledQuantity=50,
        )
        event = TransactionEvent(
            account="DU001",
            timestamp="1700000000000",
            received_at="2024-01-01T00:00:00Z",
            payload=payload,
        )

        assert isinstance(event.payload, TransactionPayload)
        assert event.payload.id == "456"
        assert event.payload.orderId == "789"
        assert event.payload.symbol == "TSLA"
        assert event.payload.filledPrice == 250.00
        assert event.payload.filledQuantity == 50

    # -- Schema uses $ref / $defs --------------------------------------

    @pytest.mark.parametrize(
        ("model", "payload_model_name"),
        [
            (OrderStatusEvent, "OrderStatusPayload"),
            (TransactionEvent, "TransactionPayload"),
        ],
        ids=["order", "transaction"],
    )
    def test_schema_contains_defs_with_payload_model(
        self, model: type, payload_model_name: str
    ) -> None:
        """JSON schema must use $defs to define the payload model."""
        schema = model.model_json_schema()

        assert "$defs" in schema, (
            f"{model.__name__} schema is missing '$defs'. "
            "Payload should be a typed Pydantic model, not a plain str."
        )
        assert payload_model_name in schema["$defs"], (
            f"'$defs' does not contain '{payload_model_name}'. "
            f"Found: {list(schema['$defs'].keys())}"
        )

    @pytest.mark.parametrize(
        ("model",),
        [
            (OrderStatusEvent,),
            (TransactionEvent,),
        ],
        ids=["order", "transaction"],
    )
    def test_schema_payload_property_uses_ref(self, model: type) -> None:
        """The payload property in the JSON schema must use $ref."""
        schema = model.model_json_schema()
        payload_prop = schema["properties"]["payload"]

        # Pydantic may wrap the $ref in an allOf; accept either form.
        has_direct_ref = "$ref" in payload_prop
        has_allof_ref = any(
            "$ref" in item
            for item in payload_prop.get("allOf", [])
        )

        assert has_direct_ref or has_allof_ref, (
            f"{model.__name__} payload property does not use '$ref'. "
            f"Got: {payload_prop}"
        )

    # -- Required payload field ----------------------------------------

    def test_order_status_event_requires_payload(self) -> None:
        """Constructing OrderStatusEvent without payload must raise ValidationError."""
        with pytest.raises(ValidationError) as exc_info:
            OrderStatusEvent(
                account="DU001",
                received_at="2024-01-01T00:00:00Z",
            )

        errors = exc_info.value.errors()
        payload_errors = [e for e in errors if "payload" in e["loc"]]
        assert payload_errors, (
            "Expected a validation error for missing 'payload' field. "
            f"Got errors: {errors}"
        )
