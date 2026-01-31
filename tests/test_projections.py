"""Tests for projections and ProjectionEngine."""

import pytest

from dml.events import Event, EventType
from dml.projections import (
    ConstraintProjection,
    DecisionProjection,
    FactProjection,
    ProjectionEngine,
    ProjectionState,
)


class TestProjections:
    def test_fact_projection(self):
        fact = FactProjection(
            key="test_key",
            value="test_value",
            confidence=0.9,
            source_event_id=1,
        )
        assert fact.key == "test_key"
        assert fact.value == "test_value"
        assert fact.confidence == 0.9

        d = fact.to_dict()
        assert d["key"] == "test_key"
        assert d["confidence"] == 0.9

    def test_constraint_projection(self):
        constraint = ConstraintProjection(
            text="Never use eval()",
            source_event_id=2,
            active=True,
        )
        assert constraint.text == "Never use eval()"
        assert constraint.active is True

    def test_decision_projection(self):
        decision = DecisionProjection(
            text="Use json.loads instead",
            source_event_id=3,
            references=[1, 2],
        )
        assert decision.text == "Use json.loads instead"
        assert decision.references == [1, 2]


class TestProjectionEngine:
    def test_empty_state(self):
        engine = ProjectionEngine()
        state = engine.state
        assert len(state.facts) == 0
        assert len(state.constraints) == 0
        assert len(state.decisions) == 0

    def test_apply_fact_added(self):
        engine = ProjectionEngine()
        event = Event(
            type=EventType.FactAdded,
            payload={"key": "user_name", "value": "Alice", "confidence": 0.95},
            global_seq=1,
            timestamp=1,
        )
        engine.apply_event(event)

        assert "user_name" in engine.state.facts
        fact = engine.state.facts["user_name"]
        assert fact.value == "Alice"
        assert fact.confidence == 0.95
        assert fact.source_event_id == 1

    def test_apply_constraint_added(self):
        engine = ProjectionEngine()
        event = Event(
            type=EventType.ConstraintAdded,
            payload={"text": "Never use eval()"},
            global_seq=2,
            timestamp=2,
        )
        engine.apply_event(event)

        assert "Never use eval()" in engine.state.constraints
        constraint = engine.state.constraints["Never use eval()"]
        assert constraint.active is True
        assert constraint.source_event_id == 2

    def test_apply_constraint_deactivated(self):
        engine = ProjectionEngine()

        # Add constraint
        engine.apply_event(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "Never use eval()"},
            global_seq=1,
            timestamp=1,
        ))

        # Deactivate it
        engine.apply_event(Event(
            type=EventType.ConstraintDeactivated,
            payload={"text": "Never use eval()"},
            global_seq=2,
            timestamp=2,
        ))

        constraint = engine.state.constraints["Never use eval()"]
        assert constraint.active is False

    def test_apply_decision_made(self):
        engine = ProjectionEngine()
        event = Event(
            type=EventType.DecisionMade,
            payload={"text": "Use json.loads", "references": [1, 2]},
            global_seq=3,
            timestamp=3,
        )
        engine.apply_event(event)

        assert len(engine.state.decisions) == 1
        decision = engine.state.decisions[0]
        assert decision.text == "Use json.loads"
        assert decision.references == [1, 2]

    def test_apply_memory_write_committed_with_facts(self):
        engine = ProjectionEngine()
        event = Event(
            type=EventType.MemoryWriteCommitted,
            payload={
                "proposal_id": "test-123",
                "items": [
                    {"type": "fact", "key": "language", "value": "Python"},
                    {"type": "fact", "key": "version", "value": "3.11", "confidence": 0.8},
                ],
            },
            global_seq=4,
            timestamp=4,
        )
        engine.apply_event(event)

        assert "language" in engine.state.facts
        assert engine.state.facts["language"].value == "Python"
        assert "version" in engine.state.facts
        assert engine.state.facts["version"].confidence == 0.8

    def test_apply_memory_write_committed_with_constraint(self):
        engine = ProjectionEngine()
        event = Event(
            type=EventType.MemoryWriteCommitted,
            payload={
                "proposal_id": "test-456",
                "items": [
                    {"type": "constraint", "text": "Always validate input"},
                ],
            },
            global_seq=5,
            timestamp=5,
        )
        engine.apply_event(event)

        assert "Always validate input" in engine.state.constraints

    def test_rebuild_from_events(self):
        events = [
            Event(type=EventType.FactAdded, payload={"key": "a", "value": 1}, global_seq=1, timestamp=1),
            Event(type=EventType.FactAdded, payload={"key": "b", "value": 2}, global_seq=2, timestamp=2),
            Event(type=EventType.ConstraintAdded, payload={"text": "Rule 1"}, global_seq=3, timestamp=3),
            Event(type=EventType.DecisionMade, payload={"text": "Decision 1"}, global_seq=4, timestamp=4),
        ]

        engine = ProjectionEngine()
        state = engine.rebuild(events)

        assert len(state.facts) == 2
        assert len(state.constraints) == 1
        assert len(state.decisions) == 1
        assert state.last_seq == 4

    def test_rebuild_is_deterministic(self):
        events = [
            Event(type=EventType.FactAdded, payload={"key": "x", "value": 10}, global_seq=1, timestamp=1),
            Event(type=EventType.ConstraintAdded, payload={"text": "Constraint A"}, global_seq=2, timestamp=2),
            Event(type=EventType.DecisionMade, payload={"text": "Decision X"}, global_seq=3, timestamp=3),
        ]

        engine1 = ProjectionEngine()
        state1 = engine1.rebuild(events)

        engine2 = ProjectionEngine()
        state2 = engine2.rebuild(events)

        # Same events should produce identical states
        assert state1.to_dict() == state2.to_dict()

    def test_fact_overwrite(self):
        engine = ProjectionEngine()

        # Add fact
        engine.apply_event(Event(
            type=EventType.FactAdded,
            payload={"key": "counter", "value": 1},
            global_seq=1,
            timestamp=1,
        ))

        # Overwrite with new value
        engine.apply_event(Event(
            type=EventType.FactAdded,
            payload={"key": "counter", "value": 2},
            global_seq=2,
            timestamp=2,
        ))

        assert engine.state.facts["counter"].value == 2
        assert engine.state.facts["counter"].source_event_id == 2

    def test_get_active_constraints(self):
        engine = ProjectionEngine()

        engine.apply_event(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "Active constraint"},
            global_seq=1,
            timestamp=1,
        ))
        engine.apply_event(Event(
            type=EventType.ConstraintAdded,
            payload={"text": "Inactive constraint"},
            global_seq=2,
            timestamp=2,
        ))
        engine.apply_event(Event(
            type=EventType.ConstraintDeactivated,
            payload={"text": "Inactive constraint"},
            global_seq=3,
            timestamp=3,
        ))

        active = engine.get_active_constraints()
        assert len(active) == 1
        assert active[0].text == "Active constraint"
