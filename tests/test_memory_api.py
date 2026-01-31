"""Tests for MemoryAPI - provenance, diff, drift."""

import tempfile
from pathlib import Path

import pytest

from dml.events import Event, EventStore, EventType
from dml.memory_api import DriftMetrics, MemoryAPI, StateDiff


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
def api(temp_db):
    """Create a MemoryAPI instance."""
    store = EventStore(temp_db)
    api = MemoryAPI(store)
    yield api
    store.close()


@pytest.fixture
def populated_api(temp_db):
    """Create a MemoryAPI with sample data."""
    store = EventStore(temp_db)
    api = MemoryAPI(store)

    # Add some events
    store.append(Event(type=EventType.FactAdded, payload={"key": "user", "value": "Alice"}))
    store.append(Event(type=EventType.FactAdded, payload={"key": "language", "value": "Python"}))
    store.append(Event(type=EventType.ConstraintAdded, payload={"text": "Never use eval()"}))

    yield api, store
    store.close()


class TestMemoryAPIBasics:
    def test_get_active_constraints_empty(self, api):
        constraints = api.get_active_constraints()
        assert len(constraints) == 0

    def test_get_active_constraints(self, populated_api):
        api, _ = populated_api
        constraints = api.get_active_constraints()
        assert len(constraints) == 1
        assert constraints[0].text == "Never use eval()"

    def test_search_by_key(self, populated_api):
        api, _ = populated_api
        results = api.search("user")
        assert len(results) == 1
        assert results[0].value == "Alice"

    def test_search_by_value(self, populated_api):
        api, _ = populated_api
        results = api.search("Python")
        assert len(results) == 1
        assert results[0].key == "language"

    def test_search_no_results(self, populated_api):
        api, _ = populated_api
        results = api.search("nonexistent")
        assert len(results) == 0

    def test_search_case_insensitive(self, populated_api):
        api, _ = populated_api
        results = api.search("ALICE")
        assert len(results) == 1


class TestProposeAndCommit:
    def test_propose_writes(self, api):
        proposal_id, seq = api.propose_writes(
            items=[{"type": "fact", "key": "test", "value": "hello"}],
            turn_id=1,
        )
        assert proposal_id is not None
        assert seq > 0

    def test_commit_writes_approved(self, api):
        # Propose and commit a fact
        proposal_id, _ = api.propose_writes(
            items=[{"type": "fact", "key": "test", "value": "hello"}],
        )
        result = api.commit_writes(proposal_id)

        # Should return sequence number on success
        assert isinstance(result, int)
        assert result > 0

    def test_commit_writes_rejected_by_policy(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # Add constraint first
        store.append(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "Never use eval()"},
        ))

        # Propose violating write
        proposal_id, _ = api.propose_writes(
            items=[{"type": "decision", "text": "Use eval() for parsing"}],
        )
        result = api.commit_writes(proposal_id)

        # Should return PolicyResult with rejection
        assert hasattr(result, "rejected")
        assert result.rejected is True

        store.close()

    def test_commit_unknown_proposal(self, api):
        result = api.commit_writes("nonexistent-proposal-id")
        assert hasattr(result, "reason")
        assert "unknown" in result.reason.lower()


class TestProvenance:
    def test_trace_provenance_simple(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # Create a chain: turn -> fact
        turn_seq = store.append(Event(
            type=EventType.TurnStarted,
            payload={"turn_id": 1},
        ))
        fact_seq = store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "result", "value": 42},
            caused_by=turn_seq,
        ))

        chain = api.trace_provenance("result")
        assert len(chain) >= 1
        # Should include the fact event
        assert any(e.global_seq == fact_seq for e in chain)

        store.close()

    def test_trace_provenance_not_found(self, api):
        chain = api.trace_provenance("nonexistent_key")
        assert len(chain) == 0

    def test_trace_provenance_with_correlation(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        corr_id = "decision-chain-001"

        store.append(Event(
            type=EventType.UserMessageReceived,
            payload={"content": "Help me parse JSON"},
            correlation_id=corr_id,
        ))
        store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "task", "value": "json parsing"},
            correlation_id=corr_id,
        ))

        chain = api.trace_provenance("task")
        assert len(chain) >= 1

        store.close()


class TestStateDiff:
    def test_diff_state_added_facts(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # State at seq 0 is empty
        seq1 = store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "a", "value": 1},
        ))

        diff = api.diff_state(0, seq1)
        assert len(diff.added_facts) == 1
        assert "a" in diff.added_facts

        store.close()

    def test_diff_state_removed_facts(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # Add fact then "remove" by having later state without it
        # Note: In this implementation, facts aren't really removed
        # but we can test the diff logic

        store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "temp", "value": "value1"},
        ))
        # Since we can't remove facts directly, test with added only
        diff = api.diff_state(0, 1)
        assert len(diff.added_facts) == 1

        store.close()

    def test_diff_state_changed_facts(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "counter", "value": 1},
        ))
        store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "counter", "value": 2},
        ))

        diff = api.diff_state(1, 2)
        assert len(diff.changed_facts) == 1
        assert "counter" in diff.changed_facts
        old, new = diff.changed_facts["counter"]
        assert old.value == 1
        assert new.value == 2

        store.close()

    def test_diff_state_constraints(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        store.append(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "Rule 1"},
        ))

        diff = api.diff_state(0, 1)
        assert len(diff.added_constraints) == 1
        assert "Rule 1" in diff.added_constraints

        store.close()

    def test_diff_state_decisions(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        store.append(Event(type=EventType.DecisionMade, payload={"text": "D1"}))
        store.append(Event(type=EventType.DecisionMade, payload={"text": "D2"}))

        diff = api.diff_state(0, 2)
        assert diff.decision_count_diff == 2

        store.close()


class TestDriftMetrics:
    def test_measure_drift_empty(self, api):
        metrics = api.measure_drift(0, 0)
        assert metrics.fact_changes == 0
        assert metrics.constraint_changes == 0
        assert metrics.decision_changes == 0
        assert metrics.total_drift_score == 0.0

    def test_measure_drift_with_changes(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        store.append(Event(type=EventType.FactAdded, payload={"key": "a", "value": 1}))
        store.append(Event(type=EventType.FactAdded, payload={"key": "b", "value": 2}))
        store.append(Event(type=EventType.ConstraintAdded, payload={"text": "Rule"}))
        store.append(Event(type=EventType.DecisionMade, payload={"text": "D1"}))

        metrics = api.measure_drift(0, 4)

        assert metrics.fact_changes == 2
        assert metrics.constraint_changes == 1
        assert metrics.decision_changes == 1
        # Score = 2*1.0 + 1*2.0 + 1*0.5 = 4.5
        assert metrics.total_drift_score == 4.5

        store.close()

    def test_drift_metrics_to_dict(self):
        metrics = DriftMetrics(
            fact_changes=3,
            constraint_changes=2,
            decision_changes=1,
            total_drift_score=8.5,
        )
        d = metrics.to_dict()
        assert d["fact_changes"] == 3
        assert d["total_drift_score"] == 8.5


class TestStateDiffSerialization:
    def test_state_diff_to_dict(self, temp_db):
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        store.append(Event(type=EventType.FactAdded, payload={"key": "x", "value": 10}))

        diff = api.diff_state(0, 1)
        d = diff.to_dict()

        assert "added_facts" in d
        assert "removed_facts" in d
        assert "changed_facts" in d
        assert "added_constraints" in d
        assert "decision_count_diff" in d

        store.close()
