"""Agent-facing Memory API with provenance, diff, and drift tracking."""

import uuid
from dataclasses import dataclass, field
from typing import Any

from dml.events import Event, EventStore, EventType
from dml.policy import PolicyEngine, PolicyResult, PolicyStatus, WriteProposal
from dml.projections import ConstraintProjection, FactProjection, ProjectionEngine
from dml.replay import ReplayEngine


@dataclass
class StateDiff:
    """Difference between two projection states."""

    added_facts: dict[str, FactProjection] = field(default_factory=dict)
    removed_facts: dict[str, FactProjection] = field(default_factory=dict)
    changed_facts: dict[str, tuple[FactProjection, FactProjection]] = field(
        default_factory=dict
    )
    added_constraints: dict[str, ConstraintProjection] = field(default_factory=dict)
    removed_constraints: dict[str, ConstraintProjection] = field(default_factory=dict)
    changed_constraints: dict[str, tuple[ConstraintProjection, ConstraintProjection]] = field(
        default_factory=dict
    )
    decision_count_diff: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "added_facts": {k: v.to_dict() for k, v in self.added_facts.items()},
            "removed_facts": {k: v.to_dict() for k, v in self.removed_facts.items()},
            "changed_facts": {
                k: (v[0].to_dict(), v[1].to_dict())
                for k, v in self.changed_facts.items()
            },
            "added_constraints": {
                k: v.to_dict() for k, v in self.added_constraints.items()
            },
            "removed_constraints": {
                k: v.to_dict() for k, v in self.removed_constraints.items()
            },
            "changed_constraints": {
                k: (v[0].to_dict(), v[1].to_dict())
                for k, v in self.changed_constraints.items()
            },
            "decision_count_diff": self.decision_count_diff,
        }


@dataclass
class DriftMetrics:
    """Metrics measuring drift between two states."""

    fact_changes: int = 0
    constraint_changes: int = 0
    decision_changes: int = 0
    total_drift_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_changes": self.fact_changes,
            "constraint_changes": self.constraint_changes,
            "decision_changes": self.decision_changes,
            "total_drift_score": self.total_drift_score,
        }


