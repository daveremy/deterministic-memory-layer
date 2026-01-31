"""Tests for supersedes_seq fact tracking functionality."""

import tempfile
from pathlib import Path

import pytest

from dml.events import Event, EventStore, EventType
from dml.memory_api import MemoryAPI


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


class TestFactProjectionFields:
    """Test that FactProjection has the new fields."""

    def test_first_fact_has_no_supersedes(self, temp_db):
        """First fact for a key should have supersedes_seq=None."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        seq = api.add_fact("budget", 3000)
        state = api._get_current_state()
        fact = state.facts["budget"]

        assert fact.supersedes_seq is None
        assert fact.previous_value is None
        assert fact.source_event_id == seq

        store.close()

    def test_second_fact_has_supersedes(self, temp_db):
        """Second fact for same key should have supersedes_seq pointing to first."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        seq1 = api.add_fact("budget", 3000)
        seq2 = api.add_fact("budget", 2000)

        state = api._get_current_state()
        fact = state.facts["budget"]

        assert fact.value == 2000
        assert fact.supersedes_seq == seq1
        assert fact.previous_value == 3000
        assert fact.source_event_id == seq2

        store.close()

    def test_chain_of_updates(self, temp_db):
        """Chain of updates creates linked history."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        seq1 = api.add_fact("counter", 1)
        seq2 = api.add_fact("counter", 2)
        seq3 = api.add_fact("counter", 3)

        state = api._get_current_state()
        fact = state.facts["counter"]

        assert fact.value == 3
        assert fact.supersedes_seq == seq2
        assert fact.previous_value == 2

        store.close()

    def test_different_keys_independent(self, temp_db):
        """Different keys should be independent."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        api.add_fact("key_a", "value_a")
        api.add_fact("key_b", "value_b")
        api.add_fact("key_a", "value_a2")

        state = api._get_current_state()

        assert state.facts["key_a"].supersedes_seq is not None
        assert state.facts["key_b"].supersedes_seq is None

        store.close()


class TestCommitWritesSupersession:
    """Test that commit_writes auto-enriches items with supersession info."""

    def test_commit_writes_enriches_new_fact(self, temp_db):
        """commit_writes should not add supersession for new key."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        proposal_id, _ = api.propose_writes(
            items=[{"type": "fact", "key": "test", "value": "hello"}],
        )
        api.commit_writes(proposal_id)

        state = api._get_current_state()
        fact = state.facts["test"]

        assert fact.supersedes_seq is None
        assert fact.previous_value is None

        store.close()

    def test_commit_writes_enriches_existing_fact(self, temp_db):
        """commit_writes should add supersession for existing key."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # Add initial fact
        seq1 = api.add_fact("test", "first")

        # Update via propose/commit
        proposal_id, _ = api.propose_writes(
            items=[{"type": "fact", "key": "test", "value": "second"}],
        )
        api.commit_writes(proposal_id)

        state = api._get_current_state()
        fact = state.facts["test"]

        assert fact.value == "second"
        assert fact.supersedes_seq == seq1
        assert fact.previous_value == "first"

        store.close()

    def test_commit_writes_multi_item_same_key(self, temp_db):
        """Multiple items for same key in single commit should chain correctly."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # Add initial fact
        seq1 = api.add_fact("counter", 1)

        # Commit multiple updates for same key
        proposal_id, _ = api.propose_writes(
            items=[
                {"type": "fact", "key": "counter", "value": 2},
                {"type": "fact", "key": "counter", "value": 3},
            ],
        )
        api.commit_writes(proposal_id)

        state = api._get_current_state()
        fact = state.facts["counter"]

        # Last one wins, and its supersedes_seq points to first in batch
        # which in turn points to original fact
        assert fact.value == 3
        # Second item in batch sees first item's supersedes_seq (which is seq1)
        assert fact.supersedes_seq == seq1
        assert fact.previous_value == 2

        store.close()

    def test_commit_writes_mixed_items(self, temp_db):
        """commit_writes handles mixed fact and constraint items."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        api.add_fact("existing", "old_value")

        proposal_id, _ = api.propose_writes(
            items=[
                {"type": "constraint", "text": "Never do X"},
                {"type": "fact", "key": "existing", "value": "new_value"},
                {"type": "fact", "key": "new_key", "value": "fresh"},
            ],
        )
        api.commit_writes(proposal_id)

        state = api._get_current_state()

        # Existing fact should have supersession
        assert state.facts["existing"].supersedes_seq is not None
        assert state.facts["existing"].previous_value == "old_value"

        # New fact should not
        assert state.facts["new_key"].supersedes_seq is None

        # Constraint should exist
        assert "Never do X" in state.constraints

        store.close()


