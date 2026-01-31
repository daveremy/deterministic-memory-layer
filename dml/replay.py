"""Replay engine for deterministic state reconstruction and counterfactual analysis."""

from dml.events import Event, EventStore
from dml.projections import ProjectionEngine, ProjectionState


class ReplayEngine:
    """Replays events to reconstruct state deterministically."""

    def __init__(self, store: EventStore) -> None:
        self.store = store

    def replay_to(self, seq: int | None = None) -> ProjectionState:
        """
        Rebuild state up to a specific sequence number.

        Args:
            seq: Maximum sequence to replay to (inclusive).
                 If None, replays all events.

        Returns:
            ProjectionState at the specified point in time.
        """
        if seq is None:
            events = self.store.get_events()
        else:
            events = self.store.get_events(from_seq=0, to_seq=seq)

        engine = ProjectionEngine()
        return engine.rebuild(events)

    def replay_excluding(
        self, event_ids: list[int] | set[int]
    ) -> ProjectionState:
        """
        Rebuild state excluding specific events (counterfactual).

        This enables "what-if" analysis by replaying history
        without certain events.

        Args:
            event_ids: Sequence numbers of events to exclude.

        Returns:
            ProjectionState with excluded events removed from history.
        """
        exclude_set = set(event_ids)
        events = self.store.get_events()

        # Filter out excluded events
        filtered_events = [
            e for e in events if e.global_seq not in exclude_set
        ]

        engine = ProjectionEngine()
        return engine.rebuild(filtered_events)

    def replay_range(self, from_seq: int, to_seq: int) -> ProjectionState:
        """
        Rebuild state from a range of events.

        Args:
            from_seq: Starting sequence (inclusive).
            to_seq: Ending sequence (inclusive).

        Returns:
            ProjectionState built from events in range.
        """
        events = self.store.get_events(from_seq=from_seq, to_seq=to_seq)
        engine = ProjectionEngine()
        return engine.rebuild(events)

    def get_state_at(self, seq: int) -> ProjectionState:
        """
        Get projection state at exactly the given sequence.

        Alias for replay_to for clarity.
        """
        return self.replay_to(seq)

    def compare_states(
        self, seq1: int, seq2: int
    ) -> tuple[ProjectionState, ProjectionState]:
        """
        Get states at two different points for comparison.

        Returns:
            Tuple of (state_at_seq1, state_at_seq2).
        """
        state1 = self.replay_to(seq1)
        state2 = self.replay_to(seq2)
        return state1, state2
