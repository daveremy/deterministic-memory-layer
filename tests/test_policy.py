"""Tests for PolicyEngine - constraint enforcement."""

import pytest

from dml.events import Event, EventType
from dml.policy import PolicyEngine, PolicyResult, PolicyStatus, WriteProposal
from dml.projections import ConstraintProjection, ProjectionEngine, ProjectionState


@pytest.fixture
def policy_engine():
    return PolicyEngine()


@pytest.fixture
def state_with_constraints():
    """Create a projection state with active constraints."""
    state = ProjectionState()
    state.constraints["Never use eval()"] = ConstraintProjection(
        text="Never use eval()",
        source_event_id=1,
        active=True,
    )
    state.constraints["Do not call external APIs"] = ConstraintProjection(
        text="Do not call external APIs",
        source_event_id=2,
        active=True,
    )
    state.constraints["Avoid using globals"] = ConstraintProjection(
        text="Avoid using globals",
        source_event_id=3,
        active=True,
    )
    return state


class TestPolicyResult:
    def test_approved_result(self):
        result = PolicyResult(status=PolicyStatus.APPROVED)
        assert result.approved is True
        assert result.rejected is False

    def test_rejected_result(self):
        result = PolicyResult(
            status=PolicyStatus.REJECTED,
            reason="Violates constraint",
            details={"constraint": "Never use eval()"},
        )
        assert result.approved is False
        assert result.rejected is True
        assert result.reason == "Violates constraint"

    def test_to_dict(self):
        result = PolicyResult(
            status=PolicyStatus.REJECTED,
            reason="Test reason",
            details={"key": "value"},
        )
        d = result.to_dict()
        assert d["status"] == "rejected"
        assert d["reason"] == "Test reason"
        assert d["details"] == {"key": "value"}


