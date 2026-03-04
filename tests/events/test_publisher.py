"""Tests for RedisStreamPublisher (event subscription).

Covers: connection lifecycle, publish with XADD, error handling,
consecutive failure tracking with escalating log severity,
single JSON field serialization via envelope models, and is_connected property.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import MagicMock, patch

import pytest
import redis

from tiger_mcp.events.models import OrderStatusEvent, TransactionEvent
from tiger_mcp.events.publisher import RedisStreamPublisher

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

REDIS_URL = "redis://localhost:6379/0"
STREAM_PREFIX = "tiger:events"
MAXLEN = 1000


@pytest.fixture()
def publisher() -> RedisStreamPublisher:
    """Create a RedisStreamPublisher instance (not connected)."""
    return RedisStreamPublisher(
        redis_url=REDIS_URL,
        stream_prefix=STREAM_PREFIX,
        maxlen=MAXLEN,
    )


@pytest.fixture()
def mock_redis_client() -> MagicMock:
    """Create a mock redis.Redis instance."""
    client = MagicMock(spec=redis.Redis)
    client.xadd.return_value = "1234567890-0"
    return client


@pytest.fixture()
def connected_publisher(
    publisher: RedisStreamPublisher,
    mock_redis_client: MagicMock,
) -> RedisStreamPublisher:
    """Create a connected RedisStreamPublisher with a mocked Redis client."""
    with patch(
        "tiger_mcp.events.publisher.redis.Redis.from_url",
        return_value=mock_redis_client,
    ):
        publisher.connect()
    return publisher


def _make_order_event(**overrides: object) -> OrderStatusEvent:
    """Create a minimal valid OrderStatusEvent for testing."""
    defaults = {
        "account": "DU12345",
        "received_at": "2024-01-15T10:30:00+00:00",
        "payload": {},
    }
    defaults.update(overrides)
    return OrderStatusEvent(**defaults)


# ---------------------------------------------------------------------------
# Connection lifecycle
# ---------------------------------------------------------------------------


class TestConnection:
    """Test connect(), close(), and is_connected property."""

    def test_connect_calls_from_url_and_ping(
        self, publisher: RedisStreamPublisher
    ) -> None:
        """connect() should create a Redis client via from_url and ping it."""
        mock_client = MagicMock(spec=redis.Redis)
        with patch(
            "tiger_mcp.events.publisher.redis.Redis.from_url",
            return_value=mock_client,
        ) as mock_from_url:
            publisher.connect()

        mock_from_url.assert_called_once_with(
            REDIS_URL, decode_responses=True
        )
        mock_client.ping.assert_called_once()

    def test_is_connected_false_before_connect(
        self, publisher: RedisStreamPublisher
    ) -> None:
        """is_connected should be False before connect() is called."""
        assert publisher.is_connected is False

    def test_is_connected_true_after_connect(
        self, connected_publisher: RedisStreamPublisher
    ) -> None:
        """is_connected should be True after connect() succeeds."""
        assert connected_publisher.is_connected is True

    def test_is_connected_false_after_close(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """is_connected should be False after close() is called."""
        connected_publisher.close()
        assert connected_publisher.is_connected is False

    def test_close_calls_redis_close(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """close() should call redis.close() and set the client to None."""
        connected_publisher.close()

        mock_redis_client.close.assert_called_once()
        assert connected_publisher._redis is None

    def test_close_when_not_connected_is_noop(
        self, publisher: RedisStreamPublisher
    ) -> None:
        """close() when not connected should not raise."""
        publisher.close()  # Should not raise
        assert publisher.is_connected is False

    def test_connect_raises_on_ping_failure(
        self, publisher: RedisStreamPublisher
    ) -> None:
        """connect() should propagate ConnectionError from ping()."""
        mock_client = MagicMock(spec=redis.Redis)
        mock_client.ping.side_effect = redis.ConnectionError("refused")
        with patch(
            "tiger_mcp.events.publisher.redis.Redis.from_url",
            return_value=mock_client,
        ):
            with pytest.raises(redis.ConnectionError, match="refused"):
                publisher.connect()
        # _redis is only assigned after ping() succeeds. Since ping()
        # raised, _redis remains None and is_connected returns False.

    def test_is_connected_false_after_failed_ping(
        self, publisher: RedisStreamPublisher
    ) -> None:
        """After a failed connect(), is_connected should be False.

        connect() only assigns _redis after ping() succeeds. If ping()
        fails, _redis remains None.
        """
        mock_client = MagicMock(spec=redis.Redis)
        mock_client.ping.side_effect = redis.ConnectionError("refused")
        with patch(
            "tiger_mcp.events.publisher.redis.Redis.from_url",
            return_value=mock_client,
        ):
            with pytest.raises(redis.ConnectionError):
                publisher.connect()
        assert publisher.is_connected is False
        assert publisher._redis is None


# ---------------------------------------------------------------------------
# Publishing events
# ---------------------------------------------------------------------------


class TestPublish:
    """Test publish() method behavior."""

    def test_publish_calls_xadd_with_correct_args(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() should call XADD with correct stream key and single data field."""
        event = _make_order_event(
            payload={"status": "FILLED", "symbol": "AAPL"},
            timestamp="2024-01-15T10:30:00Z",
        )
        connected_publisher.publish("order", event)

        mock_redis_client.xadd.assert_called_once()
        call_args = mock_redis_client.xadd.call_args

        # Positional args: stream_key, fields
        assert call_args[0][0] == f"{STREAM_PREFIX}:order"
        fields = call_args[0][1]
        # Should be a single "data" field containing serialized JSON
        assert "data" in fields
        assert len(fields) == 1
        # Verify the JSON content is valid and contains expected data
        data = json.loads(fields["data"])
        assert data["account"] == "DU12345"
        assert data["payload"]["status"] == "FILLED"
        assert data["payload"]["symbol"] == "AAPL"

        # Keyword args
        assert call_args[1]["maxlen"] == MAXLEN
        assert call_args[1]["approximate"] is True

    def test_publish_returns_entry_id(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() should return the entry ID from XADD."""
        mock_redis_client.xadd.return_value = "9999999999-5"

        event = _make_order_event(payload={"status": "FILLED"})
        entry_id = connected_publisher.publish("order", event)

        assert entry_id == "9999999999-5"

    def test_publish_when_not_connected_returns_none(
        self, publisher: RedisStreamPublisher
    ) -> None:
        """publish() before connect() should return None without error."""
        event = _make_order_event(payload={"status": "FILLED"})
        result = publisher.publish("order", event)
        assert result is None

    def test_publish_serializes_event_as_single_json_field(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() should serialize the entire event as a single JSON data field."""
        event = _make_order_event(
            payload={"symbol": "AAPL", "totalQuantity": 100, "limitPrice": 150.50},
        )
        connected_publisher.publish("order", event)

        fields = mock_redis_client.xadd.call_args[0][1]
        assert list(fields.keys()) == ["data"]
        data = json.loads(fields["data"])
        assert data["payload"]["symbol"] == "AAPL"
        assert data["payload"]["totalQuantity"] == 100
        assert data["payload"]["limitPrice"] == 150.50

    def test_publish_uses_exclude_unset(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() should use exclude_unset=True so unset payload fields are omitted."""
        event = _make_order_event(
            payload={"status": "FILLED"},
        )
        connected_publisher.publish("order", event)

        fields = mock_redis_client.xadd.call_args[0][1]
        data = json.loads(fields["data"])
        payload = data["payload"]
        # Only "status" was set, so other fields should not appear
        assert "status" in payload
        assert "symbol" not in payload
        assert "id" not in payload

    def test_publish_uses_provided_received_at(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() should include the received_at from the event model."""
        event = _make_order_event(
            received_at="2024-01-15T10:30:00+00:00",
            payload={"status": "FILLED"},
        )
        connected_publisher.publish("order", event)

        fields = mock_redis_client.xadd.call_args[0][1]
        data = json.loads(fields["data"])
        assert data["received_at"] == "2024-01-15T10:30:00+00:00"

    def test_publish_transaction_event(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() should handle TransactionEvent the same as OrderStatusEvent."""
        event = TransactionEvent(
            account="DU12345",
            received_at="2024-01-15T10:30:00+00:00",
            payload={"filledPrice": 175.50},
        )
        result = connected_publisher.publish("transaction", event)

        assert result is not None
        call_args = mock_redis_client.xadd.call_args
        assert call_args[0][0] == "tiger:events:transaction"
        fields = call_args[0][1]
        assert "data" in fields
        data = json.loads(fields["data"])
        assert data["payload"]["filledPrice"] == 175.50


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestPublishErrors:
    """Test error handling during publish."""

    def test_publish_connection_error_returns_none(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """redis.ConnectionError during XADD should return None."""
        mock_redis_client.xadd.side_effect = redis.ConnectionError(
            "Connection lost"
        )

        event = _make_order_event(payload={"status": "FILLED"})
        result = connected_publisher.publish("order", event)

        assert result is None

    def test_publish_timeout_error_returns_none(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """redis.TimeoutError during XADD should return None."""
        mock_redis_client.xadd.side_effect = redis.TimeoutError(
            "Timed out"
        )

        event = _make_order_event(payload={"status": "FILLED"})
        result = connected_publisher.publish("order", event)

        assert result is None


# ---------------------------------------------------------------------------
# Consecutive failure tracking
# ---------------------------------------------------------------------------


class TestConsecutiveFailures:
    """Test consecutive failure counter and log escalation."""

    def test_consecutive_failure_counter_increments(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """Each failed publish should increment the consecutive failure counter."""
        mock_redis_client.xadd.side_effect = redis.ConnectionError("fail")
        event = _make_order_event()

        connected_publisher.publish("order", event)
        assert connected_publisher._consecutive_failures == 1

        connected_publisher.publish("order", event)
        assert connected_publisher._consecutive_failures == 2

        connected_publisher.publish("order", event)
        assert connected_publisher._consecutive_failures == 3

    def test_consecutive_failure_counter_resets_on_success(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """A successful publish should reset the consecutive failure counter to 0."""
        event = _make_order_event()

        # First, cause some failures
        mock_redis_client.xadd.side_effect = redis.ConnectionError("fail")
        connected_publisher.publish("order", event)
        connected_publisher.publish("order", event)
        assert connected_publisher._consecutive_failures == 2

        # Now succeed
        mock_redis_client.xadd.side_effect = None
        mock_redis_client.xadd.return_value = "123-0"
        connected_publisher.publish("order", event)
        assert connected_publisher._consecutive_failures == 0

    def test_escalating_log_severity_warning_under_10(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Failures under 10 consecutive should log at WARNING level."""
        mock_redis_client.xadd.side_effect = redis.ConnectionError("fail")
        event = _make_order_event()

        with caplog.at_level(logging.WARNING, logger="tiger_mcp.events.publisher"):
            connected_publisher.publish("order", event)

        assert connected_publisher._consecutive_failures == 1
        warning_records = [
            r for r in caplog.records
            if r.levelno == logging.WARNING
            and "redis_publish_failed" in r.message
        ]
        assert len(warning_records) == 1

    def test_escalating_log_severity_error_at_10(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """At 10+ consecutive failures, should log at ERROR level."""
        mock_redis_client.xadd.side_effect = redis.ConnectionError("fail")
        event = _make_order_event()

        # Fail 9 times first (these are warnings)
        for _ in range(9):
            connected_publisher.publish("order", event)

        assert connected_publisher._consecutive_failures == 9

        # The 10th failure should be ERROR
        with caplog.at_level(logging.WARNING, logger="tiger_mcp.events.publisher"):
            caplog.clear()
            connected_publisher.publish("order", event)

        assert connected_publisher._consecutive_failures == 10
        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "redis_publish_failed" in r.message
        ]
        assert len(error_records) == 1

    def test_escalating_log_severity_error_above_10(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """At 11+ consecutive failures, should still log at ERROR level."""
        mock_redis_client.xadd.side_effect = redis.ConnectionError("fail")
        event = _make_order_event()

        # Fail 10 times first
        for _ in range(10):
            connected_publisher.publish("order", event)

        # The 11th failure should also be ERROR
        with caplog.at_level(logging.WARNING, logger="tiger_mcp.events.publisher"):
            caplog.clear()
            connected_publisher.publish("order", event)

        assert connected_publisher._consecutive_failures == 11
        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "redis_publish_failed" in r.message
        ]
        assert len(error_records) == 1
