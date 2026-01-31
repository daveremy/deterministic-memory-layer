"""Event store backends for DML.

This module provides the abstract interface for event storage and concrete
implementations. The default SQLite backend is suitable for single-agent
deployments. Alternative backends (Redis, Postgres) support distributed
and high-scale scenarios.

Backends:
    - SQLiteEventStore: Default, single-file, portable (implemented)
    - RedisEventStore: Distributed, streaming-ready (stub for future)
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dml.events import Event, EventType


class EventStoreBackend(ABC):
    """Abstract interface for event storage backends.

    All backends must provide append-only semantics with the following guarantees:
    - Events are never modified after append
    - global_seq is monotonically increasing
    - Replay of events produces deterministic state

    The interface mirrors distributed tracing concepts:
    - global_seq <-> span_id
    - caused_by <-> parent_span_id
    - correlation_id <-> trace_id
    """

    @abstractmethod
    def append(self, event: "Event") -> int:
        """Append event to store, return assigned global_seq.

        The implementation must:
        1. Assign a unique, monotonically increasing global_seq
        2. Assign a monotonic timestamp
        3. Persist the event durably
        4. Update event.global_seq and event.timestamp in place
        """
        ...

    @abstractmethod
    def get_event(self, seq: int) -> "Event | None":
        """Get single event by global_seq."""
        ...

    @abstractmethod
    def get_events(
        self, from_seq: int = 0, to_seq: int | None = None
    ) -> list["Event"]:
        """Get events in sequence range (inclusive)."""
        ...

    @abstractmethod
    def get_by_correlation(self, correlation_id: str) -> list["Event"]:
        """Get all events with given correlation_id."""
        ...

    @abstractmethod
    def get_by_type(self, event_type: "EventType") -> list["Event"]:
        """Get all events of a specific type."""
        ...

    @abstractmethod
    def get_caused_by(self, seq: int) -> list["Event"]:
        """Get all events caused by a specific event."""
        ...

    @abstractmethod
    def get_max_seq(self) -> int:
        """Get the maximum global_seq in the store."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close the backend and release resources."""
        ...


class RedisEventStore(EventStoreBackend):
    """Redis Streams backend for distributed event storage.

    This is a STUB implementation for future development. Redis Streams
    provide natural support for event sourcing patterns:

    - Append-only: XADD adds entries that cannot be modified
    - Ordering: Stream IDs provide monotonic ordering
    - Consumer groups: Multiple readers with delivery guarantees
    - Pub/sub: Real-time notifications of new events

    Architecture (planned):
        - Each DML instance writes to a Redis Stream
        - Stream ID maps to global_seq
        - Consumer groups enable distributed replay
        - Pub/sub notifies of constraint violations

    Note:
        This implementation is not functional. It serves as a design
        placeholder showing the intended interface for Redis integration.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        stream_key: str = "dml:events",
        **redis_kwargs,
    ):
        """Initialize Redis connection (stub).

        Args:
            host: Redis server host.
            port: Redis server port.
            stream_key: Redis Stream key for events.
            **redis_kwargs: Additional arguments for redis.Redis().
        """
        self._host = host
        self._port = port
        self._stream_key = stream_key
        self._redis_kwargs = redis_kwargs
        self._client = None  # Would be redis.Redis instance

        # Note: Not connecting - this is a stub
        raise NotImplementedError(
            "RedisEventStore is a design stub. "
            "Use SQLite EventStore for current functionality. "
            "Redis implementation planned for future release."
        )

    def append(self, event: "Event") -> int:
        """Append event using XADD (stub).

        Would use:
            stream_id = self._client.xadd(
                self._stream_key,
                event.to_dict(),
                id='*'  # Auto-generate ID
            )
        """
        raise NotImplementedError("RedisEventStore is a stub")

    def get_event(self, seq: int) -> "Event | None":
        """Get event using XRANGE (stub).

        Would use:
            entries = self._client.xrange(
                self._stream_key,
                min=seq, max=seq, count=1
            )
        """
        raise NotImplementedError("RedisEventStore is a stub")

    def get_events(
        self, from_seq: int = 0, to_seq: int | None = None
    ) -> list["Event"]:
        """Get events using XRANGE (stub).

        Would use:
            entries = self._client.xrange(
                self._stream_key,
                min=from_seq,
                max=to_seq or '+',
            )
        """
        raise NotImplementedError("RedisEventStore is a stub")

    def get_by_correlation(self, correlation_id: str) -> list["Event"]:
        """Get events by correlation_id (stub).

        Note: This would require a secondary index or full scan.
        Options:
            1. Maintain a separate sorted set per correlation_id
            2. Use RedisSearch for indexed queries
            3. Full XRANGE scan with filtering (slow)
        """
        raise NotImplementedError("RedisEventStore is a stub")

    def get_by_type(self, event_type: "EventType") -> list["Event"]:
        """Get events by type (stub).

        Similar indexing considerations as get_by_correlation.
        """
        raise NotImplementedError("RedisEventStore is a stub")

    def get_caused_by(self, seq: int) -> list["Event"]:
        """Get events caused by seq (stub).

        Similar indexing considerations as get_by_correlation.
        """
        raise NotImplementedError("RedisEventStore is a stub")

    def get_max_seq(self) -> int:
        """Get max seq using XREVRANGE (stub).

        Would use:
            entries = self._client.xrevrange(
                self._stream_key, count=1
            )
        """
        raise NotImplementedError("RedisEventStore is a stub")

    def close(self) -> None:
        """Close Redis connection (stub)."""
        if self._client:
            self._client.close()


# Note: The existing EventStore in events.py is the SQLite implementation.
# It implicitly implements EventStoreBackend but doesn't inherit from it
# to avoid circular imports. For type checking purposes, it's compatible.
