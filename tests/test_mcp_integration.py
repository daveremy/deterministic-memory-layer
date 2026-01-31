"""End-to-end integration tests for MCP server tools.

Tests the full flow of MCP tool handlers as they would be called by Claude.
"""

import os
import tempfile
import pytest

from dml.events import EventStore
from dml.memory_api import MemoryAPI
from dml.policy import PolicyEngine
from dml.replay import ReplayEngine

# Import server handlers directly
from dml import server


@pytest.fixture
def mcp_server():
    """Set up MCP server with fresh database."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    # Initialize server globals
    server.store = EventStore(db_path)
    server.replay_engine = ReplayEngine(server.store)
    server.policy_engine = PolicyEngine()
    server.memory_api = MemoryAPI(server.store)

    yield server

    server.store.close()
    os.unlink(db_path)


class TestAddFact:
    """Test add_fact tool."""

    def test_add_first_fact(self, mcp_server):
        result = server.handle_add_fact({"key": "destination", "value": "Japan"})

        assert result["seq"] == 1
        assert result["key"] == "destination"
        assert result["value"] == "Japan"
        assert "drift_alert" not in result

    def test_add_fact_with_confidence(self, mcp_server):
        result = server.handle_add_fact({
            "key": "budget",
            "value": "3000",
            "confidence": 0.8
        })

        assert result["seq"] == 1
        assert result["key"] == "budget"

    def test_add_fact_supersession(self, mcp_server):
        """Test that updating a fact tracks supersession."""
        r1 = server.handle_add_fact({"key": "budget", "value": "4000"})
        r2 = server.handle_add_fact({"key": "budget", "value": "3000"})

        assert r2["previous_value"] == "4000"
        assert r2["drift_alert"] is True

    def test_drift_detection(self, mcp_server):
        """Test drift alert when fact changes."""
        server.handle_add_fact({"key": "budget", "value": "4000"})
        result = server.handle_add_fact({"key": "budget", "value": "3000"})

        assert result["drift_alert"] is True
        assert result["previous_value"] == "4000"


class TestAddConstraint:
    """Test add_constraint tool."""

    def test_add_required_constraint(self, mcp_server):
        result = server.handle_add_constraint({
            "text": "wheelchair accessible rooms required"
        })

        assert result["seq"] == 1
        assert result["constraint"] == "wheelchair accessible rooms required"
        assert result["priority"] == "required"

    def test_add_learned_constraint(self, mcp_server):
        # First add a decision that gets blocked
        server.handle_add_fact({"key": "destination", "value": "Japan"})

        result = server.handle_add_constraint({
            "text": "verify accessibility BEFORE recommending",
            "priority": "learned",
            "triggered_by": 1
        })

        assert result["priority"] == "learned"
        assert result["triggered_by"] == 1

    def test_learned_without_trigger_fails(self, mcp_server):
        result = server.handle_add_constraint({
            "text": "some learned constraint",
            "priority": "learned"
        })

        assert "error" in result


class TestRecordDecision:
    """Test record_decision tool with policy enforcement."""

    def test_decision_allowed_no_constraints(self, mcp_server):
        result = server.handle_record_decision({
            "text": "Book Hotel Granvia",
            "rationale": "Good reviews and location"
        })

        assert result["status"] == "COMMITTED"
        assert result["seq"] == 1

    def test_decision_blocked_by_constraint(self, mcp_server):
        # Add constraint using "never" pattern that policy engine understands
        server.handle_add_constraint({
            "text": "never book without checking accessibility"
        })

        # Try to make decision that violates it (contains "book without checking")
        result = server.handle_record_decision({
            "text": "Book without checking accessibility info",
            "rationale": "Looks nice"
        })

        assert result["status"] == "BLOCKED"
        assert "suggestion" in result

    def test_decision_with_references(self, mcp_server):
        # Add a fact
        r1 = server.handle_add_fact({"key": "destination", "value": "Japan"})

        # Decision referencing the fact
        result = server.handle_record_decision({
            "text": "Plan trip to Tokyo",
            "rationale": "User wants Japan",
            "references": [r1["seq"]]
        })

        assert result["status"] == "COMMITTED"


class TestQueryMemory:
    """Test query_memory tool."""

    def test_query_facts(self, mcp_server):
        server.handle_add_fact({"key": "destination", "value": "Japan"})
        server.handle_add_fact({"key": "budget", "value": "3000"})

        result = server.handle_query_memory({
            "question": "japan",
            "scope": "facts"
        })

        assert "query_seq" in result
        assert len(result["facts"]) == 1
        assert result["facts"][0]["key"] == "destination"

    def test_query_constraints(self, mcp_server):
        server.handle_add_constraint({"text": "wheelchair accessible"})

        result = server.handle_query_memory({
            "question": "wheelchair",
            "scope": "constraints"
        })

        assert len(result["constraints"]) == 1

    def test_query_all(self, mcp_server):
        server.handle_add_fact({"key": "budget", "value": "3000"})
        server.handle_add_constraint({"text": "budget limit"})

        result = server.handle_query_memory({
            "question": "budget",
            "scope": "all"
        })

        assert "facts" in result
        assert "constraints" in result
        assert "decisions" in result

    def test_query_records_event(self, mcp_server):
        """Query should emit MemoryQueryIssued event."""
        result = server.handle_query_memory({"question": "test"})

        # The query_seq should be the event that was emitted
        assert result["query_seq"] == 1


class TestGetMemoryContext:
    """Test get_memory_context tool."""

    def test_get_full_context(self, mcp_server):
        server.handle_add_fact({"key": "destination", "value": "Japan"})
        server.handle_add_constraint({"text": "budget limit $3000"})
        server.handle_record_decision({
            "text": "Book flight",
            "rationale": "Best price"
        })

        result = server.handle_get_memory_context({})

        assert result["current_seq"] == 3
        assert "destination" in result["facts"]
        assert len(result["constraints"]) == 1
        assert len(result["decisions"]) == 1


class TestTraceProvenance:
    """Test trace_provenance tool."""

    def test_trace_by_seq(self, mcp_server):
        r1 = server.handle_add_fact({"key": "budget", "value": "3000"})

        result = server.handle_trace_provenance({"seq": r1["seq"]})

        assert "chain" in result
        assert len(result["chain"]) >= 1

    def test_trace_by_fact_key(self, mcp_server):
        server.handle_add_fact({"key": "destination", "value": "Japan"})

        result = server.handle_trace_provenance({"fact_key": "destination"})

        assert "chain" in result
        assert result["chain"][0]["payload"]["key"] == "destination"

    def test_trace_missing_returns_error(self, mcp_server):
        result = server.handle_trace_provenance({"fact_key": "nonexistent"})

        assert "error" in result


class TestTimeTravel:
    """Test time_travel tool."""

    def test_time_travel_to_past(self, mcp_server):
        server.handle_add_fact({"key": "budget", "value": "4000"})
        server.handle_add_fact({"key": "budget", "value": "3000"})

        result = server.handle_time_travel({"to_seq": 1})

        assert result["mode"] == "FLASHBACK"
        assert result["viewing_seq"] == 1
        assert result["current_seq"] == 2

        # Historical state should have old budget
        hist_facts = result["historical_state"]["facts"]
        assert hist_facts["budget"]["value"] == "4000"

    def test_time_travel_diff(self, mcp_server):
        server.handle_add_fact({"key": "budget", "value": "4000"})
        server.handle_add_fact({"key": "destination", "value": "Japan"})

        result = server.handle_time_travel({"to_seq": 1})

        # Should show destination was added after seq 1
        diff = result["diff_from_current"]
        assert any(c["key"] == "destination" for c in diff["added"])


class TestSimulateTimeline:
    """Test simulate_timeline tool (Fork the Future)."""

    def test_simulate_constraint_blocks_decision(self, mcp_server):
        # Add some initial facts
        server.handle_add_fact({"key": "destination", "value": "Japan"})

        result = server.handle_simulate_timeline({
            "inject_constraint": "never book without accessibility check",
            "at_seq": 1,
            "then_decide": "Book without accessibility check"
        })

        assert result["timeline"] == "B (simulated)"
        assert result["result"] == "BLOCKED"

    def test_simulate_allows_compliant_decision(self, mcp_server):
        server.handle_add_fact({"key": "destination", "value": "Japan"})

        result = server.handle_simulate_timeline({
            "inject_constraint": "prefer traditional accommodations",
            "at_seq": 1,
            "then_decide": "Book modern hotel",
            "priority": "preferred"
        })

        # Preferred constraints don't block
        assert result["result"] == "ALLOWED"

    def test_fork_the_future_scenario(self, mcp_server):
        """Full Fork the Future scenario from demo."""
        # Timeline A: Add facts, make decision, then add constraint
        server.handle_add_fact({"key": "destination", "value": "Japan"})
        server.handle_add_fact({"key": "budget", "value": "4000"})

        # Decision made at seq 3
        server.handle_record_decision({
            "text": "Book Ryokan Kurashiki",
            "rationale": "Traditional experience"
        })

        # Constraint added at seq 4 (after decision) - use "never" pattern with exact match
        server.handle_add_constraint({
            "text": "never book traditional ryokan"
        })

        # Now simulate: what if constraint was at seq 1?
        # The decision text must contain the forbidden phrase exactly
        result = server.handle_simulate_timeline({
            "inject_constraint": "never book traditional ryokan",
            "at_seq": 1,
            "then_decide": "Book traditional ryokan Kurashiki"
        })

        # In Timeline B, the same decision would be BLOCKED
        assert result["result"] == "BLOCKED"
        assert result["injected_at_seq"] == 1


class TestFullDemoFlow:
    """Test the complete demo flow end-to-end."""

    def test_travel_agent_demo_flow(self, mcp_server):
        """Simulate the 8-act demo from DEMO_DESIGN.md."""

        # Act 1: Setup
        r1 = server.handle_add_fact({"key": "destination", "value": "Japan"})
        r2 = server.handle_add_fact({"key": "budget", "value": "4000"})
        assert r1["seq"] == 1
        assert r2["seq"] == 2

        # Act 2: First decision (should pass)
        server.handle_add_constraint({
            "text": "prefer traditional ryokan accommodations",
            "priority": "preferred"
        })
        r3 = server.handle_record_decision({
            "text": "Book Ryokan Kurashiki",
            "rationale": "Traditional Japanese experience"
        })
        assert r3["status"] == "COMMITTED"

        # Act 3: Drift (budget changes)
        r4 = server.handle_add_fact({"key": "budget", "value": "3000"})
        assert r4["drift_alert"] is True
        assert r4["previous_value"] == "4000"

        # Act 4: The Block - use "verify before" pattern for procedural blocking
        server.handle_add_constraint({
            "text": "verify accessibility before booking",
            "priority": "required"
        })
        r5 = server.handle_record_decision({
            "text": "Booking Ryokan Kurashiki without verification",
            "rationale": "Already booked"
        })
        assert r5["status"] == "BLOCKED"

        # Act 5: Learning - add another procedural constraint
        r6 = server.handle_add_constraint({
            "text": "check availability before booking",
            "priority": "learned",
            "triggered_by": r5.get("violated_constraint_seq", 6)
        })
        assert r6["priority"] == "learned"

        # Act 6: Double-tap (blocked for not verifying availability)
        r7 = server.handle_record_decision({
            "text": "Booking Hotel Granvia now",
            "rationale": "Heard it's nice"
        })
        assert r7["status"] == "BLOCKED"

        # Query first (verification step) - adds "accessibility" and "availability" to pending
        r8 = server.handle_query_memory({
            "question": "accessibility availability",
            "scope": "constraints"
        })
        assert "query_seq" in r8

        # Now decide with verification reference - query added topics to pending
        r9 = server.handle_record_decision({
            "text": "Booking Hotel Granvia - verified accessible and available",
            "rationale": "Verified wheelchair accessible",
            "references": [r8["query_seq"]]
        })
        assert r9["status"] == "COMMITTED"

        # Act 7: Fork the Future - use "never" pattern with exact match
        r10 = server.handle_simulate_timeline({
            "inject_constraint": "never book unverified hotels",
            "at_seq": 2,  # Before the original ryokan decision
            "then_decide": "Book unverified hotels"
        })
        assert r10["timeline"] == "B (simulated)"
        assert r10["result"] == "BLOCKED"

        # Act 8: Get full context for Weave dashboard
        context = server.handle_get_memory_context({})
        assert context["current_seq"] >= 9
        assert len(context["facts"]) >= 2
        assert len(context["constraints"]) >= 3
        assert len(context["decisions"]) >= 2


class TestSupersessionTracking:
    """Test that supersession is properly tracked through MCP server."""

    def test_fact_supersession_via_mcp(self, mcp_server):
        """Verify supersession works through MCP add_fact handler."""
        r1 = server.handle_add_fact({"key": "budget", "value": "5000"})
        r2 = server.handle_add_fact({"key": "budget", "value": "4000"})
        r3 = server.handle_add_fact({"key": "budget", "value": "3000"})

        # Check drift alerts
        assert r2["drift_alert"] is True
        assert r2["previous_value"] == "5000"
        assert r3["drift_alert"] is True
        assert r3["previous_value"] == "4000"

        # Verify history via memory API
        history = server.memory_api.get_fact_history("budget")
        assert len(history) == 3
        assert history[0].value == "5000"
        assert history[1].value == "4000"
        assert history[2].value == "3000"
        assert history[1].supersedes_seq == r1["seq"]
        assert history[2].supersedes_seq == r2["seq"]
