"""Tests for event envelope models (_BaseEvent hierarchy).

Covers: sparse payload serialization with exclude_unset, explicit None values,
timestamp=None inclusion, and round-trip JSON serialization.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from tiger_mcp.events.models import OrderStatusEvent, TransactionEvent


# ---------------------------------------------------------------------------
# model_dump_json with sparse payload
# ---------------------------------------------------------------------------


class TestModelDumpJsonSparsePayload:
    """Test that model_dump_json(exclude_unset=True) only includes set fields."""

    def test_sparse_order_payload_only_includes_set_fields(self) -> None:
        """Only fields explicitly passed to the payload appear in JSON output."""
        event = OrderStatusEvent(
            account="DU12345",
            received_at="2024-01-15T10:30:00+00:00",
            payload={"status": "FILLED", "symbol": "AAPL"},
        )

        data = json.loads(event.model_dump_json(exclude_unset=True))

        assert data["account"] == "DU12345"
        assert data["received_at"] == "2024-01-15T10:30:00Z"
        # payload should only contain the fields we set
        payload = data["payload"]
        assert payload["status"] == "FILLED"
        assert payload["symbol"] == "AAPL"
        # Fields not set should be absent (not null)
        assert "id" not in payload
        assert "action" not in payload
        assert "filledQuantity" not in payload

    def test_transaction_event_sparse_payload(self) -> None:
        """TransactionEvent with sparse payload only includes set fields."""
        event = TransactionEvent(
            account="DU12345",
            received_at="2024-01-15T10:30:00+00:00",
            payload={"filledPrice": 175.50, "symbol": "AAPL"},
        )

        data = json.loads(event.model_dump_json(exclude_unset=True))

        # Only filledPrice and symbol should be in payload
        assert set(data["payload"].keys()) == {"filledPrice", "symbol"}
        assert data["payload"]["filledPrice"] == 175.50
        assert data["payload"]["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# Explicit None values
# ---------------------------------------------------------------------------


class TestExplicitNoneValues:
    """Test that explicitly set None values appear as null in JSON."""

    def test_payload_with_explicit_none_produces_null(self) -> None:
        """Fields explicitly set to None should appear as null in JSON."""
        event = OrderStatusEvent(
            account="DU12345",
            received_at="2024-01-15T10:30:00+00:00",
            payload={"status": None, "symbol": "AAPL"},
        )

        data = json.loads(event.model_dump_json(exclude_unset=True))

        payload = data["payload"]
        assert payload["status"] is None
        assert payload["symbol"] == "AAPL"


# ---------------------------------------------------------------------------
# timestamp=None inclusion
# ---------------------------------------------------------------------------


class TestTimestampNoneInclusion:
    """Test that timestamp=None is included when explicitly set."""

    def test_timestamp_none_explicitly_set_included_in_json(self) -> None:
        """timestamp=None should be present in JSON when explicitly passed."""
        event = OrderStatusEvent(
            account="DU12345",
            timestamp=None,
            received_at="2024-01-15T10:30:00+00:00",
            payload={"status": "FILLED"},
        )

        data = json.loads(event.model_dump_json(exclude_unset=True))

        # timestamp was explicitly set to None, so it should appear
        assert "timestamp" in data
        assert data["timestamp"] is None

    def test_omitted_timestamp_excluded_by_exclude_unset(self) -> None:
        """When timestamp is not explicitly passed, exclude_unset=True should exclude it."""
        event = OrderStatusEvent(
            account="DU12345",
            received_at="2024-01-15T10:30:00+00:00",
            payload={},
        )

        data = json.loads(event.model_dump_json(exclude_unset=True))

        # timestamp was not explicitly set, so it should be absent
        assert "timestamp" not in data


# ---------------------------------------------------------------------------
# Round-trip serialization
# ---------------------------------------------------------------------------


class TestRoundTripSerialization:
    """Test JSON serialization round-trip fidelity."""

    def test_order_event_round_trip(self) -> None:
        """model_dump_json() -> model_validate_json() reconstructs identical model."""
        original = OrderStatusEvent(
            account="DU12345",
            timestamp="1700000000",
            received_at="2024-01-15T10:30:00+00:00",
            payload={"status": "FILLED", "symbol": "AAPL", "filledQuantity": 100},
        )

        json_str = original.model_dump_json()
        restored = OrderStatusEvent.model_validate_json(json_str)

        assert restored == original
        assert restored.account == original.account
        assert restored.timestamp == original.timestamp
        assert restored.received_at == original.received_at
        assert restored.payload == original.payload

    def test_transaction_event_round_trip(self) -> None:
        """TransactionEvent round-trip also works correctly."""
        original = TransactionEvent(
            account="DU12345",
            timestamp="1700000000",
            received_at="2024-01-15T10:30:00+00:00",
            payload={"filledPrice": 175.50, "symbol": "AAPL"},
        )

        json_str = original.model_dump_json()
        restored = TransactionEvent.model_validate_json(json_str)

        assert restored == original


# ---------------------------------------------------------------------------
# received_at validation
# ---------------------------------------------------------------------------


class TestReceivedAtValidation:
    """Test that received_at rejects invalid inputs."""

    def test_rejects_naive_datetime(self) -> None:
        with pytest.raises(ValidationError):
            OrderStatusEvent(account="X", received_at=datetime(2024, 1, 1), payload={})

    def test_rejects_none(self) -> None:
        with pytest.raises(ValidationError):
            OrderStatusEvent(account="X", received_at=None, payload={})

    def test_rejects_non_datetime_string(self) -> None:
        with pytest.raises(ValidationError):
            OrderStatusEvent(account="X", received_at="not-a-date", payload={})

    def test_normalizes_non_utc_to_utc(self) -> None:
        """Non-UTC offset should be normalized to UTC."""
        non_utc = datetime(2024, 1, 1, 5, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))
        event = OrderStatusEvent(account="X", received_at=non_utc, payload={})
        assert event.received_at.tzinfo == timezone.utc
        assert event.received_at == datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# datetime-object construction (mirrors production usage)
# ---------------------------------------------------------------------------


class TestDatetimeObjectConstruction:
    """Test that datetime objects work correctly for received_at (production path)."""

    def test_order_event_with_datetime_received_at(self) -> None:
        """Production passes datetime objects; verify serialization."""
        event = OrderStatusEvent(
            account="DU12345",
            received_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            payload={"status": "FILLED"},
        )
        data = json.loads(event.model_dump_json(exclude_unset=True))
        assert data["received_at"] == "2024-01-15T10:30:00Z"
