"""Redis Stream publisher for Tiger Brokers events."""

from __future__ import annotations

import logging

import redis

from tiger_mcp.events.models import _BaseEvent

logger = logging.getLogger(__name__)


class RedisStreamPublisher:
    """Publishes events to Redis Streams using XADD.

    Uses synchronous redis.Redis because PushClient callbacks run in
    a thread pool, not an asyncio event loop.

    Parameters
    ----------
    redis_url:
        Redis connection URL (e.g. ``redis://localhost:6379/0``).
    stream_prefix:
        Prefix for stream keys. Events are published to
        ``{stream_prefix}:{event_type}``.
    maxlen:
        Approximate maximum stream length for trimming via ``MAXLEN ~``.
    """

    def __init__(self, redis_url: str, stream_prefix: str, maxlen: int) -> None:
        self._redis_url = redis_url
        self._stream_prefix = stream_prefix
        self._maxlen = maxlen
        self._redis: redis.Redis | None = None
        self._consecutive_failures: int = 0

    def connect(self) -> None:
        """Establish connection to Redis."""
        client = redis.Redis.from_url(
            self._redis_url, decode_responses=True
        )
        # Verify connectivity before assigning to self._redis
        client.ping()
        self._redis = client
        logger.info("redis_connected", extra={"url": self._redis_url})

    def publish(self, event_type: str, event: _BaseEvent) -> str | None:
        """Publish an event to a Redis stream.

        Parameters
        ----------
        event_type:
            Event category (e.g. ``"order"``). Used as stream key suffix.
        event:
            A typed envelope model instance to serialize and publish.

        Returns
        -------
        str | None
            The Redis stream entry ID on success, or ``None`` on failure.
        """
        # Snapshot the reference to avoid TOCTOU race with close().
        client = self._redis
        if client is None:
            logger.warning(
                "redis_publish_skipped",
                extra={"reason": "not connected"},
            )
            return None

        stream_key = f"{self._stream_prefix}:{event_type}"
        fields = {"data": event.model_dump_json(exclude_unset=True)}

        try:
            entry_id = client.xadd(
                stream_key, fields, maxlen=self._maxlen, approximate=True
            )
            self._consecutive_failures = 0
            return entry_id
        except (redis.ConnectionError, redis.TimeoutError) as exc:
            self._consecutive_failures += 1
            log_extra = {
                "stream": stream_key,
                "consecutive_failures": self._consecutive_failures,
                "error": str(exc),
            }
            is_escalated = self._consecutive_failures >= 10
            log_fn = logger.error if is_escalated else logger.warning
            log_fn("redis_publish_failed", extra=log_extra)
            return None

    def close(self) -> None:
        """Close the Redis connection."""
        if self._redis is not None:
            self._redis.close()
            self._redis = None
            logger.info("redis_disconnected")

    @property
    def is_connected(self) -> bool:
        """Return True if a Redis connection is established."""
        return self._redis is not None
