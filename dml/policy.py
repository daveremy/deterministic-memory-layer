"""Policy engine for mutation control and constraint enforcement."""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dml.projections import ConstraintProjection, ProjectionState

# Strict pattern matching for "verify X before Y" constraints
VERIFY_BEFORE_PATTERN = re.compile(
    r"^(verify|check)\s+(.+?)\s+before\s+(.+)$",
    re.IGNORECASE
)


class PolicyStatus(str, Enum):
    """Policy check result status."""

    APPROVED = "approved"
    REJECTED = "rejected"
    CONFLICT = "conflict"


@dataclass
class PolicyResult:
    """Result of a policy check."""

    status: PolicyStatus
    reason: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def approved(self) -> bool:
        return self.status == PolicyStatus.APPROVED

    @property
    def rejected(self) -> bool:
        return self.status == PolicyStatus.REJECTED

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "details": self.details,
        }


@dataclass
class WriteProposal:
    """A proposed write to memory."""

    items: list[dict[str, Any]]
    proposal_id: str | None = None
    source_event_id: int | None = None


class PolicyEngine:
    """Enforces policies on memory writes."""

    def check_write(
        self, proposal: WriteProposal, current_state: ProjectionState
    ) -> PolicyResult:
        """
        Check if a write proposal is allowed given current state.

        MVP policy: reject writes that contradict active constraints.

        Args:
            proposal: The proposed write.
            current_state: Current projection state with active constraints.

        Returns:
            PolicyResult indicating approval, rejection, or conflict.
        """
        # Only enforce "required" and "learned" constraints, not "preferred"
        active_constraints = [
            c for c in current_state.constraints.values()
            if c.active and c.priority != "preferred"
        ]

        # Check each item in the proposal
        violations = []
        for item in proposal.items:
            for constraint in active_constraints:
                if self._violates_constraint(item, constraint, current_state):
                    violations.append(
                        {
                            "item": item,
                            "constraint": constraint.text,
                            "constraint_source": constraint.source_event_id,
                            "constraint_priority": constraint.priority,
                        }
                    )

        if violations:
            return PolicyResult(
                status=PolicyStatus.REJECTED,
                reason="Write violates active constraints",
                details={"violations": violations},
            )

        return PolicyResult(status=PolicyStatus.APPROVED)

    def _violates_constraint(
        self, item: dict[str, Any], constraint: ConstraintProjection,
        state: ProjectionState
    ) -> bool:
        """
        Check if an item violates a constraint.

        Checks:
        1. Direct prohibition patterns (never/do not/avoid)
        2. Procedural patterns (verify X before Y)
        """
        # Normalize constraint text (strip whitespace, lowercase)
        constraint_text = constraint.text.strip().lower()
        item_text = self._item_to_text(item).lower()

        # Check for direct contradiction patterns using word boundaries
        # "Never use X" constraint vs item mentioning "use X"
        if re.search(r'\bnever\b', constraint_text):
            # Extract what should never be done, normalize punctuation
            forbidden = re.sub(r'\bnever\b', '', constraint_text).strip()
            forbidden = self._normalize_forbidden(forbidden)
            if self._forbidden_in_text(forbidden, item_text):
                return True
            # Also extract the core term (e.g., "eval()" from "use eval()")
            core_term = self._extract_core_term(forbidden)
            if core_term and self._forbidden_in_text(core_term, item_text):
                return True

        # "Do not X" constraint - use word boundary
        if re.search(r'\bdo\s+not\b', constraint_text):
            forbidden = re.sub(r'\bdo\s+not\b', '', constraint_text).strip()
            forbidden = self._normalize_forbidden(forbidden)
            if self._forbidden_in_text(forbidden, item_text):
                return True
            core_term = self._extract_core_term(forbidden)
            if core_term and self._forbidden_in_text(core_term, item_text):
                return True

        # "Avoid X" constraint - use word boundary
        if re.search(r'\bavoid\b', constraint_text):
            forbidden = re.sub(r'\bavoid\b', '', constraint_text).strip()
            forbidden = self._normalize_forbidden(forbidden)
            if self._forbidden_in_text(forbidden, item_text):
                return True
            core_term = self._extract_core_term(forbidden)
            if core_term and self._forbidden_in_text(core_term, item_text):
                return True

        # "Verify X before Y" pattern (procedural constraint)
        # Normalize text before matching to handle trailing punctuation
        normalized_constraint = constraint.text.strip().rstrip('.,!?;:')
        match = VERIFY_BEFORE_PATTERN.match(normalized_constraint)
        if match:
            verification_topic = match.group(2).strip().lower()  # e.g., "accessibility"
            action_type = match.group(3).strip().lower()  # e.g., "booking"

            # Check if this item matches the action type
            if self._matches_action(item_text, action_type):
                # Check if verification was done (via MemoryQueryIssued events)
                # For multi-word topics like "dietary restrictions", check if ANY
                # significant word from the topic was verified
                if not self._topic_verified(verification_topic, state.pending_verifications):
                    return True  # VIOLATION: didn't verify before acting

        return False

    def _topic_verified(self, topic: str, pending_verifications: set[str]) -> bool:
        """Check if a topic was verified.

        For multi-word topics like 'dietary restrictions', returns True if ANY
        significant word from the topic appears in pending_verifications.
        """
        # Direct match
        if topic in pending_verifications:
            return True

        # Check if any significant word (>3 chars) from topic was verified
        topic_words = [w.strip() for w in topic.split() if len(w.strip()) > 3]
        for word in topic_words:
            if word in pending_verifications:
                return True

        # Check if any verification contains the topic or vice versa
        for verified in pending_verifications:
            if topic in verified or verified in topic:
                return True

        return False

    def _matches_action(self, item_text: str, action_type: str) -> bool:
        """Word-boundary match for action type with verb form variations.

        Handles variations like 'book' matching 'booking', 'booked', etc.
        """
        # Try exact match first
        pattern = r'\b' + re.escape(action_type) + r'\b'
        if re.search(pattern, item_text, re.IGNORECASE):
            return True

        # Try stem matching for common verb forms
        # Strip common suffixes to get stem
        stem = action_type.rstrip('ing').rstrip('ed').rstrip('s')
        if len(stem) >= 3 and stem != action_type:
            # Match stem followed by common verb endings
            pattern = r'\b' + re.escape(stem) + r'(ing|ed|s|e)?\b'
            if re.search(pattern, item_text, re.IGNORECASE):
                return True

        return False

    def _normalize_forbidden(self, forbidden: str) -> str:
        """Normalize forbidden term by stripping trailing punctuation."""
        return forbidden.rstrip('.,!?;:"\' ')

    def _forbidden_in_text(self, forbidden: str, item_text: str) -> bool:
        """Check if forbidden term appears in item text using word boundaries.

        For terms with special chars like 'eval()', we escape them for regex.
        Word boundaries only apply at positions adjacent to word characters.
        """
        if not forbidden:
            return False

        escaped = re.escape(forbidden)

        # Only add \b at start if term starts with a word character
        if forbidden[0].isalnum() or forbidden[0] == '_':
            pattern = r'\b' + escaped
        else:
            pattern = escaped

        # Only add \b at end if term ends with a word character
        if forbidden[-1].isalnum() or forbidden[-1] == '_':
            pattern = pattern + r'\b'

        return bool(re.search(pattern, item_text, re.IGNORECASE))

    def _extract_core_term(self, forbidden: str) -> str | None:
        """Extract the core forbidden term from phrases like 'use eval()' -> 'eval()'."""
        # Common verb patterns to strip (expanded list)
        verbs = [
            "use ", "call ", "invoke ", "execute ", "run ",
            "employ ", "utilize ", "apply ", "perform ",
            "do ", "make ", "create ", "add ", "include ",
        ]
        for verb in verbs:
            if forbidden.startswith(verb):
                return forbidden[len(verb):].strip()
        return None

    def _item_to_text(self, item: dict[str, Any]) -> str:
        """Convert an item to searchable text."""
        parts = []
        if "text" in item:
            parts.append(str(item["text"]))
        if "value" in item:
            parts.append(str(item["value"]))
        if "key" in item:
            parts.append(str(item["key"]))
        return " ".join(parts)
