"""Projection types and ProjectionEngine for deterministic state reconstruction."""

from dataclasses import dataclass, field
from typing import Any

from dml.events import Event, EventType


@dataclass
class FactProjection:
    """A fact derived from events."""

    key: str
    value: Any
    confidence: float = 1.0
    source_event_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "confidence": self.confidence,
            "source_event_id": self.source_event_id,
        }


@dataclass
class ConstraintProjection:
    """A constraint that governs agent behavior."""

    text: str
    source_event_id: int | None = None
    active: bool = True
    priority: str = "required"  # "required" | "preferred" | "learned"
    triggered_by: int | None = None  # seq that triggered learning (for learned constraints)

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_event_id": self.source_event_id,
            "active": self.active,
            "priority": self.priority,
            "triggered_by": self.triggered_by,
        }


@dataclass
class DecisionProjection:
    """A decision made by the agent."""

    text: str
    source_event_id: int | None = None
    references: list[int] = field(default_factory=list)  # event IDs referenced
    rationale: str | None = None  # why this decision was made
    status: str = "committed"  # "committed" | "blocked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "text": self.text,
            "source_event_id": self.source_event_id,
            "references": self.references,
            "rationale": self.rationale,
            "status": self.status,
        }


@dataclass
class ProjectionState:
    """Complete projection state at a point in time."""

    facts: dict[str, FactProjection] = field(default_factory=dict)
    constraints: dict[str, ConstraintProjection] = field(default_factory=dict)
    decisions: list[DecisionProjection] = field(default_factory=list)
    pending_verifications: set[str] = field(default_factory=set)  # topics verified via query
    last_seq: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "facts": {k: v.to_dict() for k, v in self.facts.items()},
            "constraints": {k: v.to_dict() for k, v in self.constraints.items()},
            "decisions": [d.to_dict() for d in self.decisions],
            "pending_verifications": list(self.pending_verifications),
            "last_seq": self.last_seq,
        }


class ProjectionEngine:
    """Builds projections from events deterministically."""

    def __init__(self) -> None:
        self._state = ProjectionState()

    @property
    def state(self) -> ProjectionState:
        return self._state

    def rebuild(self, events: list[Event]) -> ProjectionState:
        """Rebuild state from events deterministically."""
        self._state = ProjectionState()

        for event in events:
            self._apply_event(event)

        return self._state

    def apply_event(self, event: Event) -> None:
        """Apply a single event to current state."""
        self._apply_event(event)

    def _apply_event(self, event: Event) -> None:
        """Internal event application logic."""
        if event.global_seq is not None:
            self._state.last_seq = max(self._state.last_seq, event.global_seq)

        if event.type == EventType.FactAdded:
            self._apply_fact_added(event)
        elif event.type == EventType.ConstraintAdded:
            self._apply_constraint_added(event)
        elif event.type == EventType.ConstraintDeactivated:
            self._apply_constraint_deactivated(event)
        elif event.type == EventType.DecisionMade:
            self._apply_decision_made(event)
        elif event.type == EventType.MemoryWriteCommitted:
            self._apply_memory_write_committed(event)
        elif event.type == EventType.MemoryQueryIssued:
            self._apply_memory_query_issued(event)

    def _apply_fact_added(self, event: Event) -> None:
        """Apply FactAdded event."""
        payload = event.payload
        key = payload.get("key")
        if key:
            self._state.facts[key] = FactProjection(
                key=key,
                value=payload.get("value"),
                confidence=payload.get("confidence", 1.0),
                source_event_id=event.global_seq,
            )

    def _apply_constraint_added(self, event: Event) -> None:
        """Apply ConstraintAdded event."""
        payload = event.payload
        text = payload.get("text")
        if text:
            # Use text as key for deduplication
            self._state.constraints[text] = ConstraintProjection(
                text=text,
                source_event_id=event.global_seq,
                active=True,
                priority=payload.get("priority", "required"),
                triggered_by=payload.get("triggered_by"),
            )

    def _apply_constraint_deactivated(self, event: Event) -> None:
        """Apply ConstraintDeactivated event."""
        payload = event.payload
        text = payload.get("text")
        if text and text in self._state.constraints:
            self._state.constraints[text].active = False

    def _apply_decision_made(self, event: Event) -> None:
        """Apply DecisionMade event."""
        payload = event.payload
        text = payload.get("text")
        if text:
            self._state.decisions.append(
                DecisionProjection(
                    text=text,
                    source_event_id=event.global_seq,
                    references=payload.get("references", []),
                    rationale=payload.get("rationale"),
                    status=payload.get("status", "committed"),
                )
            )
        # Clear pending verifications after each decision
        self._state.pending_verifications.clear()

    def _apply_memory_write_committed(self, event: Event) -> None:
        """Apply MemoryWriteCommitted event - may contain facts or constraints."""
        payload = event.payload
        items = payload.get("items", [])

        for item in items:
            item_type = item.get("type")
            if item_type == "fact":
                key = item.get("key")
                if key:
                    self._state.facts[key] = FactProjection(
                        key=key,
                        value=item.get("value"),
                        confidence=item.get("confidence", 1.0),
                        source_event_id=event.global_seq,
                    )
            elif item_type == "constraint":
                text = item.get("text")
                if text:
                    self._state.constraints[text] = ConstraintProjection(
                        text=text,
                        source_event_id=event.global_seq,
                        active=True,
                        priority=item.get("priority", "required"),
                        triggered_by=item.get("triggered_by"),
                    )

    def get_active_constraints(self) -> list[ConstraintProjection]:
        """Get all active constraints."""
        return [c for c in self._state.constraints.values() if c.active]

    def get_facts(self) -> dict[str, FactProjection]:
        """Get all facts."""
        return self._state.facts.copy()

    def get_decisions(self) -> list[DecisionProjection]:
        """Get all decisions."""
        return self._state.decisions.copy()

    def _apply_memory_query_issued(self, event: Event) -> None:
        """Apply MemoryQueryIssued event - tracks verifications."""
        payload = event.payload
        question = payload.get("question", "")
        # Extract keywords from the query and add to pending verifications
        for keyword in self._extract_keywords(question):
            self._state.pending_verifications.add(keyword)

    def _extract_keywords(self, query: str) -> list[str]:
        """Extract searchable keywords from a query string.

        For demo reliability, we use exact term matching.
        The system prompt instructs agents to use standardized terms.
        """
        # Standardized keywords from system prompt - expanded for demo reliability
        KNOWN_KEYWORDS = {
            # Accessibility terms
            "accessibility", "accessible", "wheelchair", "mobility",
            # Financial terms
            "budget", "price", "cost", "rate", "fee",
            # Travel terms
            "destination", "booking", "book", "canceling", "cancel",
            "selecting", "select", "hotel", "flight", "room",
            # Dietary terms
            "dietary", "vegetarian", "vegan", "allergies", "allergy",
            # Common action terms
            "verify", "check", "confirm", "review",
        }

        query_lower = query.lower()
        found = []

        # Check for known keywords first
        for keyword in KNOWN_KEYWORDS:
            if keyword in query_lower:
                found.append(keyword)

        # Also add any word longer than 3 chars as potential keyword (reduced from 4)
        words = query_lower.split()
        for word in words:
            word = word.strip(".,!?\"'()[]")
            if len(word) > 3 and word not in found and word not in KNOWN_KEYWORDS:
                found.append(word)

        return found
