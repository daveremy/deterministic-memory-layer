"""Deterministic Memory Layer - Event-sourced memory for AI agents."""

from dml.events import Event, EventStore, EventType
from dml.projections import (
    ConstraintProjection,
    DecisionProjection,
    FactProjection,
    ProjectionEngine,
)
from dml.replay import ReplayEngine
from dml.policy import PolicyEngine, PolicyResult
from dml.memory_api import MemoryAPI, StateDiff, DriftMetrics
from dml.stores import EventStoreBackend, RedisEventStore
from dml.tracing import (
    TracedEventStore,
    TracedMemoryAPI,
    init_tracing,
    event_to_span_attributes,
)

__all__ = [
    # Core
    "Event",
    "EventStore",
    "EventType",
    # Projections
    "FactProjection",
    "ConstraintProjection",
    "DecisionProjection",
    "ProjectionEngine",
    # Replay
    "ReplayEngine",
    # Policy
    "PolicyEngine",
    "PolicyResult",
    # Memory API
    "MemoryAPI",
    "StateDiff",
    "DriftMetrics",
    # Store backends
    "EventStoreBackend",
    "RedisEventStore",
    # Observability
    "TracedEventStore",
    "TracedMemoryAPI",
    "init_tracing",
    "event_to_span_attributes",
]