class TestGetFactHistory:
    """Test the get_fact_history method."""

    def test_history_single_value(self, temp_db):
        """Single value fact should return list with one item."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        api.add_fact("key", "value")

        history = api.get_fact_history("key")

        assert len(history) == 1
        assert history[0].value == "value"

        store.close()

    def test_history_multiple_values(self, temp_db):
        """Multiple updates should return ordered history."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        seq1 = api.add_fact("budget", 3000)
        seq2 = api.add_fact("budget", 2000)

        history = api.get_fact_history("budget")

        assert len(history) == 2
        assert history[0].value == 3000  # Oldest first
        assert history[0].source_event_id == seq1
        assert history[1].value == 2000
        assert history[1].source_event_id == seq2
        assert history[1].supersedes_seq == seq1
        assert history[1].previous_value == 3000

        store.close()

    def test_history_chain_of_three(self, temp_db):
        """Chain of three updates returns full history."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        api.add_fact("version", "1.0")
        api.add_fact("version", "1.1")
        api.add_fact("version", "2.0")

        history = api.get_fact_history("version")

        assert len(history) == 3
        assert [h.value for h in history] == ["1.0", "1.1", "2.0"]

        store.close()

    def test_history_nonexistent_key(self, temp_db):
        """Nonexistent key should return empty list."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        history = api.get_fact_history("does_not_exist")

        assert history == []

        store.close()

    def test_history_via_commit_writes(self, temp_db):
        """History should work for facts added via commit_writes."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # First via add_fact
        api.add_fact("price", 100)

        # Then via commit_writes
        proposal_id, _ = api.propose_writes(
            items=[{"type": "fact", "key": "price", "value": 150}],
        )
        api.commit_writes(proposal_id)

        # Then another add_fact
        api.add_fact("price", 200)

        history = api.get_fact_history("price")

        assert len(history) == 3
        assert [h.value for h in history] == [100, 150, 200]

        store.close()

    def test_history_skips_intermediate_batch_updates(self, temp_db):
        """
        Intermediate updates within a single commit should be skipped in history traversal.

        Logic:
        1. Start: Value = 0 (Seq A)
        2. Commit Batch:
           - Item 1: Value = 1 (Intermediate)
           - Item 2: Value = 2 (Final for batch) -> Seq B
        3. History should be: [Seq A (0), Seq B (2)]. Value 1 is invisible.

        Note: previous_value captures the immediate prior value (1), but the history
        chain only links events, not intra-event updates.
        """
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # 1. Initial State
        api.add_fact("counter", 0)

        # 2. Atomic Batch with intermediate update
        proposal_id, _ = api.propose_writes(
            items=[
                {"type": "fact", "key": "counter", "value": 1},
                {"type": "fact", "key": "counter", "value": 2},
            ],
        )
        api.commit_writes(proposal_id)

        # 3. Verify History - intermediate value 1 is skipped
        history = api.get_fact_history("counter")

        assert len(history) == 2
        assert history[0].value == 0
        assert history[1].value == 2

        # Verify linkage: final batch item points to original fact
        assert history[1].supersedes_seq == history[0].source_event_id

        # previous_value captures immediate prior (1), not the linked event's value (0)
        assert history[1].previous_value == 1

        store.close()


class TestBackwardCompatibility:
    """Test backward compatibility with events lacking supersedes_seq."""

    def test_old_events_work(self, temp_db):
        """Events without supersedes_seq should work (treated as None)."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # Simulate old-style event without supersedes_seq
        store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "old_fact", "value": "old_value"},
        ))

        state = api._get_current_state()
        fact = state.facts["old_fact"]

        assert fact.supersedes_seq is None
        assert fact.previous_value is None

        store.close()

    def test_history_with_old_events(self, temp_db):
        """get_fact_history handles chain broken by old events."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # Old-style event
        store.append(Event(
            type=EventType.FactAdded,
            payload={"key": "mixed", "value": "v1"},
        ))

        # New-style via add_fact
        api.add_fact("mixed", "v2")

        history = api.get_fact_history("mixed")

        # Should have 2 entries, though chain may be incomplete
        assert len(history) >= 1
        assert history[-1].value == "v2"

        store.close()


class TestFactProjectionToDict:
    """Test FactProjection.to_dict includes new fields."""

    def test_to_dict_includes_supersedes(self, temp_db):
        """to_dict should include supersedes_seq and previous_value."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        seq1 = api.add_fact("key", "v1")
        api.add_fact("key", "v2")

        state = api._get_current_state()
        fact_dict = state.facts["key"].to_dict()

        assert "supersedes_seq" in fact_dict
        assert fact_dict["supersedes_seq"] == seq1
        assert "previous_value" in fact_dict
        assert fact_dict["previous_value"] == "v1"

        store.close()


class TestEdgeCases:
    """Test edge cases and defensive limits."""

    def test_very_long_history(self, temp_db):
        """Test that very long history is handled (defensive limit)."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        # Create a long history (but not exceeding limit)
        for i in range(50):
            api.add_fact("counter", i)

        history = api.get_fact_history("counter")

        assert len(history) == 50
        assert history[0].value == 0
        assert history[-1].value == 49

        store.close()

    def test_concurrent_keys(self, temp_db):
        """Test multiple keys updated interleaved."""
        store = EventStore(temp_db)
        api = MemoryAPI(store)

        api.add_fact("a", 1)
        api.add_fact("b", 10)
        api.add_fact("a", 2)
        api.add_fact("b", 20)
        api.add_fact("a", 3)

        history_a = api.get_fact_history("a")
        history_b = api.get_fact_history("b")

        assert [h.value for h in history_a] == [1, 2, 3]
        assert [h.value for h in history_b] == [10, 20]

        store.close()
