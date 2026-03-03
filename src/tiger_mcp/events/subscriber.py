"""Tiger Brokers PushClient subscriber for real-time order events.

Bridges Tiger's WebSocket-based PushClient to Redis Streams by subscribing
to order status change events and publishing them via RedisStreamPublisher.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from tigeropen.push.push_client import PushClient

from tiger_mcp.api.config_factory import build_client_config
from tiger_mcp.config import Settings
from tiger_mcp.events.publisher import RedisStreamPublisher
from tiger_mcp.events.serializers import serialize_order_status, serialize_transaction

logger = logging.getLogger(__name__)


class PushSubscriber:
    """Subscribes to Tiger PushClient events and publishes to Redis streams.

    The PushClient callbacks run in a thread pool managed by the SDK.
    This class uses synchronous Redis (via RedisStreamPublisher) because
    the callbacks are not in an asyncio context.

    Parameters
    ----------
    settings:
        Runtime settings with credentials and reconnection config.
    publisher:
        RedisStreamPublisher for writing events to Redis streams.
    """

    def __init__(self, settings: Settings, publisher: RedisStreamPublisher) -> None:
        self._settings = settings
        self._publisher = publisher
        self._push_client: PushClient | None = None
        self._client_config: Any = None
        self._reconnect_attempt: int = 0
        self._reconnecting: bool = False
        self._reconnect_lock = threading.Lock()
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Connect the PushClient and subscribe to order status events."""
        self._client_config = build_client_config(self._settings)
        host_port = self._client_config.socket_host_port
        # socket_host_port is a tuple of (protocol, host, port)
        self._push_client = PushClient(
            host_port[1],
            host_port[2],
            use_ssl=(host_port[0] == "ssl"),
        )
        self._push_client.order_changed = self._on_order_changed
        self._push_client.transaction_changed = self._on_transaction_changed
        self._push_client.connect_callback = self._on_connected
        self._push_client.disconnect_callback = self._on_disconnected
        self._push_client.error_callback = self._on_error

        self._push_client.connect(
            self._client_config.tiger_id,
            self._client_config.private_key,
        )
        logger.info(
            "push_subscriber_started",
            extra={"account": self._settings.tiger_account},
        )

    def stop(self) -> None:
        """Disconnect the PushClient and close the publisher."""
        self._stop_event.set()
        if self._push_client is not None:
            try:
                self._push_client.disconnect()
            except Exception:
                logger.warning("push_client_disconnect_error", exc_info=True)
            self._push_client = None
        self._publisher.close()
        logger.info("push_subscriber_stopped")

    # ------------------------------------------------------------------
    # PushClient callbacks (called from SDK thread pool)
    # ------------------------------------------------------------------

    def _handle_event(
        self,
        frame: Any,
        serializer: Callable[[Any], dict[str, Any]],
        event_type: str,
        error_key: str,
    ) -> None:
        """Serialize a PushClient frame and publish to Redis streams.

        Parameters
        ----------
        frame:
            Raw frame object from the PushClient callback.
        serializer:
            Function that converts the frame into a JSON-serializable dict.
        event_type:
            Event type string passed to the publisher (e.g. "order").
        error_key:
            Structured-logging key used when an exception is caught.
        """
        try:
            received_at = datetime.now(UTC).isoformat()
            payload = serializer(frame)
            account = getattr(frame, "account", self._settings.tiger_account)
            timestamp = str(getattr(frame, "timestamp", ""))
            self._publisher.publish(
                event_type=event_type,
                payload=payload,
                account=account or self._settings.tiger_account,
                timestamp=timestamp,
                received_at=received_at,
            )
        except Exception:
            logger.error(error_key, exc_info=True)

    def _on_order_changed(self, frame: Any) -> None:
        """Handle order status change events from PushClient."""
        self._handle_event(
            frame, serialize_order_status, "order", "order_event_processing_failed"
        )

    def _on_transaction_changed(self, frame: Any) -> None:
        """Handle transaction change events from PushClient."""
        self._handle_event(
            frame,
            serialize_transaction,
            "transaction",
            "transaction_event_processing_failed",
        )

    def _on_connected(self, frame: Any) -> None:
        """Handle successful PushClient connection."""
        self._reconnect_attempt = 0
        logger.info("push_client_connected")
        # Subscribe to order status events for our account
        if self._push_client is not None:
            self._push_client.subscribe_order(
                account=self._settings.tiger_account,
            )
            logger.info(
                "push_subscribed_orders",
                extra={"account": self._settings.tiger_account},
            )
            self._push_client.subscribe_transaction(
                account=self._settings.tiger_account,
            )
            logger.info(
                "push_subscribed_transactions",
                extra={"account": self._settings.tiger_account},
            )

    def _on_disconnected(self) -> None:
        """Handle PushClient disconnection with exponential backoff reconnection.

        Spawns a daemon thread for the reconnection loop so the SDK
        callback thread is not blocked.
        """
        if self._stop_event.is_set():
            logger.info("push_client_disconnected_by_stop")
            return

        with self._reconnect_lock:
            if self._reconnecting:
                return
            self._reconnecting = True

        t = threading.Thread(
            target=self._reconnect_worker,
            daemon=True,
            name="push-reconnect",
        )
        t.start()

    def _on_error(self, frame: Any) -> None:
        """Handle PushClient errors."""
        logger.error(
            "push_client_error",
            extra={"frame": str(frame)},
        )

    # ------------------------------------------------------------------
    # Reconnection logic
    # ------------------------------------------------------------------

    def _reconnect_worker(self) -> None:
        """Wrapper that runs _reconnect_with_backoff and resets the flag."""
        try:
            self._reconnect_with_backoff()
        except Exception:
            logger.critical("push_reconnect_worker_error", exc_info=True)
        finally:
            with self._reconnect_lock:
                self._reconnecting = False

    def _reconnect_with_backoff(self) -> None:
        """Attempt reconnection with exponential backoff."""
        max_attempts = self._settings.push_reconnect_max_attempts
        base_delay = self._settings.push_reconnect_base_delay

        while self._reconnect_attempt < max_attempts:
            if self._stop_event.is_set():
                return

            delay = min(base_delay * (2 ** self._reconnect_attempt), 60.0)
            self._reconnect_attempt += 1

            logger.warning(
                "push_reconnecting",
                extra={
                    "attempt": self._reconnect_attempt,
                    "max_attempts": max_attempts,
                    "delay_seconds": delay,
                },
            )

            self._stop_event.wait(timeout=delay)
            if self._stop_event.is_set():
                return

            try:
                if self._push_client is not None:
                    self._push_client.connect(
                        self._client_config.tiger_id,
                        self._client_config.private_key,
                    )
                    # _on_connected callback handles re-subscribing
                    return
            except Exception:
                logger.warning(
                    "push_reconnect_failed",
                    exc_info=True,
                    extra={"attempt": self._reconnect_attempt},
                )

        logger.critical(
            "push_reconnect_exhausted",
            extra={"max_attempts": max_attempts},
        )
