#!/usr/bin/env python3
"""Demo scenario from PRD Section 7.

This demonstrates:
1. Insert constraint: "Never use eval()"
2. Simulate decision that violates constraint
3. Show policy rejection
4. Replay to before constraint
5. Show decision would have succeeded
6. Log to Weave for comparison
"""

import json
from pathlib import Path

from dml.events import Event, EventStore, EventType
from dml.memory_api import MemoryAPI
from dml.replay import ReplayEngine
from dml.tracing import init_tracing, TracedEventStore, TracedMemoryAPI


def main() -> None:
    print("=" * 60)
    print("Deterministic Memory Layer - Demo Scenario")
    print("=" * 60)

    # Initialize Weave tracing (optional)
    tracing_enabled = init_tracing("dml-demo")
    if tracing_enabled:
        print("\nWeave tracing enabled - check your dashboard!")
    else:
        print("\nWeave not available - running without tracing")

    # Create fresh memory store
    db_path = "demo_memory.db"
    if Path(db_path).exists():
        Path(db_path).unlink()

    # Create store (with optional tracing wrapper)
    base_store = EventStore(db_path)
    store = TracedEventStore(base_store) if tracing_enabled else base_store

    # Create API (with optional tracing wrapper)
    base_api = MemoryAPI(base_store)
    api = TracedMemoryAPI(base_api) if tracing_enabled else base_api
    replay_engine = ReplayEngine(base_store)

    print("\n" + "-" * 60)
    print("Step 1: Recording initial turn")
    print("-" * 60)

    # Turn 1: User starts a conversation
    turn1_start = Event(
        type=EventType.TurnStarted,
        payload={"turn_id": 1},
        turn_id=1,
    )
    seq_t1 = store.append(turn1_start)
    print(f"Turn started at seq={seq_t1}")

    # User asks about parsing
    user_msg = Event(
        type=EventType.UserMessageReceived,
        payload={"content": "How should I parse user input in Python?"},
        turn_id=1,
        caused_by=seq_t1,
    )
    store.append(user_msg)

    print("\n" + "-" * 60)
    print("Step 2: Adding security constraint")
    print("-" * 60)

    # Add security constraint
    constraint_event = Event(
        type=EventType.ConstraintAdded,
        payload={"text": "Never use eval()"},
        turn_id=1,
    )
    constraint_seq = store.append(constraint_event)
    print(f"Constraint 'Never use eval()' added at seq={constraint_seq}")

    # Show active constraints
    constraints = api.get_active_constraints()
    print(f"Active constraints: {[c.text for c in constraints]}")

    print("\n" + "-" * 60)
    print("Step 3: Simulating decision that violates constraint")
    print("-" * 60)

    # Turn 2: Agent tries to make a bad decision
    turn2_start = Event(
        type=EventType.TurnStarted,
        payload={"turn_id": 2},
        turn_id=2,
    )
    store.append(turn2_start)

    # Propose using eval() - this should be rejected
    proposal_id, prop_seq = api.propose_writes(
        items=[
            {
                "type": "decision",
                "text": "Use eval() to parse the user's input dynamically",
            }
        ],
        turn_id=2,
        correlation_id="decision-001",
    )
    print(f"Proposed decision at seq={prop_seq}")
    print(f"Proposal ID: {proposal_id}")

    # Try to commit - should be rejected by policy
    result = api.commit_writes(proposal_id, turn_id=2, correlation_id="decision-001")
    print(f"\nPolicy result: {result.status.value if hasattr(result, 'status') else 'committed'}")
    if hasattr(result, "reason"):
        print(f"Reason: {result.reason}")
        print(f"Violations: {json.dumps(result.details, indent=2)}")

    print("\n" + "-" * 60)
    print("Step 4: Counterfactual - replay without constraint")
    print("-" * 60)

    # What if the constraint hadn't been added?
    state_without_constraint = replay_engine.replay_excluding([constraint_seq])
    active_constraints = [
        c for c in state_without_constraint.constraints.values() if c.active
    ]
    print(f"State without constraint event {constraint_seq}:")
    print(f"  Active constraints: {len(active_constraints)}")
    print(f"  (The decision would have been allowed!)")

    print("\n" + "-" * 60)
    print("Step 5: Making a compliant decision")
    print("-" * 60)

    # Now propose a safe alternative
    proposal_id2, prop_seq2 = api.propose_writes(
        items=[
            {
                "type": "decision",
                "text": "Use json.loads() for parsing JSON input safely",
            }
        ],
        turn_id=2,
        correlation_id="decision-002",
    )
    print(f"Proposed safe decision at seq={prop_seq2}")

    result2 = api.commit_writes(proposal_id2, turn_id=2, correlation_id="decision-002")
    if isinstance(result2, int):
        print(f"Decision APPROVED and committed at seq={result2}")
    else:
        print(f"Unexpected result: {result2}")

    # Add a fact about the decision
    fact_event = Event(
        type=EventType.FactAdded,
        payload={
            "key": "parsing_method",
            "value": "json.loads",
            "confidence": 0.95,
        },
        turn_id=2,
        caused_by=result2 if isinstance(result2, int) else None,
    )
    fact_seq = store.append(fact_event)
    print(f"Fact recorded at seq={fact_seq}")

    print("\n" + "-" * 60)
    print("Step 6: Provenance tracking")
    print("-" * 60)

    # Trace provenance of the parsing_method fact
    chain = api.trace_provenance("parsing_method")
    print(f"Provenance chain for 'parsing_method' ({len(chain)} events):")
    for event in chain:
        print(f"  seq={event.global_seq}: {event.type.value}")

    print("\n" + "-" * 60)
    print("Step 7: State comparison and drift")
    print("-" * 60)

    # Compare state at different points
    max_seq = base_store.get_max_seq()
    diff = api.diff_state(0, max_seq)
    print(f"\nDiff from seq=0 to seq={max_seq}:")
    print(f"  Added facts: {len(diff.added_facts)}")
    print(f"  Added constraints: {len(diff.added_constraints)}")
    print(f"  Decision count diff: {diff.decision_count_diff}")

    drift = api.measure_drift(0, max_seq)
    print(f"\nDrift metrics:")
    print(f"  Fact changes: {drift.fact_changes}")
    print(f"  Constraint changes: {drift.constraint_changes}")
    print(f"  Decision changes: {drift.decision_changes}")
    print(f"  Total drift score: {drift.total_drift_score}")

    print("\n" + "-" * 60)
    print("Step 8: Determinism verification")
    print("-" * 60)

    # Verify deterministic replay
    state1 = replay_engine.replay_to()
    state2 = replay_engine.replay_to()

    # Compare serialized states
    s1 = json.dumps(state1.to_dict(), sort_keys=True)
    s2 = json.dumps(state2.to_dict(), sort_keys=True)

    if s1 == s2:
        print("PASSED: Replaying twice produces identical state")
    else:
        print("FAILED: States differ!")
        print(f"State 1: {s1[:100]}...")
        print(f"State 2: {s2[:100]}...")

    # Clean up
    base_store.close()

    print("\n" + "=" * 60)
    print("Demo complete!")
    if tracing_enabled:
        print("Check Weave dashboard for traces.")
    print("=" * 60)


if __name__ == "__main__":
    main()
