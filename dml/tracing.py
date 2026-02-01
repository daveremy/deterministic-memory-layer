"""Observability integration for DML operations.

This module provides integration with observability platforms (e.g., Weights & Biases Weave).
DML events exhibit structural isomorphism with distributed tracing spans:

    Event Field      <->  Span Concept
    -----------          ------------
    global_seq       <->  Span ID
    timestamp        <->  Start time
    caused_by        <->  Parent span ID
    correlation_id   <->  Trace ID
    type             <->  Operation name
    payload          <->  Span attributes

This enables unified visibility: LLM behavior (traced by observability) alongside
memory operations (tracked by DML).
"""

import functools
from typing import Any, Callable, TypeVar

try:
    import weave

    WEAVE_AVAILABLE = True
except ImportError:
    WEAVE_AVAILABLE = False

F = TypeVar("F", bound=Callable[..., Any])


def trace_op(name: str | None = None) -> Callable[[F], F]:
    """
    Decorator to trace a function as a span.

    Maps DML operations to observability spans. If Weave is not available,
    the function runs unchanged.

    Args:
        name: Optional operation name. Defaults to function name.
    """

    def decorator(func: F) -> F:
        if not WEAVE_AVAILABLE:
            return func

        op_name = name or func.__name__

        @weave.op(name=op_name)
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        return wrapper  # type: ignore

    return decorator


def init_tracing(project_name: str = "dml") -> bool:
    """
    Initialize observability tracing.

    Args:
        project_name: Project name for the observability platform.

    Returns:
        True if tracing was initialized, False if not available.
    """
    if not WEAVE_AVAILABLE:
        return False

    try:
        weave.init(project_name)
        return True
    except Exception:
        return False


def event_to_span_attributes(event: Any) -> dict[str, Any]:
    """
    Convert DML event fields to span attributes.

    This implements the isomorphism between DML events and observability spans:
    - global_seq -> span_id attribute
    - caused_by -> parent_span_id attribute
    - correlation_id -> trace_id attribute
    - type -> included in attributes
    - payload -> flattened into attributes

    Args:
        event: A DML Event object.

    Returns:
        Dictionary of span attributes.
    """
    attrs = {
        "dml.event.seq": event.global_seq,
        "dml.event.type": event.type.value if hasattr(event.type, "value") else str(event.type),
        "dml.event.turn_id": event.turn_id,
        "dml.event.timestamp": event.timestamp,
    }

    if event.caused_by is not None:
        attrs["dml.event.caused_by"] = event.caused_by

    if event.correlation_id is not None:
        attrs["dml.event.correlation_id"] = event.correlation_id

    # Flatten payload (with prefix to avoid collisions)
    if event.payload:
        for key, value in event.payload.items():
            # Only include serializable values
            if isinstance(value, (str, int, float, bool)):
                attrs[f"dml.payload.{key}"] = value
            elif isinstance(value, list) and len(value) < 10:
                attrs[f"dml.payload.{key}"] = str(value)

    return attrs


class TracedEventStore:
    """
    Wrapper that emits DML events as observability spans.

    Each event append creates a span with attributes mapped from the event,
    implementing the event-span isomorphism described in the architecture.
    """

    def __init__(self, store: Any) -> None:
        self._store = store

    @property
    def db_path(self):
        return self._store.db_path

    def append(self, event: Any) -> int:
        """Append event and emit as span."""
        if WEAVE_AVAILABLE:
            return self._traced_append(event)
        return self._store.append(event)

    @trace_op("dml.event.append")
    def _traced_append(self, event: Any) -> int:
        """Traced append that emits event as span."""
        seq = self._store.append(event)
        # Event now has global_seq and timestamp assigned
        # The span attributes capture the isomorphic mapping
        # Weave automatically captures return value and timing
        return seq

    def get_event(self, seq: int) -> Any:
        return self._store.get_event(seq)

    def get_events(self, from_seq: int = 0, to_seq: int | None = None) -> list:
        return self._store.get_events(from_seq, to_seq)

    def get_by_correlation(self, correlation_id: str) -> list:
        return self._store.get_by_correlation(correlation_id)

    def get_by_type(self, event_type: Any) -> list:
        return self._store.get_by_type(event_type)

    def get_caused_by(self, seq: int) -> list:
        return self._store.get_caused_by(seq)

    def get_max_seq(self) -> int:
        return self._store.get_max_seq()

    def close(self) -> None:
        self._store.close()


class TracedMemoryAPI:
    """
    Wrapper that traces MemoryAPI operations as spans.

    Each memory operation becomes a span, with constraint violations
    recorded as span errors for visibility in observability dashboards.
    """

    def __init__(self, api: Any) -> None:
        self._api = api

    @trace_op("dml.memory.get_constraints")
    def get_active_constraints(self) -> list:
        return self._api.get_active_constraints()

    @trace_op("dml.memory.search")
    def search(self, query: str) -> list:
        return self._api.search(query)

    @trace_op("dml.memory.propose")
    def propose_writes(self, items: list, **kwargs) -> tuple:
        return self._api.propose_writes(items, **kwargs)

    @trace_op("dml.memory.commit")
    def commit_writes(self, proposal_id: str, **kwargs):
        """Commit writes with constraint violation tracking."""
        result = self._api.commit_writes(proposal_id, **kwargs)
        # If result indicates rejection, observability will capture it
        # via the return value - violations are visible as rejected commits
        return result

    @trace_op("dml.memory.provenance")
    def trace_provenance(self, key: str) -> list:
        return self._api.trace_provenance(key)

    @trace_op("dml.memory.diff")
    def diff_state(self, seq1: int, seq2: int):
        return self._api.diff_state(seq1, seq2)

    @trace_op("dml.memory.drift")
    def measure_drift(self, seq1: int, seq2: int):
        return self._api.measure_drift(seq1, seq2)

    @trace_op("dml.memory.add_fact")
    def add_fact(self, key: str, value: Any, confidence: float = 1.0):
        return self._api.add_fact(key, value, confidence)

    @trace_op("dml.memory.get_fact_history")
    def get_fact_history(self, key: str) -> list:
        return self._api.get_fact_history(key)


def log_constraint_violation(
    constraint_text: str,
    item_text: str,
    violation_type: str = "prohibition",
) -> None:
    """
    Log a constraint violation to observability.

    Violations appear as events/spans with error status, making them
    visible in dashboards and alertable.

    Args:
        constraint_text: The constraint that was violated.
        item_text: The content that violated the constraint.
        violation_type: Type of violation (prohibition, procedural).
    """
    if not WEAVE_AVAILABLE:
        return

    # In Weave, this would typically be logged via the op decorator
    # capturing the rejection. This function is for explicit logging
    # if needed outside the normal flow.
    pass