class TestPolicyEngine:
    def test_approve_compliant_write(self, policy_engine, state_with_constraints):
        proposal = WriteProposal(
            items=[{"type": "decision", "text": "Use json.loads for parsing"}]
        )
        result = policy_engine.check_write(proposal, state_with_constraints)

        assert result.approved is True

    def test_reject_never_constraint_violation(self, policy_engine, state_with_constraints):
        proposal = WriteProposal(
            items=[{"type": "decision", "text": "Use eval() to parse input"}]
        )
        result = policy_engine.check_write(proposal, state_with_constraints)

        assert result.rejected is True
        assert "violates active constraints" in result.reason.lower()
        assert len(result.details["violations"]) == 1

    def test_reject_do_not_constraint_violation(self, policy_engine, state_with_constraints):
        proposal = WriteProposal(
            items=[{"type": "decision", "text": "Call external APIs for data"}]
        )
        result = policy_engine.check_write(proposal, state_with_constraints)

        assert result.rejected is True

    def test_reject_avoid_constraint_violation(self, policy_engine, state_with_constraints):
        proposal = WriteProposal(
            items=[{"type": "decision", "text": "Using globals for state"}]
        )
        result = policy_engine.check_write(proposal, state_with_constraints)

        assert result.rejected is True

    def test_multiple_violations(self, policy_engine, state_with_constraints):
        proposal = WriteProposal(
            items=[
                {"type": "decision", "text": "Use eval() and call external APIs"},
            ]
        )
        result = policy_engine.check_write(proposal, state_with_constraints)

        assert result.rejected is True
        # Should catch at least one violation
        assert len(result.details["violations"]) >= 1

    def test_inactive_constraint_not_enforced(self, policy_engine):
        state = ProjectionState()
        state.constraints["Never use eval()"] = ConstraintProjection(
            text="Never use eval()",
            source_event_id=1,
            active=False,  # Inactive
        )

        proposal = WriteProposal(
            items=[{"type": "decision", "text": "Use eval() for dynamic code"}]
        )
        result = policy_engine.check_write(proposal, state)

        # Should be approved since constraint is inactive
        assert result.approved is True

    def test_empty_constraints_approves_all(self, policy_engine):
        state = ProjectionState()  # No constraints

        proposal = WriteProposal(
            items=[{"type": "decision", "text": "Do anything we want"}]
        )
        result = policy_engine.check_write(proposal, state)

        assert result.approved is True

    def test_fact_value_checked(self, policy_engine, state_with_constraints):
        proposal = WriteProposal(
            items=[{"type": "fact", "key": "parsing_method", "value": "eval()"}]
        )
        result = policy_engine.check_write(proposal, state_with_constraints)

        assert result.rejected is True

    def test_case_insensitive_matching(self, policy_engine, state_with_constraints):
        proposal = WriteProposal(
            items=[{"type": "decision", "text": "Use EVAL() for parsing"}]
        )
        result = policy_engine.check_write(proposal, state_with_constraints)

        assert result.rejected is True

    def test_multiple_items_one_violates(self, policy_engine, state_with_constraints):
        proposal = WriteProposal(
            items=[
                {"type": "fact", "key": "safe_method", "value": "json.loads"},
                {"type": "decision", "text": "Use eval() as fallback"},
            ]
        )
        result = policy_engine.check_write(proposal, state_with_constraints)

        assert result.rejected is True
        # Only the violating item should be in violations
        violations = result.details["violations"]
        assert any("eval()" in str(v["item"]).lower() for v in violations)

    def test_verify_before_constraint_blocks_without_verification(self, policy_engine):
        """Test that 'verify X before Y' blocks when verification wasn't done."""
        state = ProjectionState()
        state.constraints["verify accessibility before booking"] = ConstraintProjection(
            text="verify accessibility before booking",
            source_event_id=1,
            active=True,
            priority="learned",
        )
        # No pending verifications - should block

        proposal = WriteProposal(
            items=[{"type": "decision", "text": "booking Hotel Granvia"}]
        )
        result = policy_engine.check_write(proposal, state)

        assert result.rejected is True
        assert "verify accessibility before booking" in result.details["violations"][0]["constraint"]

    def test_verify_before_constraint_allows_with_verification(self, policy_engine):
        """Test that 'verify X before Y' allows when verification was done."""
        state = ProjectionState()
        state.constraints["verify accessibility before booking"] = ConstraintProjection(
            text="verify accessibility before booking",
            source_event_id=1,
            active=True,
            priority="learned",
        )
        # Add pending verification for accessibility
        state.pending_verifications.add("accessibility")

        proposal = WriteProposal(
            items=[{"type": "decision", "text": "booking Hotel Granvia"}]
        )
        result = policy_engine.check_write(proposal, state)

        assert result.approved is True

    def test_preferred_constraint_not_enforced(self, policy_engine):
        """Test that 'preferred' constraints don't block."""
        state = ProjectionState()
        state.constraints["Never use eval()"] = ConstraintProjection(
            text="Never use eval()",
            source_event_id=1,
            active=True,
            priority="preferred",  # Preferred, not required
        )

        proposal = WriteProposal(
            items=[{"type": "decision", "text": "Use eval() for parsing"}]
        )
        result = policy_engine.check_write(proposal, state)

        # Should be approved since constraint is only preferred
        assert result.approved is True

    def test_learned_constraint_enforced(self, policy_engine):
        """Test that 'learned' constraints are enforced like 'required'."""
        state = ProjectionState()
        state.constraints["Never use eval()"] = ConstraintProjection(
            text="Never use eval()",
            source_event_id=1,
            active=True,
            priority="learned",
            triggered_by=5,  # Learned from event 5
        )

        proposal = WriteProposal(
            items=[{"type": "decision", "text": "Use eval() for parsing"}]
        )
        result = policy_engine.check_write(proposal, state)

        assert result.rejected is True

    def test_check_before_pattern_also_works(self, policy_engine):
        """Test that 'check X before Y' works like 'verify X before Y'."""
        state = ProjectionState()
        state.constraints["check budget before booking"] = ConstraintProjection(
            text="check budget before booking",
            source_event_id=1,
            active=True,
        )
        # No pending verifications

        proposal = WriteProposal(
            items=[{"type": "decision", "text": "booking flight to Japan"}]
        )
        result = policy_engine.check_write(proposal, state)

        assert result.rejected is True
