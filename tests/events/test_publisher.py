"""Tests for RedisStreamPublisher (event subscription).

Covers: connection lifecycle, publish with XADD, error handling,
consecutive failure tracking with escalating log severity,
orjson serialization, and is_connected property.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import orjson
import pytest
import redis

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
        # Client was assigned but ping failed — still appears connected
        # because _redis was set before ping. This is the current behavior.
        # The caller is responsible for handling the exception.

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
        """publish() should call XADD with correct stream key, fields, maxlen."""
        payload = {"status": "FILLED", "price": 150.0}
        connected_publisher.publish(
            event_type="order",
            payload=payload,
            account="DU12345",
            timestamp="2024-01-15T10:30:00Z",
        )

        mock_redis_client.xadd.assert_called_once()
        call_args = mock_redis_client.xadd.call_args

        # Positional args: stream_key, fields
        assert call_args[0][0] == f"{STREAM_PREFIX}:order"
        fields = call_args[0][1]
        assert fields["account"] == "DU12345"
        assert fields["timestamp"] == "2024-01-15T10:30:00Z"
        assert "received_at" in fields
        assert "payload" in fields

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

        entry_id = connected_publisher.publish(
            event_type="order",
            payload={"status": "FILLED"},
        )

        assert entry_id == "9999999999-5"

    def test_publish_when_not_connected_returns_none(
        self, publisher: RedisStreamPublisher
    ) -> None:
        """publish() before connect() should return None without error."""
        result = publisher.publish(
            event_type="order",
            payload={"status": "FILLED"},
        )
        assert result is None

    def test_publish_serializes_payload_with_orjson(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() should serialize the payload dict using orjson."""
        payload = {"symbol": "AAPL", "quantity": 100, "price": 150.50}
        connected_publisher.publish(
            event_type="order",
            payload=payload,
        )

        fields = mock_redis_client.xadd.call_args[0][1]
        expected_json = orjson.dumps(payload).decode()
        assert fields["payload"] == expected_json

    def test_publish_default_account_and_timestamp(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() with default account/timestamp should use empty strings."""
        connected_publisher.publish(
            event_type="order",
            payload={"status": "NEW"},
        )

        fields = mock_redis_client.xadd.call_args[0][1]
        assert fields["account"] == ""
        assert fields["timestamp"] == ""

    def test_publish_uses_provided_received_at(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() should use the provided received_at timestamp."""
        connected_publisher.publish(
            event_type="order",
            payload={"status": "FILLED"},
            received_at="2024-01-15T10:30:00+00:00",
        )

        fields = mock_redis_client.xadd.call_args[0][1]
        assert fields["received_at"] == "2024-01-15T10:30:00+00:00"

    def test_publish_falls_back_to_now_when_no_received_at(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """publish() without received_at should use datetime.now(UTC)."""
        connected_publisher.publish(
            event_type="order",
            payload={"status": "NEW"},
        )

        fields = mock_redis_client.xadd.call_args[0][1]
        # received_at should be a non-empty ISO timestamp
        assert fields["received_at"] != ""
        assert "T" in fields["received_at"]


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

        result = connected_publisher.publish(
            event_type="order",
            payload={"status": "FILLED"},
        )

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

        result = connected_publisher.publish(
            event_type="order",
            payload={"status": "FILLED"},
        )

        assert result is None

    def test_publish_non_serializable_payload_raises(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """Non-serializable payload should raise (not caught by publish).

        orjson.JSONEncodeError is not in the except clause, so it
        propagates to the caller (_on_order_changed catches it).
        """
        non_serializable = {"obj": object()}
        with pytest.raises(TypeError):
            connected_publisher.publish(
                event_type="order",
                payload=non_serializable,
            )


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

        connected_publisher.publish(event_type="order", payload={})
        assert connected_publisher._consecutive_failures == 1

        connected_publisher.publish(event_type="order", payload={})
        assert connected_publisher._consecutive_failures == 2

        connected_publisher.publish(event_type="order", payload={})
        assert connected_publisher._consecutive_failures == 3

    def test_consecutive_failure_counter_resets_on_success(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
    ) -> None:
        """A successful publish should reset the consecutive failure counter to 0."""
        # First, cause some failures
        mock_redis_client.xadd.side_effect = redis.ConnectionError("fail")
        connected_publisher.publish(event_type="order", payload={})
        connected_publisher.publish(event_type="order", payload={})
        assert connected_publisher._consecutive_failures == 2

        # Now succeed
        mock_redis_client.xadd.side_effect = None
        mock_redis_client.xadd.return_value = "123-0"
        connected_publisher.publish(event_type="order", payload={})
        assert connected_publisher._consecutive_failures == 0

    def test_escalating_log_severity_warning_under_10(
        self,
        connected_publisher: RedisStreamPublisher,
        mock_redis_client: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Failures under 10 consecutive should log at WARNING level."""
        mock_redis_client.xadd.side_effect = redis.ConnectionError("fail")

        with caplog.at_level(logging.WARNING, logger="tiger_mcp.events.publisher"):
            connected_publisher.publish(event_type="order", payload={})

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

        # Fail 9 times first (these are warnings)
        for _ in range(9):
            connected_publisher.publish(event_type="order", payload={})

        assert connected_publisher._consecutive_failures == 9

        # The 10th failure should be ERROR
        with caplog.at_level(logging.WARNING, logger="tiger_mcp.events.publisher"):
            caplog.clear()
            connected_publisher.publish(event_type="order", payload={})

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

        # Fail 10 times first
        for _ in range(10):
            connected_publisher.publish(event_type="order", payload={})

        # The 11th failure should also be ERROR
        with caplog.at_level(logging.WARNING, logger="tiger_mcp.events.publisher"):
            caplog.clear()
            connected_publisher.publish(event_type="order", payload={})

        assert connected_publisher._consecutive_failures == 11
        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "redis_publish_failed" in r.message
        ]
        assert len(error_records) == 1
