"""Event types, Event dataclass, and SQLite-backed EventStore."""

import json
import sqlite3
import threading
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class EventType(str, Enum):
    """Event types from PRD 5.1."""

    TurnStarted = "TurnStarted"
    UserMessageReceived = "UserMessageReceived"
    MemoryQueryIssued = "MemoryQueryIssued"
    MemoryQueryResult = "MemoryQueryResult"
    DecisionMade = "DecisionMade"
    MemoryWriteProposed = "MemoryWriteProposed"
    MemoryWriteCommitted = "MemoryWriteCommitted"
    OutputEmitted = "OutputEmitted"
    TurnCompleted = "TurnCompleted"
    # Additional types for memory operations
    FactAdded = "FactAdded"
    ConstraintAdded = "ConstraintAdded"
    ConstraintDeactivated = "ConstraintDeactivated"


@dataclass
class Event:
    """Immutable event record."""

    type: EventType
    payload: dict[str, Any]
    turn_id: int | None = None
    caused_by: int | None = None  # global_seq of causing event
    correlation_id: str | None = None
    global_seq: int | None = None  # assigned by EventStore
    timestamp: int | None = None  # monotonic counter, not wall-clock

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "global_seq": self.global_seq,
            "turn_id": self.turn_id,
            "timestamp": self.timestamp,
            "type": self.type.value,
            "payload": self.payload,
            "caused_by": self.caused_by,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Event":
        """Deserialize from dictionary."""
        return cls(
            global_seq=data.get("global_seq"),
            turn_id=data.get("turn_id"),
            timestamp=data.get("timestamp"),
            type=EventType(data["type"]),
            payload=data["payload"],
            caused_by=data.get("caused_by"),
            correlation_id=data.get("correlation_id"),
        )


class EventStore:
    """SQLite-backed append-only event storage with WAL mode."""

    def __init__(self, db_path: str | Path = "memory.db"):
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._monotonic_counter = 0
        self._counter_lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get thread-local connection."""
        if not hasattr(self._local, "conn"):
            self._local.conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for concurrency
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize database schema."""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS events (
                global_seq INTEGER PRIMARY KEY AUTOINCREMENT,
                turn_id INTEGER,
                timestamp INTEGER NOT NULL,
                type TEXT NOT NULL,
                payload TEXT NOT NULL,
                caused_by INTEGER,
                correlation_id TEXT,
                FOREIGN KEY (caused_by) REFERENCES events(global_seq)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_correlation
            ON events(correlation_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_turn
            ON events(turn_id)
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type
            ON events(type)
        """)
        conn.commit()

        # Initialize monotonic counter from existing events
        cursor = conn.execute("SELECT MAX(timestamp) FROM events")
        row = cursor.fetchone()
        if row[0] is not None:
            self._monotonic_counter = row[0]

    def append(self, event: Event) -> int:
        """Append event to store, return assigned global_seq."""
        conn = self._get_conn()

        # Assign monotonic timestamp
        with self._counter_lock:
            self._monotonic_counter += 1
            timestamp = self._monotonic_counter

        cursor = conn.execute(
            """
            INSERT INTO events (turn_id, timestamp, type, payload, caused_by, correlation_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                event.turn_id,
                timestamp,
                event.type.value,
                json.dumps(event.payload),
                event.caused_by,
                event.correlation_id,
            ),
        )
        conn.commit()

        global_seq = cursor.lastrowid
        event.global_seq = global_seq
        event.timestamp = timestamp
        return global_seq

    def get_event(self, seq: int) -> Event | None:
        """Get single event by global_seq."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM events WHERE global_seq = ?", (seq,)
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_event(row)

    def get_events(
        self, from_seq: int = 0, to_seq: int | None = None
    ) -> list[Event]:
        """Get events in sequence range (inclusive)."""
        conn = self._get_conn()
        if to_seq is None:
            cursor = conn.execute(
                "SELECT * FROM events WHERE global_seq >= ? ORDER BY global_seq",
                (from_seq,),
            )
        else:
            cursor = conn.execute(
                "SELECT * FROM events WHERE global_seq >= ? AND global_seq <= ? ORDER BY global_seq",
                (from_seq, to_seq),
            )
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def get_by_correlation(self, correlation_id: str) -> list[Event]:
        """Get all events with given correlation_id for provenance chain."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM events WHERE correlation_id = ? ORDER BY global_seq",
            (correlation_id,),
        )
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def get_by_type(self, event_type: EventType) -> list[Event]:
        """Get all events of a specific type."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM events WHERE type = ? ORDER BY global_seq",
            (event_type.value,),
        )
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def get_caused_by(self, seq: int) -> list[Event]:
        """Get all events caused by a specific event."""
        conn = self._get_conn()
        cursor = conn.execute(
            "SELECT * FROM events WHERE caused_by = ? ORDER BY global_seq",
            (seq,),
        )
        return [self._row_to_event(row) for row in cursor.fetchall()]

    def get_max_seq(self) -> int:
        """Get the maximum global_seq in the store."""
        conn = self._get_conn()
        cursor = conn.execute("SELECT MAX(global_seq) FROM events")
        row = cursor.fetchone()
        return row[0] if row[0] is not None else 0

    def _row_to_event(self, row: sqlite3.Row) -> Event:
        """Convert database row to Event."""
        return Event(
            global_seq=row["global_seq"],
            turn_id=row["turn_id"],
            timestamp=row["timestamp"],
            type=EventType(row["type"]),
            payload=json.loads(row["payload"]),
            caused_by=row["caused_by"],
            correlation_id=row["correlation_id"],
        )

    def close(self) -> None:
        """Close the database connection."""
        if hasattr(self._local, "conn"):
            self._local.conn.close()
            del self._local.conn
