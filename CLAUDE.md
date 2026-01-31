# Deterministic Memory Layer (DML)

Event-sourced memory layer for AI agents with deterministic replay.

## Project Overview

DML provides a memory system where every mutation is captured as an immutable event. This enables:
- **Deterministic replay**: Rebuild state from any point in history
- **Counterfactual analysis**: "What if this constraint didn't exist?"
- **Policy enforcement**: Reject writes that violate active constraints
- **Provenance tracking**: Trace any fact back to its origin
- **Drift measurement**: Quantify state changes over time

## Architecture

```
Events (append-only) → ProjectionEngine → Current State
                    ↓
              ReplayEngine → Historical/Counterfactual States
                    ↓
               MemoryAPI → Agent-facing interface
```

## Key Files

| File | Purpose |
|------|---------|
| `dml/events.py` | EventType enum, Event dataclass, SQLite EventStore |
| `dml/projections.py` | Fact/Constraint/Decision projections, ProjectionEngine |
| `dml/replay.py` | ReplayEngine for deterministic state reconstruction |
| `dml/policy.py` | PolicyEngine for constraint enforcement |
| `dml/memory_api.py` | Agent-facing API (search, propose, commit, trace, diff, drift) |
| `dml/tracing.py` | W&B Weave integration |
| `cli.py` | Click CLI interface |
| `demo.py` | Demo scenario showing full workflow |

## Development Workflow

1. **Write tests first** for new features
2. **Run tests**: `pytest tests/`
3. **Run demo**: `python demo.py`
4. **Use CLI**: `python cli.py --help`

## Running the Project

```bash
# Install dependencies
uv sync

# Initialize a memory store
python cli.py init

# Add an event
python cli.py append TurnStarted '{"turn_id": 1}'

# View current state
python cli.py replay

# Run evaluation
python cli.py eval

# Run demo
python demo.py

# Run tests
pytest tests/ -v
```

## Code Style

- Keep functions small and focused
- No over-engineering - minimal code for requirements
- Timestamps use monotonic counters, NOT wall-clock time
- All mutations go through events - no direct state modification

## Forbidden Patterns

- **NO wall-clock timestamps** - breaks determinism
- **NO mutation outside events** - all changes must be events
- **NO blocking I/O in projections** - projections must be pure
- **NO side effects in replay** - replay must be deterministic

## Event Types

From PRD 5.1:
- `TurnStarted`, `TurnCompleted` - Turn boundaries
- `UserMessageReceived` - User input
- `MemoryQueryIssued`, `MemoryQueryResult` - Memory reads
- `DecisionMade` - Agent decisions
- `MemoryWriteProposed`, `MemoryWriteCommitted` - Memory writes
- `OutputEmitted` - Agent output
- `FactAdded`, `ConstraintAdded`, `ConstraintDeactivated` - Direct memory ops

## Policy Engine

MVP policy: Reject writes that contradict active constraints.
Constraint patterns detected:
- "Never X" - forbids X
- "Do not X" - forbids X
- "Avoid X" - forbids X

## Testing Focus

- `test_events.py`: Event storage, WAL mode, monotonic timestamps
- `test_replay.py`: **Determinism guarantee** - same events → same state
- `test_projections.py`: Fact/constraint/decision building
- `test_policy.py`: Constraint violation rejection
- `test_memory_api.py`: Provenance chains, diff, drift metrics

## Weave Integration

Tracing is optional. When `weave` is installed:
- Event appends are traced
- Memory API calls are traced
- Check W&B dashboard for traces

## Dependencies

Minimal deps per PRD:
- `click` - CLI
- `pydantic` - Data validation (future use)
- `weave` - Tracing (optional)
- `sqlite3` - Storage (stdlib)
