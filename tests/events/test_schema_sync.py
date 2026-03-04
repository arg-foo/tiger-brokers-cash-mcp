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
