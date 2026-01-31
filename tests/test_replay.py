"""Tests for ReplayEngine - determinism and counterfactual analysis."""

import json
import tempfile
from pathlib import Path

import pytest

from dml.events import Event, EventStore, EventType
from dml.replay import ReplayEngine


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield db_path
    Path(db_path).unlink(missing_ok=True)
    Path(db_path + "-wal").unlink(missing_ok=True)
    Path(db_path + "-shm").unlink(missing_ok=True)


@pytest.fixture
def populated_store(temp_db):
    """Create a store with sample events."""
    store = EventStore(temp_db)

    # Add sequence of events
    store.append(Event(type=EventType.TurnStarted, payload={"turn_id": 1}))
    store.append(Event(type=EventType.FactAdded, payload={"key": "user", "value": "Alice"}))
    store.append(Event(type=EventType.ConstraintAdded, payload={"text": "Never use eval()"}))
    store.append(Event(type=EventType.DecisionMade, payload={"text": "Use safe parsing"}))
    store.append(Event(type=EventType.FactAdded, payload={"key": "method", "value": "json.loads"}))

    yield store
    store.close()


class TestReplayEngine:
    def test_replay_to_all(self, populated_store):
        engine = ReplayEngine(populated_store)
        state = engine.replay_to()

        assert len(state.facts) == 2
        assert len(state.constraints) == 1
        assert len(state.decisions) == 1

    def test_replay_to_specific_seq(self, populated_store):
        engine = ReplayEngine(populated_store)

        # Replay to seq 2 (should only have user fact)
        state = engine.replay_to(2)
        assert len(state.facts) == 1
        assert "user" in state.facts
        assert len(state.constraints) == 0

        # Replay to seq 3 (should have fact and constraint)
        state = engine.replay_to(3)
        assert len(state.facts) == 1
        assert len(state.constraints) == 1

    def test_replay_excluding_single_event(self, populated_store):
        engine = ReplayEngine(populated_store)

        # Exclude the constraint event (seq 3)
        state = engine.replay_excluding([3])

        assert len(state.facts) == 2
        assert len(state.constraints) == 0  # Constraint excluded
        assert len(state.decisions) == 1

    def test_replay_excluding_multiple_events(self, populated_store):
        engine = ReplayEngine(populated_store)

        # Exclude fact events
        state = engine.replay_excluding([2, 5])

        assert len(state.facts) == 0  # Both facts excluded
        assert len(state.constraints) == 1
        assert len(state.decisions) == 1

    def test_deterministic_replay(self, populated_store):
        """Same events should always produce identical state."""
        engine = ReplayEngine(populated_store)

        state1 = engine.replay_to()
        state2 = engine.replay_to()

        # Serialize and compare
        s1 = json.dumps(state1.to_dict(), sort_keys=True)
        s2 = json.dumps(state2.to_dict(), sort_keys=True)

        assert s1 == s2

    def test_deterministic_replay_multiple_times(self, populated_store):
        """Replaying many times should always give same result."""
        engine = ReplayEngine(populated_store)

        states = [engine.replay_to() for _ in range(10)]
        serialized = [json.dumps(s.to_dict(), sort_keys=True) for s in states]

        # All should be identical
        assert len(set(serialized)) == 1

    def test_replay_range(self, populated_store):
        engine = ReplayEngine(populated_store)

        # Only events 2-4
        state = engine.replay_range(2, 4)

        assert len(state.facts) == 1  # Only user fact
        assert len(state.constraints) == 1
        assert len(state.decisions) == 1

    def test_compare_states(self, populated_store):
        engine = ReplayEngine(populated_store)

        state1, state2 = engine.compare_states(2, 5)

        assert len(state1.facts) == 1
        assert len(state2.facts) == 2

    def test_counterfactual_analysis(self, temp_db):
        """Test what-if scenario: what if a constraint was never added?"""
        store = EventStore(temp_db)

        # Add events including a constraint
        store.append(Event(type=EventType.TurnStarted, payload={"turn_id": 1}))
        constraint_seq = store.append(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "No external APIs"},
        ))
        store.append(Event(
            type=EventType.DecisionMade,
            payload={"text": "Use internal service"},
        ))

        engine = ReplayEngine(store)

        # Normal state - constraint exists
        normal_state = engine.replay_to()
        assert len(normal_state.constraints) == 1

        # Counterfactual - what if constraint never existed?
        counterfactual_state = engine.replay_excluding([constraint_seq])
        assert len(counterfactual_state.constraints) == 0

        store.close()

    def test_empty_store_replay(self, temp_db):
        store = EventStore(temp_db)
        engine = ReplayEngine(store)

        state = engine.replay_to()
        assert len(state.facts) == 0
        assert len(state.constraints) == 0
        assert len(state.decisions) == 0
        assert state.last_seq == 0

        store.close()

    def test_replay_with_fact_overwrites(self, temp_db):
        """Test that later events properly overwrite earlier ones."""
        store = EventStore(temp_db)

        store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "counter", "value": 1},
        ))
        store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "counter", "value": 2},
        ))
        store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "counter", "value": 3},
        ))

        engine = ReplayEngine(store)
        state = engine.replay_to()

        # Should have latest value
        assert state.facts["counter"].value == 3

        # Replay to seq 2 should have value 2
        state_at_2 = engine.replay_to(2)
        assert state_at_2.facts["counter"].value == 2

        store.close()
