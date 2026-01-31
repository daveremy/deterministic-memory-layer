"""Tests for EventStore and Event."""

import tempfile
from pathlib import Path

import pytest

from dml.events import Event, EventStore, EventType


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)
    # Also clean up WAL files
    Path(db_path + "-wal").unlink(missing_ok=True)
    Path(db_path + "-shm").unlink(missing_ok=True)


@pytest.fixture
def store(temp_db):
    """Create an EventStore instance."""
    s = EventStore(temp_db)
    yield s
    s.close()


class TestEvent:
    def test_event_creation(self):
        event = Event(
            type=EventType.TurnStarted,
            payload={"turn_id": 1},
            turn_id=1,
        )
        assert event.type == EventType.TurnStarted
        assert event.payload == {"turn_id": 1}
        assert event.turn_id == 1
        assert event.global_seq is None
        assert event.timestamp is None

    def test_event_to_dict(self):
        event = Event(
            type=EventType.DecisionMade,
            payload={"text": "Use json.loads"},
            turn_id=2,
            caused_by=1,
            correlation_id="test-123",
        )
        event.global_seq = 5
        event.timestamp = 100

        d = event.to_dict()
        assert d["type"] == "DecisionMade"
        assert d["payload"] == {"text": "Use json.loads"}
        assert d["turn_id"] == 2
        assert d["caused_by"] == 1
        assert d["correlation_id"] == "test-123"
        assert d["global_seq"] == 5
        assert d["timestamp"] == 100

    def test_event_from_dict(self):
        d = {
            "type": "FactAdded",
            "payload": {"key": "test", "value": 42},
            "turn_id": 3,
            "global_seq": 10,
            "timestamp": 200,
            "caused_by": None,
            "correlation_id": None,
        }
        event = Event.from_dict(d)
        assert event.type == EventType.FactAdded
        assert event.payload["key"] == "test"
        assert event.global_seq == 10


class TestEventStore:
    def test_append_returns_seq(self, store):
        event = Event(
            type=EventType.TurnStarted,
            payload={"turn_id": 1},
        )
        seq = store.append(event)
        assert seq == 1
        assert event.global_seq == 1
        assert event.timestamp == 1

    def test_append_multiple_events(self, store):
        seq1 = store.append(Event(type=EventType.TurnStarted, payload={}))
        seq2 = store.append(Event(type=EventType.UserMessageReceived, payload={}))
        seq3 = store.append(Event(type=EventType.DecisionMade, payload={}))

        assert seq1 == 1
        assert seq2 == 2
        assert seq3 == 3

    def test_monotonic_timestamps(self, store):
        events = []
        for i in range(5):
            e = Event(type=EventType.TurnStarted, payload={"i": i})
            store.append(e)
            events.append(e)

        timestamps = [e.timestamp for e in events]
        assert timestamps == sorted(timestamps)
        assert len(set(timestamps)) == 5  # All unique

    def test_get_event(self, store):
        event = Event(
            type=EventType.FactAdded,
            payload={"key": "test", "value": "hello"},
            turn_id=1,
        )
        seq = store.append(event)

        retrieved = store.get_event(seq)
        assert retrieved is not None
        assert retrieved.type == EventType.FactAdded
        assert retrieved.payload["key"] == "test"

    def test_get_event_not_found(self, store):
        result = store.get_event(999)
        assert result is None

    def test_get_events_all(self, store):
        for i in range(3):
            store.append(Event(type=EventType.TurnStarted, payload={"i": i}))

        events = store.get_events()
        assert len(events) == 3

    def test_get_events_range(self, store):
        for i in range(5):
            store.append(Event(type=EventType.TurnStarted, payload={"i": i}))

        events = store.get_events(from_seq=2, to_seq=4)
        assert len(events) == 3
        assert events[0].global_seq == 2
        assert events[-1].global_seq == 4

    def test_get_by_correlation(self, store):
        corr_id = "test-correlation"
        store.append(Event(type=EventType.TurnStarted, payload={}, correlation_id=corr_id))
        store.append(Event(type=EventType.DecisionMade, payload={}, correlation_id=corr_id))
        store.append(Event(type=EventType.TurnStarted, payload={}, correlation_id="other"))

        events = store.get_by_correlation(corr_id)
        assert len(events) == 2
        assert all(e.correlation_id == corr_id for e in events)

    def test_get_by_type(self, store):
        store.append(Event(type=EventType.TurnStarted, payload={}))
        store.append(Event(type=EventType.DecisionMade, payload={}))
        store.append(Event(type=EventType.TurnStarted, payload={}))

        events = store.get_by_type(EventType.TurnStarted)
        assert len(events) == 2

    def test_get_caused_by(self, store):
        seq1 = store.append(Event(type=EventType.TurnStarted, payload={}))
        store.append(Event(type=EventType.DecisionMade, payload={}, caused_by=seq1))
        store.append(Event(type=EventType.FactAdded, payload={}, caused_by=seq1))
        store.append(Event(type=EventType.TurnStarted, payload={}))

        caused = store.get_caused_by(seq1)
        assert len(caused) == 2

    def test_get_max_seq(self, store):
        assert store.get_max_seq() == 0

        store.append(Event(type=EventType.TurnStarted, payload={}))
        assert store.get_max_seq() == 1

        store.append(Event(type=EventType.TurnStarted, payload={}))
        store.append(Event(type=EventType.TurnStarted, payload={}))
        assert store.get_max_seq() == 3

    def test_wal_mode_enabled(self, temp_db):
        store = EventStore(temp_db)
        conn = store._get_conn()
        cursor = conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        assert mode.lower() == "wal"
        store.close()
