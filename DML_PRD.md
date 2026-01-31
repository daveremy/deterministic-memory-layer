# Deterministic Memory Layer (DML) for Agents

**Version:** 0.1\
**Date:** 2026-01-30\
**Author:** Dave Remy

------------------------------------------------------------------------

# 1. Executive Summary

The Deterministic Memory Layer (DML) is an event-sourced memory
substrate for AI agents. It replaces opaque, mutation-prone prompt-based
memory with a structured, replayable, policy-controlled memory system.

DML enables: - Deterministic state reconstruction - Auditable memory
evolution - Conflict-aware memory updates - Counterfactual replay -
Systematic self-improvement

DML is designed to integrate with existing coding agents (Claude Code,
Codex CLI, Gemini CLI) as a memory enhancement layer rather than a full
agent replacement.

------------------------------------------------------------------------

# 2. Problem Statement

Modern AI agents rely on heuristic memory mechanisms such as:

-   Prompt stuffing
-   Summarization
-   Vector databases
-   Hidden project files
-   Implicit mutation

These approaches lead to:

-   Memory drift over time
-   Silent overwrites
-   Inability to trace decisions
-   Lack of reproducibility
-   Inability to systematically improve behavior

There is no deterministic, auditable memory core.

------------------------------------------------------------------------

# 3. Vision

Memory should behave like a database, not a string.

DML treats memory as:

-   Append-only event log (source of truth)
-   Derived projections (facts, constraints, decisions)
-   Policy-controlled mutation layer
-   Replayable state machine

------------------------------------------------------------------------

# 4. Core Principles

1.  Memory is append-only.
2.  State is a projection of events.
3.  Mutation is policy-controlled.
4.  Every fact has provenance.
5.  Memory is replayable.
6.  Drift is measurable.

------------------------------------------------------------------------

# 5. Functional Requirements

## 5.1 Event Store

Each event includes: - global_seq (autoincrement) - turn_id -
timestamp - type - payload (JSON) - caused_by - correlation_id

Event types (MVP): - TurnStarted - UserMessageReceived -
MemoryQueryIssued - MemoryQueryResult - DecisionMade -
MemoryWriteProposed - MemoryWriteCommitted - OutputEmitted -
TurnCompleted

------------------------------------------------------------------------

## 5.2 Projections

### FactProjection

-   key
-   value
-   confidence
-   source_event_id

### ConstraintProjection

-   text
-   source_event_id
-   active flag

### DecisionProjection

-   decision text
-   references to event ids

------------------------------------------------------------------------

## 5.3 Replay Engine

Capability: - Rebuild memory state to any event index - Support
counterfactual exclusion of events - Enable deterministic projection
reconstruction

------------------------------------------------------------------------

## 5.4 Memory Tool API

Agent-accessible tools:

-   memory.get_active_constraints()
-   memory.search(query)
-   memory.propose_writes(items)
-   memory.trace_provenance(key)
-   memory.diff_state(seq1, seq2)

------------------------------------------------------------------------

# 6. Non-Functional Requirements

-   Deterministic state reconstruction
-   SQLite-backed persistence
-   No destructive updates
-   Minimal dependency footprint
-   Under 1,000 LOC for MVP

------------------------------------------------------------------------

# 7. Hackathon Scope

MVP includes:

-   CLI interface
-   Event store
-   Basic projections
-   Replay engine
-   Weights & Biases Weave tracing
-   Demo scenario showing:
    -   Constraint insertion
    -   Decision violation
    -   Replay before constraint
    -   Behavior difference

------------------------------------------------------------------------

# 8. Evaluation Plan

Demonstrate improvement using Weave:

1.  Run baseline scenario (no constraint policy)
2.  Add constraint capture policy
3.  Replay scenario
4.  Show eval improvement (constraint respected)

------------------------------------------------------------------------

# 9. Risks

-   Overengineering during hackathon
-   Scope creep
-   UI distraction instead of core functionality

Mitigation: - CLI-first implementation - Focus on deterministic core

------------------------------------------------------------------------

# 10. Future Extensions

-   Conflict detection policies
-   Memory decay modeling
-   Drift metrics dashboard
-   MCP server integration
-   Distributed event streaming backend

------------------------------------------------------------------------

# 11. Repository Naming Options

Recommended: - deterministic-memory-layer - agent-dml - dml-core -
dml-agents - dml-memory

Preferred: **deterministic-memory-layer**

------------------------------------------------------------------------

# 12. Pitch Summary

DML is a deterministic, event-sourced memory layer for AI agents. It
replaces opaque prompt memory with a replayable, auditable,
policy-controlled state model that enables systematic self-improvement.