class MemoryAPI:
    """Agent-facing API for memory operations."""

    def __init__(self, store: EventStore) -> None:
        self.store = store
        self.replay_engine = ReplayEngine(store)
        self.policy_engine = PolicyEngine()
        self._projection_engine = ProjectionEngine()
        self._pending_proposals: dict[str, WriteProposal] = {}

    def _get_current_state(self):
        """Get current projection state."""
        return self.replay_engine.replay_to()

    def get_active_constraints(self) -> list[ConstraintProjection]:
        """Get all active constraints."""
        state = self._get_current_state()
        return [c for c in state.constraints.values() if c.active]

    def search(self, query: str) -> list[FactProjection]:
        """
        Search facts by simple SQL LIKE match.

        No vectors/embeddings per PRD minimal deps requirement.
        """
        state = self._get_current_state()
        results = []
        query_lower = query.lower()

        for key, fact in state.facts.items():
            # Match on key or value
            if query_lower in key.lower():
                results.append(fact)
            elif query_lower in str(fact.value).lower():
                results.append(fact)

        return results

    def propose_writes(
        self,
        items: list[dict[str, Any]],
        turn_id: int | None = None,
        correlation_id: str | None = None,
    ) -> tuple[str, int]:
        """
        Propose writes to memory.

        Emits MemoryWriteProposed event and returns proposal_id.

        Args:
            items: List of items to write (facts or constraints).
            turn_id: Current turn ID.
            correlation_id: Correlation ID for provenance.

        Returns:
            Tuple of (proposal_id, event_seq).
        """
        proposal_id = str(uuid.uuid4())

        event = Event(
            type=EventType.MemoryWriteProposed,
            payload={
                "proposal_id": proposal_id,
                "items": items,
            },
            turn_id=turn_id,
            correlation_id=correlation_id,
        )
        seq = self.store.append(event)

        # Store proposal for later commit
        proposal = WriteProposal(
            items=items,
            proposal_id=proposal_id,
            source_event_id=seq,
        )
        self._pending_proposals[proposal_id] = proposal

        return proposal_id, seq

    def commit_writes(
        self,
        proposal_id: str,
        turn_id: int | None = None,
        correlation_id: str | None = None,
    ) -> PolicyResult | int:
        """
        Commit a proposed write after policy check.

        Args:
            proposal_id: ID from propose_writes.
            turn_id: Current turn ID.
            correlation_id: Correlation ID for provenance.

        Returns:
            PolicyResult if rejected, or event sequence number if committed.
        """
        proposal = self._pending_proposals.get(proposal_id)
        if proposal is None:
            return PolicyResult(
                status=PolicyStatus.REJECTED,
                reason=f"Unknown proposal_id: {proposal_id}",
            )

        # Check policy
        current_state = self._get_current_state()
        result = self.policy_engine.check_write(proposal, current_state)

        if not result.approved:
            # Clean up rejected proposal to prevent memory leak
            del self._pending_proposals[proposal_id]
            return result

        # Commit the write
        event = Event(
            type=EventType.MemoryWriteCommitted,
            payload={
                "proposal_id": proposal_id,
                "items": proposal.items,
            },
            turn_id=turn_id,
            caused_by=proposal.source_event_id,
            correlation_id=correlation_id,
        )
        seq = self.store.append(event)

        # Clean up pending proposal
        del self._pending_proposals[proposal_id]

        return seq

    def trace_provenance(self, key: str) -> list[Event]:
        """
        Trace provenance chain for a fact key.

        Traverses caused_by and correlation_id chains.
        """
        # Find the fact's source event
        state = self._get_current_state()
        fact = state.facts.get(key)
        if fact is None or fact.source_event_id is None:
            return []

        # Build chain by following caused_by and correlation_id links
        chain = []
        visited = set()
        to_visit = [fact.source_event_id]

        while to_visit:
            seq = to_visit.pop(0)
            if seq in visited:
                continue
            visited.add(seq)

            event = self.store.get_event(seq)
            if event is None:
                continue

            chain.append(event)

            # Follow caused_by link backwards
            if event.caused_by and event.caused_by not in visited:
                to_visit.append(event.caused_by)

            # Also get events that caused this one
            caused = self.store.get_caused_by(seq)
            for e in caused:
                if e.global_seq not in visited:
                    to_visit.append(e.global_seq)

            # Follow correlation_id chain
            if event.correlation_id:
                correlated = self.store.get_by_correlation(event.correlation_id)
                for e in correlated:
                    if e.global_seq not in visited:
                        to_visit.append(e.global_seq)

        # Sort by sequence
        chain.sort(key=lambda e: e.global_seq)
        return chain

    def diff_state(self, seq1: int, seq2: int) -> StateDiff:
        """
        Compute difference between states at two sequence points.

        Args:
            seq1: Earlier sequence number.
            seq2: Later sequence number.

        Returns:
            StateDiff with added/removed/changed facts, constraints, decisions.
        """
        state1 = self.replay_engine.replay_to(seq1)
        state2 = self.replay_engine.replay_to(seq2)

        diff = StateDiff()

        # Compare facts
        keys1 = set(state1.facts.keys())
        keys2 = set(state2.facts.keys())

        for key in keys2 - keys1:
            diff.added_facts[key] = state2.facts[key]

        for key in keys1 - keys2:
            diff.removed_facts[key] = state1.facts[key]

        for key in keys1 & keys2:
            f1 = state1.facts[key]
            f2 = state2.facts[key]
            if f1.value != f2.value or f1.confidence != f2.confidence:
                diff.changed_facts[key] = (f1, f2)

        # Compare constraints
        ckeys1 = set(state1.constraints.keys())
        ckeys2 = set(state2.constraints.keys())

        for key in ckeys2 - ckeys1:
            diff.added_constraints[key] = state2.constraints[key]

        for key in ckeys1 - ckeys2:
            diff.removed_constraints[key] = state1.constraints[key]

        for key in ckeys1 & ckeys2:
            c1 = state1.constraints[key]
            c2 = state2.constraints[key]
            if c1.active != c2.active:
                diff.changed_constraints[key] = (c1, c2)

        # Compare decisions count
        diff.decision_count_diff = len(state2.decisions) - len(state1.decisions)

        return diff

    def measure_drift(self, seq1: int, seq2: int) -> DriftMetrics:
        """
        Measure drift between two states.

        Drift = count of changes between states (PRD principle #6).

        Args:
            seq1: Earlier sequence number.
            seq2: Later sequence number.

        Returns:
            DriftMetrics with change counts and total drift score.
        """
        diff = self.diff_state(seq1, seq2)

        metrics = DriftMetrics()
        metrics.fact_changes = (
            len(diff.added_facts)
            + len(diff.removed_facts)
            + len(diff.changed_facts)
        )
        metrics.constraint_changes = (
            len(diff.added_constraints)
            + len(diff.removed_constraints)
            + len(diff.changed_constraints)
        )
        metrics.decision_changes = abs(diff.decision_count_diff)

        # Simple weighted drift score
        metrics.total_drift_score = (
            metrics.fact_changes * 1.0
            + metrics.constraint_changes * 2.0  # constraints weighted more
            + metrics.decision_changes * 0.5
        )

        return metrics
