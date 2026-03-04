"""Tests for PushSubscriber (Tiger PushClient -> Redis Streams bridge).

Covers: start/stop lifecycle, PushClient callback wiring, order event
serialization and publishing, reconnection with exponential backoff,
thread-safe reconnecting guard, and edge cases.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tiger_mcp.config import Settings
from tiger_mcp.events.models import OrderStatusEvent, TransactionEvent
from tiger_mcp.events.subscriber import PushSubscriber

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def tmp_key_file(tmp_path: Path) -> Path:
    """Create a temporary file to act as a private key."""
    key_file = tmp_path / "private.pem"
    key_file.write_text("fake-key-content")
    return key_file


@pytest.fixture()
def settings(tmp_key_file: Path) -> Settings:
    """Create a Settings instance with event-related fields configured."""
    return Settings(
        tiger_id="test-tiger-id",
        tiger_account="DU12345",
        private_key_path=tmp_key_file,
        events_enabled=True,
        redis_url="redis://localhost:6379/0",
        redis_stream_prefix="tiger:events",
        redis_stream_maxlen=1000,
        push_reconnect_max_attempts=5,
        push_reconnect_base_delay=1.0,
    )


@pytest.fixture()
def mock_publisher() -> MagicMock:
    """Create a mock RedisStreamPublisher."""
    publisher = MagicMock()
    publisher.publish.return_value = "1234567890-0"
    return publisher


@pytest.fixture()
def subscriber(settings: Settings, mock_publisher: MagicMock) -> PushSubscriber:
    """Create a PushSubscriber instance (not started)."""
    return PushSubscriber(settings=settings, publisher=mock_publisher)


@pytest.fixture()
def mock_client_config() -> MagicMock:
    """Create a mock TigerOpenClientConfig returned by build_client_config."""
    config = MagicMock()
    config.tiger_id = "test-tiger-id"
    config.private_key = "fake-key-content"
    config.socket_host_port = ("ssl", "openapi.itigerup.com", 9883)
    return config


# ---------------------------------------------------------------------------
# Start lifecycle
# ---------------------------------------------------------------------------


class TestStart:
    """Test start() method -- PushClient creation, callback wiring, connect."""

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_start_creates_push_client_and_connects(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """start() should create a PushClient and call connect()."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance

        subscriber.start()

        mock_build_config.assert_called_once_with(subscriber._settings)
        mock_push_client_cls.assert_called_once_with(
            "openapi.itigerup.com",
            9883,
            use_ssl=True,
        )
        mock_push_instance.connect.assert_called_once_with(
            mock_client_config.tiger_id,
            mock_client_config.private_key,
        )

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_start_sets_correct_callbacks(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """start() should assign all 5 callback attributes on the PushClient."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance

        subscriber.start()

        assert mock_push_instance.order_changed == subscriber._on_order_changed
        assert (
            mock_push_instance.transaction_changed
            == subscriber._on_transaction_changed
        )
        assert mock_push_instance.connect_callback == subscriber._on_connected
        assert (
            mock_push_instance.disconnect_callback == subscriber._on_disconnected
        )
        assert mock_push_instance.error_callback == subscriber._on_error

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_start_caches_client_config(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """start() should cache the client_config for reconnect reuse."""
        mock_build_config.return_value = mock_client_config
        mock_push_client_cls.return_value = MagicMock()

        subscriber.start()

        assert subscriber._client_config is mock_client_config

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_start_propagates_connect_exception(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """PushClient.connect() errors should propagate from start()."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_instance.connect.side_effect = ConnectionError("unreachable")
        mock_push_client_cls.return_value = mock_push_instance

        with pytest.raises(ConnectionError, match="unreachable"):
            subscriber.start()


# ---------------------------------------------------------------------------
# Stop lifecycle
# ---------------------------------------------------------------------------


class TestStop:
    """Test stop() method -- disconnect, publisher cleanup, error handling."""

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_stop_disconnects_push_client(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """stop() should call disconnect() on the PushClient."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance

        subscriber.start()
        subscriber.stop()

        mock_push_instance.disconnect.assert_called_once()

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_stop_closes_publisher(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
        mock_client_config: MagicMock,
    ) -> None:
        """stop() should call close() on the publisher."""
        mock_build_config.return_value = mock_client_config
        mock_push_client_cls.return_value = MagicMock()

        subscriber.start()
        subscriber.stop()

        mock_publisher.close.assert_called_once()

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_stop_handles_disconnect_error(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """stop() should not propagate exceptions from disconnect()."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_instance.disconnect.side_effect = RuntimeError("connection lost")
        mock_push_client_cls.return_value = mock_push_instance

        subscriber.start()
        # Should not raise
        subscriber.stop()

        mock_push_instance.disconnect.assert_called_once()
        assert subscriber._push_client is None

    def test_stop_without_start_closes_publisher(
        self,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """stop() before start() should still close the publisher without error."""
        subscriber.stop()

        mock_publisher.close.assert_called_once()

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_stop_sets_push_client_to_none(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """stop() should set _push_client to None."""
        mock_build_config.return_value = mock_client_config
        mock_push_client_cls.return_value = MagicMock()

        subscriber.start()
        assert subscriber._push_client is not None

        subscriber.stop()
        assert subscriber._push_client is None


# ---------------------------------------------------------------------------
# _on_order_changed callback
# ---------------------------------------------------------------------------


class TestOnOrderChanged:
    """Test the order status change callback."""

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_order_status")
    def test_on_order_changed_serializes_and_publishes(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_on_order_changed should serialize the frame and publish an envelope model."""
        mock_datetime.now.return_value.isoformat.return_value = (
            "2024-01-15T10:30:00+00:00"
        )
        mock_serialize.return_value = {"status": "FILLED", "symbol": "AAPL"}
        frame = MagicMock()
        frame.account = "DU12345"
        frame.timestamp = 1700000000

        subscriber._on_order_changed(frame)

        mock_serialize.assert_called_once_with(frame)
        # publish is now called with positional args: (event_type, event)
        call_args = mock_publisher.publish.call_args
        assert call_args[0][0] == "order"
        event = call_args[0][1]
        assert isinstance(event, OrderStatusEvent)
        assert event.account == "DU12345"
        assert event.timestamp == "1700000000"
        assert event.received_at == "2024-01-15T10:30:00+00:00"
        assert event.payload.status == "FILLED"
        assert event.payload.symbol == "AAPL"

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_order_status")
    def test_on_order_changed_uses_account_from_frame(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """When frame has an account attribute, it should be used."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        mock_serialize.return_value = {"status": "NEW"}
        frame = MagicMock()
        frame.account = "DU99999"
        frame.timestamp = 1700000000

        subscriber._on_order_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.account == "DU99999"

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_order_status")
    def test_on_order_changed_falls_back_to_settings_account(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """When frame.account is missing, fall back to settings.tiger_account."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        mock_serialize.return_value = {"status": "CANCELLED"}
        frame = MagicMock(spec=[])  # spec=[] means no attributes at all

        subscriber._on_order_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.account == "DU12345"

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_order_status")
    def test_on_order_changed_falls_back_when_account_is_empty(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """Empty frame.account falls back to settings.tiger_account."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        mock_serialize.return_value = {"status": "CANCELLED"}
        frame = MagicMock()
        frame.account = ""
        frame.timestamp = 1700000000

        subscriber._on_order_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.account == "DU12345"

    @patch("tiger_mcp.events.subscriber.serialize_order_status")
    def test_on_order_changed_exception_caught(
        self,
        mock_serialize: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Exceptions in callback should be caught and logged."""
        mock_serialize.side_effect = ValueError("bad frame data")
        frame = MagicMock()

        with caplog.at_level(logging.ERROR, logger="tiger_mcp.events.subscriber"):
            subscriber._on_order_changed(frame)

        # Should not raise
        mock_publisher.publish.assert_not_called()
        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "order_event_processing_failed" in r.message
        ]
        assert len(error_records) == 1

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_order_status")
    def test_on_order_changed_timestamp_fallback(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """When frame.timestamp is missing, None should be passed."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        mock_serialize.return_value = {"status": "FILLED"}
        frame = MagicMock(spec=[])  # No attributes

        subscriber._on_order_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.timestamp is None

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_order_status")
    def test_on_order_changed_passes_received_at(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """received_at should be set at callback invocation time."""
        mock_datetime.now.return_value.isoformat.return_value = (
            "2024-06-01T12:00:00+00:00"
        )
        mock_serialize.return_value = {"status": "FILLED"}
        frame = MagicMock()
        frame.account = "DU12345"
        frame.timestamp = 1700000000

        subscriber._on_order_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.received_at == "2024-06-01T12:00:00+00:00"


# ---------------------------------------------------------------------------
# _on_transaction_changed callback
# ---------------------------------------------------------------------------


class TestOnTransactionChanged:
    """Test the transaction change callback."""

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_transaction")
    def test_on_transaction_changed_serializes_and_publishes(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_on_transaction_changed should serialize the frame and publish an envelope model."""
        mock_datetime.now.return_value.isoformat.return_value = (
            "2024-01-15T10:30:00+00:00"
        )
        mock_serialize.return_value = {"filledPrice": 175.50, "symbol": "AAPL"}
        frame = MagicMock()
        frame.account = "DU12345"
        frame.timestamp = 1700000000

        subscriber._on_transaction_changed(frame)

        mock_serialize.assert_called_once_with(frame)
        call_args = mock_publisher.publish.call_args
        assert call_args[0][0] == "transaction"
        event = call_args[0][1]
        assert isinstance(event, TransactionEvent)
        assert event.account == "DU12345"
        assert event.timestamp == "1700000000"
        assert event.received_at == "2024-01-15T10:30:00+00:00"
        assert event.payload.filledPrice == 175.50
        assert event.payload.symbol == "AAPL"

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_transaction")
    def test_on_transaction_changed_uses_account_from_frame(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """When frame has an account attribute, it should be used."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        mock_serialize.return_value = {"filledPrice": 100.0}
        frame = MagicMock()
        frame.account = "DU99999"
        frame.timestamp = 1700000000

        subscriber._on_transaction_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.account == "DU99999"

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_transaction")
    def test_on_transaction_changed_falls_back_to_settings_account(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """When frame.account is missing, fall back to settings.tiger_account."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        mock_serialize.return_value = {"filledPrice": 200.0}
        frame = MagicMock(spec=[])  # spec=[] means no attributes at all

        subscriber._on_transaction_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.account == "DU12345"

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_transaction")
    def test_on_transaction_changed_falls_back_when_account_is_empty(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """Empty frame.account falls back to settings.tiger_account."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        mock_serialize.return_value = {"filledPrice": 200.0}
        frame = MagicMock()
        frame.account = ""
        frame.timestamp = 1700000000

        subscriber._on_transaction_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.account == "DU12345"

    @patch("tiger_mcp.events.subscriber.serialize_transaction")
    def test_on_transaction_changed_exception_caught(
        self,
        mock_serialize: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Exceptions in callback should be caught and logged."""
        mock_serialize.side_effect = ValueError("bad frame data")
        frame = MagicMock()

        with caplog.at_level(logging.ERROR, logger="tiger_mcp.events.subscriber"):
            subscriber._on_transaction_changed(frame)

        # Should not raise
        mock_publisher.publish.assert_not_called()
        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "transaction_event_processing_failed" in r.message
        ]
        assert len(error_records) == 1

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_transaction")
    def test_on_transaction_changed_passes_received_at(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """received_at should be set at callback invocation time."""
        mock_datetime.now.return_value.isoformat.return_value = (
            "2024-06-01T12:00:00+00:00"
        )
        mock_serialize.return_value = {"filledPrice": 175.50}
        frame = MagicMock()
        frame.account = "DU12345"
        frame.timestamp = 1700000000

        subscriber._on_transaction_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.received_at == "2024-06-01T12:00:00+00:00"

    @patch("tiger_mcp.events.subscriber.datetime")
    @patch("tiger_mcp.events.subscriber.serialize_transaction")
    def test_on_transaction_changed_timestamp_fallback(
        self,
        mock_serialize: MagicMock,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """When frame.timestamp is missing, None should be passed."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        mock_serialize.return_value = {"filledPrice": 175.50}
        frame = MagicMock(spec=[])  # No attributes

        subscriber._on_transaction_changed(frame)

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.timestamp is None


# ---------------------------------------------------------------------------
# _handle_event (shared event handling logic)
# ---------------------------------------------------------------------------


class TestHandleEvent:
    """Test the shared _handle_event method that both callbacks delegate to."""

    @patch("tiger_mcp.events.subscriber.datetime")
    def test_handle_event_delegates_serializer(
        self,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_handle_event should call the provided serializer with the frame."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        serializer = MagicMock(return_value={"key": "value"})
        frame = MagicMock()
        frame.account = "DU12345"
        frame.timestamp = 1700000000

        subscriber._handle_event(
            frame, serializer, "test_event", "test_error_key",
            model_cls=OrderStatusEvent,
        )

        serializer.assert_called_once_with(frame)

    @patch("tiger_mcp.events.subscriber.datetime")
    def test_handle_event_publishes_with_correct_event_type(
        self,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_handle_event should pass the event_type to publisher.publish."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        serializer = MagicMock(return_value={"key": "value"})
        frame = MagicMock()
        frame.account = "DU12345"
        frame.timestamp = 1700000000

        subscriber._handle_event(
            frame, serializer, "custom_type", "err",
            model_cls=OrderStatusEvent,
        )

        call_args = mock_publisher.publish.call_args
        assert call_args[0][0] == "custom_type"

    @patch("tiger_mcp.events.subscriber.datetime")
    def test_handle_event_uses_frame_account(
        self,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_handle_event should use frame.account when present."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        serializer = MagicMock(return_value={})
        frame = MagicMock()
        frame.account = "DU99999"
        frame.timestamp = 1700000000

        subscriber._handle_event(
            frame, serializer, "evt", "err",
            model_cls=OrderStatusEvent,
        )

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.account == "DU99999"

    @patch("tiger_mcp.events.subscriber.datetime")
    def test_handle_event_falls_back_to_settings_account(
        self,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_handle_event should fall back to settings account when frame lacks one."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        serializer = MagicMock(return_value={})
        frame = MagicMock(spec=[])  # No attributes

        subscriber._handle_event(
            frame, serializer, "evt", "err",
            model_cls=OrderStatusEvent,
        )

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.account == "DU12345"

    @patch("tiger_mcp.events.subscriber.datetime")
    def test_handle_event_falls_back_when_account_empty(
        self,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_handle_event should fall back when frame.account is empty string."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        serializer = MagicMock(return_value={})
        frame = MagicMock()
        frame.account = ""
        frame.timestamp = 1700000000

        subscriber._handle_event(
            frame, serializer, "evt", "err",
            model_cls=OrderStatusEvent,
        )

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.account == "DU12345"

    @patch("tiger_mcp.events.subscriber.datetime")
    def test_handle_event_timestamp_fallback(
        self,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_handle_event should use None when frame lacks timestamp."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        serializer = MagicMock(return_value={})
        frame = MagicMock(spec=[])

        subscriber._handle_event(
            frame, serializer, "evt", "err",
            model_cls=OrderStatusEvent,
        )

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.timestamp is None

    @patch("tiger_mcp.events.subscriber.datetime")
    def test_handle_event_sets_received_at(
        self,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_handle_event should capture current time as received_at."""
        mock_datetime.now.return_value.isoformat.return_value = (
            "2024-06-01T12:00:00+00:00"
        )
        serializer = MagicMock(return_value={})
        frame = MagicMock()
        frame.account = "DU12345"
        frame.timestamp = 1700000000

        subscriber._handle_event(
            frame, serializer, "evt", "err",
            model_cls=OrderStatusEvent,
        )

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert event.received_at == "2024-06-01T12:00:00+00:00"

    def test_handle_event_logs_error_with_custom_key(
        self,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """_handle_event should log with the provided error_key on exception."""
        serializer = MagicMock(side_effect=ValueError("boom"))
        frame = MagicMock()

        with caplog.at_level(logging.ERROR, logger="tiger_mcp.events.subscriber"):
            subscriber._handle_event(
                frame, serializer, "evt", "my_custom_error_key",
                model_cls=OrderStatusEvent,
            )

        mock_publisher.publish.assert_not_called()
        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "my_custom_error_key" in r.message
        ]
        assert len(error_records) == 1

    @patch("tiger_mcp.events.subscriber.datetime")
    def test_handle_event_catches_model_construction_error(
        self,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Model construction errors should be caught and logged."""
        mock_datetime.now.return_value.isoformat.return_value = (
            "2024-01-15T10:30:00+00:00"
        )
        serializer = MagicMock(return_value={"status": "FILLED"})
        frame = MagicMock()
        frame.account = "DU12345"
        frame.timestamp = 1700000000

        bad_model_cls = MagicMock(side_effect=ValueError("bad model"))

        with caplog.at_level(logging.ERROR, logger="tiger_mcp.events.subscriber"):
            subscriber._handle_event(
                frame, serializer, "evt", "model_error_key",
                model_cls=bad_model_cls,
            )

        mock_publisher.publish.assert_not_called()
        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "model_error_key" in r.message
        ]
        assert len(error_records) == 1

    @patch("tiger_mcp.events.subscriber.datetime")
    def test_handle_event_constructs_envelope_model(
        self,
        mock_datetime: MagicMock,
        subscriber: PushSubscriber,
        mock_publisher: MagicMock,
    ) -> None:
        """_handle_event should construct the correct model type from serialized data."""
        mock_datetime.now.return_value.isoformat.return_value = "t"
        serializer = MagicMock(return_value={"filledPrice": 175.50})
        frame = MagicMock()
        frame.account = "DU12345"
        frame.timestamp = 1700000000

        subscriber._handle_event(
            frame, serializer, "transaction", "err",
            model_cls=TransactionEvent,
        )

        call_args = mock_publisher.publish.call_args
        event = call_args[0][1]
        assert isinstance(event, TransactionEvent)
        assert event.payload.filledPrice == 175.50


# ---------------------------------------------------------------------------
# _on_connected callback
# ---------------------------------------------------------------------------


class TestOnConnected:
    """Test the connected callback."""

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_on_connected_resets_reconnect_attempt(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """_on_connected should reset the reconnect attempt counter to 0."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance

        subscriber.start()
        # Simulate some failed reconnect attempts
        subscriber._reconnect_attempt = 5

        subscriber._on_connected(MagicMock())

        assert subscriber._reconnect_attempt == 0

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_on_connected_subscribes_to_orders_and_transactions(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """_on_connected should subscribe to both orders and transactions."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance

        subscriber.start()
        subscriber._on_connected(MagicMock())

        mock_push_instance.subscribe_order.assert_called_once_with(
            account="DU12345"
        )
        mock_push_instance.subscribe_transaction.assert_called_once_with(
            account="DU12345"
        )

    def test_on_connected_without_push_client_does_not_subscribe(
        self,
        subscriber: PushSubscriber,
    ) -> None:
        """_on_connected when _push_client is None should not raise."""
        assert subscriber._push_client is None
        # Should not raise
        subscriber._on_connected(MagicMock())


# ---------------------------------------------------------------------------
# _on_disconnected callback
# ---------------------------------------------------------------------------


class TestOnDisconnected:
    """Test the disconnected callback and reconnection trigger."""

    @patch.object(PushSubscriber, "_reconnect_worker")
    def test_on_disconnected_spawns_reconnect_thread(
        self,
        mock_worker: MagicMock,
        subscriber: PushSubscriber,
    ) -> None:
        """_on_disconnected should spawn a daemon thread for reconnection."""
        with patch("tiger_mcp.events.subscriber.threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            subscriber._on_disconnected()

            mock_thread_cls.assert_called_once_with(
                target=subscriber._reconnect_worker,
                daemon=True,
                name="push-reconnect",
            )
            mock_thread.start.assert_called_once()

    def test_on_disconnected_skipped_when_stopped(
        self,
        subscriber: PushSubscriber,
    ) -> None:
        """After stop_event is set, _on_disconnected should not spawn a thread."""
        subscriber._stop_event.set()

        with patch("tiger_mcp.events.subscriber.threading.Thread") as mock_thread_cls:
            subscriber._on_disconnected()

        mock_thread_cls.assert_not_called()

    def test_on_disconnected_skipped_when_already_reconnecting(
        self,
        subscriber: PushSubscriber,
    ) -> None:
        """If already reconnecting, _on_disconnected should be a no-op."""
        subscriber._reconnecting = True

        with patch("tiger_mcp.events.subscriber.threading.Thread") as mock_thread_cls:
            subscriber._on_disconnected()

        mock_thread_cls.assert_not_called()

    def test_on_disconnected_sets_reconnecting_flag(
        self,
        subscriber: PushSubscriber,
    ) -> None:
        """_on_disconnected should set _reconnecting=True before spawning."""
        with patch("tiger_mcp.events.subscriber.threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            subscriber._on_disconnected()

        assert subscriber._reconnecting is True

    def test_reconnect_lock_prevents_duplicate_spawns(
        self,
        subscriber: PushSubscriber,
    ) -> None:
        """Sequential _on_disconnected calls should only spawn one thread.

        After the first call sets _reconnecting=True, subsequent calls
        should see the flag and skip spawning. The flag is only reset
        by _reconnect_worker, which doesn't run (mocked thread).
        """
        with patch("tiger_mcp.events.subscriber.threading.Thread") as mock_thread_cls:
            mock_thread = MagicMock()
            mock_thread_cls.return_value = mock_thread

            # First call should spawn
            subscriber._on_disconnected()
            # Second call should see _reconnecting=True and skip
            subscriber._on_disconnected()

        assert mock_thread_cls.call_count == 1
        assert mock_thread.start.call_count == 1


# ---------------------------------------------------------------------------
# _reconnect_worker
# ---------------------------------------------------------------------------


class TestReconnectWorker:
    """Test the reconnect worker wrapper."""

    @patch.object(PushSubscriber, "_reconnect_with_backoff")
    def test_worker_resets_reconnecting_flag(
        self,
        mock_backoff: MagicMock,
        subscriber: PushSubscriber,
    ) -> None:
        """_reconnect_worker should reset _reconnecting to False."""
        subscriber._reconnecting = True

        subscriber._reconnect_worker()

        assert subscriber._reconnecting is False

    @patch.object(PushSubscriber, "_reconnect_with_backoff")
    def test_worker_resets_flag_on_exception(
        self,
        mock_backoff: MagicMock,
        subscriber: PushSubscriber,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """_reconnecting resets even if _reconnect_with_backoff raises."""
        mock_backoff.side_effect = RuntimeError("unexpected")
        subscriber._reconnecting = True

        with caplog.at_level(
            logging.CRITICAL, logger="tiger_mcp.events.subscriber"
        ):
            subscriber._reconnect_worker()

        assert subscriber._reconnecting is False
        critical_records = [
            r for r in caplog.records
            if r.levelno == logging.CRITICAL
            and "push_reconnect_worker_error" in r.message
        ]
        assert len(critical_records) == 1


# ---------------------------------------------------------------------------
# _on_error callback
# ---------------------------------------------------------------------------


class TestOnError:
    """Test the error callback."""

    def test_on_error_logs_error(
        self,
        subscriber: PushSubscriber,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """_on_error should log the frame at ERROR level."""
        frame = MagicMock()
        frame.__str__ = lambda _: "error frame content"

        with caplog.at_level(logging.ERROR, logger="tiger_mcp.events.subscriber"):
            subscriber._on_error(frame)

        error_records = [
            r for r in caplog.records
            if r.levelno == logging.ERROR
            and "push_client_error" in r.message
        ]
        assert len(error_records) == 1

    def test_on_error_handles_frame_str_failure(
        self,
        subscriber: PushSubscriber,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """_on_error should handle frames whose __str__ raises."""
        frame = MagicMock()
        frame.__str__ = MagicMock(side_effect=RuntimeError("bad str"))

        # str() on a broken object raises; the logger extra dict
        # calls str(frame) which will raise. Verify it propagates
        # (the callback doesn't have a try/except wrapper).
        with pytest.raises(RuntimeError, match="bad str"):
            subscriber._on_error(frame)


# ---------------------------------------------------------------------------
# Reconnection with backoff
# ---------------------------------------------------------------------------


class TestReconnectWithBackoff:
    """Test the exponential backoff reconnection logic."""

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_reconnect_backoff_delay_calculation(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """Backoff delays should follow: base * 2^attempt, capped at 60s."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance
        subscriber._push_client = mock_push_instance
        subscriber._client_config = mock_client_config

        # Make connect always fail so we iterate through all attempts
        mock_push_instance.connect.side_effect = ConnectionError("fail")

        recorded_delays: list[float] = []

        def capture_delay(timeout: float) -> bool:
            recorded_delays.append(timeout)
            return False  # Not stopped

        with patch.object(subscriber._stop_event, "wait", side_effect=capture_delay):
            subscriber._reconnect_with_backoff()

        # With base_delay=1.0 and max_attempts=5:
        # attempt 0: 1.0 * 2^0 = 1.0
        # attempt 1: 1.0 * 2^1 = 2.0
        # attempt 2: 1.0 * 2^2 = 4.0
        # attempt 3: 1.0 * 2^3 = 8.0
        # attempt 4: 1.0 * 2^4 = 16.0
        expected = [1.0, 2.0, 4.0, 8.0, 16.0]
        assert recorded_delays == expected

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_reconnect_backoff_capped_at_60(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        settings: Settings,
        mock_publisher: MagicMock,
        mock_client_config: MagicMock,
    ) -> None:
        """Backoff delay should be capped at 60 seconds."""
        # Override with high max_attempts to reach cap
        settings_high = Settings(
            tiger_id=settings.tiger_id,
            tiger_account=settings.tiger_account,
            private_key_path=settings.private_key_path,
            events_enabled=True,
            redis_url="redis://localhost:6379/0",
            push_reconnect_max_attempts=10,
            push_reconnect_base_delay=1.0,
        )
        sub = PushSubscriber(settings=settings_high, publisher=mock_publisher)

        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance
        sub._push_client = mock_push_instance
        sub._client_config = mock_client_config
        mock_push_instance.connect.side_effect = ConnectionError("fail")

        recorded_delays: list[float] = []

        def capture_delay(timeout: float) -> bool:
            recorded_delays.append(timeout)
            return False

        with patch.object(sub._stop_event, "wait", side_effect=capture_delay):
            sub._reconnect_with_backoff()

        # attempt 6: 1.0 * 2^6 = 64 -> capped to 60
        # attempt 7: 1.0 * 2^7 = 128 -> capped to 60
        # etc.
        for delay in recorded_delays:
            assert delay <= 60.0

        # Verify at least some delays hit the cap
        assert 60.0 in recorded_delays

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_reconnect_exhausted_logs_critical(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """After exhausting all attempts, a CRITICAL log should be emitted."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance
        subscriber._push_client = mock_push_instance
        subscriber._client_config = mock_client_config
        mock_push_instance.connect.side_effect = ConnectionError("fail")

        with patch.object(subscriber._stop_event, "wait", return_value=False):
            with caplog.at_level(
                logging.CRITICAL, logger="tiger_mcp.events.subscriber"
            ):
                subscriber._reconnect_with_backoff()

        critical_records = [
            r
            for r in caplog.records
            if r.levelno == logging.CRITICAL
            and "push_reconnect_exhausted" in r.message
        ]
        assert len(critical_records) == 1

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_reconnect_stops_when_stop_event_set(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """Reconnection loop should exit early when stop_event is set."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance
        subscriber._push_client = mock_push_instance
        subscriber._client_config = mock_client_config

        # Set stop event after the first wait call
        call_count = 0

        def set_stop_on_second_call(timeout: float) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                subscriber._stop_event.set()
                return True
            return False

        with patch.object(
            subscriber._stop_event, "wait", side_effect=set_stop_on_second_call
        ):
            subscriber._reconnect_with_backoff()

        # Should have exited early -- not all 5 attempts consumed
        assert subscriber._reconnect_attempt < 5

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_reconnect_successful_on_second_attempt(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """Successful reconnection should stop the backoff loop."""
        mock_build_config.return_value = mock_client_config
        mock_push_instance = MagicMock()
        mock_push_client_cls.return_value = mock_push_instance
        subscriber._push_client = mock_push_instance
        subscriber._client_config = mock_client_config

        # Fail first, succeed second
        mock_push_instance.connect.side_effect = [
            ConnectionError("fail"),
            None,  # Success
        ]

        with patch.object(subscriber._stop_event, "wait", return_value=False):
            subscriber._reconnect_with_backoff()

        # Should have stopped after 2 attempts (connect called twice)
        assert mock_push_instance.connect.call_count == 2
        assert subscriber._reconnect_attempt == 2

    @patch("tiger_mcp.events.subscriber.build_client_config")
    @patch("tiger_mcp.events.subscriber.PushClient")
    def test_reconnect_stops_when_stop_event_set_before_wait(
        self,
        mock_push_client_cls: MagicMock,
        mock_build_config: MagicMock,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """Pre-set stop_event causes immediate reconnect exit."""
        mock_build_config.return_value = mock_client_config
        subscriber._push_client = MagicMock()
        subscriber._client_config = mock_client_config

        subscriber._stop_event.set()
        subscriber._reconnect_with_backoff()

        # No connect attempts should have been made
        assert subscriber._reconnect_attempt == 0

    def test_reconnect_uses_cached_client_config(
        self,
        subscriber: PushSubscriber,
        mock_client_config: MagicMock,
    ) -> None:
        """_reconnect_with_backoff should use cached config, not rebuild it."""
        subscriber._push_client = MagicMock()
        subscriber._client_config = mock_client_config

        # Make connect succeed on first attempt
        subscriber._push_client.connect.return_value = None

        with patch.object(subscriber._stop_event, "wait", return_value=False):
            with patch(
                "tiger_mcp.events.subscriber.build_client_config"
            ) as mock_build:
                subscriber._reconnect_with_backoff()

        # build_client_config should NOT be called during reconnect
        mock_build.assert_not_called()
        subscriber._push_client.connect.assert_called_once_with(
            mock_client_config.tiger_id,
            mock_client_config.private_key,
        )
